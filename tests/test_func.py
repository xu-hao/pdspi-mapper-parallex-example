from tx.dateutils.utils import strtodate
import pdspi.pds_fhir_loader
import pdsphenotypemapping.clinical_feature
from tx.functional.either import Either, Right
from tx.parallex import run
import datetime

timestamp = strtodate("2020-05-02T00:00:00Z")
pids = ["MickeyMouse"]
pid = pids[0]
json_in_dir = "./tests/ptdata"
X = 10
Y = 10
study_start = strtodate("2010-01-01T00:00:00Z")
study_end = strtodate("2011-01-01T00:00:00Z")
resource_names = ["Patient", "Observation", "Condition", "MedicationRequest"]
age_unit = "year"

def test_age():
    fhir = pdspi.pds_fhir_loader.get_entries(json_in_dir=json_in_dir, pid=pid, resource_names=resource_names)
    patient = pdsphenotypemapping.clinical_feature.get_patient(patient_id=pid, fhir=fhir)
    age = pdsphenotypemapping.clinical_feature.age(unit=age_unit, timestamp=timestamp, patient=patient.value)
    assert age == Right({
        'certitude': 2,
        'how': {
            'birthDate': {
                'computed_from': {
                    'field': 'birthDate',
                    'resourceType': 'Patient'
                },
                'value': '1960-10-1'
            },
            'computed_from': ['request_timestamp', 'birthDate'],
            'request_timestamp': '2020-05-02'
        },
        'variableValue': {'unit': 'year', 'value': 59}
    })


def test_DOAC():
    fhir = pdspi.pds_fhir_loader.get_entries(json_in_dir=json_in_dir, pid=pid, resource_names=resource_names)
    records = pdsphenotypemapping.clinical_feature.get_medication_request(patient_id=pid, fhir=fhir)
    interventions = pdsphenotypemapping.clinical_feature.DOAC(study_start=study_start, study_end=study_end, records=records.value)
    assert isinstance(interventions, Right)
    assert len(interventions.value) == 4


def test_run():
    ret = run(3, "tests/spec.yaml", "tests/data.yaml")
    keys = set(['0.age', '0.bmi', '0.height', '0.weight'])
    assert keys == ret.keys()
    for key in ret.keys():
        assert isinstance(ret[key], Right)

    


