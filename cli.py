from tx.parallex import run
import pprint
ret = run(3, "age.yaml", "data.yaml")
pp = pprint.PrettyPrinter(indent=4)
pp.pprint({k: v.value for k,v in ret.items()})

