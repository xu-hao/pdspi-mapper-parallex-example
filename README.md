[![Build Status](https://travis-ci.com/RENCI/pdspi-mapper-parallex-example.svg?branch=master)](https://travis-ci.com/RENCI/pdspi-mapper-parallex-example)

# pdspi-mapper-parallex-example

require python 3.8 or higher

```
pip install -r requirements.txt
```

update `data.yml`

update `spec.py`

update `clinical_feature.py` with functions you’ll need for the spec

use `query_records_closest_before` to get records closest before date; 

use `query_records_closest_after` to get records closest after date; 

use `query_records_closest` to get records closest to date; 

`query_records_interval` can take a start/end time

look at extant function for examples you can reuse

if you want to run individually:
```
fish: env PYTHONPATH=tx-utils/src python cli.py spec.py data.yaml 3
bash: PYTHONPATH=tx-utils/src python cli.py spec.py data.yaml 3
```
```
fish: env PYTHONPATH="tx-utils/src:." pytest
bash: PYTHONPATH="tx-utils/src:." pytest
```

# cli tools

To use the cli tools, put your spec under `config`. Put your custom python functions under a sub dir in that dir. There is a `cli.py`. You can run it as

```
python cli.py <file containing your spec> <sub dir containing custom python functions> <a yaml file containing additional data> <number of threads> <a yaml file containing resource types> <a yaml file contains pids> <timestamp> <fhir plugin port> <mapper plugin port>
```

For example

```
python cli.py spec.py modules data.yaml 4 ../resourceTypes.yaml ../patientIds.yaml "2000-01-01T00:00:00Z" 8080 8081
```

In this example, you would put your spec in `config/spec.py`. Anything under the `config/modules` dir can be imported in your spec. For example, if you have `config/modules/clivar.py`, you can reference functions in that module in various way, for example `from clivar import *`. Your spec should output the format that the api specifies. See `config/spec4.py`'s `return` statement for example.