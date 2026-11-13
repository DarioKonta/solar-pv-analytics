-- Q3b. Serbia: estimated solar by month (GWh) with the low/high band. Complete months only.
SELECT date_trunc('month', date_local)::date      AS month,
       round((sum(solar_mwh) / 1e3)::numeric, 1)     AS solar_gwh_est,
       round((sum(solar_mwh_low) / 1e3)::numeric, 1) AS solar_gwh_low,
       round((sum(solar_mwh_high) / 1e3)::numeric, 1) AS solar_gwh_high
FROM mart.v_solar_hourly
WHERE country_code = 'rs' AND date_local >= DATE '2023-01-01'
  AND date_local < date_trunc('month', current_date)
GROUP BY 1 ORDER BY 1;
