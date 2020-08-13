from pdsphenotypemapping.clinical_feature import *
from tx.dateutils.utils import strtodate
from clinical import *
study_start = "2010-01-01T00:00:00Z"
study_end = "2011-01-01T00:00:00Z"

for pid in ["MickeyMouse", "MickeyMouse"]:
  with Seq:
    med_request = get_medication_request(patient_id=pid, fhir=data)
    start = strtodate(study_start)
    end = strtodate(study_end)
  X = big_compute1(start, end, med_request)
  Y = big_compute2(start, end, med_request)
  Z = big_compute3(start, end, med_request)
  with Seq:
    A = small_compute1(X)
  XX = big_compute(A)
  X2 = small_compute(Y)
  Y2 = small_compute(X2)
  with Seq:
    B = small_compute2(A)
    C = small_compute3(Y2)
  yield {
    "a": A, 
    "b": B, 
    "c": C, 
    "x": X,
    "y": Y,
    "z": Z
  }
