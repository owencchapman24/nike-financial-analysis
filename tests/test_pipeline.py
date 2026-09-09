from pathlib import Path

from nike_financial_analysis.pipeline import write_csv
from nike_financial_analysis.validation import (
    scan_generated_text,
    validate_historical_rows,
)


def historical_row(year: int) -> dict[str, str]:
    return {
        "fiscal_year": f"FY{year}",
        "period_end": f"{year}-05-31",
        "revenue": "100",
        "cost_of_revenue": "60",
        "gross_profit": "40",
        "total_selling_and_administrative_expense": "30",
        "derived_operating_income": "10",
        "operating_margin": "0.1",
        "income_before_income_taxes": "12",
        "interest_income_expense_nonoperating_net": "1",
        "other_nonoperating_income_expense": "1",
        "notes_payable_and_short_term_borrowings": "1",
        "current_portion_long_term_debt": "9",
        "noncurrent_long_term_debt": "20",
        "total_interest_bearing_debt": "30",
        "current_operating_lease_liabilities": "4",
        "noncurrent_operating_lease_liabilities": "6",
        "total_operating_lease_liabilities": "10",
        "revenue_status": "selected",
        "gross_profit_status": "selected",
        "total_selling_and_administrative_expense_status": "selected",
        "derived_operating_income_status": "calculated",
        "income_before_income_taxes_status": "selected",
        "interest_income_expense_nonoperating_net_status": "selected",
        "other_nonoperating_income_expense_status": "selected",
        "operating_margin_status": "calculated",
        "notes_payable_and_short_term_borrowings_status": "selected",
        "current_portion_long_term_debt_status": "selected",
        "noncurrent_long_term_debt_status": "selected",
        "total_interest_bearing_debt_status": "calculated",
        "current_operating_lease_liabilities_status": "selected",
        "noncurrent_operating_lease_liabilities_status": "selected",
        "total_operating_lease_liabilities_status": "calculated",
    }


def test_validation_requires_exact_requested_period_mapping():
    rows = [historical_row(year) for year in range(2022, 2027)]

    checks = {check.check_id: check for check in validate_historical_rows(rows)}

    assert checks["five_requested_periods"].status == "pass"
    assert checks["unique_chronological_period_ends"].status == "pass"
    assert checks["requested_period_mapping"].status == "pass"
    assert checks["gross_profit_equation"].status == "pass"
    assert checks["derived_operating_income_formula"].status == "pass"
    assert checks["derived_operating_income_crosscheck"].status == "pass"
    assert checks["operating_margin_formula"].status == "pass"
    assert checks["debt_component_equation"].status == "pass"
    assert checks["operating_lease_component_equation"].status == "pass"


def test_validation_rejects_failed_operating_income_crosscheck():
    rows = [historical_row(year) for year in range(2022, 2027)]
    rows[2]["income_before_income_taxes"] = "13.1"

    checks = {check.check_id: check for check in validate_historical_rows(rows)}

    assert checks["derived_operating_income_formula"].status == "pass"
    assert checks["derived_operating_income_crosscheck"].status == "fail"


def test_validation_rejects_debt_total_that_omits_notes_payable():
    rows = [historical_row(year) for year in range(2022, 2027)]
    rows[0]["total_interest_bearing_debt"] = "29"

    checks = {check.check_id: check for check in validate_historical_rows(rows)}

    assert checks["debt_component_equation"].status == "fail"


def test_validation_rejects_calculation_using_manual_review_input():
    rows = [historical_row(year) for year in range(2022, 2027)]
    rows[0]["notes_payable_and_short_term_borrowings"] = ""
    rows[0]["notes_payable_and_short_term_borrowings_status"] = "manual_review"
    rows[0]["total_interest_bearing_debt"] = "29"

    checks = {check.check_id: check for check in validate_historical_rows(rows)}

    assert checks["manual_review_not_used_in_calculations"].status == "fail"


def test_validation_rejects_out_of_order_periods():
    rows = [historical_row(year) for year in range(2022, 2027)]
    rows[1], rows[2] = rows[2], rows[1]

    checks = {check.check_id: check for check in validate_historical_rows(rows)}

    assert checks["unique_chronological_period_ends"].status == "fail"
    assert checks["requested_period_mapping"].status == "fail"


def test_csv_writes_are_deterministic(tmp_path):
    output = tmp_path / "output.csv"
    rows = [{"metric": "revenue", "value": "100"}]

    write_csv(output, rows)
    first = output.read_bytes()
    write_csv(output, rows)

    assert output.read_bytes() == first
    assert b"\r\n" not in first
    assert first.endswith(b"\n")


def test_generated_output_privacy_scan(tmp_path):
    safe = tmp_path / "safe.csv"
    safe.write_text("metric,value\nrevenue,100\n", encoding="utf-8")
    unsafe = tmp_path / "unsafe.csv"
    unsafe.write_text("path,C:\\Users\\example\n", encoding="utf-8")

    assert scan_generated_text([safe]).status == "pass"
    assert scan_generated_text([unsafe]).status == "fail"
