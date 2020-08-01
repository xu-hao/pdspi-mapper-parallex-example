import os
import logging
from pathlib import Path
from tx.parallex import start_python
from tx.functional.maybe import Just, Nothing
from pathvalidate import validate_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    modelParameters = body.get("settingsRequested", {}).get("modelParameters", [])
    logger.info(f"modelParameters = {modelParameters}")
    specNames = [modelParameter for modelParameter in modelParameters if modelParameter["id"] == "specName"]
    logger.info(f"specNames = {specNames}")
    if len(specNames) == 0:
        specName = "spec.py"
    else:
        specName = specNames[0]["parameterValue"]["value"]
        validate_filename(specName)
    specNames = [modelParameter for modelParameter in modelParameters if modelParameter["id"] == "libraryPath"]
    if len(specNames) == 0:
        pythonLibrary = Nothing
    else:
        pythonLibrary = Just(specNames[0]["parameterValue"]["value"])
        pythonLibrary.map(validate_filename)
    
    spec_path = Path(__file__).parent.parent / "config" / specName
    lib_path = pythonLibrary.map(lambda pythonLibrary: str(Path(__file__).parent.parent / "config" / pythonLibrary)).rec(lambda x: [x], [])
    logger.info(f"spec_path = {spec_path}")
    
    with open(spec_path) as f:
        spec = f.read()

    logger.info(f"spec = {spec}")

    res = start_python(number_of_workers, py = spec, data = {
        "patientIds": body["patientIds"],
        "timestamp": body["timestamp"],
        "data": body["data"]
    }, output_path = None, system_paths = lib_path, validate_spec = False)

    ret = None
    for k,v in res.items():
        indices = [] if k == "" else k.split(".")
        ret = assign(ret, list(map(int, indices)), v.value)
    
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

