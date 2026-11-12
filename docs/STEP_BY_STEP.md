# Step-by-step guide

Each step has two parts:
- **In simple words**: what we did and why, without jargon.
- **In detail**: the technical how, with commands and design decisions.

---

## Step 0 — Choosing the questions and the data

### In simple words
Before writing any code, we decided which questions the project should answer and checked
that free data exists for them. We picked Serbia as the focus and four neighbours to compare against.
While checking, we found that Serbia does not publish hourly solar production, so part of the
project is to *estimate* it.

### In detail
- We probed the Energy-Charts API (`/public_power`, `/price`, `/installed_power`) for RS, HU, RO, HR and BG.
  - Serbia returns load, hydro, coal, gas and wind, but **no `Solar` production series**. Its installed
    solar capacity is available: 0.03 GW (2023), 0.07 GW (2024), 0.19 GW (2025).
  - The neighbours all return an hourly `Solar` series, which gives us data to validate our Serbian estimate.
  - Day-ahead prices are available for every bidding zone, including RS (SEEPEX).
  - The API rate-limits quickly (HTTP 429), so the extractors need throttling and caching.
- A quick check of negative prices: Bulgaria had 11 → 55 → 170 negative-price intervals in 2023 → 2025,
  while Serbia had none in 2023. This led to the question "when could Serbia get negative prices?".
- PVGIS and Open-Meteo need no API key and cover Serbia.

---

## Step 1 — Repository setup

### In simple words
We created the project folder as a Git repository, so every change is tracked, and published it
publicly on GitHub. A `.gitignore` file tells Git which files should never be uploaded, such as
passwords, large downloaded data and personal notes.

### In detail
- `git init -b main` in the project folder.
- `.gitignore` excludes `.venv/`, `.env`, `data/raw/`, notebook checkpoints, Power BI caches and local notes.
- Created and pushed the public repo with the GitHub CLI:
  `gh repo create solar-pv-analytics --public --source . --push`.

---

## Step 2 — Python environment

### In simple words
We created an isolated Python "box" (a virtual environment) for this project and installed the
libraries it needs. Anyone can recreate the same setup from `requirements.txt`.

### In detail
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- `requests` calls the APIs, `pandas` and `numpy` handle tables, and `sqlalchemy` + `psycopg` talk to PostgreSQL.
- `scikit-learn` is used for the Serbian solar estimate, `matplotlib` and `jupyter` for analysis, and `pytest` for tests.
- Database credentials live in `.env`, which is never committed. `.env.example` shows the expected variables.

---

## Step 3 — Downloading the data (extract)

### In simple words
We wrote small Python programs that ask three free websites for data: electricity generation
and prices (Energy-Charts), how much a solar panel would produce in a given city (PVGIS),
and historical weather such as sunshine, clouds and temperature (Open-Meteo).
Every answer is saved to disk, so the data never has to be downloaded twice.
All settings (countries, cities, dates) live in one file, `config/settings.yaml`.

### In detail
- **Run:** `python -m src.extract.run` (all sources) or e.g. `python -m src.extract.run pvgis`.
- **`src/http_client.py`:** one shared client that
  - waits a fixed time between calls (3 s for Energy-Charts, which answers HTTP 429 when called too fast),
  - retries on 429/5xx with exponential backoff (and respects `Retry-After`),
  - caches every response as JSON under `data/raw/<source>/...` and writes it atomically
    (`.tmp` file, then rename), so an interrupted run never leaves half a file.
- **Chunking (`src/extract/chunks.py`):** Energy-Charts is requested per quarter and Open-Meteo per year,
  which keeps responses small. Chunks that touch the last 7 days are re-downloaded, because recent data can still be revised.
- **What is downloaded:**

  | Source | Endpoint | Granularity | Scope |
  |---|---|---|---|
  | Energy-Charts | `/public_power` | hourly (15-min since 2025) | generation by type + load, 5 countries |
  | Energy-Charts | `/price` | hourly (15-min since Oct 2025) | day-ahead prices, 5 bidding zones |
  | Energy-Charts | `/installed_power` | yearly | installed capacity by type |
  | PVGIS | `/PVcalc` | annual + monthly | 20 locations at optimal angles; Serbian cities also on a tilt × direction grid |
  | Open-Meteo | `/archive` | hourly | irradiance, cloud cover, temperature for 20 locations |

- **Parsers** turn each raw JSON into a tidy pandas DataFrame (long format, UTC timestamps).
  They are unit-tested in `tests/test_extract.py` (`pytest`).

---

## Step 4 — The database (PostgreSQL in Docker)

### In simple words
The data needs a proper home where it can be cleaned, joined and queried with SQL, and where Power BI
can read it. We use PostgreSQL, the most popular open-source database, running inside Docker.
Docker is like a ready-made box with the database preinstalled: one command starts it, and anyone who
downloads this project gets exactly the same setup.

### In detail
- `docker-compose.yml` defines one service, `db`, using the `postgres:17` image:
  - credentials come from `.env` (copy `.env.example` and set a password),
  - port `5432` is exposed on `localhost`, so Python and Power BI connect as if it were installed locally,
  - data lives in the named volume `pgdata`, so it survives `docker compose down`,
  - a health check (`pg_isready`) reports when the database is ready.
- Start it: `docker compose up -d`. Check it: `docker exec solar_pv_db psql -U postgres -d solar_pv -c "select version();"`.
- Why Docker instead of a local install: it is reproducible, takes one command, and leaves nothing behind on the machine.

---

## Step 5 — Loading and shaping the data (raw → staging → mart)

### In simple words
We moved all the downloaded files into the database in three stages. First, a **raw** copy exactly as received.
Then a **cleaned** version where everything is on the same hourly clock and power plants are grouped into
simple categories (solar, wind, hydro, coal…). Finally, a **mart**: tidy tables designed for charts and analysis.
Keeping the stages separate means any mistake can be traced back, and the whole database can be rebuilt with one command.

### In detail
- **Run everything:** `python -m src.pipeline` (or `--skip-extract` to rebuild only the database from cached files).
- **Raw load (`src/load/load_postgres.py`):** each table is truncated and refilled with PostgreSQL `COPY`
  (≈ 10.7 M generation rows in about 2 minutes). Duplicates on the primary key are dropped first, so reloading is always safe.
- **Staging (`sql/02_staging.sql`):**
  - `production_type_map` groups 23 Energy-Charts series into 9 categories. Share and consumption series are excluded.
  - 15-minute values become hourly. MW averaged over an hour equals the MWh produced in that hour.
  - Prices become an hourly mean, and the number of negative 15-minute intervals is kept.
  - Open-Meteo stamps each hour at its **end**, so weather is shifted by −1 h to line up with the energy data, which is stamped at the **start**.
- **Mart (`sql/03_marts.sql`):** star schema with `fact_country_hourly` (≈ 300 k rows) plus capacity, PV-yield and calendar tables.
  SQL techniques used: CTEs, conditional aggregation (`FILTER`), window functions (`LAG`), time-zone conversion.
- **Quality checks:** row counts per year, NULL counts and plausibility of annual totals. See `docs/data_dictionary.md`.

### First finding
Serbia's day-ahead price was **never negative from 2020 to 2025**. The first negative price came on **10 May 2026**,
on 8 days between May and July, always between 08:00 and 16:00. In **79 %** of those 15-minute intervals,
Hungary's price was negative at the same time. Serbia has very little solar of its own (~0.19 GW), so this suggests
the negative prices are **imported from neighbouring markets** rather than caused by Serbian solar.

---

## Step 6 — Estimating Serbia's hourly solar output

### In simple words
Serbia doesn't publish how much electricity its solar panels produce each hour, so we estimated it.
We taught a model how weather (sunshine, clouds, temperature) turns into solar output, using the four
neighbours that *do* publish their data. To check that it works, we hid one country at a time, predicted it from
the other three, and compared the prediction with the real numbers. Then we applied the model to Serbian
weather and scaled it to the amount of solar installed in Serbia.

### In detail
- **Code:** `src/estimate/serbia_solar.py` (run with `python -m src.estimate.serbia_solar`, or as part of `src.pipeline`).
- **Why not just capacity × weather?** The neighbours' reported capacities are year-end snapshots that partly miss
  rooftop systems. Real output per installed kW ranged from 536 to 1,449 kWh/kW per year, so dividing by reported
  capacity would mostly add noise.
- **Shape (how output moves hour by hour):**
  - Target: each country's solar output ÷ its own *rolling peak* (90th percentile of daily maxima in a 91-day window).
    This removes the capacity level and keeps only the weather-driven pattern.
  - Features: irradiance (global, direct, diffuse), temperature, cloud cover, hour of day and day of year (as sin/cos),
    and irradiance × season (tilted panels gain relatively more in winter).
  - Model: `HistGradientBoostingRegressor` (scikit-learn).
- **Validation: leave one country out** (train on 3, predict the 4th, 2020–2025):

  | Metric (mean of 4 held-out countries) | Baseline: normalised irradiance | Model |
  |---|---|---|
  | Hourly R² | 0.936 | **0.942** |
  | Daily error (nMAE) | 14.2 % | **12.9 %** |
  | Monthly error (WAPE) | 7.6 % | **6.6 %** |
  | Total bias | +3.5 % | **+0.1 %** |

  The weather → output relationship is mostly captured by irradiance alone. The model's main gain is removing
  the systematic bias and handling cloudy days a bit better.
- **Level (how much energy):** `solar_mwh = shape × k × capacity_MW`, where `k` makes one year of output equal
  *PVGIS yield for Serbia (1,250 kWh/kWp) × realisation ratio*. The realisation ratio (real ÷ PVGIS yield on the neighbours)
  has p25/p50/p75 = 0.57 / 0.73 / 0.90, which gives the low / central / high estimate (central ≈ 909 kWh/kW).
- **Capacity:** year-end values interpolated linearly. 2026 has no reported value yet, so the 2025 increment
  (+0.12 GW) is assumed again (flagged as an assumption).
- **Result:** Serbian solar ≈ 13 GWh (2023), 47 GWh (2024), 116 GWh (2025, range 92–144) and 216 GWh in 2026 so far.
  That is well under 1 % of Serbia's ≈ 34 TWh annual demand.
- **Two bugs found and covered by tests (`tests/test_estimate.py`):** missing early capacity years produced NaN,
  and database timestamps arriving in microseconds (not nanoseconds) broke the interpolation silently.

### Finding
During Serbia's negative-price hours in 2026, Serbian solar covered only **≈ 3 %** of demand.
In Hungary's negative-price hours it was **≈ 78 %**. Serbia's negative prices are imported through the coupled
regional market. Domestic solar cannot explain them.
