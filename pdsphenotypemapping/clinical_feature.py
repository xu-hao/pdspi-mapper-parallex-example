from functools import reduce, partial
from datetime import datetime, date, timezone
import os
import re
import json
from tx.fhir.utils import unbundle
from tx.dateutils.utils import tstostr, strtots, strtodate
from tx.functional.either import Left, Right, Either, either_applicative
from tx.functional.maybe import Just, Nothing
import tx.functional.maybe as maybe
from tx.functional.list import list_traversable
from tx.functional.utils import const
from tx.pint.utils import convert
import logging
from tx.readable_log import getLogger
from tempfile import mkdtemp

logger = getLogger(__name__, logging.INFO)

list_traversable_either_applicative = list_traversable(either_applicative)


def extract_key(a):
    return key(a).bind(lambda k : Just(reduce(lambda a,i: a[i], k, a) if isinstance(k, list) else a[k]))

    
def key(a):
    if "effectiveInstant" in a:
        return Just("effectiveInstant")
    elif "effectiveDateTime" in a:
        return Just("effectiveDateTime")
    elif "onsetDateTime" in a:
        return Just("onsetDateTime")
    elif "authoredOn" in a:
        return Just("authoredOn")
    elif "dispenseRequest" in a:
        return Just(["dispenseRequest", "validityPeriod", "start"])
    elif "issued" in a:               
        return Just(["issued"])       
    elif "assertedDate" in a:         
        return Just(["assertedDate"]) 
    return Nothing
        

def calculation(codes):
    return list(map(lambda a: {
        "system": a["system"],
        "code": a["code"]
    }, codes))


def calculation_template(clinical_variable, resource_name, timestamp_range, record, to_unit):
    if resource_name == "MedicationRequest":
        code_path = "medication.medicationCodeableConcept"
        rcode = record.get("medication", record)["medicationCodeableConcept"]
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
        logger.debug(f"filtering record: {record}")
        for c in codes:  
            system = c["system"]
            code = c["code"]
            is_regex = c["is_regex"]

            if resource_name == "MedicationRequest":
                code2 = record.get("medication", record).get("medicationCodeableConcept")
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
                    code2 = c2.get("code")
                    if code2 is not None:
                        if (is_regex and re.search(code, "^" + code2 + "$")) or code2 == code:
                            records_filtered.append(record)
    return Right(records_filtered)


def convert_record_to_pds(record, unit, timestamp, clinical_variable, resource_name):
    ts = extract_key(record)
    cert = ts.rec(partial(const, 2), 1) 
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
        return list_traversable_either_applicative.sequence(map(lambda record: convert_record_to_pds(record, unit, timestamp, clinical_variable, resource_name), records2))

    return filter_records(records, codes, resource_name).bind(handle_records_filtered)


def filter_records_interval(records, start, end):
    def in_study_period(a):
        ext_key = extract_key(a)
        if ext_key is Nothing:
            return False
        else:
            record_date = strtodate2(ext_key.value)
            return start <= record_date and record_date < end
        
    records = filter(in_study_period, records)
    return records

input_dir = os.environ.get("INPUT_DIR", "/tmp")

def deref(fhir, patient_id):
    if isinstance(fhir, dict) and (dirname := fhir.get("$ref")) is not None:
        try:
            with open(os.path.join(input_dir, dirname, patient_id + ".json")) as input_file:
                return Right(json.load(input_file))
        except Exception as e:
            return Left(str(e))
    else:
        return get_patient_batch_response(patient_id, fhir)

    
def get_observation(patient_id, fhir):
    return get_resource("Observation", patient_id, fhir)


def get_observation_patient(fhir):                  
    return get_resource_patient("Observation", fhir)
                                                    
                                                    
def get_condition(patient_id, fhir):
    return get_resource("Condition", patient_id, fhir)


def get_condition_patient(fhir):                  
    return get_resource_patient("Condition", fhir)
                                                  
                                                  
def get_patient_batch_response(patient_id, fhir):
    for bundle in fhir:
        mentries = unbundle(bundle)
        if isinstance(mentries, Left):
            return mentries
        else:
            for entry in mentries.value:
                if entry["resourceType"] == "Patient" and entry["id"] == patient_id:
                    return Right(bundle)
    return Left("No Bundle resource found")


def either_to_maybe(e):
    e.rec(lambda _: Nothing, identity)

    
def get_resource(resource_type, patient_id, fhir):
    return deref(fhir, patient_id).bind(partial(get_resource_patient, resource_type))
                                                                                                          
                                                                                                          
def get_resource_patient(resource_type, fhir):                                                            
    def handle_patient_batch_response(batch_response_entries):
        if resource_type == "Patient":
            for entry in batch_response_entries:
                if entry["resourceType"] == "Patient":
                    return Right(entry)
            return Left("No Patient resource found")
        else:
            for entry in batch_response_entries:
                if entry["resourceType"] == "Bundle":
                    mresources = unbundle(entry)
                    if isinstance(mresources, Left):
                        return mresources
                    else:
                        resources = mresources.value
                        if len(resources) > 0 and resources[0]["resourceType"] == resource_type:
                            return mresources
            return Right([])
    
    return unbundle(fhir).bind(handle_patient_batch_response)
        

def get_condition_icd_code(patient_id, fhir):
    records = unbundle(fhir['Condition']).value
    icd_codes = []
    icd_10_url = 'http://hl7.org/fhir/sid/icd-10-cm'
    icd_9_url = 'http://hl7.org/fhir/sid/icd-9-cm'
    for rec in records:
        codes = rec.get('code', {}).get('coding', [])
        for code in codes:
            icd_system = code.get('system', '')
            if icd_system == icd_10_url or icd_system == icd_9_url:
                icd_codes.append({'system': icd_system,
                                  'code': code.get('code', '')})
    return icd_codes


def get_medication_request(patient_id, fhir):
    return get_resource("MedicationRequest", patient_id, fhir)


def get_medication_request_patient(fhir):                 
    return get_resource_patient("MedicationRequest", fhir)
                                                          
                                                          
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
    return get_resource("Patient", patient_id, fhir)


def get_patient_patient(fhir):                  
    return get_resource_patient("Patient", fhir)


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
        ], unit, start, end, "bmi", "Observation").map(average)
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
        ], unit, timestamp, "bmi", "Observation")
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
        
    
def oxygen_saturation(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system":"http://loinc.org",
            "code":"LP21258-6",
            "is_regex": False
        }
    ], unit, timestamp, "oxygen saturation", "Observation")


def address(patient, unit, timestamp):
    if patient == None:
        return Right({
            "variableValue": {
                "value": None
            },
            "certitude": 0,
            "how": "record not found"
        })
    else:
        address = patient.get("address")
        if address is None:
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": "address not set"
            })
        else:
            # use home type address if available, otherwise, just use the first address
            used_addr_dict = None
            for addr in address:
                if addr['use'] == 'home':
                    used_addr_dict = addr
                    break
            if not used_addr_dict:
                used_addr_dict = address[0]
            used_addr_str = '{line}, {city}, {state} {pc}, {country}'.format(line=','.join(used_addr_dict['line']),
                                                                             city=used_addr_dict['city'],
                                                                             state=used_addr_dict['state'],
                                                                             pc=used_addr_dict['postalCode'],
                                                                             country=used_addr_dict['country'])
            return Right({
                "variableValue": {
                    "value": used_addr_str
                },
                "certitude": 2,
                "how": f"FHIR resource 'Patient' field>'address' = {used_addr_str}"
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
                    calculation = {
                        "from": {
                            "extension": {
                                "url": url
                            }
                        }
                    }
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


def fever(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "45701-0",
            "is_regex": False
        }
    ], unit, timestamp, "fever", "Condition")


def date_of_fever_onset(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "LP212175-6",
            "is_regex": False
        }
    ], unit, timestamp, "date of fever onset", "Condition")


def cough(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "64145-6",
            "is_regex": False
        }
    ], unit, timestamp, "cough", "Condition")


def date_of_cough_onset(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "85932-2",
            "is_regex": False
        }
    ], unit, timestamp, "date of cough onset", "Condition")


def shortness_of_breath(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "54564-0",
            "is_regex": False
        }
    ], unit, timestamp, "shortness of breath", "Condition")


def autoimmune_disease(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "LP128504-0",
            "is_regex": False
        }
    ], unit, timestamp, "autoimmune disease", "Condition")


def pulmonary_disease(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "54542-6",
            "is_regex": False
        }
    ], unit, timestamp, "pulmonary disease", "Condition")


def cardiovascular_disease(records, unit, timestamp):
    return query_records_closest(records, [
        {
            "system": "http://loinc.org",
            "code": "LP172921-1",
            "is_regex": False
        }
    ], unit, timestamp, "cardiovascular disease", "Condition")


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

def bleeding(records, unit, timestamp):
    return query_records_closest(records, bleeding_patterns, None, timestamp, "bleeding", "Condition")


def bleeding2(records, unit, start, end):
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
    return query_records_interval(records, doac_event_code_maps, None, start, end, "DOAC", "MedicationRequest")


def DOAC_Interventions(records, start, end):#for testing since records cannot find this code                   
    return query_records_interval(records, doac_event_code_maps, None, start, end, "DOAC", "MedicationRequest")
                                                                                                               

def strtodate2(s):
    date = strtodate(s)
    if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
        date = date.replace(tzinfo=timezone.utc)
    return date


def get_first_date(values):
    return get_first(values).map(lambda x: x["timestamp"])


def get_first(values):
    sorted_values = sorted(values, key=lambda x: strtodate2(x["timestamp"]))
    if len(sorted_values) == 0:
        return Left("empty list")
    else:
        return Right(sorted_values[0])


def get_last(values):
    sorted_values = sorted(values, key=lambda x: strtodate2(x["timestamp"]))
    if len(sorted_values) == 0:
        return Left("empty list")
    else:
        return Right(sorted_values[-1])


def adverse_event(records, start, end):
    return []


def average(values):
    return values[0] if len(values) > 0 else {
        "variableValue": {
            "value": None
        }
    }


def get_patient_variable_ids(patient_variables):
    return list(map(lambda x: x["id"], patient_variables))


doac_event_code_maps =[                                                
        {                                                          
            "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
            "code":"1114195",                                      
            "is_regex": False                                      
        }, {                                                       
            "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
            "code":"1599538",                                      
            "is_regex": False                                      
        },                                                          
        #apixaban                                                      
        {                                                              
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1364441",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1364447",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1992428",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1364435",                                      
                "is_regex": False                                      
        }, {                                                           
        #dabigatran etexilate                                          
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1037049",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1037181",                                      
                "is_regex": False                                      
        }, {                                                           
        #rivaroxaban                                                   
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1114202",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1232084",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1232088",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1549683",                                      
                "is_regex": False                                      
        }, {                                                           
        #edoxaban                                                      
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1599553",                                      
                "is_regex": False                                      
        }, {                                                           
                "system":"http://www.nlm.nih.gov/research/umls/rxnorm",
                "code":"1599557",                                      
                "is_regex": False                                      
        }                                                              
]                                                                      


mapping = {
    "LOINC:2160-0": (get_observation, serum_creatinine, "mg/dL"), # serum creatinine
    "LOINC:82810-3": (get_condition, pregnancy, None), # pregnancy
    "HP:0001892": (get_condition, bleeding, None), # bleeding
    "HP:0000077": (get_condition, kidney_dysfunction, None), # kidney dysfunction
    "LOINC:45701-0": (get_condition, fever, None),
    "LOINC:LP212175-6": (get_condition, date_of_fever_onset, None),
    "LOINC:64145-6": (get_condition, cough, None),
    "LOINC:85932-2": (get_condition, date_of_cough_onset, None),
    "LOINC:54564-0": (get_condition, shortness_of_breath, None),
    "LOINC:LP128504-0": (get_condition, autoimmune_disease, None),
    "LOINC:54542-6": (get_condition, pulmonary_disease, None),
    "LOINC:LP172921-1": (get_condition, cardiovascular_disease, None),
    "LOINC:30525-0": (get_patient, age, "year"),
    "LOINC:54134-2": (get_patient, race, None),
    "LOINC:54120-1": (get_patient, ethnicity, None),
    "LOINC:21840-4": (get_patient, sex, None),
    "LOINC:56799-0": (get_patient, address, None),
    "LOINC:8302-2": (get_observation, height, "m"),
    "LOINC:29463-7": (get_observation, weight, "kg"),
    "LOINC:39156-5": (get_observation, bmi, "kg/m^2"),
    "LOINC:LP21258-6": (get_observation, oxygen_saturation, "%")
}
