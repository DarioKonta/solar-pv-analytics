-- Q1a. Where in Serbia is rooftop PV most productive? (PVGIS long-term average, optimal angles, 1 kWp)
SELECT location,
       round(yield_kwh_per_kwp::numeric)                                   AS yield_kwh_per_kwp,
       tilt_deg                                                            AS optimal_tilt_deg,
       azimuth_deg                                                         AS optimal_azimuth_deg,
       round(year_to_year_sd_kwh::numeric)                                 AS year_to_year_sd_kwh,
       round((100 * (yield_kwh_per_kwp / max(yield_kwh_per_kwp) OVER () - 1))::numeric, 1) AS pct_vs_best,
       rank() OVER (ORDER BY yield_kwh_per_kwp DESC)                       AS rank
FROM mart.fact_pv_yield
WHERE country_code = 'rs' AND scenario = 'optimal'
ORDER BY rank;
