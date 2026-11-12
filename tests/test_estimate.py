import numpy as np
import pandas as pd
import pytest

from src.estimate.serbia_solar import capacity_hourly, metrics, rolling_peak


@pytest.fixture
def cap():
    return pd.DataFrame({"country_code": "rs", "year": [2018, 2019, 2023, 2024, 2025],
                         "gw": [np.nan, 0.0, 0.03, 0.07, 0.19]})


@pytest.mark.parametrize("unit", ["us", "ns"])
def test_capacity_interpolates_between_year_ends(cap, unit):
    # regression test: DB timestamps arrive in microseconds, which once broke the interpolation
    hours = pd.Series(pd.DatetimeIndex(["2025-01-01", "2025-07-02 12:00", "2026-01-01"], tz="UTC").as_unit(unit))
    mw = capacity_hourly(hours, cap, "rs")
    assert mw.iloc[0] == pytest.approx(70)          # end of 2024
    assert 120 < mw.iloc[1] < 140                   # half-way through 2025
    assert mw.iloc[2] == pytest.approx(190)         # end of 2025


def test_capacity_extrapolates_with_last_increment(cap):
    hours = pd.Series(pd.DatetimeIndex(["2027-01-01"], tz="UTC"))
    assert capacity_hourly(hours, cap, "rs").iloc[0] == pytest.approx(190 + 120)


def test_rolling_peak_ignores_cloudy_days():
    daily_max = pd.Series([100.0] * 80 + [10.0] * 11)   # a few dull days
    assert rolling_peak(daily_max).iloc[45] == pytest.approx(100)


def test_metrics_perfect_prediction():
    d = pd.DataFrame({"date_local": pd.date_range("2024-01-01", periods=48, freq="h"),
                      "y": np.tile(np.r_[np.zeros(6), np.ones(12), np.zeros(6)], 2)})
    d["pred"] = d["y"]
    m = metrics(d, "pred")
    assert m["hourly_r2"] == 1 and m["daily_nmae_pct"] == 0 and m["total_bias_pct"] == 0
