-- Q2b. Solar share of electricity demand per country and year (Serbia = estimate).
SELECT country_code,
       extract(year FROM date_local)::int                             AS year,
       round((sum(solar_mwh) / 1e3)::numeric)                          AS solar_gwh,
       round((sum(load_mwh) / 1e6)::numeric, 1)                        AS load_twh,
       round((100 * sum(solar_mwh) / NULLIF(sum(load_mwh), 0))::numeric, 2) AS solar_pct_of_load,
       bool_or(is_estimated)                                           AS is_estimated
FROM mart.v_solar_hourly
GROUP BY 1, 2
ORDER BY 1, 2;
