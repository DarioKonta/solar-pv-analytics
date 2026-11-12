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
