import requests
import yaml
from pathlib import Path
from pdspi.pds_fhir_loader import get_entries
import logging


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

json_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

data_dir = Path(__file__).parent / "ptdata"

log.info(f"looking for fhir at {data_dir}")

resource_names = ["Patient", "MedicationRequest", "Condition", "Observation"]

def query(pids, timestamp, spec_name=None, lib_name=None):
    fhir = get_entries(json_in_dir=data_dir, pids=pids, resource_names=resource_names)

    log.info(f"fhir = {fhir}")

    return requests.post(f"http://pdspi-mapper-parallex-example:8080/mapping", headers=json_headers, json={
        "data": fhir,
        "pids": pids,
        "settings_requested": {
            "modelParameters": ([] if spec_name is None else [{
                "id": "specName",
                "parameterValue": spec_name
            }]) + ([] if lib_name is None else [{
                "id": "libraryPath",
                "parameterValue": lib_name
            }])
        },
        "timestamp": timestamp,
        **({} if spec_name is None else {"specName": spec_name})
    })


def test_api_spec():
    timestamp = "2020-05-02T00:00:00Z"
    pids = ["MickeyMouse"]

    result = query(pids, timestamp)
    log.info(result.content)
    assert result.status_code == 200
                
    assert result.json() == [{
        "bmi_after": {
            "variableValue": {
                "value": None
            }
        },
        "bmi_before": {
            "variableValue": {
                "value": None
            }
        },
        "outcome": False
    }]

def test_api_spec2():
    timestamp = "2020-05-02T00:00:00Z"
    pids = ["MickeyMouse"]

    result = query(pids, timestamp, spec_name="spec2")
    log.info(result.content)
    assert result.status_code == 200
                
    assert result.json() == [{
        "outcome": False
    }]

def test_api_spec3():
    timestamp = "2020-05-02T00:00:00Z"
    pids = ["MickeyMouse"]

    result = query(pids, timestamp, spec_name="spec3", lib_name="spec3")
    log.info(result.content)
    assert result.status_code == 200
                
    assert result.json() == [{
        "outcome": [1]
    }]

    
