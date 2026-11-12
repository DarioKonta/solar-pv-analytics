from datetime import date

from src.extract.chunks import is_recent, quarters, years
from src.extract.energy_charts import parse_installed_power, parse_price, parse_public_power
from src.extract.open_meteo import parse_hourly
from src.extract.pvgis import parse_pvcalc


def test_quarters_cover_range_without_gaps():
    q = quarters(date(2020, 2, 15), date(2021, 1, 10))
    assert q[0] == (date(2020, 2, 15), date(2020, 3, 31))
    assert q[-1] == (date(2021, 1, 1), date(2021, 1, 10))
    assert len(q) == 5
    for (_, end), (nxt, _) in zip(q, q[1:]):
        assert (nxt - end).days == 1


def test_years_and_recent():
    assert years(date(2020, 6, 1), date(2021, 3, 1)) == [
        (date(2020, 6, 1), date(2020, 12, 31)), (date(2021, 1, 1), date(2021, 3, 1))]
    assert is_recent(date(2026, 11, 10), today=date(2026, 11, 12))
    assert not is_recent(date(2026, 1, 1), today=date(2026, 11, 12))


def test_parse_public_power_long_format():
    raw = {"unix_seconds": [0, 3600],
           "production_types": [{"name": "Solar", "data": [0, 5.5]},
                                {"name": "Load", "data": [100, None]}]}
    df = parse_public_power(raw, "hu")
    assert len(df) == 4
    assert set(df.columns) == {"ts_utc", "country", "production_type", "mw"}
    assert df.loc[df.production_type == "Solar", "mw"].tolist() == [0, 5.5]
    assert df["mw"].isna().sum() == 1


def test_parse_price_and_capacity():
    p = parse_price({"unix_seconds": [0], "price": [-12.5], "unit": "EUR / MWh"}, "BG")
    assert p.iloc[0].price_eur_mwh == -12.5 and p.iloc[0].bzn == "BG"
    c = parse_installed_power({"time": ["2024", "2025"],
                               "production_types": [{"name": "Solar AC", "data": [0.07, 0.19]}]}, "rs")
    assert c.year.tolist() == [2024, 2025] and c.gw.tolist() == [0.07, 0.19]


def test_parse_pvcalc_and_weather():
    raw = {"inputs": {"mounting_system": {"fixed": {"slope": {"value": 36}, "azimuth": {"value": -3}}}},
           "outputs": {"totals": {"fixed": {"E_y": 1256.5, "H(i)_y": 1610.0, "SD_y": 50.0, "l_total": -22.0}}}}
    row = parse_pvcalc(raw, "Belgrade", "optimal")
    assert row["yield_kwh_per_kwp"] == 1256.5 and row["tilt_deg"] == 36
    w = parse_hourly({"hourly": {"time": ["2025-06-01T00:00"], "shortwave_radiation": [0.0]}}, "Belgrade")
    assert str(w.ts_utc.dt.tz) == "UTC" and list(w.columns) == ["ts_utc", "location", "shortwave_radiation"]
