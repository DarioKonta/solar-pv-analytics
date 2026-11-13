"""Estimate Serbia's hourly solar generation (not published by the grid operator).

Method
------
1. SHAPE — learn how weather drives *normalised* solar output on the neighbours that do publish it
   (HU, RO, BG, HR). Output is normalised by each country's own rolling peak, which removes the effect of
   unreliable year-end capacity figures. A gradient-boosting model maps weather + sun position to
   normalised output. Validation: leave-one-country-out (train on 3 countries, predict the 4th),
   compared with a simple baseline (normalised irradiance).
2. LEVEL — scale Serbia's predicted shape to energy:
       solar_mwh = shape * k * installed_capacity_mw
   k is chosen so that one year of output per kW equals
       PVGIS long-term yield for Serbia  x  realisation ratio,
   where the realisation ratio = (actual kWh/kW) / (PVGIS kWh/kW), observed on the neighbours.
   Its 25th/75th percentiles give the low/high band.

Usage:  python -m src.estimate.serbia_solar
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
from sqlalchemy import text

from src.config import ROOT
from src.db import engine, run_sql_file

log = logging.getLogger(__name__)

NEIGHBOURS = ["hu", "ro", "bg", "hr"]
TRAIN_END_YEAR = 2025          # last year with reported capacity
# From 2025 Bulgaria's published "Solar" series contains output after sunset (up to ~1.2 GW at 20:00 in June 2026),
# most likely co-located batteries reported as solar. Those years would teach the model wrong evening behaviour.
TRAIN_EXCLUDE_FROM = {"bg": "2025-01-01"}
FEATURES = ["ghi_w_m2", "direct_w_m2", "diffuse_w_m2", "temp_c", "cloud_cover_pct",
            "hour_sin", "hour_cos", "doy_sin", "doy_cos", "ghi_x_doy_cos"]


# ---------------------------------------------------------------- data

def load_hourly() -> pd.DataFrame:
    q = """
        SELECT country_code, hour_utc, date_local, hour_local, solar_mwh,
               ghi_w_m2, direct_w_m2, diffuse_w_m2, temp_c, cloud_cover_pct
        FROM mart.fact_country_hourly
        WHERE ghi_w_m2 IS NOT NULL
    """
    df = pd.read_sql(q, engine(), parse_dates=["hour_utc", "date_local"])
    doy = df["date_local"].dt.day_of_year
    df["hour_sin"] = np.sin(2 * np.pi * df["hour_local"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour_local"] / 24)
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["ghi_x_doy_cos"] = df["ghi_w_m2"] * df["doy_cos"]   # tilted panels gain more in winter
    return df


def load_capacity() -> pd.DataFrame:
    q = "SELECT country_code, year, gw FROM raw.installed_power WHERE production_type = 'Solar AC'"
    return pd.read_sql(q, engine())


def rolling_peak(daily_max: pd.Series, window_days: int = 91, q: float = 0.9) -> pd.Series:
    """Typical clear-day peak: 90th percentile of daily maxima in a centred 91-day window."""
    return daily_max.rolling(window_days, center=True, min_periods=30).quantile(q)


def add_normalised_target(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for _, g in df.groupby("country_code"):
        g = g.copy()
        daily = g.groupby("date_local").agg(solar_max=("solar_mwh", "max"), ghi_max=("ghi_w_m2", "max"))
        peaks = pd.DataFrame({"solar_peak": rolling_peak(daily["solar_max"]),
                              "ghi_peak": rolling_peak(daily["ghi_max"])})
        g = g.join(peaks, on="date_local")
        g["y"] = g["solar_mwh"] / g["solar_peak"]
        g["baseline"] = (g["ghi_w_m2"] / g["ghi_peak"]).clip(lower=0)
        out.append(g)
    return pd.concat(out, ignore_index=True)


def capacity_hourly(hours: pd.Series, cap: pd.DataFrame, country: str) -> pd.Series:
    """Linear interpolation between year-end values. Years after the last report are extrapolated
    with the last annual increment (flagged in the docs as an assumption)."""
    c = cap[cap.country_code == country].dropna(subset=["gw"]).set_index("year")["gw"].sort_index()
    last = c.index.max()
    step = c.loc[last] - c.loc[last - 1]
    for y in range(last + 1, hours.dt.year.max() + 1):
        c.loc[y] = c.loc[y - 1] + step
    # value at the END of each year -> timestamps
    knots = pd.Series(c.values * 1000, index=pd.to_datetime([f"{y + 1}-01-01" for y in c.index], utc=True))
    knots.loc[pd.Timestamp(f"{c.index.min()}-01-01", tz="UTC")] = (c.iloc[0] * 1000)
    knots = knots.sort_index()
    # compare in epoch seconds: DB timestamps may be in us while constructed ones are in ns
    x = pd.DatetimeIndex(knots.index).as_unit("s").asi8
    t = pd.DatetimeIndex(hours).as_unit("s").asi8
    return pd.Series(np.interp(t, x, knots.values), index=hours.index)


# ---------------------------------------------------------------- model

def make_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
                                         l2_regularization=1.0, random_state=42)


def metrics(d: pd.DataFrame, pred_col: str) -> dict:
    daily = d.groupby("date_local")[["y", pred_col]].sum()
    monthly = d.groupby(d["date_local"].dt.to_period("M"))[["y", pred_col]].sum()
    return {
        "hourly_r2": r2_score(d["y"], d[pred_col]),
        "daily_nmae_pct": 100 * (daily["y"] - daily[pred_col]).abs().sum() / daily["y"].sum(),
        "monthly_wape_pct": 100 * (monthly["y"] - monthly[pred_col]).abs().sum() / monthly["y"].sum(),
        "total_bias_pct": 100 * (d[pred_col].sum() - d["y"].sum()) / d["y"].sum(),
    }


def validate(train: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Leave-one-country-out. Returns metrics table and out-of-fold predictions."""
    rows, oof = [], []
    for held_out in NEIGHBOURS:
        tr, te = train[train.country_code != held_out], train[train.country_code == held_out].copy()
        model = make_model().fit(tr[FEATURES], tr["y"])
        te["pred"] = model.predict(te[FEATURES]).clip(min=0)
        oof.append(te)
        for name, col in [("model", "pred"), ("baseline_irradiance", "baseline")]:
            rows += [{"country_code": held_out, "method": name, "metric": k, "value": v}
                     for k, v in metrics(te, col).items()]
        log.info("LOCO %s: model R2=%.3f | baseline R2=%.3f", held_out,
                 r2_score(te["y"], te["pred"]), r2_score(te["y"], te["baseline"]))
    return pd.DataFrame(rows), pd.concat(oof)


def realisation_ratios(df: pd.DataFrame, cap: pd.DataFrame) -> pd.Series:
    """Actual kWh/kW per neighbour-year divided by PVGIS kWh/kW for that country."""
    pvgis = pd.read_sql(
        "SELECT l.country_code, AVG(y.yield_kwh_per_kwp) AS pvgis FROM raw.pvgis_yield y "
        "JOIN raw.location l USING (location) WHERE scenario = 'optimal' GROUP BY 1", engine()
    ).set_index("country_code")["pvgis"]
    out = []
    for c in NEIGHBOURS:
        last_year = int(TRAIN_EXCLUDE_FROM[c][:4]) - 1 if c in TRAIN_EXCLUDE_FROM else TRAIN_END_YEAR
        g = df[(df.country_code == c) & (df.hour_utc.dt.year <= last_year)]
        capmw = capacity_hourly(g["hour_utc"], cap, c)
        yearly = pd.DataFrame({"year": g.hour_utc.dt.year, "mwh": g.solar_mwh, "capmw": capmw}) \
            .groupby("year").agg(mwh=("mwh", "sum"), capmw=("capmw", "mean"))
        ratio = (yearly.mwh * 1000 / (yearly.capmw * 1000)) / pvgis[c]
        out.append(ratio.rename(c))
    return pd.concat(out)


# ---------------------------------------------------------------- main

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = load_hourly()
    cap = load_capacity()

    nb = add_normalised_target(df[df.country_code.isin(NEIGHBOURS)])
    train = nb[(nb.hour_utc.dt.year <= TRAIN_END_YEAR) & nb.y.notna()]
    for country, start in TRAIN_EXCLUDE_FROM.items():
        train = train[~((train.country_code == country) & (train.hour_utc >= pd.Timestamp(start, tz="UTC")))]

    val, oof = validate(train)
    summary = val.pivot_table(index="metric", columns="method", values="value", aggfunc="mean")
    log.info("validation (mean of 4 held-out countries):\n%s", summary.round(3))

    # final shape model on all neighbours, predict Serbia
    model = make_model().fit(train[FEATURES], train["y"])
    rs = df[df.country_code == "rs"].copy()
    rs["shape"] = model.predict(rs[FEATURES]).clip(min=0)

    # level: kWh per kW per year = PVGIS(RS) x realisation ratio
    ratios = realisation_ratios(df, cap)
    pvgis_rs = pd.read_sql(
        "SELECT AVG(y.yield_kwh_per_kwp) FROM raw.pvgis_yield y JOIN raw.location l USING (location) "
        "WHERE l.country_code = 'rs' AND scenario = 'optimal'", engine()).iloc[0, 0]
    full_years = rs[rs.hour_utc.dt.year.between(2020, TRAIN_END_YEAR)]
    shape_per_year = full_years.groupby(full_years.hour_utc.dt.year)["shape"].sum().mean()
    q25, q50, q75 = ratios.quantile([0.25, 0.5, 0.75])
    rs["capacity_mw"] = capacity_hourly(rs["hour_utc"], cap, "rs")
    for col, r in [("solar_mwh_est", q50), ("solar_mwh_low", q25), ("solar_mwh_high", q75)]:
        k = pvgis_rs * r / shape_per_year              # kWh per kW per unit of shape
        rs[col] = rs["shape"] * k * rs["capacity_mw"]  # kWh/kW * MW = MWh
    log.info("PVGIS RS %.0f kWh/kWp; realisation ratio p25/p50/p75 = %.2f/%.2f/%.2f -> %.0f kWh/kW",
             pvgis_rs, q25, q50, q75, pvgis_rs * q50)

    # --- write results
    eng = engine()
    with eng.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS mart.fact_solar_estimate_hourly CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS mart.estimate_validation CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS mart.estimate_validation_hourly CASCADE"))
    rs[["country_code", "hour_utc", "shape", "capacity_mw", "solar_mwh_est", "solar_mwh_low", "solar_mwh_high"]] \
        .rename(columns={"shape": "solar_shape_norm"}) \
        .to_sql("fact_solar_estimate_hourly", eng, schema="mart", index=False, chunksize=5000, method="multi")
    val.to_sql("estimate_validation", eng, schema="mart", index=False)
    oof[["country_code", "hour_utc", "y", "pred", "baseline"]] \
        .rename(columns={"y": "actual_norm", "pred": "model_norm", "baseline": "baseline_norm"}) \
        .to_sql("estimate_validation_hourly", eng, schema="mart", index=False, chunksize=10000, method="multi")
    pd.DataFrame([
        {"parameter": "pvgis_rs_kwh_per_kwp", "value": pvgis_rs},
        {"parameter": "realisation_ratio_p25", "value": q25},
        {"parameter": "realisation_ratio_p50", "value": q50},
        {"parameter": "realisation_ratio_p75", "value": q75},
        {"parameter": "rs_kwh_per_kw_central", "value": pvgis_rs * q50},
    ]).to_sql("estimate_parameters", eng, schema="mart", index=False, if_exists="replace")
    with eng.begin() as conn:
        conn.execute(text("ALTER TABLE mart.fact_solar_estimate_hourly ADD PRIMARY KEY (country_code, hour_utc)"))
    run_sql_file(ROOT / "sql" / "04_views.sql")   # views were dropped by CASCADE above
    yearly = rs.groupby(rs.hour_utc.dt.year)[["solar_mwh_est", "solar_mwh_low", "solar_mwh_high"]].sum() / 1000
    log.info("Serbia estimated solar, GWh/year:\n%s", yearly.round(0))


if __name__ == "__main__":
    main()
