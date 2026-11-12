-- Layer 2: STAGING — cleaned, harmonised to one hourly grid (UTC, interval START), categories mapped.
-- Rebuilt from raw on every run.

-- 1) Map Energy-Charts production types to a small set of categories --------------------------
DROP TABLE IF EXISTS staging.production_type_map;
CREATE TABLE staging.production_type_map (production_type text PRIMARY KEY, category text NOT NULL);
INSERT INTO staging.production_type_map VALUES
    ('Solar', 'solar'),
    ('Wind onshore', 'wind'),
    ('Hydro Run-of-River', 'hydro'),
    ('Hydro water reservoir', 'hydro'),
    ('Hydro pumped storage', 'hydro'),
    ('Nuclear', 'nuclear'),
    ('Fossil brown coal / lignite', 'coal'),
    ('Fossil hard coal', 'coal'),
    ('Fossil gas', 'gas'),
    ('Fossil oil', 'other'),
    ('Biomass', 'other'),
    ('Geothermal', 'other'),
    ('Other renewables', 'other'),
    ('Waste', 'other'),
    ('Others', 'other'),
    ('Battery', 'other'),
    ('Load', 'load'),
    ('Cross border electricity trading', 'net_import');
-- Deliberately not mapped (excluded): '* consumption', 'Residual load', 'Renewable share of *'.

-- 2) Generation: 15-min / hourly MW -> hourly MWh (mean MW over the hour = MWh in that hour) ----
DROP TABLE IF EXISTS staging.power_hourly;
CREATE TABLE staging.power_hourly AS
SELECT p.country_code,
       date_trunc('hour', p.ts_utc)  AS hour_utc,
       m.category,
       -- total of all rows / number of intervals = sum of each type's hourly mean
       SUM(p.mw) / COUNT(DISTINCT p.ts_utc)::double precision AS mwh,
       COUNT(DISTINCT p.ts_utc)      AS n_intervals
FROM raw.public_power p
JOIN staging.production_type_map m USING (production_type)
GROUP BY 1, 2, 3;
ALTER TABLE staging.power_hourly ADD PRIMARY KEY (country_code, category, hour_utc);

-- 3) Prices: hourly mean + how many sub-hour intervals were negative ---------------------------
DROP TABLE IF EXISTS staging.price_hourly;
CREATE TABLE staging.price_hourly AS
SELECT bzn,
       date_trunc('hour', ts_utc)                         AS hour_utc,
       AVG(price_eur_mwh)                                 AS price_eur_mwh,
       MIN(price_eur_mwh)                                 AS min_price_eur_mwh,
       COUNT(*)                                           AS n_intervals,
       COUNT(*) FILTER (WHERE price_eur_mwh < 0)          AS n_negative_intervals
FROM raw.price
GROUP BY 1, 2;
ALTER TABLE staging.price_hourly ADD PRIMARY KEY (bzn, hour_utc);

-- 4) Weather: Open-Meteo stamps each value at the END of its hour -> shift to interval start ---
DROP TABLE IF EXISTS staging.weather_hourly;
CREATE TABLE staging.weather_hourly AS
SELECT w.location,
       l.country_code,
       w.ts_utc - interval '1 hour' AS hour_utc,
       w.shortwave_radiation        AS ghi_w_m2,
       w.direct_radiation           AS dni_horiz_w_m2,
       w.diffuse_radiation          AS dhi_w_m2,
       w.cloud_cover                AS cloud_cover_pct,
       w.temperature_2m             AS temp_c
FROM raw.weather_hourly w
JOIN raw.location l USING (location);
ALTER TABLE staging.weather_hourly ADD PRIMARY KEY (location, hour_utc);

-- 5) Country-average weather (simple mean of that country's locations) ------------------------
DROP TABLE IF EXISTS staging.weather_country_hourly;
CREATE TABLE staging.weather_country_hourly AS
SELECT country_code, hour_utc,
       AVG(ghi_w_m2)        AS ghi_w_m2,
       AVG(dni_horiz_w_m2)  AS direct_w_m2,
       AVG(dhi_w_m2)        AS diffuse_w_m2,
       AVG(cloud_cover_pct) AS cloud_cover_pct,
       AVG(temp_c)          AS temp_c
FROM staging.weather_hourly
GROUP BY 1, 2;
ALTER TABLE staging.weather_country_hourly ADD PRIMARY KEY (country_code, hour_utc);

ANALYZE staging.power_hourly, staging.price_hourly, staging.weather_hourly, staging.weather_country_hourly;
