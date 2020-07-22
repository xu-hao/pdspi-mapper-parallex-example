import os
import logging
from pathlib import Path
from tx.parallex import start_python

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

number_of_workers = os.environ.get("PARALLEL_RUNS", 3)

def assign(array, keys, value):
    if len(keys) == 0:
        return value
    else:
        key, *the_keys = keys
        if array is None:
            array = []
        if isinstance(array, list):
            if len(array) <= key:
                array = array + [{}] * (key + 1 - len(array))
        else:
            if key not in array:
                array[key] = {}

        array[key] = assign(array[key], the_keys, value)
        return array

    
def mappingClinicalFromData(body):
    spec_path = Path(__file__).parent / "config" / f"{body.get('specName', 'spec')}.py"

    with open(spec_path) as f:
        spec = f.read()

    res = start_python(number_of_workers, py = spec, data = {
        "pids": body["pids"],
        "timestamp": body["timestamp"],
        "fhir": body["data"]
    }, validate_spec = False)

    ret = None
    for k,v in res.items():
        *indices, key = k.split(".")
        ret = assign(ret, list(map(int, indices)) + [key], v.value)
    
    return ret
        

config = {
    "title": "smarthealthit.org tx-parallex variable mapper",
    "pluginType": "m",
    "pluginTypeTitle": "Mapping",
    "pluginSelectors": [],
    "supportedPatientVariables": [
        {
            "id": i,
            "title": t,
            "legalValues": lv
        } for i,t,lv in [
            ("LOINC:2160-0", "Serum creatinine", {"type": "number"}),
            ("LOINC:82810-3", "Pregnancy", {"type": "boolean"}),
            ("HP:0001892", "Bleeding", {"type": "boolean"}),
            ("HP:0000077", "Kidney dysfunction", {"type": "boolean"}),
            ("LOINC:30525-0", "Age", {"type": "integer"}),
            ("LOINC:54134-2", "Race", {"type": "string"}),
            ("LOINC:54120-1", "Ethnicity", {"type": "string"}),
            ("LOINC:21840-4", "Sex", {"type": "string"}),
            ("LOINC:8302-2", "Height", {"type": "number"}),
            ("LOINC:29463-7", "Weight", {"type": "number"}),
            ("LOINC:39156-5", "BMI", {"type": "number"})
        ]
    ]
}


def get_config():
    return config

