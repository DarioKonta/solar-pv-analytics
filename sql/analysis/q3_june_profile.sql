-- Q3a. Average hourly solar share of demand in June, per country (Serbia = estimate). Local time.
SELECT country_code,
       extract(year FROM date_local)::int AS year,
       hour_local,
       round((100 * avg(solar_mwh / NULLIF(load_mwh, 0)))::numeric, 2) AS solar_pct_of_load
FROM mart.v_solar_hourly
WHERE extract(month FROM date_local) = 6
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
