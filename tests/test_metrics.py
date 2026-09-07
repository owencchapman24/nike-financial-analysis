from decimal import Decimal

import pytest

from nike_financial_analysis.metrics import (
    MetricValue,
    add,
    cagr,
    revenue_growth,
    safe_ratio,
    subtract,
)


def selected(value: str) -> MetricValue:
    return MetricValue(Decimal(value), "selected", "fixture")


def test_margin_and_free_cash_flow_formulas():
    margin = safe_ratio(selected("21479"), selected("46710"))
    free_cash_flow = subtract(selected("5188"), selected("758"))

    assert margin.status == "calculated"
    assert margin.value == Decimal("21479") / Decimal("46710")
    assert free_cash_flow == MetricValue(
        Decimal("4430"), "calculated", "Calculated from validated inputs."
    )


def test_debt_components_include_a_documented_zero():
    documented_zero = MetricValue(Decimal("0"), "documented_zero", "fixture")

    result = add(documented_zero, selected("1000"), selected("5942"))

    assert result == MetricValue(
        Decimal("6942"), "calculated", "Calculated from validated inputs."
    )


@pytest.mark.parametrize("blocked_status", ["missing", "manual_review"])
def test_add_never_treats_a_blocked_component_as_zero(blocked_status):
    blocked = MetricValue(None, blocked_status, "fixture")

    result = add(selected("10"), blocked, selected("20"))

    assert result.value is None
    assert result.status == blocked_status


def test_division_by_zero_returns_missing():
    result = safe_ratio(selected("100"), selected("0"))

    assert result.value is None
    assert result.status == "missing"


@pytest.mark.parametrize("blocked_status", ["missing", "manual_review"])
def test_blocked_input_never_produces_calculated_metric(blocked_status):
    blocked = MetricValue(None, blocked_status, "fixture")

    result = safe_ratio(blocked, selected("100"))

    assert result.value is None
    assert result.status == blocked_status


def test_revenue_growth_formula():
    result = revenue_growth(selected("110"), selected("100"))

    assert result.value == Decimal("0.1")
    assert result.status == "calculated"


def test_five_observation_cagr_uses_four_intervals():
    result = cagr(selected("100"), selected("121.550625"), intervals=4)

    assert result.value == pytest.approx(Decimal("0.05"))
    assert "4 growth intervals" in result.reason


def test_cagr_rejects_nonpositive_interval_count():
    with pytest.raises(ValueError, match="positive"):
        cagr(selected("100"), selected("110"), intervals=0)
