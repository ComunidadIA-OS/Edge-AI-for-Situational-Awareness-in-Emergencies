"""Smoke tests for the Balbi 2015 quadratic spread-rate model.

The exact ROS for each scenario is empirical, so the tests pin the model on
monotonic behavior and order-of-magnitude bounds rather than specific values.
"""
from __future__ import annotations

import pytest

from convergence.forecast import predict_spread_rate_balbi
from convergence.fuels import FUEL_MODELS, get_fuel_model_or_default


def test_still_air_low_humidity_grass_in_reasonable_range():
    fm = FUEL_MODELS[1]
    rate = predict_spread_rate_balbi(0.0, 30.0, 25.0, fm, slope_deg=0.0)
    assert 0.5 < rate < 200.0


def test_strong_wind_increases_spread_rate_monotonically():
    fm = FUEL_MODELS[4]
    rates = [
        predict_spread_rate_balbi(w, 40.0, 28.0, fm, slope_deg=0.0)
        for w in (0.0, 10.0, 30.0, 60.0)
    ]
    assert rates[0] < rates[1] < rates[2] < rates[3]


def test_slope_increases_spread_rate_monotonically():
    fm = FUEL_MODELS[4]
    rates = [
        predict_spread_rate_balbi(20.0, 40.0, 28.0, fm, slope_deg=s)
        for s in (0.0, 15.0, 30.0, 45.0)
    ]
    assert rates[0] < rates[1] < rates[2] < rates[3]


def test_high_humidity_reduces_spread_rate():
    fm = FUEL_MODELS[4]
    dry = predict_spread_rate_balbi(20.0, 15.0, 30.0, fm, slope_deg=0.0)
    humid = predict_spread_rate_balbi(20.0, 90.0, 30.0, fm, slope_deg=0.0)
    assert humid < dry


def test_wind_and_slope_couple_non_linearly():
    """Quadratic combination => wind+slope together > sum of marginal increases."""
    fm = FUEL_MODELS[4]
    base = predict_spread_rate_balbi(0.0, 40.0, 28.0, fm, slope_deg=0.0)
    wind_only = predict_spread_rate_balbi(30.0, 40.0, 28.0, fm, slope_deg=0.0)
    slope_only = predict_spread_rate_balbi(0.0, 40.0, 28.0, fm, slope_deg=30.0)
    combined = predict_spread_rate_balbi(30.0, 40.0, 28.0, fm, slope_deg=30.0)

    marginal_sum = (wind_only - base) + (slope_only - base)
    assert combined - base > marginal_sum, (
        f"expected non-linear coupling: combined-base={combined - base:.1f} "
        f"should exceed marginal_sum={marginal_sum:.1f}"
    )


def test_rate_capped_below_extreme_ceiling():
    fm = FUEL_MODELS[3]
    rate = predict_spread_rate_balbi(150.0, 5.0, 45.0, fm, slope_deg=60.0)
    assert rate <= 8000.0


def test_negative_wind_input_handled():
    fm = FUEL_MODELS[1]
    rate = predict_spread_rate_balbi(-10.0, 40.0, 25.0, fm, slope_deg=0.0)
    assert rate > 0.0


@pytest.mark.parametrize("fuel_id", list(FUEL_MODELS.keys()))
def test_all_fuel_models_produce_finite_positive_rates(fuel_id):
    fm = get_fuel_model_or_default(fuel_id)
    rate = predict_spread_rate_balbi(15.0, 50.0, 25.0, fm, slope_deg=5.0)
    assert 0.0 < rate < 8000.0
