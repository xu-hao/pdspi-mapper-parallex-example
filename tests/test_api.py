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

resource_names = ["MedicationRequest", "Condition", "Observation"]

def query(pids, timestamp):
    fhir = get_entries(json_in_dir=data_dir, pids=pids, resource_names=resource_names)

    log.info(f"fhir = {fhir}")

    return requests.post(f"http://pdspi-mapper-parallex-example:8080/mapping", headers=json_headers, json={
        "data": fhir,
        "pids": pids,
        "timestamp": timestamp
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

    
