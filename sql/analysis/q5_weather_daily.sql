-- Q5a. Weather vs solar output, Hungary, daily (local days): normalised output vs irradiance and cloud cover.
SELECT f.date_local                             AS day,
       sum(v.actual_norm)                       AS output_norm,
       avg(f.ghi_w_m2) * 24 / 1000              AS ghi_kwh_m2,
       avg(f.cloud_cover_pct)                   AS cloud_cover_pct,
       max(f.temp_c)                            AS max_temp_c,
       d.season
FROM mart.estimate_validation_hourly v
JOIN mart.fact_country_hourly f USING (country_code, hour_utc)
JOIN mart.dim_date d ON d.date_local = f.date_local
WHERE v.country_code = 'hu'
GROUP BY f.date_local, d.season
HAVING count(*) >= 23                           -- complete days only
ORDER BY 1;
