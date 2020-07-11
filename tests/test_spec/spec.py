from pdspi.pds_fhir_loader import get_entries
from pdsphenotypemapping.clinical_feature import *
age_unit = "year"
height_unit = "m"
weight_unit = "kg"
bmi_unit = "kg/m^2"
resource_names = ["Patient", "Observation", "MedicationRequest"]
fhir = get_entries(json_in_dir=json_in_dir, pids=pids, resource_names=resource_names)
for pid in pids:
    age = age(unit=age_unit, timestamp=timestamp, patient=patient)
    bmi = bmi(height=height, weight=weight, unit=bmi_unit, timestamp=timestamp, records=observation)
    height = height(unit=height_unit, timestamp=timestamp, records=observation)
    weight = weight(unit=weight_unit, timestamp=timestamp, records=observation)
    patient = get_patient(patient_id=pid, fhir=fhir)
    medication_request = get_medication_request(patient_id=pid, fhir=fhir)
    observation = get_observation(patient_id=pid, fhir=fhir)
    return {
      "age" : age,
      "bmi" : bmi,
      "height": height,
      "weight": weight
    }

