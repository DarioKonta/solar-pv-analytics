-- Data-quality check: solar reported while irradiance is zero (sun below the horizon).
-- Should be ~0. Bulgaria from 2025 is not -> likely storage co-located with solar parks reported as "Solar".
SELECT country_code,
       extract(year FROM date_local)::int                                           AS year,
       round((sum(solar_mwh) FILTER (WHERE ghi_w_m2 = 0) / 1e3)::numeric)            AS after_dark_gwh,
       round((100 * sum(solar_mwh) FILTER (WHERE ghi_w_m2 = 0) / sum(solar_mwh))::numeric, 1) AS after_dark_pct,
       round(max(solar_mwh) FILTER (WHERE ghi_w_m2 = 0)::numeric)                     AS max_after_dark_mw
FROM mart.fact_country_hourly
WHERE solar_mwh IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;
