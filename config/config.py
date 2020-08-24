return {
    "title": "tx-parallex variable mapper",
    "pluginType": "m",
    "pluginTypeTitle": "Mapping",
    "pluginSelectors": [],
    "settingsDefaults": {
        "pluginSelectors": [],
        "patientVariables": [
            {
                "id": "bmi_before",
                "title": "bmi before",
                "legalValues": {"type": "number"}
            }, {
                "id": "bmi_after",
                "title": "bmi after",
                "legalValues": {"type": "number"}
            }, {
                "id": "outcome",
                "title": "outcome",
                "legalValues": {"type": "boolean"}
            }
        ],
        "modelParameters": [
            {
                "id": "nthreads",
                "title": "number of threads",
                "legalValues": {"type": "integer"},
                "parameterValue": {
                    "value": 3
                }
            }, {
                "id": "level",
                "title": "nested for paralleization level",
                "legalValues": {"type": "integer"},
                "parameterValue": {
                    "value": 0
                }
            }, {
                "id": "specName",
                "title": "spec name",
                "legalValues": {"type": "string"},
                "parameterValue": {
                    "value": "spec.py"
                }
            }, {
                "id": "libraryPath",
                "title": "Python load module path",
                "legalValues": {"type": "string"},
                "parameterValue": {
                    "value": None
                }
            }
        ]
    }
}
