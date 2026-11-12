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
