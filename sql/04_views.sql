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

-- ================================================================================================
-- Power BI views: flat, analysis-ready tables. Power BI imports ONLY the objects prefixed pbi_ / dim_.
-- ================================================================================================

-- Hourly fact for all countries; Serbian solar filled from the estimate.
CREATE OR REPLACE VIEW mart.pbi_hourly AS
SELECT f.country_code,
       f.hour_utc,
       f.date_local,
       f.hour_local,
       COALESCE(f.solar_mwh, e.solar_mwh_est)                  AS solar_mwh,
       e.solar_mwh_low,
       e.solar_mwh_high,
       (f.solar_mwh IS NULL AND e.solar_mwh_est IS NOT NULL)    AS is_estimated,
       f.wind_mwh, f.hydro_mwh, f.nuclear_mwh, f.coal_mwh, f.gas_mwh, f.other_mwh,
       f.load_mwh, f.net_import_mwh,
       f.price_eur_mwh, f.min_price_eur_mwh, f.has_negative_price, f.n_negative_intervals,
       f.ghi_w_m2, f.cloud_cover_pct, f.temp_c,
       -- Bulgaria's published "solar" after sunset (data-quality flag, see docs/data_dictionary.md)
       (f.ghi_w_m2 = 0 AND COALESCE(f.solar_mwh, 0) > 0)       AS solar_after_dark
FROM mart.fact_country_hourly f
LEFT JOIN mart.fact_solar_estimate_hourly e USING (country_code, hour_utc);

-- Installed solar capacity only.
CREATE OR REPLACE VIEW mart.pbi_capacity AS
SELECT country_code, year, gw AS solar_gw, gw_added AS solar_gw_added
FROM mart.fact_capacity_yearly
WHERE production_type = 'Solar AC' AND year >= 2019;

-- PV yield per location and orientation (Serbian cities have the full tilt x direction grid).
CREATE OR REPLACE VIEW mart.pbi_pv_yield AS
SELECT y.location, y.country_code, l.lat, l.lon, y.scenario,
       CASE y.orientation WHEN 'south' THEN 'South' WHEN 'south_east' THEN 'South-east'
                          WHEN 'south_west' THEN 'South-west' WHEN 'east' THEN 'East'
                          WHEN 'west' THEN 'West' ELSE 'Optimal' END AS orientation,
       y.tilt_deg, y.azimuth_deg, y.yield_kwh_per_kwp
FROM mart.fact_pv_yield y JOIN mart.dim_location l USING (location);

-- Daily weather vs normalised output (Hungary, out-of-fold) for the weather page.
CREATE OR REPLACE VIEW mart.pbi_weather_daily AS
SELECT v.country_code,
       f.date_local,
       sum(v.actual_norm)          AS output_norm,
       sum(v.model_norm)           AS model_norm,
       avg(f.ghi_w_m2) * 24 / 1000 AS ghi_kwh_m2,
       avg(f.cloud_cover_pct)      AS cloud_cover_pct,
       max(f.temp_c)               AS max_temp_c
FROM mart.estimate_validation_hourly v
JOIN mart.fact_country_hourly f USING (country_code, hour_utc)
GROUP BY v.country_code, f.date_local
HAVING count(*) >= 23;

-- Model validation metrics (long format).
CREATE OR REPLACE VIEW mart.pbi_estimate_validation AS
SELECT country_code,
       CASE method WHEN 'model' THEN 'Model' ELSE 'Baseline (irradiance only)' END AS method,
       CASE metric WHEN 'hourly_r2' THEN 'Hourly R²' WHEN 'daily_nmae_pct' THEN 'Daily error (nMAE %)'
                   WHEN 'monthly_wape_pct' THEN 'Monthly error (WAPE %)' ELSE 'Total bias %' END AS metric,
       value
FROM mart.estimate_validation;
