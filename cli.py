from tx.parallex import run_python
import pprint
import sys
import yaml
import requests
import time

specName, libraryPath, dataFile, nthreads, level, resourceTypesFile, patientIdsFile, timestamp, fhirPort, mapperPort = sys.argv[1:]

nthreadsint = int(nthreads)

with open(patientIdsFile) as f:
    patientIds = yaml.safe_load(f)

with open(resourceTypesFile) as f:
    resourceTypes = yaml.safe_load(f)

with open(dataFile) as f:
    data = yaml.safe_load(f)

json_headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}
fhirStart = time.time()
resp = requests.post(f"http://localhost:{fhirPort}/resource", json={
    "resourceTypes": resourceTypes,
    "patientIds": patientIds
}, headers=json_headers)

fhirEnd = time.time()

print(fhirEnd - fhirStart)

fhir = resp.json()

mapperStart = time.time()

resp = requests.post(f"http://localhost:{mapperPort}/mapping", json={
    "data": fhir,
    "settingsRequested": {
        "modelParameters": [{
            "id": "specName",
            "parameterValue": {"value": specName}
        }, {
            "id": "nthreads",
            "parameterValue": {"value": nthreads}
        }, {
            "id": "level",
            "parameterValue": {"value": level}
        }] + ([] if libraryPath == "" else [{
            "id": "libraryPath",
            "parameterValue": {"value": libraryPath}
        }])
    },
    "patientIds": patientIds,
    "timestamp": timestamp
}, headers=json_headers)

mapperEnd = time.time()

print(mapperEnd - mapperStart)

if resp.status_code == 200:
    ret = resp.json()

    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(ret)
else:
    print(resp.text)


