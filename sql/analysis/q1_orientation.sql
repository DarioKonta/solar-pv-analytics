-- Q1b. How much does panel orientation matter? Yield by tilt and direction, as % of the city's optimum.
WITH opt AS (
    SELECT location, yield_kwh_per_kwp AS opt_yield
    FROM mart.fact_pv_yield WHERE scenario = 'optimal' AND country_code = 'rs'
)
SELECT y.location, y.orientation, y.tilt_deg,
       round(y.yield_kwh_per_kwp::numeric)                       AS yield_kwh_per_kwp,
       round((100 * y.yield_kwh_per_kwp / o.opt_yield)::numeric, 1) AS pct_of_optimum
FROM mart.fact_pv_yield y
JOIN opt o USING (location)
WHERE y.scenario <> 'optimal'
ORDER BY y.location, y.orientation, y.tilt_deg;
