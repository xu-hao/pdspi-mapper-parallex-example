from tx.fhir.utils import unbundle
from tx.dateutils.utils import tstostr, strtots, strtodate
from datetime import datetime, date
import os
import re
from oslash import Left, Right
from tx.pint.utils import convert


def extract_key(a):
    if "effectiveInstant" in a:
        return a["effectiveInstant"]
    if "effectiveDateTime" in a:
        return a["effectiveDateTime"]
    if "onsetDateTime" in a:
        return a["onsetDateTime"]
    return None
    

def key(a):
    if "effectiveInstant" in a:
        return "effectiveInstant"
    if "effectiveDateTime" in a:
        return "effectiveDateTime"
    if "onsetDateTime" in a:
        return "onsetDateTime"
    return None
        

def calculation(codes):
    return ",".join(list(map(lambda a: a["system"] + " " + a["code"], codes)))


def calculation_template(clinical_variable, resource_name, timestamp_today, record, to_unit):
    from_code = calculation(record["code"]["coding"])
    timestamp_record = extract_key(record)
    if timestamp_record is not None:
        record_timestamp_name = key(record)
        timestamp = f" (Date computed from FHIR resource '{resource_name}', field>'{record_timestamp_name}' = '{timestamp_record}');"
    else:
        timestamp = " (record has no timestamp)"
    vq = record.get("valueQuantity")
    if vq is None:
        from_value = ""
    else:
        value = vq["value"]
        from_unit = vq.get("units")
        if from_unit is None:
            from_unit = vq.get("code")
            from_unit_from = "code"
        else:
            from_unit_from = "unit"
        if from_unit is not None:
            def unit_eq(a, b):
                return a == b
            if to_unit is not None and not unit_eq(to_unit, from_unit):
                unit = f", '{from_unit_from}'>'{from_unit}' converted to {to_unit}"
            else:
                unit = f", '{from_unit_from}'>'{from_unit}'"
        else:
            unit = ""
        from_value = f", field>'valueQuantity'field>'value' = '{value}'{unit}"
    return f"current as of {timestamp_today}.{timestamp} '{clinical_variable}' computed from FHIR resource '{resource_name}' code {from_code}{from_value}."

def query_records(records, codes, unit, timestamp, clinical_variable, resource_name):
    if records == None:
        return Right({
            "value": None,
            "certitude": 0,
            "how": "no record found"
        })

    records_filtered = []
    for record in records:
        for c in codes:  
            system = c["system"]
            code = c["code"]
            is_regex = c["is_regex"]

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
        ts = strtots(timestamp)
        def key(a):
            ext_key = extract_key(a)
            if ext_key is None:
                return float("inf")
            else:
                return abs(strtots(ext_key) - ts)
        record = min(records_filtered, key = key)
        keyr = extract_key(record)
        if keyr is None:
            ts = None
            cert = 1
        else:
            ts = extract_key(record)
            cert = 2
        vq = record.get("valueQuantity")
        if vq is not None:
            v = vq["value"]
            from_u = vq.get("units")
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
                **({"units": unit} if unit is not None else {"units": from_u} if from_u is not None else {}),
            },
            "certitude": cert,
            "timestamp": ts,
            "how": c
        })
    

def get_observation(patient_id, fhir):
    records = unbundle(fhir)
    return records.map(lambda xs : list(filter (lambda x : x["resourceType"] == "Observation", xs)))


def get_condition(patient_id, fhir):
    records = unbundle(fhir)
    return records.map(lambda xs : list(filter (lambda x : x["resourceType"] == "Condition", xs)))


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
    records = unbundle(fhir)
    return records.bind(lambda xs : one(list(filter (lambda x : x["resourceType"] == "Patient", xs))))


def get_patient2(patient_id, fhir):
    return get_patient(patient_id, fhir).value


def height(records, unit, timestamp):
    return query_records(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"8302-2",
	        "is_regex": False
	    }
        ], unit, timestamp, "height", "Observation")


def weight(records, unit, timestamp):
    return query_records(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"29463-7",
	        "is_regex": False
	    }
        ], unit, timestamp, "weight", "Observation")


def bmi(records, unit, timestamp):
    return query_records(records, [
	    {
	        "system":"http://loinc.org",
	        "code":"39156-5",
	        "is_regex": False
	    }
        ], unit, timestamp, "bmi", "Observation")
    

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
            date_of_birth = strtodate(birth_date)
            today = strtodate(timestamp).strftime("%Y-%m-%d")
            mage = calculate_age2(date_of_birth, timestamp)
            return mage.map(lambda age: {
                "variableValue": {
                    "value": age,
                    "units": "year"
                },
                "certitude": 2,
                "how": f"Current date '{today}' minus patient's birthdate (FHIR resource 'Patient' field>'birthDate' = '{birth_date}')"
            })
        else:
            return Right({
                "variableValue": {
                    "value": None
                },
                "certitude": 0,
                "how": "birthDate not set"
            })


def age2(patient, unit, timestamp):
    return age(patient, unit, timestamp).value


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
    return query_records(records, [
	{
	    "system":"http://loinc.org",
	    "code":"2160-0",
	    "is_regex": False
	}
    ], unit, timestamp, "serum creatinine", "Observation")


def pregnancy(records, unit, timestamp):
    return query_records(records, [
        {
            "system":"http://hl7.org/fhir/sid/icd-10-cm",
            "code":"^Z34\\.",
            "is_regex": True
        }
    ], unit, timestamp, "pregnancy", "Condition")


def bleeding(records, unit, timestamp):
    return query_records(records, [
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
    ], unit, timestamp, "bleeding", "Condition")


def kidney_dysfunction(records, unit, timestamp):
    return query_records(records, [
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
