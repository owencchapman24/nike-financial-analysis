"""Validation rules for approved operating-scenario assumptions and forecasts."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping


SCENARIOS = ("base", "bull", "bear")
FORECAST_YEARS = ("FY2027", "FY2028", "FY2029", "FY2030", "FY2031")
REQUIRED_DRIVERS = (
    "revenue_growth",
    "gross_margin",
    "sga_percent_revenue",
    "normalized_tax_rate",
    "da_percent_revenue",
    "capex_percent_revenue",
    "operating_nwc_percent_revenue",
)
VALUATION_TERMS = frozenset(
    {
        "wacc",
        "terminal_growth",
        "terminal_value",
        "discount_factor",
        "present_value",
        "enterprise_value",
        "equity_value",
        "share_price",
    }
)


@dataclass(frozen=True)
class ForecastCheck:
    """One human-readable forecast validation result."""

    check_id: str
    scope: str
    status: str
    details: str


def _decimal(row: Mapping[str, str]) -> Decimal:
    try:
        return Decimal(row["value"])
    except (InvalidOperation, KeyError) as exc:
        raise ValueError(
            f"Invalid decimal for {row.get('scenario', '?')} "
            f"{row.get('fiscal_year', '?')} {row.get('driver', '?')}."
        ) from exc


def validate_assumption_rows(
    rows: Iterable[Mapping[str, str]], *, require_approved: bool = True
) -> list[ForecastCheck]:
    """Validate the complete scenario assumption grid and directional coherence."""

    materialized = list(rows)
    expected = {
        (scenario, year, driver)
        for scenario in SCENARIOS
        for year in FORECAST_YEARS
        for driver in REQUIRED_DRIVERS
    }
    keys = [
        (row.get("scenario", ""), row.get("fiscal_year", ""), row.get("driver", ""))
        for row in materialized
    ]
    actual = set(keys)
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    checks = [
        ForecastCheck(
            "assumption_grid",
            "assumptions",
            "pass" if actual == expected and not duplicates else "fail",
            (
                "Exactly 105 unique scenario-year-driver assumptions are present."
                if actual == expected and not duplicates
                else f"Missing={len(expected - actual)}; unexpected={len(actual - expected)}; "
                f"duplicates={len(duplicates)}."
            ),
        )
    ]
    if actual != expected or duplicates:
        return checks

    approved = all(row.get("owner_status") == "approved" for row in materialized)
    checks.append(
        ForecastCheck(
            "owner_approval",
            "assumptions",
            "pass" if approved or not require_approved else "fail",
            "All required assumptions are owner-approved."
            if approved
            else "At least one required assumption is not approved.",
        )
    )
    units_valid = all(row.get("unit") == "decimal" for row in materialized)
    source_ids_present = all(row.get("source_id", "").strip() for row in materialized)
    no_valuation = not any(row["driver"] in VALUATION_TERMS for row in materialized)
    checks.extend(
        [
            ForecastCheck(
                "assumption_units",
                "assumptions",
                "pass" if units_valid else "fail",
                "All drivers use decimal rate semantics."
                if units_valid
                else "Every forecast driver must use unit=decimal.",
            ),
            ForecastCheck(
                "assumption_sources",
                "assumptions",
                "pass" if source_ids_present else "fail",
                "Every assumption has a source or rationale identifier."
                if source_ids_present
                else "At least one assumption lacks a source identifier.",
            ),
            ForecastCheck(
                "valuation_boundary",
                "scope",
                "pass" if no_valuation else "fail",
                "No valuation driver is present."
                if no_valuation
                else "A valuation driver entered the Phase 4 assumptions.",
            ),
        ]
    )

    values = {(r["scenario"], r["fiscal_year"], r["driver"]): _decimal(r) for r in materialized}
    bounds_valid = True
    for key, value in values.items():
        driver = key[2]
        if driver == "revenue_growth" and value <= Decimal("-1"):
            bounds_valid = False
        elif driver == "gross_margin" and not Decimal("0") < value < Decimal("1"):
            bounds_valid = False
        elif driver == "sga_percent_revenue" and not Decimal("0") <= value < Decimal("1"):
            bounds_valid = False
        elif driver == "normalized_tax_rate" and not Decimal("0") <= value <= Decimal("0.50"):
            bounds_valid = False
        elif driver in {
            "da_percent_revenue",
            "capex_percent_revenue",
            "operating_nwc_percent_revenue",
        } and value < 0:
            bounds_valid = False
        if values[(key[0], key[1], "gross_margin")] <= values[
            (key[0], key[1], "sga_percent_revenue")
        ]:
            bounds_valid = False
    checks.append(
        ForecastCheck(
            "economic_bounds",
            "assumptions",
            "pass" if bounds_valid else "fail",
            "All rates are within documented operating bounds."
            if bounds_valid
            else "At least one rate is outside its documented bound.",
        )
    )

    direction_valid = True
    for year in FORECAST_YEARS:
        for driver in ("revenue_growth", "gross_margin", "capex_percent_revenue"):
            if not (
                values[("bull", year, driver)]
                >= values[("base", year, driver)]
                >= values[("bear", year, driver)]
            ):
                direction_valid = False
        for driver in ("sga_percent_revenue", "operating_nwc_percent_revenue"):
            if not (
                values[("bull", year, driver)]
                <= values[("base", year, driver)]
                <= values[("bear", year, driver)]
            ):
                direction_valid = False
        tax_rates = {values[(scenario, year, "normalized_tax_rate")] for scenario in SCENARIOS}
        if tax_rates != {Decimal("0.210")}:
            direction_valid = False
    checks.append(
        ForecastCheck(
            "scenario_direction",
            "coherence",
            "pass" if direction_valid else "fail",
            "Scenario drivers retain the approved directional ordering."
            if direction_valid
            else "One or more scenario drivers violate the approved ordering.",
        )
    )
    return checks


def validate_forecast_rows(rows: Iterable[Mapping[str, object]]) -> list[ForecastCheck]:
    """Validate forecast periods, exact formulas, signs, and scenario ordering."""

    materialized = list(rows)
    expected_keys = {(scenario, year) for scenario in SCENARIOS for year in FORECAST_YEARS}
    actual_keys = {(str(r["scenario"]), str(r["fiscal_year"])) for r in materialized}
    checks = [
        ForecastCheck(
            "forecast_periods",
            "forecast",
            "pass" if actual_keys == expected_keys and len(materialized) == 15 else "fail",
            "Exactly three scenarios and FY2027-FY2031 are present."
            if actual_keys == expected_keys and len(materialized) == 15
            else "Forecast rows do not match the required 15 scenario-year combinations.",
        )
    ]
    identities = True
    driver_identities = True
    decimal_values = True
    positive_revenue = True
    no_loss_tax_benefit = True
    for row in materialized:
        revenue = row["revenue"]
        gross_profit = row["gross_profit"]
        sga = row["total_selling_and_administrative_expense"]
        derived = row["derived_operating_income"]
        tax_expense = row["normalized_operating_tax_expense"]
        nopat = row["nopat"]
        da = row["depreciation_and_amortization"]
        capex = row["capital_expenditures"]
        delta = row["change_in_operating_nwc"]
        fcff = row["fcff"]
        numeric_fields = (
            "revenue_growth",
            "revenue",
            "gross_margin",
            "gross_profit",
            "sga_percent_revenue",
            "total_selling_and_administrative_expense",
            "derived_operating_income",
            "operating_margin",
            "normalized_tax_rate",
            "normalized_operating_tax_expense",
            "nopat",
            "da_percent_revenue",
            "depreciation_and_amortization",
            "capex_percent_revenue",
            "capital_expenditures",
            "operating_nwc_percent_revenue",
            "operating_nwc_proxy",
            "change_in_operating_nwc",
            "fcff",
            "fcff_margin",
        )
        if not all(isinstance(row[field], Decimal) for field in numeric_fields):
            decimal_values = False
        if revenue <= 0:
            positive_revenue = False
        if not (
            gross_profit - sga == derived
            and derived - tax_expense == nopat
            and nopat + da - capex - delta == fcff
            and row["operating_margin"]
            == row["gross_margin"] - row["sga_percent_revenue"]
        ):
            identities = False
        if not (
            revenue * row["gross_margin"] == gross_profit
            and revenue * row["sga_percent_revenue"] == sga
            and revenue * row["da_percent_revenue"] == da
            and revenue * row["capex_percent_revenue"] == capex
            and revenue * row["operating_nwc_percent_revenue"]
            == row["operating_nwc_proxy"]
            and fcff / revenue == row["fcff_margin"]
        ):
            driver_identities = False
        if derived < 0 and tax_expense != Decimal("0"):
            no_loss_tax_benefit = False
    checks.extend(
        [
            ForecastCheck(
                "positive_revenue",
                "forecast",
                "pass" if positive_revenue else "fail",
                "Revenue remains positive in every forecast year."
                if positive_revenue
                else "A forecast revenue value is nonpositive.",
            ),
            ForecastCheck(
                "forecast_identities",
                "forecast",
                "pass" if identities else "fail",
                "Derived operating income, NOPAT, margin, and FCFF identities hold exactly."
                if identities
                else "At least one forecast identity failed.",
            ),
            ForecastCheck(
                "loss_tax_treatment",
                "tax",
                "pass" if no_loss_tax_benefit else "fail",
                "Negative derived operating income cannot generate a tax benefit."
                if no_loss_tax_benefit
                else "A tax benefit was generated without an NOL schedule.",
            ),
            ForecastCheck(
                "driver_identities",
                "forecast",
                "pass" if driver_identities else "fail",
                "Gross profit, SG&A, D&A, capex, operating NWC, and FCFF margin match their approved drivers exactly."
                if driver_identities
                else "At least one driver-to-output identity failed.",
            ),
            ForecastCheck(
                "decimal_precision",
                "forecast",
                "pass" if decimal_values else "fail",
                "Every forecast numeric value remains Decimal-based."
                if decimal_values
                else "A forecast numeric value left the Decimal calculation path.",
            ),
        ]
    )
    ordering = True
    by_key = {(str(r["scenario"]), str(r["fiscal_year"])): r for r in materialized}
    for year in FORECAST_YEARS:
        for metric in ("revenue", "derived_operating_income", "operating_margin", "fcff"):
            if not (
                by_key[("bull", year)][metric]
                >= by_key[("base", year)][metric]
                >= by_key[("bear", year)][metric]
            ):
                ordering = False
    checks.append(
        ForecastCheck(
            "scenario_output_ordering",
            "coherence",
            "pass" if ordering else "warning",
            "Bull, base, and bear outputs retain directional ordering."
            if ordering
            else "A scenario output exception requires explanation; it is not automatically invalid.",
        )
    )
    return checks


def require_passing(checks: Iterable[ForecastCheck]) -> None:
    """Stop final output generation when a required check fails."""

    failures = [check for check in checks if check.status == "fail"]
    if failures:
        raise ValueError("Forecast validation failed: " + "; ".join(c.details for c in failures))
