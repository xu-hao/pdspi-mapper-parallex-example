from tx.fhir.utils import unbundle
from tx.dateutils.utils import tstostr, strtots, strtodate
from datetime import datetime, date, timezone
import os
import re
from tx.functional.either import Left, Right, Either, either
from tx.functional.maybe import Just, Nothing, maybe
from tx.functional.utils import const
from tx.pint.utils import convert
import logging
from tx.readable_log import getLogger

logger = getLogger(__name__, logging.INFO)



def extract_key(a):
    return key(a).bind(lambda k : Just(a[k]))

    
def key(a):
    if "effectiveInstant" in a:
        return Just("effectiveInstant")
    elif "effectiveDateTime" in a:
        return Just("effectiveDateTime")
    elif "onsetDateTime" in a:
        return Just("onsetDateTime")
    elif "authoredOn" in a:
        return Just("authoredOn")
    return Nothing
        

def calculation(codes):
    return list(map(lambda a: {
        "system": a["system"],
        "code": a["code"]
    }, codes))


def calculation_template(clinical_variable, resource_name, timestamp_range, record, to_unit):
    if resource_name == "MedicationRequest":
        code_path = "medication.medicationCodeableConcept"
        rcode = record["medication"]["medicationCodeableConcept"]
    else:
        code_path = "code.coding"
        rcode = record["code"]
    from_code = {
        "computed_from": {
            "resourceType": resource_name,
            "field": code_path 
        },
        "value": calculation(rcode["coding"])
    }
    timestamp_record = extract_key(record)
    if timestamp_record is not Nothing:
        record_timestamp_name = key(record).value
        timestamp = {
            "value": timestamp_record.value,
            "computed_from": {
                "resourceType": resource_name,
                "field": record_timestamp_name
            }
        }
    else:
        timestamp = {
            "value": None,
            "computed_from": "record has no timestamp"
        }
    vq = record.get("valueQuantity")
    if vq is None:
        from_value = {}
        value = True
        unit = None
    else:
        value = vq["value"]
        from_unit = vq.get("unit")
        if from_unit is None:
            from_unit = vq.get("code")
            from_unit_from = "valueQuantity.code"
        else:
            from_unit_from = "valueQuantity.unit"
        if from_unit is not None:
            def unit_eq(a, b):
                return a == b
            unit_from = {
                "computed_from": {
                    "resourceType": resource_name,
                    "field": from_unit_from
                },
                "value": from_unit
            }
            if to_unit is not None and not unit_eq(to_unit, from_unit):
                unit = {
                    "computed_from": ["from", "to"],
                    "from": unit_from,
                    "to": {
                        "value": to_unit
                    }
                }
            else:
                unit = unit_from
        else:
            unit = {
                "value": None
            }
        from_value = {
            "computed_from": {
                "resourceType": resource_name,
                "field": "valueQuantity.value"
            },
            "value": value
        }
    return {
        "request_timestamp": timestamp_range,
        "computed_from": ["timestamp", "code", "value", "unit", "request_timestamp"],
        "code": from_code,
        "value": from_value,
        "unit": unit,
        "timestamp": timestamp
    }


def filter_records(records, codes, resource_name):
    records_filtered = []
    for record in records:
        logger.info(f"filtering record: {record}")
        for c in codes:  
            system = c["system"]
            code = c["code"]
            is_regex = c["is_regex"]

            if resource_name == "MedicationRequest":
                code2 = record.get("medication", {}).get("medicationCodeableConcept")
            else:
                code2 = record.get("code")
                
            if code2 is None:
                return Left({
                    "error": f"malformated record: no code",
                    "record": record
                })
            coding2 = code2.get("coding")
            if coding2 is None:
                return Left({
                    "error": f"malformated record: no coding under code",
                    "record": record
                })
            for c2 in coding2: 
                if c2["system"] == system:
                    if (is_regex and re.search(code, "^" + c2["code"] + "$")) or c2["code"] == code:
                        records_filtered.append(record)
    return Right(records_filtered)


def convert_record_to_pds(record, unit, timestamp, clinical_variable, resource_name):
    ts = extract_key(record)
    cert = ts.rec(const(2), 1) 
    vq = record.get("valueQuantity")
    if vq is not None:
        v = vq["value"]
        from_u = vq.get("unit")
        if from_u is None:
            from_u = vq.get("code")
        mv = convert(v, from_u, unit)
        if isinstance(mv, Left):
            return mv
        else:
            v = mv.value
    else:
        v = True
        from_u = None
    c = calculation_template(clinical_variable, resource_name, timestamp, record, unit)
    return Right({
        "variableValue": {
            "value": v,
            **({"unit": unit} if unit is not None else {"unit": from_u} if from_u is not None else {}),
        },
        "certitude": cert,
        "timestamp": maybe.to_python(ts),
        "how": c
    })


def _query_records_closest(records, codes, unit, timestamp, clinical_variable, resource_name, diff_func):
    if records == None:
        return Right({
            "value": None,
            "certitude": 0,
            "how": "no record found"
        })

    def handle_records_filtered(records_filtered):
        if len(records_filtered) == 0:
            from_code = calculation(codes) 
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": f"no record found code {from_code}"
            })
        else:
            ts = timestamp.timestamp()
            def key(a):
                return extract_key(a).rec(lambda ext_key: diff_func(strtots(ext_key) - ts), float("inf"))
        
            records_filtered_key = [(a, key(a)) for a in records_filtered]
            records_with_key = [a for a in records_filtered_key if a[1] is not None]
        
            if len(records_with_key) == 0:
                return Right({
                    "variableValue": {
                        "value": None
                    },
                    "certitude": 0,
                    "how": f"no record found code {from_code}"
                })
            else:
                record = min(records_with_key, key = lambda a: a[1])[0]
                return convert_record_to_pds(record, unit, timestamp, clinical_variable, resource_name)
        
    return filter_records(records, codes, resource_name).bind(handle_records_filtered)


def diff_before(x):
    if x <= 0:
        return -x
    else:
        return None


def diff_after(x):
    if x >= 0:
        return x
    else:
        return None


def query_records_closest(records, codes, unit, timestamp, clinical_variable, resource_name):
    return _query_records_closest(records, codes, unit, timestamp, clinical_variable, resource_name, abs)


def query_records_closest_before(records, codes, unit, timestamp, clinical_variable, resource_name):
    return _query_records_closest(records, codes, unit, timestamp, clinical_variable, resource_name, diff_before)


def query_records_closest_after(records, codes, unit, timestamp, clinical_variable, resource_name):
    return _query_records_closest(records, codes, unit, timestamp, clinical_variable, resource_name, diff_after)


def query_records_interval(records, codes, unit, start, end, clinical_variable, resource_name):
    def in_study_period(a):
        ext_key = extract_key(a)
        if ext_key is Nothing:
            return False
        else:
            record_date = strtodate2(ext_key.value)
            return start <= record_date and record_date < end
        
    def handle_records_filtered(records_filtered):
        records2 = filter(in_study_period, records_filtered)
        timestamp = {"start": start, "end": end}
        return either.sequence(map(lambda record: convert_record_to_pds(record, unit, timestamp, clinical_variable, resource_name), records2))

    return filter_records(records, codes, resource_name).bind(handle_records_filtered)


def get_observation(patient_id, fhir):
    return unbundle(fhir[patient_id]["Observation"])
#    return records.map(lambda xs : list(filter (lambda x : x["resourceType"] == "Observation", xs)))


def get_condition(patient_id, fhir):
    return unbundle(fhir[patient_id]["Condition"])
#    return records.map(lambda xs : list(filter (lambda x : x["resourceType"] == "Condition", xs)))


def get_medication_request(patient_id, fhir):
    return unbundle(fhir[patient_id]["MedicationRequest"])
#    return records.map(lambda xs : list(filter (lambda x : x["resourceType"] == "Condition", xs)))


def one(xs):
    if len(xs) == 1:
        return Right(xs[0])
    elif len(xs) == 0:
        return Right(None)
    else:
        return Left({
            "variableValue": {
                "value": None
            },
            "how": "more than one record found",
            "certitude": 0
        })        

    
def get_patient(patient_id, fhir):
    return unbundle(fhir[patient_id]["Patient"]).bind(one)
#    return records.bind(lambda xs : one(list(filter (lambda x : x["resourceType"] == "Patient", xs))))

def get_medication_request(patient_id, fhir):
    return unbundle(fhir[patient_id]["MedicationRequest"])

def height(records, unit, timestamp):
    return query_records_closest(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"8302-2",
	        "is_regex": False
	    }
        ], unit, timestamp, "height", "Observation")


def weight(records, unit, timestamp):
    return query_records_closest(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"29463-7",
	        "is_regex": False
	    }
        ], unit, timestamp, "weight", "Observation")


def height2(records, unit, start, end):
    return query_records_interval(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"8302-2",
	        "is_regex": False
	    }
        ], unit, start, end, "height", "Observation")


def weight2(records, unit, start, end):
    return query_records_interval(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"29463-7",
	        "is_regex": False
	    }
        ], unit, start, end, "weight", "Observation")


def bmi2(height, weight, records, unit, start, end):
    h = height["variableValue"]
    w = weight["variableValue"]
    if h["value"] is None or w["value"] is None:
        return query_records_interval(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"39156-5",
	        "is_regex": False
	    }
        ], unit, start, end, "bmi", "Observation").map(lambda x:average(x,start,end))
    else:
        hc = convert(h["value"], h["unit"], "m")
        wc = convert(w["value"], w["unit"], "kg")

        if isinstance(hc, Left):
            return hc
        elif isinstance(wc, Left):
            return wc
        bmi = wc.value / (hc.value * hc.value)
        return convert(bmi, "kg/m^2", unit).map(lambda bmic: {
            "variableValue": {
                "value": bmic,
                "unit": unit
            },
            "certitutde": min(height["certitude"], weight["certitude"]),
            "how": {
                "computed_from": ["height", "weight"],
                "height": height['how'],
                "weight": weight['how']
            }
        })
        
    
def bmi(height, weight, records, unit, timestamp):
    h = height["variableValue"]
    w = weight["variableValue"]
    if h["value"] is None or w["value"] is None:
        return query_records_closest(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"39156-5",
	        "is_regex": False
	    }
        ], unit, timestamp, "bmi", "Observation").map(average)
    else:
        hc = convert(h["value"], h["unit"], "m")
        wc = convert(w["value"], w["unit"], "kg")

        if isinstance(hc, Left):
            return hc
        elif isinstance(wc, Left):
            return wc
        bmi = wc.value / (hc.value * hc.value)
        return convert(bmi, "kg/m^2", unit).map(lambda bmic: {
            "variableValue": {
                "value": bmic,
                "unit": unit
            },
            "certitutde": min(height["certitude"], weight["certitude"]),
            "how": {
                "computed_from": ["height", "weight"],
                "height": height['how'],
                "weight": weight['how']
            }
        })
        
    
def calculate_age2(born, timestamp):
    today = timestamp
    return Right(today.year - born.year - ((today.month, today.day) < (born.month, born.day)))


def age(patient, unit, timestamp):
    if unit is not None and unit != "year":
        return Left((f"unsupported unit {unit}", 400))

    if patient == None:
        return Right({
            "variableValue": {
                "value": None
            },
            "certitude": 0,
            "how": "record not found"            
        })
    else:
        if "birthDate" in patient:
            birth_date = patient["birthDate"]
            date_of_birth = strtodate2(birth_date)
            today = timestamp.strftime("%Y-%m-%d")
            mage = calculate_age2(date_of_birth, timestamp)
            return mage.map(lambda age: {
                "variableValue": {
                    "value": age,
                    "unit": "year"
                },
                "certitude": 2,
                "how": {
                    "request_timestamp": today,
                    "computed_from": [
                        "request_timestamp", "birthDate"
                    ],
                    "birthDate": {
                        "computed_from": {
                            "resourceType": "Patient",
                            "field": "birthDate"
                        },
                        "value": birth_date
                    }
                }
            })
        else:
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": "birthDate not set"
            })


def sex(patient, unit, timestamp):
    if patient == None:
        return Right({
            "variableValue": {
                "value": None
            },
            "certitude": 0,
            "how": "record not found"            
        })
    else:
        gender = patient.get("gender")
        if gender is None:
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": "gender not set"
            })
        else:
            return Right({
                "variableValue": {
                    "value": gender
                },
                "certitude": 2,
                "how": f"FHIR resource 'Patient' field>'gender' = {gender}"
            })


def demographic_extension(url):
    def func(patient, unit, timestamp):
        if patient == None:
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": "record not found"            
            })
        else:
            extension = patient.get("extension")
            if extension is None:
                return Right({
                    "variableValue": {
                        "value": None
                    },
                    "certitude": 0,
                    "how": "extension not found"
                })
            else:
                
                filtered = filter(lambda x: x["url"]==url, extension)
                if len(filtered) == 0:
                    return Right({
                        "variableValue": {
                            "value": None
                        },
                        "certitude": 0,
                        "how": f"extension not found url {url}"
                    })
                else:
                    certitude = 2
                    value = []
                    calculation = url
                    hasValueCodeableConcept = True
                    
                    for a in filtered:
                        valueCodeableConcept = a.get("valueCodeableConcept")
                        if valueCodeableConcept is None:
                            certitude = 1
                            calculation += " valueCodeableConcept not found"
                        else:
                            hasValueCodeableConcept = True
                            value.append(valueCodeableConcept)
                            
                    if len(value) == 0:
                        certitude = 0
                    elif not hasValueCodeableConcept:
                        calculation += " on some extension"

                    return Right({
                        "variableValue": {
                            "value": value
                        },
                        "certitude": certitude,
                        "how": calculation
                    })
    return func


race = demographic_extension("http://hl7.org/fhir/StructureDefinition/us-core-race")


ethnicity = demographic_extension("http://hl7.org/fhir/StructureDefinition/us-core-ethnicity")


def serum_creatinine(records, unit, timestamp):
    return query_records_closest(records, [
	{
	    "system":"http://loinc.org",
	    "code":"2160-0",
	    "is_regex": False
	}
    ], unit, timestamp, "serum creatinine", "Observation")


def pregnancy(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"^Z34\\.",
            "is_regex": True
        }
    ], unit, timestamp, "pregnancy", "Condition")

bleeding_patterns = [
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I60\\..*",
            "is_regex":True 
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I61\\..*",
            "is_regex":True
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I62\\..*",
            "is_regex":True
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"G95.19",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"T85.830",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H11.3",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H31.3",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H43.1",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H59.1",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H59.3",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I85.01",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K22.11",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H22.6",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H25.0",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H25.2",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H25.4",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H25.6",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H26.0",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H26.2",
            "is_regex":False
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H26.4",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H26.6",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H27.0",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H27.2",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H27.4",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H27.6",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H28.0",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H28.2",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H28.4",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"H28.6",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K29.01",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K31.811",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K92.0",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K55.21",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.01",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.21",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.31",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.33",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.41",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.51",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.53",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.81",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.91",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K57.93",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K62.5",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K92.1",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K92.2",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"K66.1",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"M25.0",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I31.2",
            "is_regex":False,
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"R58\\..*",
            "is_regex":True,
        }
    ]

def bleeding(records, timestamp):
    return query_records_closest(records, bleeding_patterns, None, timestamp, "bleeding", "Condition")


def bleeding2(records, start, end):
    return query_records_interval(records, bleeding_patterns, None, start, end, "bleeding", "Condition")


def kidney_dysfunction(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N00\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N10\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N17\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N14\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N14.1",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N14.2",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"T36.5X5",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"B52.0",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"D59.3",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"E10.2",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"E11.2",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"E13.2",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I12\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I13\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I15.1",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"I15.2",
            "is_regex":False,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N01\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N02\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N03\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N04\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N05\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N06\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N07\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N08\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N11\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N13\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N15\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N16\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N18\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N19\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N25\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N26\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N27\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N28\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N29\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Q60\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Q61\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Q62\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Q63\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Z49\\..*",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"Z99.2",
            "is_regex":True,
	    
        },
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"N12\\..*",
            "is_regex":True,
	    
        }
    ], unit, timestamp, "kidney dysfunction", "Condition")


def DOAC2(records, start, end):
    print("records = " + str(records))
    return query_records_interval(records, [
        {
            "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
            "code":"1114195",
            "is_regex": False
        }, {
            "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
            "code":"1599538",
            "is_regex": False
        }
    ], None, start, end, "DOAC", "MedicationRequest")


def strtodate2(s):
    date = strtodate(s)
    if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
        date = date.replace(tzinfo=timezone.utc)
    return date


def get_first_date(values):
    sorted_values = sorted(values, key=lambda x: strtodate2(x["timestamp"]))
    if len(sorted_values) == 0:
        return None
    else:
        return strtodate2(sorted_values[0]["timestamp"])


def get_first(values):
    sorted_values = sorted(values, key=lambda x: strtodate2(x["timestamp"]))
    if len(sorted_values) == 0:
        return None
    else:
        return sorted_values[0]


def get_last(values):
    sorted_values = sorted(values, key=lambda x: strtodate2(x["timestamp"]))
    if len(sorted_values) == 0:
        return None
    else:
        return sorted_values[-1]


def adverse_event(records, start, end):
    return []


def average(values, start, end):
    return values[0] if len(values) > 0 else {
        "variableValue": {
            "value": None
        }
    }


mapping = {
    "LOINC:2160-0": (get_observation, serum_creatinine, "mg/dL"), # serum creatinine
    "LOINC:82810-3": (get_condition, pregnancy, None), # pregnancy
    "HP:0001892": (get_condition, bleeding, None), # bleeding
    "HP:0000077": (get_condition, kidney_dysfunction, None), # kidney dysfunction
    "LOINC:30525-0": (get_patient, age, "year"),
    "LOINC:54134-2": (get_patient, race, None),
    "LOINC:54120-1": (get_patient, ethnicity, None),
    "LOINC:21840-4": (get_patient, sex, None),
    "LOINC:8302-2": (get_observation, height, "m"),
    "LOINC:29463-7": (get_observation, weight, "kg"),
    "LOINC:39156-5": (get_observation, bmi, "kg/m^2")
}
