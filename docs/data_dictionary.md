# Data dictionary

Three layers in PostgreSQL database `solar_pv`:

| Layer | Purpose |
|---|---|
| `raw` | API data parsed into rows, unchanged values, native time resolution |
| `staging` | Cleaned: one hourly grid (UTC, interval **start**), generation types grouped into categories |
| `mart` | Star schema read by Power BI and the notebooks |

All timestamps are stored in **UTC** (`timestamptz`). Local columns use `Europe/Belgrade`
(the same time zone as HU/HR; RO and BG are one hour ahead, which doesn't matter for the comparisons).

## mart.fact_country_hourly — one row per country per hour
| Column | Unit | Description |
|---|---|---|
| country_code | | `rs`, `hu`, `ro`, `hr`, `bg` |
| hour_utc | timestamptz | start of the hour |
| date_local, hour_local | | Belgrade local date and hour (0–23) |
| solar_mwh … other_mwh | MWh | generation by category. `solar_mwh` is NULL for Serbia (not published) |
| load_mwh | MWh | electricity consumption |
| net_import_mwh | MWh | cross-border trading balance as reported by Energy-Charts |
| price_eur_mwh | €/MWh | day-ahead price, hourly mean (15-min prices averaged since Oct 2025) |
| min_price_eur_mwh | €/MWh | lowest sub-hour price in that hour |
| n_negative_intervals / n_price_intervals | count | how many of the hour's price intervals were < 0 |
| has_negative_price | bool | at least one negative interval in the hour |
| ghi_w_m2 | W/m² | global horizontal irradiance, mean of the country's weather locations |
| cloud_cover_pct, temp_c | %, °C | country-mean weather |

## mart.fact_capacity_yearly
Installed capacity per country, production type and year (GW), with `gw_added` = change vs the previous year.

## mart.fact_pv_yield / mart.fact_pv_yield_monthly
PVGIS long-term average output of **1 kWp** with 14 % system losses.
`scenario` = `optimal` (PVGIS-chosen angles) or `tilt<deg>_<direction>` (Serbian cities only).
Azimuth: 0 = south, −90 = east, 90 = west.

## Dimensions
`mart.dim_country`, `mart.dim_location` (lat/lon of the weather and PVGIS points), `mart.dim_date` (calendar, season, weekend).

## Known data issues
- **Serbia has no hourly solar series** in Energy-Charts (ENTSO-E source). It is estimated in a later step.
- Prices switched from hourly to 15-minute resolution in October 2025. The mart averages them back to hourly.
- Croatia is missing one hour in 2022.
- Energy-Charts solar figures cover grid-reported generation. Rooftop self-consumption may be partly missing,
  so yields per installed kW can look low.
