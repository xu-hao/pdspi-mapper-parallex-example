import os
import logging
from pathlib import Path
from tx.parallex import start_python
from tx.functional.maybe import Just, Nothing
from tx.functional.either import Left
from tx.functional.utils import identity
from pathvalidate import validate_filename
from tx.requests.utils import get
import yappi
import json
import jsonpickle

yappi.set_clock_type(os.environ.get("CLOCK_TYPE", "wall"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config_url = os.environ.get("CONFIG_URL")

def mappend(a, b):
    if isinstance(a, list) and isinstance(b, list):
        obj = a + b
    elif isinstance(a, dict) and isinstance(b, dict):
        obj = {}
        for k, v in a.items():
            if k in b:
                obj[k] = mappend(v, b[k])
            else:
                obj[k] = v
        for kb, vb in b.items():
            if kb not in a:
                obj[kb] = vb
    else:
        obj = b

    return obj
    
def assign(array, keys, value):
    if len(keys) == 0:
        return mappend(array, value)
    else:
        key, *the_keys = keys
        if array is None:
            array = []

        if isinstance(key, int):
            if isinstance(array, list):
                if len(array) <= key:
                    array = array + [{}] * (key + 1 - len(array))
            else:
                if key not in array:
                    array[key] = {}
        else:
            if isinstance(array, list):
                obj = {}
                for i, elem in enumerate(array):
                    obj[i] = elem
                array = obj
            if key not in array:
                array[key] = {}
                
        array[key] = assign(array[key], the_keys, value)
        
        return array

    
def getModelParameter(modelParameters, modelParameterId, proc, default):
    specNames = [modelParameter for modelParameter in modelParameters if modelParameter["id"] == modelParameterId]
    if len(specNames) == 0 or specNames[0].get("parameterValue", {}).get("value") is None:
        specName = default()
    else:
        specName = proc(specNames[0]["parameterValue"]["value"])
    return specName


def jsonify(obj):
    if isinstance(obj, dict):
        return {k: json.dumps(jsonify(v), sort_keys=True) if k == "how" else jsonify(v) for k, v in obj.items()}
    elif isinstance(obj, list) or isinstance(obj, tuple) or isinstance(obj, set):
        return [jsonify(elem) for elem in obj]
    elif isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool) or isinstance(obj, str) or obj is None:
        return obj
    else:
        return str(obj)


output_dir = os.environ.get("OUTPUT_DIR")

def mappingClinicalFromData(body):
    config = get_default_config(get_config())
    settingsRequested = body.get("settingsRequested", {})
    settingsDefault = config.get("settingsDefault", {})
    modelParameters = settingsRequested.get("modelParameters", [])
    modelParametersDefault = settingsDefault.get("modelParameters", [])
    patientVariables = settingsRequested.get("patientVariables", settingsRequested.get("patientVariables", []))

    specName = getModelParameter(modelParameters, "specName", identity, lambda: getModelParameter(modelParametersDefault, "specName", identity, lambda: "spec.py"))
    logger.info(f"specName = {specName}")
    validate_filename(specName)
    
    pythonLibrary = getModelParameter(modelParameters, "libraryPath", identity, lambda: getModelParameter(modelParametersDefault, "libraryPath", identity, lambda: []))

    logger.info(f"pythonLibrary = {pythonLibrary}")
    for p in pythonLibrary:
        validate_filename(p)

    outputPath = getModelParameter(modelParameters, "outputPath", identity, lambda: getModelParameter(modelParametersDefault, "outputPath", identity, lambda: None))
    if outputPath is not None:
        validate_filename(outputPath)

    nthreads = getModelParameter(modelParameters, "nthreads", int, lambda: getModelParameter(modelParametersDefault, "nthreads", int, lambda: 3))
    logger.info(f"nthreads = {nthreads}")

    level = getModelParameter(modelParameters, "level", int, lambda: getModelParameter(modelParametersDefault, "level", int, lambda: 0))
    logger.info(f"level = {level}")
    additional_arguments = getModelParameter(modelParameters, "args", identity, lambda: getModelParameter(modelParametersDefault, "args", identity, lambda: {}))
    logger.info(f"additional_arguments = {additional_arguments}")
    
    spec_path = Path(__file__).parent.parent / "config" / specName
    lib_path = list(map(lambda p: str(Path(__file__).parent.parent / "config" / p), pythonLibrary))
    logger.info(f"spec_path = {spec_path}")
    logger.info(f"lib_path = {lib_path}")
    logger.info(f"output_path = {outputPath}")
    
    with open(spec_path) as f:
        spec = f.read()

    logger.info(f"spec = {spec}")

    profile = os.environ.get("PROFILE")
    if profile is not None:
        yappi.start()

    output_file = None if outputPath is None else os.path.join(output_dir, outputPath)
    res = start_python(nthreads, py = spec, data = {
        "patientIds": body["patientIds"],
        "patientVariables": patientVariables,
        "timestamp": body["timestamp"],
        "data": body["data"],
        **additional_arguments
    }, output_path = output_file, system_paths = lib_path, validate_spec = False, level=level, object_store=None)

    if profile is not None:
        yappi.stop()

        stats = yappi.get_func_stats()
        stats.sort("tsub")
        stats.print_all()

    def proc_res(res, ret):
        for k,v in res.items():
            indices = [] if k == "" else k.split(".")
            ret = assign(ret, list(map(lambda index: int(index) if index.isdigit() else index, indices)), v.value)
        return ret

    ret = None
    if outputPath is None:
        ret = proc_res(res, ret)
    else:
        with open(output_file) as o:
            for line in o:
                ret = proc_res(jsonpickle.decode(line), ret)
        with open(output_file, "w") as o2:
            json.dump(jsonify(ret), o2)
        ret = None
    return jsonify(ret)
        

def get_default_config(default):

    if config_url is None:
        return default
    obj = get(config_url)
    if isinstance(obj, Left):
        return objl.value

    else:
        settingsDefault = None if config_url is None else obj.value.get("settingsDefaults", None)

        return {
            "title": "pds parallex mapper",
            'piid': "pdspi-mapper-parallex-example",
            "pluginType": "m",
            **({
                "settingsDefaults": settingsDefault,
            } if settingsDefault is not None else {}),
            "pluginTypeTitle": "Mapping"
        }


def get_config():
    spec_path = Path(__file__).parent.parent / "config" / "config.py"
    
    with open(spec_path) as f:
        spec = f.read()

    res = start_python(1, py=spec, data={}, output_path=None, system_paths=[], validate_spec=False, level=0, object_store=None)

    return res[""].value
