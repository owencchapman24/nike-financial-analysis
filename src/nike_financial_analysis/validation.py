"""Human-readable data-quality checks for the historical pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class ValidationCheck:
    """One stable, reviewer-readable validation result."""

    check_id: str
    scope: str
    status: str
    details: str


def _number(row: dict[str, str], metric: str) -> Decimal | None:
    text = row.get(metric, "").strip()
    return Decimal(text) if text else None


def validate_historical_rows(rows: list[dict[str, str]]) -> list[ValidationCheck]:
    """Validate shape, chronology, equations, and selection statuses."""

    checks: list[ValidationCheck] = []
    period_ends = [row["period_end"] for row in rows]
    checks.append(
        ValidationCheck(
            "five_requested_periods",
            "dataset",
            "pass" if len(rows) == 5 else "fail",
            f"Found {len(rows)} fiscal periods; expected 5.",
        )
    )
    chronology_ok = period_ends == sorted(period_ends) and len(set(period_ends)) == 5
    checks.append(
        ValidationCheck(
            "unique_chronological_period_ends",
            "dataset",
            "pass" if chronology_ok else "fail",
            "Period ends are unique and oldest-first."
            if chronology_ok
            else "Period ends are duplicated or not chronological.",
        )
    )

    expected_ends = [f"{year}-05-31" for year in range(2022, 2027)]
    checks.append(
        ValidationCheck(
            "requested_period_mapping",
            "dataset",
            "pass" if period_ends == expected_ends else "fail",
            "Fiscal periods map to May 31, 2022 through May 31, 2026.",
        )
    )

    gross_profit_ok = True
    derived_operating_income_ok = True
    operating_margin_ok = True
    operating_income_crosscheck_ok = True
    debt_ok = True
    lease_ok = True
    for row in rows:
        revenue = _number(row, "revenue")
        cost = _number(row, "cost_of_revenue")
        gross_profit = _number(row, "gross_profit")
        if None in {revenue, cost, gross_profit} or abs(revenue - cost - gross_profit) > Decimal("1"):
            gross_profit_ok = False

        selling_and_administrative = _number(
            row, "total_selling_and_administrative_expense"
        )
        derived_operating_income = _number(row, "derived_operating_income")
        pretax_income = _number(row, "income_before_income_taxes")
        interest_nonoperating = _number(
            row, "interest_income_expense_nonoperating_net"
        )
        other_nonoperating = _number(row, "other_nonoperating_income_expense")
        operating_margin = _number(row, "operating_margin")
        if (
            None
            in {
                gross_profit,
                selling_and_administrative,
                derived_operating_income,
            }
            or abs(
                gross_profit
                - selling_and_administrative
                - derived_operating_income
            )
            > Decimal("0.001")
        ):
            derived_operating_income_ok = False
        if (
            None
            in {
                derived_operating_income,
                pretax_income,
                interest_nonoperating,
                other_nonoperating,
            }
            or abs(
                derived_operating_income
                + interest_nonoperating
                + other_nonoperating
                - pretax_income
            )
            > Decimal("0.001")
        ):
            operating_income_crosscheck_ok = False
        if (
            None in {derived_operating_income, revenue, operating_margin}
            or revenue == 0
            or abs(derived_operating_income / revenue - operating_margin)
            > Decimal("0.000001")
        ):
            operating_margin_ok = False

        notes_payable = _number(row, "notes_payable_and_short_term_borrowings")
        current_long_term_debt = _number(row, "current_portion_long_term_debt")
        noncurrent_long_term_debt = _number(row, "noncurrent_long_term_debt")
        total_debt = _number(row, "total_interest_bearing_debt")
        if (
            None
            in {
                notes_payable,
                current_long_term_debt,
                noncurrent_long_term_debt,
                total_debt,
            }
            or abs(
                notes_payable
                + current_long_term_debt
                + noncurrent_long_term_debt
                - total_debt
            )
            > Decimal("0.001")
        ):
            debt_ok = False

        current_leases = _number(row, "current_operating_lease_liabilities")
        noncurrent_leases = _number(row, "noncurrent_operating_lease_liabilities")
        total_leases = _number(row, "total_operating_lease_liabilities")
        if (
            None in {current_leases, noncurrent_leases, total_leases}
            or abs(current_leases + noncurrent_leases - total_leases)
            > Decimal("0.001")
        ):
            lease_ok = False

    checks.extend(
        [
            ValidationCheck(
                "gross_profit_equation",
                "income_statement",
                "pass" if gross_profit_ok else "fail",
                "Gross profit equals revenue less cost of revenue within USD 1 million.",
            ),
            ValidationCheck(
                "derived_operating_income_formula",
                "income_statement",
                "pass" if derived_operating_income_ok else "fail",
                "Derived operating income equals gross profit less total selling and administrative expense for all five fiscal years.",
            ),
            ValidationCheck(
                "derived_operating_income_crosscheck",
                "income_statement",
                "pass" if operating_income_crosscheck_ok else "fail",
                "Derived operating income plus signed interest and other non-operating income or expense equals income before taxes for all five fiscal years.",
            ),
            ValidationCheck(
                "operating_margin_formula",
                "income_statement",
                "pass" if operating_margin_ok else "fail",
                "Operating margin equals derived operating income divided by revenue for all five fiscal years.",
            ),
            ValidationCheck(
                "debt_component_equation",
                "balance_sheet",
                "pass" if debt_ok else "fail",
                "Total interest-bearing debt equals notes payable or short-term borrowings plus current and noncurrent long-term debt for all five fiscal years.",
            ),
            ValidationCheck(
                "operating_lease_component_equation",
                "balance_sheet",
                "pass" if lease_ok else "fail",
                "Total operating lease liabilities equal current plus noncurrent components for all five fiscal years and remain outside base debt.",
            ),
        ]
    )

    status_columns = [column for column in rows[0] if column.endswith("_status")]
    allowed_statuses = {
        "selected",
        "calculated",
        "documented_zero",
        "manual_review",
        "missing",
        "not_applicable",
    }
    invalid = sorted(
        {
            row[column]
            for row in rows
            for column in status_columns
            if row[column] not in allowed_statuses
        }
    )
    checks.append(
        ValidationCheck(
            "allowed_selection_statuses",
            "dataset",
            "pass" if not invalid else "fail",
            "All result statuses use the documented vocabulary."
            if not invalid
            else "Unexpected statuses: " + ", ".join(invalid),
        )
    )

    allowed_inputs = {"selected", "calculated", "documented_zero"}
    dependencies = {
        "derived_operating_income": (
            "gross_profit",
            "total_selling_and_administrative_expense",
        ),
        "operating_margin": ("derived_operating_income", "revenue"),
        "gross_margin": ("gross_profit", "revenue"),
        "net_margin": ("net_income", "revenue"),
        "operating_cash_flow_margin": ("operating_cash_flow", "revenue"),
        "total_interest_bearing_debt": (
            "notes_payable_and_short_term_borrowings",
            "current_portion_long_term_debt",
            "noncurrent_long_term_debt",
        ),
        "total_operating_lease_liabilities": (
            "current_operating_lease_liabilities",
            "noncurrent_operating_lease_liabilities",
        ),
        "free_cash_flow": ("operating_cash_flow", "capital_expenditures"),
        "free_cash_flow_margin": ("free_cash_flow", "revenue"),
        "cash_conversion": ("operating_cash_flow", "net_income"),
    }
    blocked_calculations: list[str] = []
    for row in rows:
        for metric, inputs in dependencies.items():
            if row.get(f"{metric}_status") != "calculated":
                continue
            if any(
                row.get(f"{dependency}_status") not in allowed_inputs
                or not row.get(dependency, "").strip()
                for dependency in inputs
            ):
                blocked_calculations.append(f"{row['fiscal_year']} {metric}")
    checks.append(
        ValidationCheck(
            "manual_review_not_used_in_calculations",
            "calculated_metrics",
            "pass" if not blocked_calculations else "fail",
            "No calculated metric uses a missing or manual-review input."
            if not blocked_calculations
            else "Blocked fiscal years: " + ", ".join(blocked_calculations),
        )
    )

    core_missing = sorted(
        {
            column.removesuffix("_status")
            for row in rows
            for column in status_columns
            if row[column] == "missing"
        }
    )
    checks.append(
        ValidationCheck(
            "missing_values_disclosed",
            "dataset",
            "warning" if core_missing else "pass",
            "Missing metrics: " + ", ".join(core_missing)
            if core_missing
            else "No requested metric is silently missing.",
        )
    )
    return checks


def scan_generated_text(paths: list[Path]) -> ValidationCheck:
    """Reject obvious secrets and machine-specific paths in tracked outputs."""

    forbidden = ("SEC_USER_AGENT", "C:\\Users\\", "/Users/", "@")
    hits: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8-sig")
        if any(marker in text for marker in forbidden):
            hits.append(path.as_posix())
    return ValidationCheck(
        "generated_output_privacy_scan",
        "generated_files",
        "pass" if not hits else "fail",
        "No user-agent values, email addresses, or machine-specific user paths found."
        if not hits
        else "Potential private material found in: " + ", ".join(hits),
    )


def validation_rows(checks: list[ValidationCheck]) -> list[dict[str, str]]:
    """Convert checks to deterministic CSV-ready dictionaries."""

    return [asdict(check) for check in checks]
