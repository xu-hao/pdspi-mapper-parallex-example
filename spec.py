height_unit = "m"
weight_unit = "kg"
bmi_unit = "kg/m^2"
x = 10
y = 10
study_start = "2010-01-01T00:00:00Z"
study_end = "2011-01-01T00:00:00Z"
for pid in pids:
    medication_request = pdsphenotypemapping.clinical_feature.get_medication_request(patient_id=pid, fhir=fhir)
    start = tx.dateutils.utils.strtodate(study_start)
    end = tx.dateutils.utils.strtodate(study_end)
    intervention = pdsphenotypemapping.clinical_feature.DOAC2(start=start, end=end, records=medication_request)
    date0 = pdsphenotypemapping.clinical_feature.get_first_date(intervention)
    xdelta = dateutil.relativedelta.relativedelta(months=x)
    ydelta = dateutil.relativedelta.relativedelta(months=y)
    window_start = data.sub(date0, xdelta)
    window_end = data.add(date0, ydelta)
    condition = pdsphenotypemapping.clinical_feature.get_condition(patient_id=pid, fhir=fhir)
    observation = pdsphenotypemapping.clinical_feature.get_observation(patient_id=pid, fhir=fhir)
    height_before = pdsphenotypemapping.clinical_feature.height2(unit=height_unit, start=window_start, end=date0, records=observation)
    weight_before = pdsphenotypemapping.clinical_feature.weight2(unit=weight_unit, start=window_start, end=date0, records=observation)
    height_before_average = pdsphenotypemapping.clinical_feature.average(start=window_start, end=date0, values=height_before)
    weight_before_average = pdsphenotypemapping.clinical_feature.average(start=window_start, end=date0, values=weight_before)
    bmi_before = pdsphenotypemapping.clinical_feature.bmi2(height=height_before_average, weight=weight_before_average, unit=bmi_unit, start=window_start, end=date0, records=observation)
    adverse_event = pdsphenotypemapping.clinical_feature.bleeding2(start=date0, end=window_end, records=condition)
    adverse_event_date0 = pdsphenotypemapping.clinical_feature.get_first_date(adverse_event)
    end2 = data.coalesce(adverse_event_date0, window_end)
    height_after = pdsphenotypemapping.clinical_feature.height2(unit=height_unit, start=date0, end=end2, records=observation)
    weight_after = pdsphenotypemapping.clinical_feature.weight2(unit=weight_unit, start=date0, end=end2, records=observation)
    height_after_average = pdsphenotypemapping.clinical_feature.average(start=date0, end=end2, values=height_before)
    weight_after_average = pdsphenotypemapping.clinical_feature.average(start=date0, end=end2, values=weight_before)
    bmi_after = pdsphenotypemapping.clinical_feature.bmi2(height=height_after_average, weight=weight_after_average, unit=bmi_unit, start=date0, end=end2, records=observation)
    outcome = data.ne(adverse_event_date0, None)
    return {
      "outcome": outcome,
      "bmi_before": bmi_before,
      "bmi_after": bmi_after
    }
