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
