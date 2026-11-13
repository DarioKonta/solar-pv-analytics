"""Answer the five business questions: run sql/analysis/*.sql, draw figures, write reports/findings.md.

Usage:  python -m src.analysis.report
"""
from __future__ import annotations

import calendar
import logging
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import text

from src.config import ROOT, settings
from src.db import engine

log = logging.getLogger(__name__)

SQL = ROOT / "sql" / "analysis"
FIG = ROOT / "reports" / "figures"
REPORT = ROOT / "reports" / "findings.md"

# ---------------------------------------------------------------- style
# Fixed colour per country in every chart (colour follows the entity, never its rank).
COUNTRY_COLOR = {"rs": "#2a78d6", "hu": "#eb6834", "ro": "#1baf7a", "hr": "#eda100", "bg": "#e87ba4"}
COUNTRY_NAME = {c["code"]: c["name"] for c in settings()["countries"]}
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]   # ordinal (years)

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "lines.linewidth": 2, "legend.frameon": False, "legend.labelcolor": INK_2,
})


def q(name: str) -> pd.DataFrame:
    return pd.read_sql(text((SQL / f"{name}.sql").read_text(encoding="utf-8")), engine())


def save(fig: plt.Figure, name: str, note: str | None = None) -> str:
    if note:
        # place the source note just below everything already drawn (axis labels included)
        bb = fig.get_tightbbox(fig.canvas.get_renderer())
        x0 = bb.x0 / fig.get_figwidth()
        y0 = bb.y0 / fig.get_figheight()
        fig.text(x0, y0 - 0.02, note, color=MUTED, fontsize=8, ha="left", va="top")
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}.png"


def end_labels(ax, x, items: list[tuple[float, str, bool]], min_gap: float) -> None:
    """Direct labels at the right end of lines, nudged apart so they never overlap.
    items: (y_value, text, bold). min_gap is in data units."""
    placed: list[float] = []
    for y, label, bold in sorted(items):
        pos = max([y] + [p + min_gap for p in placed])
        placed.append(pos)
        ax.annotate(label, (x, pos), xytext=(6, 0), textcoords="offset points", va="center",
                    color=INK_2, fontsize=9, fontweight="bold" if bold else "normal", annotation_clip=False)


def md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


# ---------------------------------------------------------------- Q1

def payback_table(city: pd.DataFrame) -> pd.DataFrame:
    e = settings()["pv_economics"]
    capex = e["system_kwp"] * e["capex_eur_per_kwp"]
    value_per_kwh = (e["self_consumption_share"] * e["retail_tariff_eur_per_kwh"]
                     + (1 - e["self_consumption_share"]) * e["feed_in_eur_per_kwh"])
    rows = []
    for _, r in city.iterrows():
        kwh_y1 = r.yield_kwh_per_kwp * e["system_kwp"]
        cum, years = 0.0, None
        for y in range(1, e["lifetime_years"] + 1):
            cum += kwh_y1 * (1 - e["degradation_pct_per_year"] / 100) ** (y - 1) * value_per_kwh
            if years is None and cum >= capex:
                years = y - 1 + (capex - (cum - kwh_y1 * value_per_kwh)) / (kwh_y1 * value_per_kwh)
        rows.append({"City": r.location, "kWh/year (6 kWp)": round(kwh_y1),
                     "Savings €/year": round(kwh_y1 * value_per_kwh),
                     "Payback (years)": round(years, 1) if years else None,
                     f"Net gain over {e['lifetime_years']} y (€)": round(cum - capex)})
    return pd.DataFrame(rows)


def q1() -> str:
    city = q("q1_city_yield")
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    c = city.sort_values("yield_kwh_per_kwp")
    ax.barh(c.location, c.yield_kwh_per_kwp, color=COUNTRY_COLOR["rs"], height=0.6)
    for y, v in zip(c.location, c.yield_kwh_per_kwp):
        ax.annotate(f"{v:,.0f}", (v, y), xytext=(4, 0), textcoords="offset points", va="center", color=INK_2, fontsize=9)
    ax.set_xlim(1000, 1320)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("kWh per kWp per year (optimal tilt, south)")
    ax.set_title("Q1 · Solar yield across Serbian cities differs by less than 7 %")
    f1 = save(fig, "q1_city_yield", "Source: PVGIS 5.3 (EU JRC), long-term average, 14 % system losses. Axis starts at 1,000.")

    o = q("q1_orientation")
    bg = o[o.location == "Belgrade"].copy()
    bg["group"] = bg.orientation.map({"south": "South", "south_east": "South-east / south-west",
                                      "south_west": "South-east / south-west", "east": "East / west", "west": "East / west"})
    g = bg.groupby(["group", "tilt_deg"]).pct_of_optimum.mean().reset_index()
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ends = []
    for name, color in zip(["South", "South-east / south-west", "East / west"], ["#2a78d6", "#eb6834", "#1baf7a"]):
        d = g[g.group == name].sort_values("tilt_deg")
        ax.plot(d.tilt_deg, d.pct_of_optimum, color=color, marker="o", markersize=4, label=name)
        ends.append((d.pct_of_optimum.iloc[-1], f"{name.split(' /')[0]}  {d.pct_of_optimum.iloc[-1]:.0f} %", False))
    end_labels(ax, 90, ends, min_gap=3)
    ax.set_xticks([0, 10, 20, 30, 35, 40, 50, 60, 90])
    ax.set_xlabel("Panel tilt (degrees; 0 = flat, 90 = vertical)")
    ax.set_ylabel("% of the optimum")
    ax.set_title("Q1 · Orientation matters more than location (Belgrade)")
    ax.legend(loc="lower left")
    f2 = save(fig, "q1_orientation", "Source: PVGIS 5.3. East/west and the two diagonals are averaged pairs.")

    pay = payback_table(city)
    e = settings()["pv_economics"]
    return f"""## Q1 · Where in Serbia is rooftop PV most worth it?

![City yield]({f1})

{md(city[['location', 'yield_kwh_per_kwp', 'optimal_tilt_deg', 'pct_vs_best']].rename(columns={'location': 'City', 'yield_kwh_per_kwp': 'kWh/kWp/yr', 'optimal_tilt_deg': 'Optimal tilt °', 'pct_vs_best': '% vs best'}))}

![Orientation]({f2})

**Payback of a typical {e['system_kwp']} kWp rooftop system**. Assumptions (editable in `config/settings.yaml`):
€{e['capex_eur_per_kwp']}/kWp installed, {int(e['self_consumption_share']*100)} % self-consumed at €{e['retail_tariff_eur_per_kwh']}/kWh,
the rest exported at €{e['feed_in_eur_per_kwh']}/kWh, {e['degradation_pct_per_year']} %/yr degradation.

{md(pay)}

**Takeaways**
- Niš and Vojvodina (Novi Sad, Subotica) are the best locations. Zlatibor, in the mountains, is the weakest, but the whole
  spread is under 7 %. Solar is viable everywhere in Serbia.
- **Orientation matters about 3× more than location.** A south-facing roof at 30–40° reaches ~99 % of the optimum.
  East or west at the same tilt loses ~20 %, and a flat roof ~15 %.
- With these assumptions a rooftop system pays back in about 10–11 years. The result depends mostly on how much
  electricity is used on site, because self-consumed kWh are worth twice as much as exported ones.
"""


# ---------------------------------------------------------------- Q2

def q2() -> str:
    cap = q("q2_capacity")
    share = q("q2_solar_share")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    last = cap.year.max()
    ends = []
    for code, d in cap.groupby("country_code"):
        ax.plot(d.year, d.gw, color=COUNTRY_COLOR[code], marker="o", markersize=4)
        ends.append((d.gw.iloc[-1], f"{COUNTRY_NAME[code]}  {d.gw.iloc[-1]:.2f} GW", code == "rs"))
    end_labels(ax, last, ends, min_gap=0.45)
    ax.set_xticks(sorted(cap.year.unique()))
    ax.set_xlim(cap.year.min() - 0.2, last + 0.2)
    ax.set_ylabel("Installed solar (GW, year end)")
    ax.set_title("Q2 · Serbia's solar fleet is still tiny next to its neighbours")
    f1 = save(fig, "q2_capacity", "Source: Energy-Charts (Fraunhofer ISE), installed capacity 'Solar AC'.")

    pivot_cap = cap.pivot(index="year", columns="country_name", values="gw").reset_index()
    pivot_share = share.pivot(index="year", columns="country_code", values="solar_pct_of_load") \
        .rename(columns=COUNTRY_NAME).reset_index()
    rs = cap[cap.country_code == "rs"].set_index("year").gw
    ratio = {c: cap[(cap.country_code == c) & (cap.year == 2025)].gw.iloc[0] / rs.loc[2025] for c in ["hu", "bg", "ro", "hr"]}
    rs_share = share[(share.country_code == "rs") & (share.year == 2025)].solar_pct_of_load.iloc[0]
    return f"""## Q2 · How fast is Serbian solar growing compared with its neighbours?

![Capacity]({f1})

Installed solar capacity (GW, year end):

{md(pivot_cap)}

Solar output as % of electricity demand (Serbia = estimate from Q3; 2026 = January to mid-November):

{md(pivot_share)}

**Takeaways**
- Serbia went from ~0 to **{rs.loc[2025]:.2f} GW** (2023→2025: ×{rs.loc[2025] / rs.loc[2023]:.0f}). That is fast in relative terms,
  but the fleet is {ratio['hu']:.0f}× smaller than Hungary's, {ratio['bg']:.0f}× smaller than Bulgaria's,
  {ratio['ro']:.0f}× smaller than Romania's and {ratio['hr']:.0f}× smaller than Croatia's.
- Solar covered about **{rs_share:.1f} %** of Serbian demand in 2025, against ~16 % in Hungary
  (Bulgaria's 2025–26 shares are overstated; see the data-quality note).
"""


# ---------------------------------------------------------------- Q3

def q3() -> str:
    val = pd.read_sql(text("SELECT * FROM mart.v_estimate_validation WHERE country_code = 'mean' ORDER BY metric, method"), engine())
    sample = q("q3_validation_sample")
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(sample.ts_local, sample.actual_norm, color=INK, linewidth=1.6, label="Actual (published)")
    ax.plot(sample.ts_local, sample.model_norm, color=COUNTRY_COLOR["rs"], linewidth=1.6, label="Model (Hungary never seen in training)")
    ax.set_ylabel("Output ÷ clear-day peak")
    ax.set_title("Q3 · The model reproduces sunny and cloudy days in a country it never saw")
    ax.legend(loc="upper left", ncols=2, bbox_to_anchor=(0, 1.02))
    ax.set_ylim(0, 1.35)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    f1 = save(fig, "q3_validation", "Hungary, 9–22 June 2025. Leave-one-country-out: trained on Romania, Bulgaria and Croatia only.")

    june = q("q3_june_profile")
    june = june[june.year == 2026]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for code, d in june.groupby("country_code"):
        ax.plot(d.hour_local, d.solar_pct_of_load, color=COUNTRY_COLOR[code],
                linestyle="--" if code == "rs" else "-", label=COUNTRY_NAME[code] + (" (estimate)" if code == "rs" else ""))
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day (local time)")
    ax.set_ylabel("Solar as % of demand")
    ax.set_title("Q3 · At noon in June, solar covers ~78 % of Hungary's demand and ~3 % of Serbia's")
    ax.legend(loc="upper left")
    f2 = save(fig, "q3_june_profile", "June 2026, hourly average. Serbia's line is the model estimate (dashed).\n"
                                      "Bulgaria's evening bump is not solar: see the data-quality note at the end.")

    mon = q("q3_rs_monthly")
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.fill_between(mon.month, mon.solar_gwh_low, mon.solar_gwh_high, color=COUNTRY_COLOR["rs"], alpha=0.18,
                    linewidth=0, label="Low–high range")
    ax.plot(mon.month, mon.solar_gwh_est, color=COUNTRY_COLOR["rs"], label="Central estimate")
    ax.set_ylabel("GWh per month")
    ax.set_title("Q3 · Estimated Serbian solar generation")
    ax.legend(loc="upper left")
    f3 = save(fig, "q3_rs_monthly", "Model estimate. 2026 assumes capacity grows by the same amount as in 2025 (+0.12 GW).")

    v = val.pivot(index="metric", columns="method", values="value").reset_index()
    v.columns = ["Metric", "Baseline (irradiance only)", "Model"]
    v["Metric"] = v["Metric"].map({"daily_nmae_pct": "Daily error, nMAE (%)", "hourly_r2": "Hourly R²",
                                   "monthly_wape_pct": "Monthly error, WAPE (%)", "total_bias_pct": "Total bias (%)"})
    v[["Baseline (irradiance only)", "Model"]] = v[["Baseline (irradiance only)", "Model"]].astype(float).round(2)
    yearly = mon.assign(year=pd.to_datetime(mon.month).dt.year).groupby("year")[["solar_gwh_est", "solar_gwh_low", "solar_gwh_high"]].sum().round(0).reset_index()
    yearly.columns = ["Year", "Estimate (GWh)", "Low", "High"]
    mv = v.set_index("Metric")["Model"]
    y25 = yearly.set_index("Year").loc[2025]
    rs_peak = june[june.country_code == "rs"].solar_pct_of_load.max()
    return f"""## Q3 · What does Serbia's hourly solar output look like?

Serbia publishes no hourly solar data, so it was **estimated** (method in `docs/STEP_BY_STEP.md`, Step 6).
Validation: hide one neighbour, train on the other three, predict the hidden one.

![Validation]({f1})

{md(v)}

![June profile]({f2})

![Serbia monthly]({f3})

{md(yearly)}

**Takeaways**
- The weather model transfers well between countries (hourly R² ≈ {mv['Hourly R²']:.2f}, monthly error ≈ {mv['Monthly error, WAPE (%)']:.0f} %,
  bias {mv['Total bias (%)']:+.1f} %).
- Serbian solar generated an estimated **~{y25['Estimate (GWh)']:.0f} GWh in 2025** (range {y25['Low']:.0f}–{y25['High']:.0f}).
  Even at the June noon peak it covers only ~{rs_peak:.0f} % of demand.
"""


# ---------------------------------------------------------------- Q4

def q4() -> str:
    neg = q("q4_negative_hours")
    neg = neg[neg.year >= 2020]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for code, d in neg.groupby("country_code"):
        ax.plot(d.year, d.negative_hours, color=COUNTRY_COLOR[code], marker="o", markersize=4, label=COUNTRY_NAME[code])
    ax.set_ylabel("Hours with a negative price")
    ax.set_title("Q4 · Negative prices are spreading: Serbia's first ones came in 2026")
    ax.legend(loc="upper left")
    f1 = save(fig, "q4_negative_hours", "Day-ahead market. An hour counts if any of its 15-min prices was < 0. 2026 = to mid-November.")

    prof = q("q4_price_profile")
    rs = prof[(prof.country_code == "rs") & (prof.year.isin([2023, 2024, 2025, 2026]))]
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ends = []
    for (yr, d), color in zip(rs.groupby("year"), BLUE_RAMP[1:]):
        ax.plot(d.hour_local, d.avg_price_eur_mwh, color=color)
        ends.append((d.avg_price_eur_mwh.iloc[-1], str(yr), False))
    end_labels(ax, 23, ends, min_gap=9)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlim(0, 23.3)
    ax.set_xlabel("Hour of day (local time)")
    ax.set_ylabel("Average price (€/MWh)")
    ax.set_title("Q4 · Since 2023, Serbia's midday price has collapsed relative to the evening")
    f2 = save(fig, "q4_price_profile", "Serbia (SEEPEX day-ahead), April–September average by hour. Darker = more recent.")

    cap = q("q4_capture_rate")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for code, d in cap.groupby("country_code"):
        ax.plot(d.year, d.capture_rate_pct, color=COUNTRY_COLOR[code], marker="o", markersize=4,
                linestyle="--" if code == "rs" else "-", label=COUNTRY_NAME[code] + (" (estimated profile)" if code == "rs" else ""))
    ax.axhline(100, color=AXIS, linewidth=1)
    ax.set_ylabel("Solar capture rate (% of average price)")
    ax.set_title("Q4 · Solar now earns ~30–40 % less than the average price")
    ax.legend(loc="lower left")
    f3 = save(fig, "q4_capture_rate", "Capture rate = output-weighted price ÷ time-weighted average price.")

    origin = q("q4_rs_negative_origin").iloc[0].astype(float)
    rs_cap = cap[cap.country_code == "rs"].set_index("year").capture_rate_pct
    pvt = neg.pivot(index="year", columns="country_code", values="negative_hours").rename(columns=COUNTRY_NAME).reset_index()
    capt = cap.pivot(index="year", columns="country_code", values="capture_rate_pct").rename(columns=COUNTRY_NAME) \
        .astype(object).where(lambda x: x.notna(), "–").reset_index()
    rs_all = prof[prof.country_code == "rs"]
    p = rs_all.assign(slot=pd.cut(rs_all.hour_local, [10, 14, 17, 21], labels=["midday", "x", "evening"])) \
        .groupby(["year", "slot"], observed=True).avg_price_eur_mwh.mean().unstack()
    dip = (100 * (1 - p["midday"] / p["evening"])).round(0).astype(int)
    dip_tbl = pd.DataFrame({"Year": dip.index, "Midday (11–14 h) €/MWh": p["midday"].round(1).values,
                            "Evening (18–21 h) €/MWh": p["evening"].round(1).values, "Midday discount %": dip.values})

    # Scenario: when would Serbia's OWN solar reach the share at which Hungary's negative prices took off?
    share = q("q2_solar_share")
    hu_threshold = share[(share.country_code == "hu") & (share.year == 2023)].solar_pct_of_load.iloc[0]
    rs_load_twh = share[(share.country_code == "rs") & (share.year == 2025)].load_twh.iloc[0]
    kwh_per_kw = round(pd.read_sql(text("SELECT value FROM mart.estimate_parameters "
                                        "WHERE parameter = 'rs_kwh_per_kw_central'"), engine()).iloc[0, 0])
    gw_needed = hu_threshold / 100 * rs_load_twh * 1e9 / kwh_per_kw / 1e6
    start = 0.19
    scen = []
    for name, step in [("Linear, +0.12 GW/yr (2025 pace)", ("lin", 0.12)), ("Linear, +0.5 GW/yr", ("lin", 0.5)),
                       ("Linear, +1 GW/yr", ("lin", 1.0)), ("Doubling every year", ("exp", 2.0))]:
        kind, v = step
        years = (gw_needed - start) / v if kind == "lin" else math.log(gw_needed / start, v)
        scen.append({"Scenario": name, "Year Serbia reaches the threshold": 2025 + math.ceil(years)})
    return f"""## Q4 · How does solar affect electricity prices, and when will Serbia see negative prices?

![Negative hours]({f1})

Hours with at least one negative price:

{md(pvt)}

![Price profile]({f2})

Serbia, April–September averages:

{md(dip_tbl)}

![Capture rate]({f3})

Solar capture rate, % of the average price (Serbia = estimated generation profile):

{md(capt)}

**Are Serbia's negative prices home-grown or imported?** In 2026 Serbia had **{origin.rs_negative_hours:.0f} negative-price hours**.
In those hours Serbian solar covered only **{origin.rs_avg_solar_pct_of_load:.1f} %** of demand (estimate).
At least one neighbour was also negative in **{origin.hours_with_any_neighbour_negative:.0f}** of them, and all four were in **{origin.hours_with_all_neighbours_negative:.0f}**.

**When could Serbia's *own* solar push prices negative?** Hungary's negative prices took off in 2023, when solar reached
**{hu_threshold:.1f} %** of its annual demand. For Serbia (≈ {rs_load_twh:.0f} TWh demand, ≈ {kwh_per_kw} kWh/kW) that means
**≈ {gw_needed:.1f} GW** of solar, about 20× today's fleet.

{md(pd.DataFrame(scen))}

**Takeaways**
- Negative prices started in Croatia and Hungary and reached Bulgaria and Romania by 2023. **Serbia's first ones came on 10 May 2026.**
- Long before that, the regional solar boom was already reshaping Serbian prices. Midday used to be ~20 % cheaper than the
  evening (2020–2022). From 2024 it has been **70–80 % cheaper**.
- They are **imported**. Serbia's market is coupled to its neighbours, so when the region has a midday solar glut, the
  price in Serbia falls too, even though Serbian solar barely registers.
- That already hurts Serbian solar investors: the estimated capture rate fell from ~{rs_cap[2023]:.0f} % (2023)
  to ~{rs_cap[2025]:.0f} % (2025). A Serbian solar plant earns about a third less per MWh than the average price.
- Bulgaria's apparent recovery in 2026 ({cap[(cap.country_code == "bg") & (cap.year == 2026)].capture_rate_pct.iloc[0]:.0f} %) is probably a data artefact. Its "solar" series now includes
  evening output sold at high evening prices (see the data-quality note).
- Home-grown negative prices need several GW of domestic solar. Serbia's hydro and its role as a regional
  transit country (flexibility, exports) would push that threshold higher still. These scenarios are illustrations, not forecasts.
"""


# ---------------------------------------------------------------- Q5

def q5() -> str:
    d = q("q5_weather_daily")
    r_ghi = d.output_norm.corr(d.ghi_kwh_m2)
    r_cloud = d.output_norm.corr(d.cloud_cover_pct)
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    ax.scatter(d.ghi_kwh_m2, d.output_norm, s=10, color=COUNTRY_COLOR["hu"], alpha=0.35, linewidths=0)
    ax.set_xlabel("Daily irradiance (kWh/m², country average)")
    ax.set_ylabel("Daily solar output (÷ clear-day peak)")
    ax.set_title("Q5 · Sunlight explains almost all day-to-day variation")
    ax.annotate(f"r = {r_ghi:.2f}", (0.03, 0.92), xycoords="axes fraction", color=INK, fontsize=11, fontweight="bold")
    f1 = save(fig, "q5_weather_scatter", "Hungary 2020–2025, one dot per day. Published output, normalised for capacity growth.")

    m = q("q5_monthly_variability")
    m["month_name"] = m.month.map(lambda i: calendar.month_abbr[int(i)])
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.bar(m.month_name, m.cv_pct, color=COUNTRY_COLOR["hu"], width=0.6)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Day-to-day variation (CV, %)")
    ax.set_title("Q5 · Winter solar is 6× less predictable than summer solar")
    f2 = save(fig, "q5_variability", "Hungary 2025. CV = standard deviation ÷ mean of daily output.")

    season = d.groupby("season").agg(days=("day", "count"), avg_cloud_pct=("cloud_cover_pct", "mean"),
                                     r_irradiance=("output_norm", lambda s: s.corr(d.loc[s.index, "ghi_kwh_m2"]))).round(2).reset_index()
    season.columns = ["Season", "Days", "Avg cloud cover %", "r (output vs irradiance)"]
    season["Avg cloud cover %"] = season["Avg cloud cover %"].round(0).astype(int)
    return f"""## Q5 · How much does weather drive solar output?

![Weather scatter]({f1})

- Correlation of daily output with irradiance: **r = {r_ghi:.2f}**. With cloud cover: **r = {r_cloud:.2f}**.

{md(season)}

![Variability]({f2})

{md(m[['month_name', 'avg_daily_gwh', 'cv_pct', 'best_to_worst_day']].rename(columns={'month_name': 'Month', 'avg_daily_gwh': 'Avg GWh/day', 'cv_pct': 'CV %', 'best_to_worst_day': 'Best ÷ worst day'}))}

**Takeaways**
- Irradiance is the whole story. Cloud cover is a weaker proxy, because thin clouds still let a lot of light through.
- In June the best day produces only 1.6× the worst. In November–January it is 13–16×. Winter solar needs
  backup (hydro, imports, storage), and accurate weather forecasts matter most in winter.
"""


# ---------------------------------------------------------------- main

def data_quality() -> str:
    dq = q("dq_solar_after_dark")
    bg = dq[(dq.country_code == "bg") & (dq.year >= 2023)]
    bg.columns = ["Country", "Year", "Solar after dark (GWh)", "% of annual solar", "Max after dark (MW)"]
    return f"""## Data-quality note · Bulgaria's "solar" after sunset

Solar output should be ~0 when irradiance is zero. For Hungary, Romania and Croatia it is (≤ 0.2 %).
**Bulgaria's published solar series is not, from 2025 onwards:**

{md(bg)}

The pattern (≈ 1 GW sustained after sunset in summer 2026) looks like **batteries built next to solar parks and reported as solar**.
That is an assumption, not a confirmed cause. Consequences in this project:
- Bulgarian 2025–2026 data is **excluded from training** the Serbian solar model.
- Bulgaria's 2025–2026 solar share and capture rate are **overstated**. They are shown as published, with this caveat.
"""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parts = []
    for fn in (q1, q2, q3, q4, q5, data_quality):
        log.info("building %s", fn.__name__)
        parts.append(fn())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Findings\n\nGenerated by `python -m src.analysis.report` from the `mart` schema.\n\n"
                      + "\n---\n\n".join(parts), encoding="utf-8")
    log.info("wrote %s and %d figures", REPORT.relative_to(ROOT), len(list(FIG.glob("*.png"))))


if __name__ == "__main__":
    main()
