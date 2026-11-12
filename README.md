# ☀️ Solar PV Analytics — Serbia vs. its neighbours

An end-to-end data analytics project: **public energy APIs → Python → PostgreSQL → Power BI**.
It looks at solar photovoltaic (PV) energy in South-East Europe, with **Serbia** as the focus and
Hungary, Romania, Croatia and Bulgaria as benchmarks.

> 🚧 Work in progress. Findings and dashboard screenshots will be added as the analysis is completed.

## Business questions

| # | Question | Data |
|---|----------|------|
| 1 | **Where in Serbia is rooftop PV most worth it?** Yield (kWh/kWp), optimal tilt and payback by city | PVGIS |
| 2 | **How fast is Serbian solar growing compared with its neighbours?** | Energy-Charts installed capacity |
| 3 | **What does Serbia's hourly solar output look like?** Serbia publishes no hourly solar data, so it is *estimated* and the method is validated on countries that do | Energy-Charts + Open-Meteo |
| 4 | **How does solar affect electricity prices?** Midday price dip, capture price, negative-price hours, and *when Serbia could see negative prices* | Energy-Charts day-ahead prices |
| 5 | **How much does weather drive solar output?** | Open-Meteo + Energy-Charts |

## Tech stack

| Layer | Tools |
|-------|-------|
| Extract | Python (`requests`), REST APIs with throttling, retry and raw caching |
| Store / transform | PostgreSQL 17 (Docker), SQL (`raw` → `staging` → `mart` layers, CTEs, window functions) |
| Analysis | pandas, scikit-learn, Jupyter |
| Visualisation | Power BI (DAX measures, star schema) |
| Quality | pytest, SQL data checks |

## Data sources (all free and public)

- [Energy-Charts API](https://api.energy-charts.info/) (Fraunhofer ISE): generation by source, load, day-ahead prices, installed capacity
- [PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) (EU Joint Research Centre): PV yield for any location
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api): hourly irradiance, cloud cover, temperature

## Project structure

```
config/        settings (countries, cities, date range, PV assumptions)
src/           Python pipeline: extract → load → estimate
sql/           schema, staging, marts and analysis queries
notebooks/     exploration and analysis
powerbi/       dashboard (.pbix), DAX measures, screenshots
docs/          step-by-step guide and data dictionary
tests/         unit tests
```

## How to run

Requirements: Python 3.12+, Docker Desktop, Power BI Desktop (for the dashboard).

```powershell
git clone https://github.com/DarioKonta/solar-pv-analytics.git
cd solar-pv-analytics
copy .env.example .env                  # then set PG_PASSWORD
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
docker compose up -d                    # PostgreSQL 17 on localhost:5432
.\.venv\Scripts\python -m src.extract.run   # download raw data (~30 min, cached)
```

_Loading, transformation and analysis steps will be added as they are built._

## Step-by-step guide

See [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md) for how every step was built, explained simply and then in detail.

## Author

**Dario Konta** · [GitHub](https://github.com/DarioKonta)
