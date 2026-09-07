from decimal import Decimal
from pathlib import Path

import pytest

from nike_financial_analysis.analysis import (
    EXPECTED_FISCAL_YEARS,
    KPI_DEFINITIONS,
    build_analysis,
    build_kpi_rows,
    build_summary_rows,
    load_historical_data,
)


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_DATA = ROOT / "data/processed/nike_financials.csv"


def analysis_fixture():
    return build_analysis(load_historical_data(HISTORICAL_DATA))


def result_for(analysis, year: str, metric: str):
    return analysis.phase3_metrics[(year, metric)]


def test_input_contract_has_exact_requested_periods():
    frame = load_historical_data(HISTORICAL_DATA)

    assert tuple(frame["fiscal_year"]) == EXPECTED_FISCAL_YEARS
    assert tuple(frame["period_end"]) == tuple(
        f"{year[2:]}-05-31" for year in EXPECTED_FISCAL_YEARS
    )


def test_input_contract_rejects_missing_columns_and_unknown_statuses(tmp_path):
    frame = load_historical_data(HISTORICAL_DATA)
    missing_column = frame.drop(columns=["inventory_status"])
    missing_path = tmp_path / "missing.csv"
    missing_column.to_csv(missing_path, index=False, lineterminator="\n")

    with pytest.raises(ValueError, match="missing required columns"):
        load_historical_data(missing_path)

    invalid_status = frame.copy()
    invalid_status.loc[0, "inventory_status"] = "approved"
    invalid_path = tmp_path / "invalid.csv"
    invalid_status.to_csv(invalid_path, index=False, lineterminator="\n")

    with pytest.raises(ValueError, match="Unsupported status"):
        load_historical_data(invalid_path)


def test_phase3_formulas_use_exact_decimal_arithmetic():
    analysis = analysis_fixture()

    assert result_for(analysis, "FY2022", "sga_as_percent_of_revenue").value == (
        Decimal("14804") / Decimal("46710")
    )
    assert result_for(
        analysis, "FY2022", "cash_and_short_term_investments"
    ).value == Decimal("12997")
    assert result_for(analysis, "FY2022", "current_ratio").value == (
        Decimal("28213") / Decimal("10730")
    )
    assert result_for(analysis, "FY2022", "net_working_capital").value == Decimal(
        "17483"
    )
    assert result_for(
        analysis, "FY2022", "net_debt_after_cash_and_short_term_investments"
    ).value == Decimal("-3567")


def test_average_balance_efficiency_formulas_and_365_day_convention():
    analysis = analysis_fixture()

    expected_receivables_days = (
        ((Decimal("4667") + Decimal("4131")) / Decimal("2"))
        / Decimal("51217")
        * Decimal("365")
    )
    expected_inventory_days = (
        ((Decimal("8420") + Decimal("8454")) / Decimal("2"))
        / Decimal("28925")
        * Decimal("365")
    )

    assert result_for(
        analysis, "FY2023", "receivables_days_proxy"
    ).value == expected_receivables_days
    assert result_for(
        analysis, "FY2023", "inventory_days"
    ).value == expected_inventory_days


def test_fy2022_efficiency_metrics_are_explicitly_not_applicable():
    analysis = analysis_fixture()

    for metric in ("receivables_days_proxy", "inventory_days"):
        result = result_for(analysis, "FY2022", metric)
        assert result.status == "not_applicable"
        assert result.value is None
        assert "FY2021 opening balances" in result.reason


def test_growth_and_period_wide_kpis():
    analysis = analysis_fixture()

    assert result_for(
        analysis, "FY2023", "accounts_receivable_growth"
    ).value == (Decimal("4131") / Decimal("4667") - Decimal("1"))
    assert result_for(analysis, "FY2026", "revenue_cumulative_change").value == Decimal(
        "-312"
    )
    assert result_for(
        analysis, "FY2026", "revenue_cumulative_change_percent"
    ).value == Decimal("-312") / Decimal("46710")
    assert result_for(analysis, "FY2026", "peak_revenue").value == Decimal("51362")
    assert analysis.dynamic_notes[("FY2026", "peak_revenue")].endswith("FY2024.")


def test_manual_review_and_missing_inputs_do_not_flow_into_calculations():
    frame = load_historical_data(HISTORICAL_DATA).copy()
    frame.loc[0, "current_liabilities"] = ""
    frame.loc[0, "current_liabilities_status"] = "manual_review"
    analysis = build_analysis(frame)

    current_ratio = result_for(analysis, "FY2022", "current_ratio")
    net_working_capital = result_for(analysis, "FY2022", "net_working_capital")

    assert current_ratio.value is None
    assert current_ratio.status == "manual_review"
    assert net_working_capital.value is None
    assert net_working_capital.status == "manual_review"


def test_division_by_zero_is_explicit():
    frame = load_historical_data(HISTORICAL_DATA).copy()
    frame.loc[0, "current_liabilities"] = "0"
    analysis = build_analysis(frame)

    result = result_for(analysis, "FY2022", "current_ratio")

    assert result.value is None
    assert result.status == "missing"
    assert "zero" in result.reason


def test_tables_preserve_phase2_values_and_ratio_units():
    analysis = analysis_fixture()
    kpi_rows = build_kpi_rows(analysis)
    summary_rows = build_summary_rows(analysis)
    lookup = {(row["fiscal_year"], row["metric"]): row for row in kpi_rows}

    assert len(summary_rows) == 5
    assert len(kpi_rows) == len(KPI_DEFINITIONS) * 5
    assert lookup[("FY2022", "gross_margin")]["value"] == "0.459837"
    assert lookup[("FY2022", "cash_conversion")]["value"] == "0.858088"
    assert lookup[("FY2022", "cash_conversion")]["unit"] == "x"
    assert lookup[("FY2026", "notes_payable_and_short_term_borrowings")][
        "value_source"
    ] == "filing_supported_documented_zero"
    assert summary_rows[-1]["net_debt_sign_convention"] == (
        "negative value means net cash"
    )


def test_kpi_identifiers_are_unique():
    identifiers = [definition.metric for definition in KPI_DEFINITIONS]

    assert len(identifiers) == len(set(identifiers))
