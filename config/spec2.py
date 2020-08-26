from pdsphenotypemapping.clinical_feature import *
from tx.dateutils.utils import strtodate
from dateutil.relativedelta import relativedelta
height_unit = "m"
weight_unit = "kg"
bmi_unit = "kg/m^2"
x = 10
y = 10
study_start = "2010-01-01T00:00:00Z"
study_end = "2011-01-01T00:00:00Z"
for pid in patientIds:
    medication_request = get_medication_request(patient_id=pid, fhir=data)
    start = strtodate(study_start)
    end = strtodate(study_end)
    intervention = DOAC2(start=start, end=end, records=medication_request)
    if intervention == []:
        yield {
            "outcome": False
        }
    else:
        intervention_date_first = strtodate(get_first_date(intervention))
        xdelta = relativedelta(months=x)
        ydelta = relativedelta(months=y)
        window_start = intervention_date_first - xdelta
        window_end = intervention_date_first + ydelta
        condition = get_condition(patient_id=pid, fhir=data)
        observation = get_observation(patient_id=pid, fhir=data)
        height_before = height2(unit=height_unit, start=window_start, end=intervention_date_first, records=observation)
        weight_before = weight2(unit=weight_unit, start=window_start, end=intervention_date_first, records=observation)
        height_before_average = average(start=window_start, end=intervention_date_first, values=height_before)
        weight_before_average = average(start=window_start, end=intervention_date_first, values=weight_before)
        bmi_before = bmi2(height=height_before_average, weight=weight_before_average, unit=bmi_unit, start=window_start, end=intervention_date_first, records=observation)
        adverse_event = bleeding2(start=intervention_date_first, end=window_end, unit=None, records=condition)
        if adverse_event == []:
            yield {
                "outcome": False
            }
        else:
            adverse_event_first = strtodate(get_first_date(adverse_event))
            end2 = data.coalesce(adverse_event_first, window_end)
            height_after = height2(unit=height_unit, start=intervention_date_first, end=end2, records=observation)
            weight_after = weight2(unit=weight_unit, start=intervention_date_first, end=end2, records=observation)
            height_after_average = average(start=intervention_date_first, end=end2, values=height_before)
            weight_after_average = average(start=intervention_date_first, end=end2, values=weight_before)
            bmi_after = bmi2(height=height_after_average, weight=weight_after_average, unit=bmi_unit, start=intervention_date_first, end=end2, records=observation)
            outcome = adverse_event_first != None
            yield {
                "outcome": outcome,
            }
