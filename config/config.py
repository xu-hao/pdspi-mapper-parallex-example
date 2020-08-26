return {
    "pluginDependencies": ["pdspi-fhir-example"],
    "title": "tx-parallex variable mapper",
    "pluginType": "m",
    "pluginTypeTitle": "Mapping",
    "pluginSelectors": [],
    "settingsDefaults": {
        "pluginSelectors": [],
        "patientVariables": [
            {
                "id": "LOINC:2160-0",
                "legalValues": {
                    "type": "number"
                },
                "title": "Serum creatinine"
            },
            {
                "id": "LOINC:82810-3",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Pregnancy"
            },
            {
                "id": "HP:0001892",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Bleeding"
            },
            {
                "id": "HP:0000077",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Kidney dysfunction"
            },
            {
                "id": "LOINC:45701-0",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Fever"
            },
            {
                "id": "LOINC:LP212175-6",
                "legalValues": {
                    "type": "string"
                },
                "title": "Date of fever onset"
            },
            {
                "id": "LOINC:64145-6",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Cough"
            },
            {
                "id": "LOINC:85932-2",
                "legalValues": {
                    "type": "string"
                },
                "title": "Date of cough onset"
            },
            {
                "id": "LOINC:54564-0",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Shortness of breath"
            },
            {
                "id": "LOINC:LP172921-1",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Cardiovascular disease"
            },
            {
                "id": "LOINC:54542-6",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Pulmonary disease"
            },
            {
                "id": "LOINC:LP128504-0",
                "legalValues": {
                    "type": "boolean"
                },
                "title": "Autoimmune disease"
            },
            {
                "id": "LOINC:LP21258-6",
                "legalValues": {
                    "type": "number"
                },
                "title": "Oxygen saturation"
            },
            {
                "id": "LOINC:30525-0",
                "legalValues": {
                    "type": "integer"
                },
                "title": "Age"
            },
            {
                "id": "LOINC:54134-2",
                "legalValues": {
                    "type": "string"
                },
                "title": "Race"
            },
            {
                "id": "LOINC:54120-1",
                "legalValues": {
                    "type": "string"
                },
                "title": "Ethnicity"
            },
            {
                "id": "LOINC:21840-4",
                "legalValues": {
                    "type": "string"
                },
                "title": "Sex"
            },
            {
                "id": "LOINC:8302-2",
                "legalValues": {
                    "type": "number"
                },
                "title": "Height"
            },
            {
                "id": "LOINC:29463-7",
                "legalValues": {
                    "type": "number"
                },
                "title": "Weight"
            },
            {
                "id": "LOINC:56799-0",
                "legalValues": {
                    "type": "string"
                },
                "title": "Address"
            },
            {
                "id": "LOINC:39156-5",
                "legalValues": {
                    "type": "number"
                },
                "title": "BMI"
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
