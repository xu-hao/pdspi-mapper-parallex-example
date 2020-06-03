from tx.parallex import run_python
import pprint
import sys

spec, data, nthreads = sys.argv[1:]
nthreadsint = int(nthreads)
ret = run_python(nthreadsint, spec, data)
pp = pprint.PrettyPrinter(indent=4)
pp.pprint({k: v.value for k,v in ret.items()})

