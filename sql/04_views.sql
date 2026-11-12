-- Views built on top of the marts AND the Serbia solar estimate (run after src.estimate.serbia_solar).

-- Solar per country per hour: published value where it exists, estimate for Serbia.
CREATE OR REPLACE VIEW mart.v_solar_hourly AS
SELECT f.country_code,
       f.hour_utc,
       f.date_local,
       f.hour_local,
       COALESCE(f.solar_mwh, e.solar_mwh_est) AS solar_mwh,
       e.solar_mwh_low,
       e.solar_mwh_high,
       (f.solar_mwh IS NULL AND e.solar_mwh_est IS NOT NULL) AS is_estimated,
       f.load_mwh,
       f.price_eur_mwh,
       f.has_negative_price
FROM mart.fact_country_hourly f
LEFT JOIN mart.fact_solar_estimate_hourly e USING (country_code, hour_utc);

-- Validation summary of the estimate (mean over the four held-out countries + per country).
CREATE OR REPLACE VIEW mart.v_estimate_validation AS
SELECT country_code, method, metric, round(value::numeric, 3) AS value
FROM mart.estimate_validation
UNION ALL
SELECT 'mean', method, metric, round(avg(value)::numeric, 3)
FROM mart.estimate_validation
GROUP BY method, metric;
