from copy import deepcopy
from pathlib import Path

from nike_financial_analysis.valuation import build_valuation_model
from nike_financial_analysis.valuation_validation import (
    validate_assumptions,
    validate_forecast_contract,
)


ROOT = Path(__file__).resolve().parents[1]


def test_assumption_register_requires_exact_grid_approval_and_sources():
    model = build_valuation_model(ROOT)
    rows = [dict(row) for row in model.assumption_rows]
    source_ids = {row["source_id"] for row in model.source_rows}
    assert all(check.status == "pass" for check in validate_assumptions(rows, source_ids))

    assert validate_assumptions(rows[:-1], source_ids)[0].status == "fail"
    duplicate = [*rows, deepcopy(rows[0])]
    assert validate_assumptions(duplicate, source_ids)[0].status == "fail"

    unapproved = deepcopy(rows)
    unapproved[0]["owner_status"] = "proposed"
    checks = validate_assumptions(unapproved, source_ids)
    assert next(c for c in checks if c.check_id == "valuation_owner_approval").status == "fail"

    unresolved_source = deepcopy(rows)
    unresolved_source[0]["source_ids"] = "UNKNOWN"
    checks = validate_assumptions(unresolved_source, source_ids)
    assert next(c for c in checks if c.check_id == "valuation_source_resolution").status == "fail"


def test_forecast_contract_rejects_missing_or_invalid_rows():
    model = build_valuation_model(ROOT)
    rows = [dict(row) for row in model.forecast_rows]
    assert all(check.status == "pass" for check in validate_forecast_contract(rows))

    required = next(
        row
        for row in rows
        if row["scenario"] == "base"
        and row["fiscal_year"] == "FY2027"
        and row["metric"] == "fcff"
    )
    rows.remove(required)
    assert validate_forecast_contract(rows)[0].status == "fail"

    rows = [dict(row) for row in model.forecast_rows]
    required = next(
        row
        for row in rows
        if row["scenario"] == "base"
        and row["fiscal_year"] == "FY2027"
        and row["metric"] == "fcff"
    )
    required["status"] = "manual_review"
    assert validate_forecast_contract(rows)[0].status == "fail"

    rows = [dict(row) for row in model.forecast_rows]
    duplicate = next(
        row
        for row in rows
        if row["scenario"] == "base"
        and row["fiscal_year"] == "FY2027"
        and row["metric"] == "fcff"
    )
    rows.append(dict(duplicate))
    assert validate_forecast_contract(rows)[0].status == "fail"


def test_terminal_dependence_is_an_observation_not_failure():
    model = build_valuation_model(ROOT)
    observations = [
        check for check in model.checks if check.check_id == "terminal_value_dependence"
    ]
    assert len(observations) == 3
    assert {check.status for check in observations} <= {"warning", "strong_warning"}
    assert not any(check.status == "fail" for check in model.checks)
