from tx.parallex import run_python
import pprint
ret = run_python(3, "spec.py", "data.yaml")
pp = pprint.PrettyPrinter(indent=4)
pp.pprint({k: v.value for k,v in ret.items()})

