from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from nike_financial_analysis.forecast import (
    build_forecast_model,
    build_long_rows,
    calculate_forecast_rows,
    operating_nwc_proxy,
)


ROOT = Path(__file__).resolve().parents[1]


def test_operating_nwc_proxy_excludes_approved_balances():
    row = {
        "current_assets": "1000",
        "current_assets_status": "selected",
        "cash_and_cash_equivalents": "100",
        "cash_and_cash_equivalents_status": "selected",
        "short_term_investments": "50",
        "short_term_investments_status": "selected",
        "current_liabilities": "600",
        "current_liabilities_status": "selected",
        "notes_payable_and_short_term_borrowings": "10",
        "notes_payable_and_short_term_borrowings_status": "selected",
        "current_portion_long_term_debt": "40",
        "current_portion_long_term_debt_status": "selected",
        "current_operating_lease_liabilities": "60",
        "current_operating_lease_liabilities_status": "selected",
    }
    assert operating_nwc_proxy(row) == Decimal("360")


def test_approved_forecast_exact_values_and_fcff_identity():
    model = build_forecast_model(ROOT)
    assert len(model.assumption_rows) == 105
    assert len(model.forecast_rows) == 15
    by_key = {(row.scenario, row.fiscal_year): row for row in model.forecast_rows}

    base_2027 = by_key[("base", "FY2027")]
    assert base_2027.revenue == Decimal("45470.040")
    assert base_2027.operating_nwc_proxy == Decimal("5047.174440")
    assert base_2027.change_in_operating_nwc == Decimal("-459.825560")
    assert base_2027.fcff == Decimal("3127.552806800")
    assert base_2027.derived_operating_income == (
        base_2027.gross_profit - base_2027.total_selling_and_administrative_expense
    )
    assert base_2027.fcff == (
        base_2027.nopat
        + base_2027.depreciation_and_amortization
        - base_2027.capital_expenditures
        - base_2027.change_in_operating_nwc
    )

    assert by_key[("bull", "FY2031")].fcff == Decimal(
        "5994.120731873274000000000"
    )
    assert by_key[("bear", "FY2031")].fcff == Decimal(
        "2988.078840225160704000000"
    )


def test_fy2026_opening_onwc_and_fy2027_normalization():
    model = build_forecast_model(ROOT)
    opening = operating_nwc_proxy(model.historical_rows[-1])
    assert opening == Decimal("5507")
    changes = {
        row.scenario: row.change_in_operating_nwc
        for row in model.forecast_rows
        if row.fiscal_year == "FY2027"
    }
    assert changes == {
        "base": Decimal("-459.825560"),
        "bull": Decimal("-470.961080"),
        "bear": Decimal("-295.576640"),
    }


def test_actual_and_forecast_lineage_remain_distinct():
    rows = build_long_rows(build_forecast_model(ROOT))
    actual_revenue = next(
        row for row in rows
        if row["scenario"] == "actual"
        and row["fiscal_year"] == "FY2026"
        and row["metric"] == "revenue"
    )
    forecast_revenue = next(
        row for row in rows
        if row["scenario"] == "base"
        and row["fiscal_year"] == "FY2027"
        and row["metric"] == "revenue"
    )
    assert actual_revenue["status"] == "selected"
    assert actual_revenue["value_source"] == "committed_sec_reported_history"
    assert forecast_revenue["status"] == "forecast_calculated"
    assert forecast_revenue["value_source"] == "project_analyst_scenario"


def test_missing_or_unresolved_historical_input_cannot_flow():
    model = build_forecast_model(ROOT)
    history = [dict(row) for row in model.historical_rows]
    history[-1]["current_assets_status"] = "manual_review"
    with pytest.raises(ValueError, match="invalid status"):
        calculate_forecast_rows(history, model.assumption_rows)


def test_forecast_uses_decimal_objects():
    model = build_forecast_model(ROOT)
    for row in model.forecast_rows:
        for value in row.__dict__.values():
            if not isinstance(value, str):
                assert isinstance(value, Decimal)
