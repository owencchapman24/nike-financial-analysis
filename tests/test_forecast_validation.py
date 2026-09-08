from copy import deepcopy
from decimal import Decimal

from nike_financial_analysis.forecast import normalized_tax_expense
from nike_financial_analysis.forecast_validation import (
    FORECAST_YEARS,
    REQUIRED_DRIVERS,
    SCENARIOS,
    validate_assumption_rows,
)


def approved_rows():
    return [
        {
            "scenario": scenario,
            "fiscal_year": year,
            "driver": driver,
            "value": "0.210" if driver == "normalized_tax_rate" else (
                "0.45" if driver == "gross_margin" else
                "0.33" if driver == "sga_percent_revenue" else
                "0.02"
            ),
            "unit": "decimal",
            "source_id": "FS01",
            "owner_status": "approved",
        }
        for scenario in SCENARIOS
        for year in FORECAST_YEARS
        for driver in REQUIRED_DRIVERS
    ]


def test_exact_assumption_grid_and_approval_are_required():
    rows = approved_rows()
    checks = validate_assumption_rows(rows)
    assert all(check.status == "pass" for check in checks)

    missing = rows[:-1]
    assert validate_assumption_rows(missing)[0].status == "fail"

    duplicate = [*rows, deepcopy(rows[0])]
    assert validate_assumption_rows(duplicate)[0].status == "fail"

    proposed = deepcopy(rows)
    proposed[0]["owner_status"] = "proposed"
    assert any(check.status == "fail" for check in validate_assumption_rows(proposed))


def test_invalid_units_and_valuation_drivers_fail():
    rows = approved_rows()
    rows[0]["unit"] = "percent"
    checks = validate_assumption_rows(rows)
    assert next(c for c in checks if c.check_id == "assumption_units").status == "fail"


def test_negative_operating_income_has_no_automatic_tax_benefit():
    assert normalized_tax_expense(Decimal("100"), Decimal("0.21")) == Decimal("21.00")
    assert normalized_tax_expense(Decimal("0"), Decimal("0.21")) == Decimal("0")
    assert normalized_tax_expense(Decimal("-100"), Decimal("0.21")) == Decimal("0")
