# Power BI dashboard: build guide

The dashboard reads the `mart` schema of the PostgreSQL database. Everything Power BI needs is prepared:

| File | What it is |
|---|---|
| `measures.dax` | every DAX measure and the what-if tables, ready to paste |
| `theme.json` | colours and fonts matching the report charts |
| `solar_pv_analytics.pbix` | the finished report (added after building) |
| `screenshots/` | one PNG per page (shown in the main README) |

**Before you start:** Docker Desktop is running (`docker compose up -d`) and the pipeline has run at least once
(`python -m src.pipeline --skip-extract`).

---

## 1. Connect to PostgreSQL

1. Power BI Desktop → **Get data → PostgreSQL database**.
2. Server: `localhost:5432` · Database: `solar_pv` · Data connectivity mode: **Import**.
3. Credentials: choose the **Database** tab. User `postgres`, password = `PG_PASSWORD` from your `.env` file.
4. If you get an SSL / encryption error, the local Docker database has no certificate. Click **OK** when Power BI offers to
   connect without encryption, or go to *File → Options and settings → Data source settings → localhost:5432;solar_pv →
   Edit permissions* and untick **Encrypt connections**.

## 2. Pick the tables

Tick these 7 (all in schema `mart`), then **Load**:

| Import | Rename to | Rows (approx.) |
|---|---|---|
| `mart.pbi_hourly` | **Hourly** | 300 k |
| `mart.pbi_capacity` | **Capacity** | 35 |
| `mart.pbi_pv_yield` | **PV Yield** | 290 |
| `mart.pbi_weather_daily` | **Weather Daily** | 8 k |
| `mart.pbi_estimate_validation` | **Validation** | 32 |
| `mart.dim_country` | **Country** | 5 |
| `mart.dim_date` | **Date** | 2.5 k |

## 3. Model

In **Model view**:

1. Rename the tables as in the table above (double-click the name).
2. Create relationships (all *one-to-many*, single direction, from the dimension to the fact):

   | From (one) | To (many) |
   |---|---|
   | `Country[country_code]` | `Hourly[country_code]`, `Capacity[country_code]`, `PV Yield[country_code]`, `Weather Daily[country_code]`, `Validation[country_code]` |
   | `Date[date_local]` | `Hourly[date_local]`, `Weather Daily[date_local]` |

   Delete any relationship Power BI auto-detected that is not in this list.
3. Select the **Date** table → *Table tools → Mark as date table* → column `date_local`.
4. Sort columns: `Country[country_name]` → *Sort by column* `sort_order`. `Date[month_name]` → sort by `month`.
   `Date[weekday_name]` → sort by `iso_weekday`.
5. Hide the technical columns from report view (right-click → *Hide*): `hour_utc`, `color_hex`, `sort_order`, all key columns on fact tables.

## 4. Theme and measures

1. *View → Themes → Browse for themes* → `powerbi/theme.json`.
2. *Home → Enter data* → name the table **_Measures** → Load. Measures go here.
3. *Modeling → New table* for each of the 5 what-if tables at the top of `measures.dax`.
4. *Modeling → New measure* for each measure in `measures.dax` (select **_Measures** first, so they land there).
   Formats: `Solar % of Load`, `Avg Hourly Solar % of Load`, `Solar Capture Rate`, `Midday Discount`, `% of Optimum` → **Percentage, 1 decimal**.
   Prices → **1 decimal**. `Simple Payback (years)` → 1 decimal.
5. Delete the dummy column in `_Measures`. The table turns into a measure folder.

**Country colours.** Each country keeps one colour everywhere: Serbia `#2a78d6`, Hungary `#eb6834`, Romania `#1baf7a`,
Croatia `#eda100`, Bulgaria `#e87ba4`. On bar/column charts *without* a legend use *Colors → fx → Field value → Country Colour*.
On line charts with a Country legend, set the five series colours once by hand with these hex codes.

---

## 5. Pages

Canvas: 16:9. Put a title text box at the top-left of each page that states the page's *finding*, not just its topic.

### Page 1 · Overview
| Visual | Fields | Notes |
|---|---|---|
| 4 cards | `First Negative Price (date)` · `Negative Price Hours` · `Solar Capture Rate` · `Installed Solar GW (latest)` | Visual-level filter **Country = Serbia**. Capture-rate card: also filter `Date[year] = 2025`. |
| Line chart | X `Date[year]` · Y `Negative Price Hours` · Legend `Country[country_name]` | The headline: Serbia's first negative hours in 2026 |
| Text box | 3 key findings from the main README | |
| Slicer | `Date[year]` (tile style) | Sync to all pages (*View → Sync slicers*) |

### Page 2 · Serbia PV potential
| Visual | Fields | Notes |
|---|---|---|
| Bar chart | Y `PV Yield[location]` · X `Optimal Yield kWh per kWp` | Filter `Country = Serbia`, sort descending, data labels on |
| Line chart | X `PV Yield[tilt_deg]` · Y `% of Optimum` · Legend `PV Yield[orientation]` | Filter `scenario` is not `optimal`. Single-select slicer on `location` (default Belgrade) |
| 5 slicers | `System kWp[Value]`, `Capex per kWp[Value]`, `Self-consumption[Value]`, `Retail Tariff[Value]`, `Feed-in Tariff[Value]` | Single value / slider: the payback calculator |
| 4 cards | `Annual Production kWh` · `Annual Savings €` · `System Cost €` · `Simple Payback (years)` | React to the slicers and the location slicer |
| Map (optional) | Latitude `lat` · Longitude `lon` · Size `Optimal Yield kWh per kWp` | Needs map visuals enabled in *Options → Security* |

### Page 3 · Grid & neighbours
| Visual | Fields | Notes |
|---|---|---|
| Line chart | X `Capacity[year]` · Y `Installed Solar GW` · Legend `Country[country_name]` | |
| Clustered column | X `Date[year]` · Y `Solar % of Load` · Legend `Country[country_name]` | Tooltip: `Solar Data Status` (Serbia = estimated) |
| Line chart | X `Hourly[hour_local]` · Y `Avg Hourly Solar % of Load` · Legend `Country[country_name]` | Visual filter `Date[month] = 6`. Use the year slicer |
| Text box | *"Bulgaria's 2025–26 solar includes output after sunset (likely batteries). See data-quality note."* | |

### Page 4 · Prices & negative hours
| Visual | Fields | Notes |
|---|---|---|
| Matrix | Rows `Country[country_name]` · Columns `Date[year]` · Values `Negative Price Hours` | *Cell elements → Background color* gradient, white → `#2a78d6` |
| Line chart | X `Hourly[hour_local]` · Y `Avg Price` · Legend `Date[year]` | Filter `Country = Serbia`, `Date[year]` in 2021, 2023–2026; April–September (`Date[month]` 4–9) |
| Column chart | X `Date[year]` · Y `Midday Discount` | Filter `Country = Serbia`, months 4–9 |
| Line chart | X `Date[year]` · Y `Solar Capture Rate` · Legend `Country[country_name]` | Add a constant line at 100 % (*Analytics pane*) |
| 2 cards | `Negative Price Hours` and `RS Negative Hours with Negative Neighbour` | Filter `Date[year] = 2026`. Shows "39 of 42 hours were imported" |

### Page 5 · Serbia solar estimate
| Visual | Fields | Notes |
|---|---|---|
| Line chart | X `Date[date_local]` (Year → Month hierarchy) · Y `Solar GWh` | Filter `Country = Serbia`, `Date[year]` ≥ 2023. *Analytics → Error bars*: upper `Solar GWh High`, lower `Solar GWh Low`, style **band** |
| Line chart | X `Weather Daily[date_local]` · Y `output_norm` (Sum) and `model_norm` (Sum) | Filter `Country = Hungary`. Date-range slicer (e.g. June 2025): the model predicting a country it never saw |
| Matrix | Rows `Validation[metric]` · Columns `Validation[method]` · Values `Model Metric` | Average of the 4 held-out countries |
| Text box | How the estimate works (3 sentences, from `docs/STEP_BY_STEP.md` Step 6) | |

### Page 6 · Weather
| Visual | Fields | Notes |
|---|---|---|
| Scatter | X `Weather Daily[ghi_kwh_m2]` · Y `Weather Daily[output_norm]` · Values `Weather Daily[date_local]` | Filter `Country = Hungary` |
| Card | `Irradiance vs Output r` | |
| Column chart | X `Date[month_name]` · Y `Daily Output CV` | Filter `Country = Hungary`, `Date[year] = 2025` |

---

## 6. Check your numbers

These values come straight from SQL. If a card shows something else, check the visual's filters and the relationships.

| Measure (filter) | Expected |
|---|---|
| `First Negative Price (date)` (Serbia) | 10 May 2026 |
| `Negative Price Hours` (Serbia, 2026) | 42 |
| `RS Negative Hours with Negative Neighbour` (2026) | 39 |
| `Solar Capture Rate` (Serbia, 2025) | 63.0 % |
| `Installed Solar GW (latest)` (Serbia) | 0.19 |
| `Midday Discount` (Serbia, 2025, months 4–9) | 78.9 % |
| `Solar % of Load` (Hungary, 2025) | 15.8 % |
| `Optimal Yield kWh per kWp` (Belgrade) | 1,256 |
| `Simple Payback (years)` (Belgrade, default slicers) | 10.2 |

The figures for the current year grow as new data is downloaded.

## 7. Save and screenshot

1. *File → Save as* → `powerbi/solar_pv_analytics.pbix`.
2. For each page: *File → Export → Export to PDF*, or use the Windows Snipping Tool (Win+Shift+S),
   and save the images as `powerbi/screenshots/01_overview.png` … `06_weather.png`.
3. Refresh later with **Home → Refresh** after re-running the pipeline.
