"""Validation controls for the Decimal-based Phase 5 valuation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Mapping, Sequence


SCENARIOS = ("base", "bull", "bear")
FORECAST_YEARS = ("FY2027", "FY2028", "FY2029", "FY2030", "FY2031")
REQUIRED_ASSUMPTIONS = frozenset(
    {
        "model_date",
        "reference_market_date",
        "reference_market_price",
        "class_a_shares_outstanding",
        "class_b_shares_outstanding",
        "incremental_dilutive_share_proxy",
        "cash_and_cash_equivalents",
        "short_term_investments",
        "fair_value_debt",
        "carrying_interest_bearing_debt",
        "redeemable_preferred_stock",
        "operating_lease_liabilities",
        "risk_free_rate",
        "equity_risk_premium",
        "debt_default_spread",
        "operating_tax_rate",
        "footwear_revenue",
        "apparel_revenue",
        "equipment_revenue",
        "other_revenue",
        "footwear_unlevered_beta",
        "apparel_unlevered_beta",
        "equipment_unlevered_beta",
        "terminal_growth_rate",
        "sensitivity_wacc_delta_minus_100bp",
        "sensitivity_wacc_delta_minus_50bp",
        "sensitivity_wacc_delta_center",
        "sensitivity_wacc_delta_plus_50bp",
        "sensitivity_wacc_delta_plus_100bp",
        "sensitivity_terminal_growth_150bp",
        "sensitivity_terminal_growth_200bp",
        "sensitivity_terminal_growth_250bp",
        "sensitivity_terminal_growth_300bp",
        "sensitivity_terminal_growth_350bp",
    }
)
REQUIRED_FORECAST_METRICS = frozenset(
    {
        "revenue",
        "gross_margin",
        "gross_profit",
        "sga_percent_revenue",
        "total_selling_and_administrative_expense",
        "derived_operating_income",
        "operating_margin",
        "normalized_tax_rate",
        "nopat",
        "da_percent_revenue",
        "depreciation_and_amortization",
        "capex_percent_revenue",
        "capital_expenditures",
        "operating_nwc_percent_revenue",
        "operating_nwc_proxy",
        "change_in_operating_nwc",
        "fcff",
    }
)


@dataclass(frozen=True)
class ValuationCheck:
    """One human-readable valuation validation result."""

    check_id: str
    category: str
    scope: str
    status: str
    actual: str
    expected: str
    difference: str
    tolerance: str
    details: str


def _check(
    check_id: str,
    category: str,
    scope: str,
    passed: bool,
    *,
    actual: object = "",
    expected: object = "",
    difference: object = "",
    tolerance: object = "exact",
    details: str,
    failure_status: str = "fail",
) -> ValuationCheck:
    return ValuationCheck(
        check_id=check_id,
        category=category,
        scope=scope,
        status="pass" if passed else failure_status,
        actual=str(actual),
        expected=str(expected),
        difference=str(difference),
        tolerance=str(tolerance),
        details=details,
    )


def validate_assumptions(
    rows: Iterable[Mapping[str, str]], source_ids: set[str]
) -> list[ValuationCheck]:
    """Validate the complete approved valuation-input register."""

    materialized = list(rows)
    names = [row.get("input_name", "") for row in materialized]
    actual = set(names)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    checks = [
        _check(
            "valuation_assumption_grid",
            "inputs",
            "all",
            actual == REQUIRED_ASSUMPTIONS and not duplicates,
            actual=len(materialized),
            expected=len(REQUIRED_ASSUMPTIONS),
            details="Every required valuation input appears exactly once.",
        )
    ]
    if actual != REQUIRED_ASSUMPTIONS or duplicates:
        return checks

    approved = all(row.get("owner_status") == "approved" for row in materialized)
    source_resolution = all(
        source_id in source_ids
        for row in materialized
        for source_id in row.get("source_ids", "").split(";")
        if source_id
    )
    values_valid = True
    for row in materialized:
        if row["unit"] == "date":
            continue
        try:
            Decimal(row["value"])
        except InvalidOperation:
            values_valid = False
    checks.extend(
        [
            _check(
                "valuation_owner_approval",
                "inputs",
                "all",
                approved,
                actual="approved" if approved else "unapproved input present",
                expected="approved",
                details="All required valuation inputs are owner-approved.",
            ),
            _check(
                "valuation_source_resolution",
                "sources",
                "all",
                source_resolution,
                actual="resolved" if source_resolution else "unknown source ID",
                expected="resolved",
                details="Every valuation assumption source ID resolves in the source register.",
            ),
            _check(
                "valuation_numeric_inputs",
                "inputs",
                "all",
                values_valid,
                actual="valid" if values_valid else "invalid numeric value",
                expected="valid",
                details="Every non-date valuation input is a valid Decimal string.",
            ),
        ]
    )
    return checks


def validate_forecast_contract(rows: Iterable[Mapping[str, str]]) -> list[ValuationCheck]:
    """Ensure Phase 5 consumes the complete approved Phase 4 forecast only."""

    materialized = [row for row in rows if row.get("scenario") in SCENARIOS]
    keyed_rows = [
        (row.get("scenario", ""), row.get("fiscal_year", ""), row.get("metric", ""))
        for row in materialized
    ]
    keys = {
        (row.get("scenario", ""), row.get("fiscal_year", ""), row.get("metric", ""))
        for row in materialized
    }
    expected = {
        (scenario, year, metric)
        for scenario in SCENARIOS
        for year in FORECAST_YEARS
        for metric in REQUIRED_FORECAST_METRICS
    }
    duplicate_required = sorted(key for key in expected if keyed_rows.count(key) > 1)
    required = expected.issubset(keys) and not duplicate_required
    valid_statuses = all(
        row.get("status") == "forecast_calculated"
        for row in materialized
        if (row["scenario"], row["fiscal_year"], row["metric"]) in expected
    )
    return [
        _check(
            "phase4_forecast_contract",
            "forecast",
            "FY2027-FY2031",
            required and valid_statuses,
            actual=(
                f"{len(keys & expected)} required rows; "
                f"{len(duplicate_required)} duplicate required keys"
            ),
            expected=f"{len(expected)} required rows",
            details=(
                "The complete approved forecast is present with forecast_calculated status."
            ),
        )
    ]


def validate_model(model: object) -> list[ValuationCheck]:
    """Validate WACC, DCF, equity bridge, sensitivity, and warning behavior."""

    checks: list[ValuationCheck] = []
    wacc = model.wacc_primary
    carrying = model.wacc_carrying_cross_check
    one = Decimal("1")
    with localcontext() as context:
        context.prec = 40
        expected_levered_beta = wacc.unlevered_beta * (
            one + (one - wacc.tax_rate) * wacc.debt / wacc.market_equity
        )
        expected_cost_of_equity = (
            wacc.risk_free_rate + wacc.levered_beta * wacc.equity_risk_premium
        )
        expected_wacc = (
            wacc.equity_weight * wacc.cost_of_equity
            + wacc.debt_weight * wacc.after_tax_cost_of_debt
        )
    checks.extend(
        [
            _check(
                "wacc_weights",
                "wacc",
                "primary",
                wacc.equity_weight + wacc.debt_weight == one,
                actual=wacc.equity_weight + wacc.debt_weight,
                expected=one,
                difference=wacc.equity_weight + wacc.debt_weight - one,
                details="Primary equity and debt weights sum exactly to one.",
            ),
            _check(
                "levered_beta_formula",
                "wacc",
                "primary",
                wacc.levered_beta == expected_levered_beta,
                actual=wacc.levered_beta,
                expected="unlevered beta * [1 + (1-tax) * debt/equity]",
                details="The approved relevering formula holds exactly.",
            ),
            _check(
                "cost_of_equity_formula",
                "wacc",
                "primary",
                wacc.cost_of_equity == expected_cost_of_equity,
                actual=wacc.cost_of_equity,
                expected="risk-free rate + levered beta * ERP",
                details="CAPM cost of equity holds exactly.",
            ),
            _check(
                "after_tax_cost_of_debt",
                "wacc",
                "primary",
                wacc.after_tax_cost_of_debt
                == wacc.pretax_cost_of_debt * (one - wacc.tax_rate),
                actual=wacc.after_tax_cost_of_debt,
                expected="pretax debt cost * (1-tax)",
                details="After-tax cost of debt holds exactly.",
            ),
            _check(
                "wacc_formula",
                "wacc",
                "primary",
                wacc.wacc == expected_wacc,
                actual=wacc.wacc,
                expected="E/V * cost of equity + D/V * after-tax cost of debt",
                details="Formula-derived WACC holds exactly.",
            ),
            _check(
                "carrying_debt_wacc_cross_check",
                "wacc",
                "cross_check",
                carrying.debt == model.carrying_debt,
                actual=carrying.debt,
                expected=model.carrying_debt,
                details="The secondary WACC build uses carrying debt only as a cross-check.",
            ),
        ]
    )

    scenario_names = tuple(item.scenario for item in model.scenario_valuations)
    checks.append(
        _check(
            "valuation_scenarios",
            "dcf",
            "all",
            set(scenario_names) == set(SCENARIOS) and len(scenario_names) == 3,
            actual=scenario_names,
            expected=SCENARIOS,
            details="Bear, Base, and Bull are valued independently without probabilities.",
        )
    )
    forecast = {
        (row["scenario"], row["fiscal_year"], row["metric"]): Decimal(row["value"])
        for row in model.forecast_rows
        if row.get("scenario") in SCENARIOS
        and row.get("fiscal_year") in FORECAST_YEARS
        and row.get("metric") in REQUIRED_FORECAST_METRICS
        and row.get("value")
    }
    for valuation in model.scenario_valuations:
        terminal = valuation.terminal
        expected_ev = valuation.pv_explicit_fcff + valuation.pv_terminal_value
        expected_equity = (
            valuation.enterprise_value
            + model.cash_and_short_term_investments
            - model.carrying_debt
            - model.preferred_stock
        )
        checks.extend(
            [
                _check(
                    "wacc_exceeds_terminal_growth",
                    "terminal_value",
                    valuation.scenario,
                    valuation.wacc > valuation.terminal_growth,
                    actual=valuation.wacc,
                    expected=f"> {valuation.terminal_growth}",
                    details="WACC exceeds terminal growth.",
                ),
                _check(
                    "terminal_fcff_identity",
                    "terminal_value",
                    valuation.scenario,
                    terminal.fcff
                    == terminal.nopat
                    + terminal.depreciation_and_amortization
                    - terminal.capital_expenditures
                    - terminal.change_in_operating_nwc,
                    actual=terminal.fcff,
                    expected="NOPAT + D&A - capex - change in operating NWC",
                    details="FY2032 terminal FCFF identity holds exactly.",
                ),
                _check(
                    "terminal_revenue_bridge",
                    "terminal_value",
                    valuation.scenario,
                    terminal.revenue
                    == forecast[(valuation.scenario, "FY2031", "revenue")]
                    * (one + valuation.terminal_growth),
                    actual=terminal.revenue,
                    expected="FY2031 revenue * (1 + terminal growth)",
                    details="FY2032 revenue applies the common terminal-growth rate exactly.",
                ),
                _check(
                    "terminal_value_formula",
                    "terminal_value",
                    valuation.scenario,
                    valuation.terminal_value
                    == terminal.fcff / (valuation.wacc - valuation.terminal_growth),
                    actual=valuation.terminal_value,
                    expected="FY2032 FCFF / (WACC - terminal growth)",
                    details="The Gordon-growth terminal-value formula holds exactly.",
                ),
                _check(
                    "enterprise_value_equation",
                    "dcf",
                    valuation.scenario,
                    valuation.enterprise_value == expected_ev,
                    actual=valuation.enterprise_value,
                    expected=expected_ev,
                    difference=valuation.enterprise_value - expected_ev,
                    details="Enterprise value equals explicit-period PV plus terminal-value PV.",
                ),
                _check(
                    "equity_bridge_equation",
                    "equity_bridge",
                    valuation.scenario,
                    valuation.equity_value == expected_equity,
                    actual=valuation.equity_value,
                    expected=expected_equity,
                    difference=valuation.equity_value - expected_equity,
                    details="The bridge adds all cash and investments and subtracts carrying debt and preferred stock only.",
                ),
                _check(
                    "positive_share_count",
                    "equity_bridge",
                    valuation.scenario,
                    model.diluted_proxy_shares > 0,
                    actual=model.diluted_proxy_shares,
                    expected="> 0",
                    details="The headline diluted-proxy denominator is positive.",
                ),
                _check(
                    "share_denominator_cross_check",
                    "equity_bridge",
                    valuation.scenario,
                    valuation.basic_share_value_cross_check
                    == valuation.equity_value / model.basic_shares
                    and model.diluted_proxy_shares > model.basic_shares,
                    actual=valuation.basic_share_value_cross_check,
                    expected="equity value / basic shares; diluted proxy exceeds basic shares",
                    details="Basic shares are retained only as a denominator cross-check.",
                ),
            ]
        )
        for flow in valuation.explicit_cash_flows:
            cash_date = date.fromisoformat(flow.cash_flow_date)
            model_date = date.fromisoformat(model.model_date)
            exponent = Decimal((cash_date - model_date).days) / Decimal("365")
            factor = one / (one + valuation.wacc) ** exponent
            checks.extend(
                [
                    _check(
                        "discount_exponent",
                        "discounting",
                        f"{valuation.scenario}:{flow.fiscal_year}",
                        flow.discount_exponent == exponent,
                        actual=flow.discount_exponent,
                        expected=exponent,
                        details="The cash-flow date uses a 365-day XNPV-equivalent exponent.",
                    ),
                    _check(
                        "discounted_fcff",
                        "discounting",
                        f"{valuation.scenario}:{flow.fiscal_year}",
                        flow.present_value == flow.fcff * factor,
                        actual=flow.present_value,
                        expected=flow.fcff * factor,
                        details="Each explicit FCFF is discounted at the full-precision WACC.",
                    ),
                ]
            )
        terminal_status = (
            "strong_warning"
            if valuation.terminal_value_share_of_ev > Decimal("0.80")
            else "warning"
            if valuation.terminal_value_share_of_ev > Decimal("0.75")
            else "pass"
        )
        checks.append(
            ValuationCheck(
                check_id="terminal_value_dependence",
                category="terminal_value",
                scope=valuation.scenario,
                status=terminal_status,
                actual=str(valuation.terminal_value_share_of_ev),
                expected="observation thresholds: warning >75%; strong warning >80%",
                difference="",
                tolerance="not a failure threshold",
                details="Terminal-value dependence is disclosed rather than hidden or treated as an automatic failure.",
            )
        )

    base = next(item for item in model.scenario_valuations if item.scenario == "base")
    center = next(cell for cell in model.sensitivity_cells if cell.is_center)
    checks.append(
        _check(
            "sensitivity_center",
            "sensitivity",
            "base",
            center.value_per_share == base.value_per_share,
            actual=center.value_per_share,
            expected=base.value_per_share,
            difference=center.value_per_share - base.value_per_share,
            details="The full-precision center cell equals the Base headline DCF.",
        )
    )
    by_rate: dict[Decimal, list[object]] = {}
    by_growth: dict[Decimal, list[object]] = {}
    for cell in model.sensitivity_cells:
        by_rate.setdefault(cell.wacc, []).append(cell)
        by_growth.setdefault(cell.terminal_growth, []).append(cell)
    growth_monotonic = all(
        all(a.value_per_share < b.value_per_share for a, b in zip(sorted(cells, key=lambda c: c.terminal_growth), sorted(cells, key=lambda c: c.terminal_growth)[1:]))
        for cells in by_rate.values()
    )
    wacc_monotonic = all(
        all(a.value_per_share > b.value_per_share for a, b in zip(sorted(cells, key=lambda c: c.wacc), sorted(cells, key=lambda c: c.wacc)[1:]))
        for cells in by_growth.values()
    )
    checks.extend(
        [
            _check(
                "sensitivity_growth_monotonicity",
                "sensitivity",
                "base",
                growth_monotonic,
                actual="increasing" if growth_monotonic else "not increasing",
                expected="increasing with terminal growth",
                details="Value increases as terminal growth rises at constant WACC.",
            ),
            _check(
                "sensitivity_wacc_monotonicity",
                "sensitivity",
                "base",
                wacc_monotonic,
                actual="decreasing" if wacc_monotonic else "not decreasing",
                expected="decreasing with WACC",
                details="Value decreases as WACC rises at constant terminal growth.",
            ),
        ]
    )
    return checks


def require_no_failures(checks: Sequence[ValuationCheck]) -> None:
    """Raise a friendly error when a required valuation check fails."""

    failures = [check for check in checks if check.status == "fail"]
    if failures:
        raise ValueError(
            "Valuation validation failed: " + "; ".join(check.details for check in failures)
        )
