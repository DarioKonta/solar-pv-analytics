-- Layer 1: RAW — data exactly as delivered by the APIs (parsed into rows, nothing cleaned).
-- Re-created on every full load, so this script is safe to run repeatedly.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS raw.country (
    country_code  text PRIMARY KEY,           -- Energy-Charts code, e.g. 'rs'
    bzn           text NOT NULL,              -- price bidding zone, e.g. 'RS'
    country_name  text NOT NULL,
    is_focus      boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS raw.location (
    location      text PRIMARY KEY,
    country_code  text NOT NULL REFERENCES raw.country,
    lat           double precision NOT NULL,
    lon           double precision NOT NULL
);

-- Generation per production type + load, native resolution (15 min or 60 min), MW average power
CREATE TABLE IF NOT EXISTS raw.public_power (
    ts_utc           timestamptz NOT NULL,
    country_code     text NOT NULL,
    production_type  text NOT NULL,
    mw               double precision,
    PRIMARY KEY (country_code, production_type, ts_utc)
);

-- Day-ahead prices, native resolution, EUR/MWh
CREATE TABLE IF NOT EXISTS raw.price (
    ts_utc         timestamptz NOT NULL,
    bzn            text NOT NULL,
    price_eur_mwh  double precision,
    PRIMARY KEY (bzn, ts_utc)
);

-- Installed capacity at year end, GW
CREATE TABLE IF NOT EXISTS raw.installed_power (
    year             int NOT NULL,
    country_code     text NOT NULL,
    production_type  text NOT NULL,
    gw               double precision,
    PRIMARY KEY (country_code, production_type, year)
);

-- PVGIS long-term annual yield per location and panel orientation
CREATE TABLE IF NOT EXISTS raw.pvgis_yield (
    location             text NOT NULL,
    scenario             text NOT NULL,       -- 'optimal' or 'tilt30_south' etc.
    tilt_deg             double precision,
    azimuth_deg          double precision,    -- 0 = south, -90 = east, 90 = west
    yield_kwh_per_kwp    double precision,
    irradiation_kwh_m2   double precision,
    year_to_year_sd_kwh  double precision,
    total_loss_pct       double precision,
    PRIMARY KEY (location, scenario)
);

CREATE TABLE IF NOT EXISTS raw.pvgis_monthly (
    location            text NOT NULL,
    month               int NOT NULL,
    yield_kwh_per_kwp   double precision,
    irradiation_kwh_m2  double precision,
    PRIMARY KEY (location, month)
);

-- Open-Meteo hourly weather. NOTE: radiation values are the mean of the PRECEDING hour.
CREATE TABLE IF NOT EXISTS raw.weather_hourly (
    ts_utc               timestamptz NOT NULL,
    location             text NOT NULL,
    shortwave_radiation  double precision,   -- W/m2, global horizontal irradiance
    direct_radiation     double precision,
    diffuse_radiation    double precision,
    cloud_cover          double precision,   -- %
    temperature_2m       double precision,   -- degC
    PRIMARY KEY (location, ts_utc)
);
