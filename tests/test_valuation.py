from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from nike_financial_analysis.valuation import (
    _discount,
    build_valuation_model,
    calculate_scenario_valuation,
)


ROOT = Path(__file__).resolve().parents[1]


def test_formula_derived_wacc_and_approved_headline_values():
    model = build_valuation_model(ROOT)
    wacc = model.wacc_primary

    assert wacc.unlevered_beta == Decimal(
        "0.9262442979137390552372716463085071884121"
    )
    assert wacc.wacc == Decimal(
        "0.08487443827540290261078735104164066393683"
    )
    assert wacc.equity_weight + wacc.debt_weight == Decimal("1")

    values = {
        result.scenario: result.value_per_share
        for result in model.scenario_valuations
    }
    assert values == {
        "base": Decimal("47.80676026082300158921320762"),
        "bull": Decimal("59.54761692014691443357771265"),
        "bear": Decimal("30.05741351721207083337826683"),
    }


def test_date_based_discounting_uses_xnpv_365_day_exponent():
    exponent, factor, present_value = _discount(
        Decimal("100"),
        cash_flow_date=date(2027, 5, 31),
        model_date=date(2026, 9, 4),
        wacc=Decimal("0.10"),
    )
    assert exponent == Decimal("269") / Decimal("365")
    assert factor == Decimal("1") / Decimal("1.10") ** exponent
    assert present_value == Decimal("100") * factor

    leap_exponent, _, _ = _discount(
        Decimal("100"),
        cash_flow_date=date(2028, 5, 31),
        model_date=date(2026, 9, 4),
        wacc=Decimal("0.10"),
    )
    assert leap_exponent == Decimal("635") / Decimal("365")


def test_terminal_value_is_independently_discounted_from_fy2031_date():
    model_date = date(2026, 9, 4)
    wacc = Decimal("0.10")
    scenario = "base"
    forecast = {
        (scenario, f"FY{year}", "fcff"): Decimal("0")
        for year in range(2027, 2032)
    }
    forecast.update(
        {
            (scenario, "FY2031", "revenue"): Decimal("100"),
            (scenario, "FY2031", "gross_margin"): Decimal("0.20"),
            (scenario, "FY2031", "sga_percent_revenue"): Decimal("0.10"),
            (scenario, "FY2031", "normalized_tax_rate"): Decimal("0"),
            (scenario, "FY2031", "da_percent_revenue"): Decimal("0"),
            (scenario, "FY2031", "capex_percent_revenue"): Decimal("0"),
            (scenario, "FY2031", "operating_nwc_percent_revenue"): Decimal("0"),
            (scenario, "FY2031", "operating_nwc_proxy"): Decimal("0"),
        }
    )

    result = calculate_scenario_valuation(
        scenario,
        forecast,
        model_date=model_date,
        wacc=wacc,
        terminal_growth=Decimal("0"),
        cash_and_investments=Decimal("0"),
        carrying_debt=Decimal("0"),
        preferred_stock=Decimal("0"),
        diluted_proxy_shares=Decimal("1"),
        basic_shares=Decimal("1"),
        reference_market_price=Decimal("1"),
        carrying_wacc=wacc,
    )

    terminal_value = Decimal("100")
    correct_exponent = Decimal((date(2031, 5, 31) - model_date).days) / Decimal(
        "365"
    )
    one_year_late_exponent = Decimal(
        (date(2032, 5, 31) - model_date).days
    ) / Decimal("365")
    expected = terminal_value / (Decimal("1") + wacc) ** correct_exponent
    one_year_late = terminal_value / (
        Decimal("1") + wacc
    ) ** one_year_late_exponent

    assert result.terminal.fcff == Decimal("10.0")
    assert result.terminal_value == terminal_value
    assert result.pv_terminal_value == expected
    assert result.pv_terminal_value != one_year_late


def test_terminal_bridge_and_equity_bridge_hold_exactly():
    model = build_valuation_model(ROOT)
    forecast = {
        (row["scenario"], row["fiscal_year"], row["metric"]): Decimal(row["value"])
        for row in model.forecast_rows
        if row["scenario"] in {"base", "bull", "bear"} and row["value"]
    }
    for value in model.scenario_valuations:
        terminal = value.terminal
        assert terminal.revenue == (
            forecast[(value.scenario, "FY2031", "revenue")]
            * (Decimal("1") + value.terminal_growth)
        )
        assert terminal.fcff == (
            terminal.nopat
            + terminal.depreciation_and_amortization
            - terminal.capital_expenditures
            - terminal.change_in_operating_nwc
        )
        assert value.enterprise_value == (
            value.pv_explicit_fcff + value.pv_terminal_value
        )
        assert value.equity_value == (
            value.enterprise_value
            + Decimal("9027")
            - Decimal("7942")
            - Decimal("0.3")
        )
        assert value.value_per_share == (
            value.equity_value / Decimal("1484.698703")
        )
        assert value.basic_share_value_cross_check == (
            value.equity_value / Decimal("1483.498703")
        )
        assert value.basic_share_value_cross_check > value.value_per_share


def test_wacc_must_exceed_terminal_growth():
    model = build_valuation_model(ROOT)
    forecast = {
        (row["scenario"], row["fiscal_year"], row["metric"]): Decimal(row["value"])
        for row in model.forecast_rows
        if row["scenario"] in {"base", "bull", "bear"} and row["value"]
    }
    with pytest.raises(ValueError, match="WACC must exceed terminal growth"):
        calculate_scenario_valuation(
            "base",
            forecast,
            model_date=date(2026, 9, 4),
            wacc=Decimal("0.025"),
            terminal_growth=Decimal("0.025"),
            cash_and_investments=Decimal("9027"),
            carrying_debt=Decimal("7942"),
            preferred_stock=Decimal("0.3"),
            diluted_proxy_shares=Decimal("1484.698703"),
            basic_shares=Decimal("1483.498703"),
            reference_market_price=Decimal("38.40"),
            carrying_wacc=Decimal("0.085"),
        )


def test_sensitivity_center_and_direction_are_coherent():
    model = build_valuation_model(ROOT)
    base = next(value for value in model.scenario_valuations if value.scenario == "base")
    center = next(cell for cell in model.sensitivity_cells if cell.is_center)
    assert center.value_per_share == base.value_per_share
    assert len(model.sensitivity_cells) == 25

    by_wacc = sorted(
        (cell for cell in model.sensitivity_cells if cell.terminal_growth == Decimal("0.025")),
        key=lambda cell: cell.wacc,
    )
    assert all(
        left.value_per_share > right.value_per_share
        for left, right in zip(by_wacc, by_wacc[1:])
    )
