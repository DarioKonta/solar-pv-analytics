-- Q2a. Installed solar capacity per country, with year-on-year growth.
SELECT c.country_name, f.country_code, f.year,
       f.gw,
       f.gw_added,
       round((100 * (f.gw / NULLIF(LAG(f.gw) OVER w, 0) - 1))::numeric) AS growth_pct
FROM mart.fact_capacity_yearly f
JOIN mart.dim_country c USING (country_code)
WHERE f.production_type = 'Solar AC' AND f.year BETWEEN 2019 AND 2025
WINDOW w AS (PARTITION BY f.country_code ORDER BY f.year)
ORDER BY f.country_code, f.year;
