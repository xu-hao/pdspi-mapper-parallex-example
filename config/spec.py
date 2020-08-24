from pdsphenotypemapping.clinical_feature import *
from tx.dateutils.utils import strtodate
from dateutil.relativedelta import relativedelta
requested_patient_variable_ids = get_patient_variable_ids(patientVariables)
timestamp_datetime = strtodate(timestamp)
for patient_data in data:
    patient = get_patient_patient(patient_data)
    pid = patient["id"]
    yield {
        "patientId": pid
    }
        
    condition = get_condition_patient(fhir=patient_data)
    observation = get_observation_patient(fhir=patient_data)

    if "LOINC:2160-0" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:2160-0",
                **serum_creatinine(observation, "mg/dL", timestamp_datetime)
            }]
        }
    if "LOINC:82810-3" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:82810-3",
                **pregnancy(condition, None, timestamp_datetime)
            }]
        }
    if "HP:0001892" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "HP:0001892",
                **bleeding(condition, None, timestamp_datetime)
            }]
        }
    if "HP:0000077" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "HP:0000077",
                **kidney_dysfunction(condition, None, timestamp_datetime)
            }]
        }
    if "LOINC:30525-0" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:30525-0",
                **age(patient, "year", timestamp_datetime)
            }]
        }
    if "LOINC:54134-2" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:54134-2",
                **race(patient, None, timestamp_datetime)
            }]
        }
    if "LOINC:54120-1" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:54120-1",
                **ethnicity(patient, None, timestamp_datetime)
            }]
       }
    if "LOINC:21840-4" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:21840-4",
                **sex(patient, None, timestamp_datetime)
            }]
        }
    if "LOINC:8302-2" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:8302-2",
                **height(observation, "m", timestamp_datetime)
            }]
        }
    if "LOINC:29463-7" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:29463-7",
                **weight(observation, "kg", timestamp_datetime)
            }]
        }
    if "LOINC:39156-5" in requested_patient_variable_ids:
        yield {
            "values": [{
                "id": "LOINC:39156-5",
                **bmi(observation, "kg/m^2", timestamp_datetime)
            }]
        }

