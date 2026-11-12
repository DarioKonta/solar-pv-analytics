-- Layer 3: MART — analysis-ready star schema. Power BI reads only this schema.

-- Dimensions -----------------------------------------------------------------------------------
DROP TABLE IF EXISTS mart.dim_country CASCADE;
CREATE TABLE mart.dim_country AS
SELECT country_code, bzn, country_name, is_focus FROM raw.country;
ALTER TABLE mart.dim_country ADD PRIMARY KEY (country_code);

DROP TABLE IF EXISTS mart.dim_location CASCADE;
CREATE TABLE mart.dim_location AS
SELECT l.location, l.country_code, c.country_name, l.lat, l.lon
FROM raw.location l JOIN raw.country c USING (country_code);
ALTER TABLE mart.dim_location ADD PRIMARY KEY (location);

DROP TABLE IF EXISTS mart.dim_date CASCADE;
CREATE TABLE mart.dim_date AS
SELECT d::date                                   AS date_local,
       extract(year FROM d)::int                 AS year,
       extract(quarter FROM d)::int              AS quarter,
       extract(month FROM d)::int                AS month,
       to_char(d, 'Mon')                         AS month_name,
       extract(isodow FROM d)::int               AS iso_weekday,
       to_char(d, 'Dy')                          AS weekday_name,
       extract(isodow FROM d) >= 6               AS is_weekend,
       CASE WHEN extract(month FROM d) IN (12, 1, 2) THEN 'Winter'
            WHEN extract(month FROM d) IN (3, 4, 5)  THEN 'Spring'
            WHEN extract(month FROM d) IN (6, 7, 8)  THEN 'Summer'
            ELSE 'Autumn' END                    AS season
FROM generate_series(DATE '2020-01-01', current_date, interval '1 day') d;
ALTER TABLE mart.dim_date ADD PRIMARY KEY (date_local);

-- Main fact: one row per country per hour ------------------------------------------------------
DROP TABLE IF EXISTS mart.fact_country_hourly CASCADE;
CREATE TABLE mart.fact_country_hourly AS
WITH power_wide AS (
    SELECT country_code, hour_utc,
           SUM(mwh) FILTER (WHERE category = 'solar')      AS solar_mwh,
           SUM(mwh) FILTER (WHERE category = 'wind')       AS wind_mwh,
           SUM(mwh) FILTER (WHERE category = 'hydro')      AS hydro_mwh,
           SUM(mwh) FILTER (WHERE category = 'nuclear')    AS nuclear_mwh,
           SUM(mwh) FILTER (WHERE category = 'coal')       AS coal_mwh,
           SUM(mwh) FILTER (WHERE category = 'gas')        AS gas_mwh,
           SUM(mwh) FILTER (WHERE category = 'other')      AS other_mwh,
           SUM(mwh) FILTER (WHERE category = 'load')       AS load_mwh,
           SUM(mwh) FILTER (WHERE category = 'net_import') AS net_import_mwh
    FROM staging.power_hourly
    GROUP BY 1, 2
)
SELECT c.country_code,
       pw.hour_utc,
       (pw.hour_utc AT TIME ZONE 'Europe/Belgrade')::date              AS date_local,
       extract(hour FROM pw.hour_utc AT TIME ZONE 'Europe/Belgrade')::int AS hour_local,
       pw.solar_mwh, pw.wind_mwh, pw.hydro_mwh, pw.nuclear_mwh, pw.coal_mwh,
       pw.gas_mwh, pw.other_mwh, pw.load_mwh, pw.net_import_mwh,
       pr.price_eur_mwh,
       pr.min_price_eur_mwh,
       pr.n_negative_intervals,
       pr.n_intervals                                                  AS n_price_intervals,
       (pr.min_price_eur_mwh < 0)                                      AS has_negative_price,
       w.ghi_w_m2, w.cloud_cover_pct, w.temp_c
FROM power_wide pw
JOIN raw.country c USING (country_code)
LEFT JOIN staging.price_hourly pr ON pr.bzn = c.bzn AND pr.hour_utc = pw.hour_utc
LEFT JOIN staging.weather_country_hourly w ON w.country_code = pw.country_code AND w.hour_utc = pw.hour_utc
WHERE pw.hour_utc >= TIMESTAMPTZ '2020-01-01 00:00 Europe/Belgrade';
ALTER TABLE mart.fact_country_hourly ADD PRIMARY KEY (country_code, hour_utc);
CREATE INDEX ON mart.fact_country_hourly (date_local);

-- Installed capacity (yearly) ------------------------------------------------------------------
DROP TABLE IF EXISTS mart.fact_capacity_yearly CASCADE;
CREATE TABLE mart.fact_capacity_yearly AS
SELECT i.country_code, i.year, i.production_type, i.gw,
       i.gw - LAG(i.gw) OVER (PARTITION BY i.country_code, i.production_type ORDER BY i.year) AS gw_added
FROM raw.installed_power i
WHERE i.year >= 2015 AND i.gw IS NOT NULL;

-- PV yield per Serbian city & orientation (PVGIS long-term average) ----------------------------
DROP TABLE IF EXISTS mart.fact_pv_yield CASCADE;
CREATE TABLE mart.fact_pv_yield AS
SELECT y.location, l.country_code, y.scenario,
       CASE WHEN y.scenario = 'optimal' THEN 'optimal' ELSE split_part(y.scenario, '_', 2)
            || COALESCE('_' || NULLIF(split_part(y.scenario, '_', 3), ''), '') END AS orientation,
       y.tilt_deg, y.azimuth_deg, y.yield_kwh_per_kwp, y.irradiation_kwh_m2, y.year_to_year_sd_kwh,
       y.total_loss_pct
FROM raw.pvgis_yield y JOIN raw.location l USING (location);

DROP TABLE IF EXISTS mart.fact_pv_yield_monthly CASCADE;
CREATE TABLE mart.fact_pv_yield_monthly AS
SELECT m.location, l.country_code, m.month, m.yield_kwh_per_kwp, m.irradiation_kwh_m2
FROM raw.pvgis_monthly m JOIN raw.location l USING (location);

ANALYZE mart.fact_country_hourly;
