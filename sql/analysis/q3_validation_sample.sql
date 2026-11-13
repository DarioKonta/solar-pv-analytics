-- Q3c. Validation sample: Hungary held out, actual vs predicted normalised output, two weeks in June 2025.
SELECT v.hour_utc AT TIME ZONE 'Europe/Belgrade' AS ts_local,
       v.actual_norm, v.model_norm, v.baseline_norm
FROM mart.estimate_validation_hourly v
WHERE v.country_code = 'hu'
  AND v.hour_utc >= TIMESTAMPTZ '2025-06-09 00:00 Europe/Belgrade'
  AND v.hour_utc <  TIMESTAMPTZ '2025-06-23 00:00 Europe/Belgrade'
ORDER BY 1;
