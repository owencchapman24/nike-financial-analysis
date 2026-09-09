"""Decimal-based Phase 5A DCF valuation and deterministic public artifacts."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable, Mapping

from nike_financial_analysis.analysis import (
    find_repository_root,
    hash_matches_expected,
    verify_phase2_hashes,
)
from nike_financial_analysis.forecast import verify_phase3_hashes
from nike_financial_analysis.valuation_validation import (
    FORECAST_YEARS,
    SCENARIOS,
    ValuationCheck,
    require_no_failures,
    validate_assumptions,
    validate_forecast_contract,
    validate_model,
)


INFORMATION_CUTOFF = "2026-09-07"
DEFAULT_ASSUMPTIONS = Path("config/valuation_assumptions.csv")
DEFAULT_SOURCES = Path("config/valuation_sources.csv")
DEFAULT_FORECAST = Path("outputs/tables/scenario_forecast_long.csv")
DEFAULT_EXPORTS_DIR = Path("outputs/model_exports")
DEFAULT_CHARTS_DIR = Path("outputs/charts")
VALUATION_EXPORT_FILENAMES = (
    "wacc_build.csv",
    "valuation_cash_flows.csv",
    "valuation_summary.csv",
    "dcf_sensitivity.csv",
    "valuation_validation_summary.csv",
)
PROTECTED_PHASE4_HASHES = {
    Path("config/scenario_assumptions.csv"): "9ddb85ac130f7b451d4af8e3ed5f7fa877297255ea7e31750d794c944479e315",
    Path("config/forecast_sources.csv"): "9564fd23b0543b5b5573116e52a5be11f5aa697c655d466d254d30d73e25e013",
    Path("outputs/tables/scenario_forecast_long.csv"): "4d255b633437a35223a198f6f89e55c36bbc1f9f67f0349e91a0e8bed8a9f42f",
    Path("outputs/tables/scenario_forecast_summary.csv"): "ddb7937dfb26110072eeed64f0b5949d98bbe4868f949a271fc8830a55f55ab7",
    Path("outputs/tables/scenario_assumptions_resolved.csv"): "78904b3ac77f62b8532c094a4b02ae44d8c0b2c41a57803dfd1e3b721cd5aea5",
    Path("outputs/tables/forecast_validation_summary.csv"): "abd130af36393da68ad4fcf0aeaf482fa68b0d29d26068cab8ef63b1a4b59e8d",
    Path("outputs/charts/06_forecast_revenue.png"): "262fa83c0cc998f96cb518c15992961faeb3f551d501ee537fb53ca8331dcccd",
    Path("outputs/charts/07_forecast_operating_margin.png"): "386779d8d302d7a4dc09ade649673fd25b8c816bfd6373d9dd6b9515ca41851e",
    Path("outputs/charts/08_forecast_fcff.png"): "fc6c9a366e7ed4ddc013ae1fe359abac5ff64ffc40f079e8fc660e798136af5b",
    Path("outputs/charts/09_forecast_reinvestment_drivers.png"): "fb0556aa47bec7ed95db296f4894a7edbf61db02dfc97592e3dfaa19d4ed5f90",
    Path("notebooks/02_scenario_forecast.ipynb"): "7604b17b3de55a069a95ed99b224012b9f3a163845614488e50799190e284818",
}


@dataclass(frozen=True)
class WaccBuild:
    """One fully formula-derived WACC build."""

    case: str
    market_price: Decimal
    basic_shares: Decimal
    market_equity: Decimal
    classified_revenue: Decimal
    other_revenue: Decimal
    total_revenue: Decimal
    unlevered_beta: Decimal
    debt: Decimal
    tax_rate: Decimal
    levered_beta: Decimal
    risk_free_rate: Decimal
    equity_risk_premium: Decimal
    cost_of_equity: Decimal
    default_spread: Decimal
    pretax_cost_of_debt: Decimal
    after_tax_cost_of_debt: Decimal
    equity_weight: Decimal
    debt_weight: Decimal
    wacc: Decimal


@dataclass(frozen=True)
class DiscountedCashFlow:
    """One explicit forecast cash flow and its date-based present value."""

    scenario: str
    fiscal_year: str
    cash_flow_date: str
    fcff: Decimal
    discount_exponent: Decimal
    discount_factor: Decimal
    present_value: Decimal


@dataclass(frozen=True)
class TerminalBridge:
    """FY2032 stable-state bridge used by the Gordon-growth calculation."""

    scenario: str
    fiscal_year: str
    cash_flow_date: str
    revenue_growth: Decimal
    revenue: Decimal
    gross_margin: Decimal
    gross_profit: Decimal
    sga_percent_revenue: Decimal
    total_selling_and_administrative_expense: Decimal
    derived_operating_income: Decimal
    operating_margin: Decimal
    normalized_tax_rate: Decimal
    nopat: Decimal
    da_percent_revenue: Decimal
    depreciation_and_amortization: Decimal
    capex_percent_revenue: Decimal
    capital_expenditures: Decimal
    operating_nwc_percent_revenue: Decimal
    operating_nwc_proxy: Decimal
    change_in_operating_nwc: Decimal
    fcff: Decimal
    ebitda_proxy: Decimal


@dataclass(frozen=True)
class ScenarioValuation:
    """Headline DCF result for one approved operating scenario."""

    scenario: str
    wacc: Decimal
    terminal_growth: Decimal
    explicit_cash_flows: tuple[DiscountedCashFlow, ...]
    terminal: TerminalBridge
    pv_explicit_fcff: Decimal
    terminal_value: Decimal
    pv_terminal_value: Decimal
    enterprise_value: Decimal
    equity_value: Decimal
    value_per_share: Decimal
    basic_share_value_cross_check: Decimal
    carrying_wacc_value_per_share_cross_check: Decimal
    reference_market_price: Decimal
    premium_discount_to_reference: Decimal
    terminal_value_share_of_ev: Decimal
    implied_terminal_ev_ebitda: Decimal


@dataclass(frozen=True)
class SensitivityCell:
    """One direct-growth Base-case sensitivity result."""

    wacc_row: int
    growth_column: int
    wacc_delta: Decimal
    wacc: Decimal
    displayed_wacc: Decimal
    terminal_growth: Decimal
    value_per_share: Decimal
    is_center: bool


@dataclass(frozen=True)
class ValuationModel:
    """Approved inputs, WACC, DCF scenarios, sensitivity, and checks."""

    assumption_rows: tuple[dict[str, str], ...]
    source_rows: tuple[dict[str, str], ...]
    forecast_rows: tuple[dict[str, str], ...]
    wacc_primary: WaccBuild
    wacc_carrying_cross_check: WaccBuild
    scenario_valuations: tuple[ScenarioValuation, ...]
    sensitivity_cells: tuple[SensitivityCell, ...]
    model_date: str
    reference_market_date: str
    cash_and_short_term_investments: Decimal
    carrying_debt: Decimal
    preferred_stock: Decimal
    operating_lease_liabilities: Decimal
    basic_shares: Decimal
    diluted_proxy_shares: Decimal
    checks: tuple[ValuationCheck, ...]


def verify_phase4_hashes(repository_root: Path) -> dict[str, str]:
    """Protect approved Phase 4 text and visual content semantically."""

    verified: dict[str, str] = {}
    for relative, expected in PROTECTED_PHASE4_HASHES.items():
        path = repository_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required Phase 4 artifact is missing: {relative}")
        if not hash_matches_expected(path, expected):
            raise ValueError(f"Protected Phase 4 artifact changed: {relative}")
        verified[relative.as_posix()] = expected
    return verified


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required valuation input is missing: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _decimal(value: str, name: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Valuation input {name} is not a valid Decimal.") from exc


def _assumption_index(rows: Iterable[Mapping[str, str]]) -> dict[str, str]:
    return {row["input_name"]: row["value"] for row in rows}


def _number(inputs: Mapping[str, str], name: str) -> Decimal:
    if name not in inputs:
        raise ValueError(f"Required valuation input is missing: {name}")
    return _decimal(inputs[name], name)


def _forecast_index(
    rows: Iterable[Mapping[str, str]],
) -> dict[tuple[str, str, str], Decimal]:
    index: dict[tuple[str, str, str], Decimal] = {}
    for row in rows:
        if row.get("scenario") not in SCENARIOS or not row.get("value"):
            continue
        index[(row["scenario"], row["fiscal_year"], row["metric"])] = _decimal(
            row["value"], row["metric"]
        )
    return index


def calculate_wacc(inputs: Mapping[str, str], *, debt_name: str, case: str) -> WaccBuild:
    """Calculate a product-weighted bottom-up WACC at full Decimal precision."""

    with localcontext() as context:
        context.prec = 40
        market_price = _number(inputs, "reference_market_price")
        basic_shares = _number(inputs, "class_a_shares_outstanding") + _number(
            inputs, "class_b_shares_outstanding"
        )
        market_equity = market_price * basic_shares
        footwear_revenue = _number(inputs, "footwear_revenue")
        apparel_revenue = _number(inputs, "apparel_revenue")
        equipment_revenue = _number(inputs, "equipment_revenue")
        other_revenue = _number(inputs, "other_revenue")
        classified_revenue = footwear_revenue + apparel_revenue + equipment_revenue
        total_revenue = classified_revenue + other_revenue
        unlevered_beta = (
            footwear_revenue * _number(inputs, "footwear_unlevered_beta")
            + apparel_revenue * _number(inputs, "apparel_unlevered_beta")
            + equipment_revenue * _number(inputs, "equipment_unlevered_beta")
        ) / classified_revenue
        debt = _number(inputs, debt_name)
        tax_rate = _number(inputs, "operating_tax_rate")
        one = Decimal("1")
        levered_beta = unlevered_beta * (
            one + (one - tax_rate) * debt / market_equity
        )
        risk_free_rate = _number(inputs, "risk_free_rate")
        equity_risk_premium = _number(inputs, "equity_risk_premium")
        cost_of_equity = risk_free_rate + levered_beta * equity_risk_premium
        default_spread = _number(inputs, "debt_default_spread")
        pretax_cost_of_debt = risk_free_rate + default_spread
        after_tax_cost_of_debt = pretax_cost_of_debt * (one - tax_rate)
        equity_weight = market_equity / (market_equity + debt)
        debt_weight = debt / (market_equity + debt)
        wacc = (
            equity_weight * cost_of_equity
            + debt_weight * after_tax_cost_of_debt
        )
        return WaccBuild(
            case=case,
            market_price=market_price,
            basic_shares=basic_shares,
            market_equity=market_equity,
            classified_revenue=classified_revenue,
            other_revenue=other_revenue,
            total_revenue=total_revenue,
            unlevered_beta=unlevered_beta,
            debt=debt,
            tax_rate=tax_rate,
            levered_beta=levered_beta,
            risk_free_rate=risk_free_rate,
            equity_risk_premium=equity_risk_premium,
            cost_of_equity=cost_of_equity,
            default_spread=default_spread,
            pretax_cost_of_debt=pretax_cost_of_debt,
            after_tax_cost_of_debt=after_tax_cost_of_debt,
            equity_weight=equity_weight,
            debt_weight=debt_weight,
            wacc=wacc,
        )


def _discount(
    amount: Decimal, *, cash_flow_date: date, model_date: date, wacc: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    exponent = Decimal((cash_flow_date - model_date).days) / Decimal("365")
    discount_factor = Decimal("1") / (Decimal("1") + wacc) ** exponent
    return exponent, discount_factor, amount * discount_factor


def calculate_terminal_bridge(
    scenario: str,
    forecast: Mapping[tuple[str, str, str], Decimal],
    terminal_growth: Decimal,
) -> TerminalBridge:
    """Roll FY2031 drivers into the stable FY2032 terminal transition year."""

    prior_year = "FY2031"
    revenue = forecast[(scenario, prior_year, "revenue")] * (
        Decimal("1") + terminal_growth
    )
    gross_margin = forecast[(scenario, prior_year, "gross_margin")]
    gross_profit = revenue * gross_margin
    sga_rate = forecast[(scenario, prior_year, "sga_percent_revenue")]
    sga = revenue * sga_rate
    derived = gross_profit - sga
    operating_margin = derived / revenue
    tax_rate = forecast[(scenario, prior_year, "normalized_tax_rate")]
    tax_expense = derived * tax_rate if derived > 0 else Decimal("0")
    nopat = derived - tax_expense
    da_rate = forecast[(scenario, prior_year, "da_percent_revenue")]
    depreciation = revenue * da_rate
    capex_rate = forecast[(scenario, prior_year, "capex_percent_revenue")]
    capital_expenditures = revenue * capex_rate
    onwc_rate = forecast[(scenario, prior_year, "operating_nwc_percent_revenue")]
    onwc = revenue * onwc_rate
    change_onwc = onwc - forecast[(scenario, prior_year, "operating_nwc_proxy")]
    fcff = nopat + depreciation - capital_expenditures - change_onwc
    return TerminalBridge(
        scenario=scenario,
        fiscal_year="FY2032",
        cash_flow_date="2032-05-31",
        revenue_growth=terminal_growth,
        revenue=revenue,
        gross_margin=gross_margin,
        gross_profit=gross_profit,
        sga_percent_revenue=sga_rate,
        total_selling_and_administrative_expense=sga,
        derived_operating_income=derived,
        operating_margin=operating_margin,
        normalized_tax_rate=tax_rate,
        nopat=nopat,
        da_percent_revenue=da_rate,
        depreciation_and_amortization=depreciation,
        capex_percent_revenue=capex_rate,
        capital_expenditures=capital_expenditures,
        operating_nwc_percent_revenue=onwc_rate,
        operating_nwc_proxy=onwc,
        change_in_operating_nwc=change_onwc,
        fcff=fcff,
        ebitda_proxy=derived + depreciation,
    )


def calculate_scenario_valuation(
    scenario: str,
    forecast: Mapping[tuple[str, str, str], Decimal],
    *,
    model_date: date,
    wacc: Decimal,
    terminal_growth: Decimal,
    cash_and_investments: Decimal,
    carrying_debt: Decimal,
    preferred_stock: Decimal,
    diluted_proxy_shares: Decimal,
    basic_shares: Decimal,
    reference_market_price: Decimal,
    carrying_wacc: Decimal,
) -> ScenarioValuation:
    """Calculate one full DCF using exact fiscal-year-end dates."""

    if wacc <= terminal_growth:
        raise ValueError("WACC must exceed terminal growth.")
    if diluted_proxy_shares <= 0 or basic_shares <= 0:
        raise ValueError("Share counts must be positive.")
    explicit: list[DiscountedCashFlow] = []
    for year in FORECAST_YEARS:
        flow = forecast[(scenario, year, "fcff")]
        flow_date = date(int(year[2:]), 5, 31)
        exponent, factor, present_value = _discount(
            flow, cash_flow_date=flow_date, model_date=model_date, wacc=wacc
        )
        explicit.append(
            DiscountedCashFlow(
                scenario=scenario,
                fiscal_year=year,
                cash_flow_date=flow_date.isoformat(),
                fcff=flow,
                discount_exponent=exponent,
                discount_factor=factor,
                present_value=present_value,
            )
        )
    terminal = calculate_terminal_bridge(scenario, forecast, terminal_growth)
    terminal_value = terminal.fcff / (wacc - terminal_growth)
    terminal_date = date(2031, 5, 31)
    _, _, pv_terminal = _discount(
        terminal_value,
        cash_flow_date=terminal_date,
        model_date=model_date,
        wacc=wacc,
    )
    pv_explicit = sum((item.present_value for item in explicit), Decimal("0"))
    enterprise_value = pv_explicit + pv_terminal
    equity_value = (
        enterprise_value + cash_and_investments - carrying_debt - preferred_stock
    )
    value_per_share = equity_value / diluted_proxy_shares
    basic_share_value = equity_value / basic_shares

    carrying_explicit = sum(
        (
            _discount(
                item.fcff,
                cash_flow_date=date.fromisoformat(item.cash_flow_date),
                model_date=model_date,
                wacc=carrying_wacc,
            )[2]
            for item in explicit
        ),
        Decimal("0"),
    )
    carrying_terminal_value = terminal.fcff / (carrying_wacc - terminal_growth)
    carrying_pv_terminal = _discount(
        carrying_terminal_value,
        cash_flow_date=terminal_date,
        model_date=model_date,
        wacc=carrying_wacc,
    )[2]
    carrying_value_per_share = (
        carrying_explicit
        + carrying_pv_terminal
        + cash_and_investments
        - carrying_debt
        - preferred_stock
    ) / diluted_proxy_shares
    return ScenarioValuation(
        scenario=scenario,
        wacc=wacc,
        terminal_growth=terminal_growth,
        explicit_cash_flows=tuple(explicit),
        terminal=terminal,
        pv_explicit_fcff=pv_explicit,
        terminal_value=terminal_value,
        pv_terminal_value=pv_terminal,
        enterprise_value=enterprise_value,
        equity_value=equity_value,
        value_per_share=value_per_share,
        basic_share_value_cross_check=basic_share_value,
        carrying_wacc_value_per_share_cross_check=carrying_value_per_share,
        reference_market_price=reference_market_price,
        premium_discount_to_reference=(
            value_per_share / reference_market_price - Decimal("1")
        ),
        terminal_value_share_of_ev=pv_terminal / enterprise_value,
        implied_terminal_ev_ebitda=terminal_value / terminal.ebitda_proxy,
    )


def _calculate_sensitivity(
    forecast: Mapping[tuple[str, str, str], Decimal],
    inputs: Mapping[str, str],
    *,
    model_date: date,
    primary_wacc: Decimal,
    cash_and_investments: Decimal,
    carrying_debt: Decimal,
    preferred_stock: Decimal,
    diluted_proxy_shares: Decimal,
    basic_shares: Decimal,
    reference_market_price: Decimal,
) -> tuple[SensitivityCell, ...]:
    deltas = tuple(
        _number(inputs, name)
        for name in (
            "sensitivity_wacc_delta_minus_100bp",
            "sensitivity_wacc_delta_minus_50bp",
            "sensitivity_wacc_delta_center",
            "sensitivity_wacc_delta_plus_50bp",
            "sensitivity_wacc_delta_plus_100bp",
        )
    )
    growths = tuple(
        _number(inputs, name)
        for name in (
            "sensitivity_terminal_growth_150bp",
            "sensitivity_terminal_growth_200bp",
            "sensitivity_terminal_growth_250bp",
            "sensitivity_terminal_growth_300bp",
            "sensitivity_terminal_growth_350bp",
        )
    )
    cells: list[SensitivityCell] = []
    for row_index, delta in enumerate(deltas, start=1):
        rate = primary_wacc + delta
        for column_index, growth in enumerate(growths, start=1):
            valuation = calculate_scenario_valuation(
                "base",
                forecast,
                model_date=model_date,
                wacc=rate,
                terminal_growth=growth,
                cash_and_investments=cash_and_investments,
                carrying_debt=carrying_debt,
                preferred_stock=preferred_stock,
                diluted_proxy_shares=diluted_proxy_shares,
                basic_shares=basic_shares,
                reference_market_price=reference_market_price,
                carrying_wacc=rate,
            )
            cells.append(
                SensitivityCell(
                    wacc_row=row_index,
                    growth_column=column_index,
                    wacc_delta=delta,
                    wacc=rate,
                    displayed_wacc=rate.quantize(Decimal("0.001")),
                    terminal_growth=growth,
                    value_per_share=valuation.value_per_share,
                    is_center=row_index == 3 and column_index == 3,
                )
            )
    return tuple(cells)


def build_valuation_model(repository_root: Path) -> ValuationModel:
    """Load approved inputs and calculate the complete Phase 5A model."""

    verify_phase2_hashes(repository_root)
    verify_phase3_hashes(repository_root)
    verify_phase4_hashes(repository_root)
    assumptions = _read_csv(repository_root / DEFAULT_ASSUMPTIONS)
    sources = _read_csv(repository_root / DEFAULT_SOURCES)
    forecast_rows = _read_csv(repository_root / DEFAULT_FORECAST)
    input_checks = validate_assumptions(
        assumptions, {row["source_id"] for row in sources}
    )
    forecast_checks = validate_forecast_contract(forecast_rows)
    require_no_failures([*input_checks, *forecast_checks])
    inputs = _assumption_index(assumptions)
    forecast = _forecast_index(forecast_rows)
    model_date = date.fromisoformat(inputs["model_date"])
    primary_wacc = calculate_wacc(
        inputs, debt_name="fair_value_debt", case="fair_value_debt_primary"
    )
    carrying_wacc = calculate_wacc(
        inputs,
        debt_name="carrying_interest_bearing_debt",
        case="carrying_debt_cross_check",
    )
    cash_and_investments = _number(inputs, "cash_and_cash_equivalents") + _number(
        inputs, "short_term_investments"
    )
    carrying_debt = _number(inputs, "carrying_interest_bearing_debt")
    preferred_stock = _number(inputs, "redeemable_preferred_stock")
    operating_leases = _number(inputs, "operating_lease_liabilities")
    basic_shares = _number(inputs, "class_a_shares_outstanding") + _number(
        inputs, "class_b_shares_outstanding"
    )
    diluted_proxy_shares = basic_shares + _number(
        inputs, "incremental_dilutive_share_proxy"
    )
    terminal_growth = _number(inputs, "terminal_growth_rate")
    reference_price = _number(inputs, "reference_market_price")
    valuations = tuple(
        calculate_scenario_valuation(
            scenario,
            forecast,
            model_date=model_date,
            wacc=primary_wacc.wacc,
            terminal_growth=terminal_growth,
            cash_and_investments=cash_and_investments,
            carrying_debt=carrying_debt,
            preferred_stock=preferred_stock,
            diluted_proxy_shares=diluted_proxy_shares,
            basic_shares=basic_shares,
            reference_market_price=reference_price,
            carrying_wacc=carrying_wacc.wacc,
        )
        for scenario in SCENARIOS
    )
    sensitivity = _calculate_sensitivity(
        forecast,
        inputs,
        model_date=model_date,
        primary_wacc=primary_wacc.wacc,
        cash_and_investments=cash_and_investments,
        carrying_debt=carrying_debt,
        preferred_stock=preferred_stock,
        diluted_proxy_shares=diluted_proxy_shares,
        basic_shares=basic_shares,
        reference_market_price=reference_price,
    )
    provisional = ValuationModel(
        assumption_rows=tuple(assumptions),
        source_rows=tuple(sources),
        forecast_rows=tuple(forecast_rows),
        wacc_primary=primary_wacc,
        wacc_carrying_cross_check=carrying_wacc,
        scenario_valuations=valuations,
        sensitivity_cells=sensitivity,
        model_date=inputs["model_date"],
        reference_market_date=inputs["reference_market_date"],
        cash_and_short_term_investments=cash_and_investments,
        carrying_debt=carrying_debt,
        preferred_stock=preferred_stock,
        operating_lease_liabilities=operating_leases,
        basic_shares=basic_shares,
        diluted_proxy_shares=diluted_proxy_shares,
        checks=(),
    )
    checks = tuple([*input_checks, *forecast_checks, *validate_model(provisional)])
    require_no_failures(checks)
    return replace(provisional, checks=checks)


def _text(value: Decimal | str | int | bool | None) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def build_wacc_rows(model: ValuationModel) -> list[dict[str, str]]:
    """Build an auditable long-form WACC calculation table."""

    definitions = (
        ("market_price", "Reference market price", "USD per share", "reported_input", "VA03", "NKE close on the separately dated market reference date."),
        ("basic_shares", "Total basic shares", "millions", "calculated", "VA04;VA05", "Class A plus Class B shares."),
        ("market_equity", "Market capitalization", "USD millions", "calculated", "VA03;VA04;VA05", "Reference market price multiplied by basic shares."),
        ("classified_revenue", "Beta-classified revenue", "USD millions", "calculated", "VA17;VA18;VA19", "Footwear; apparel; and equipment revenue used for beta weighting."),
        ("other_revenue", "Other revenue", "USD millions", "reported_input", "VA20", "Reconciles product categories to total revenue; assigned the blended core beta."),
        ("total_revenue", "Total product revenue", "USD millions", "calculated", "VA17;VA18;VA19;VA20", "Reconciles to FY2026 consolidated revenue."),
        ("unlevered_beta", "Product-weighted unlevered beta", "x", "calculated", "VA17;VA18;VA19;VA21;VA22;VA23", "Revenue-weighted cash-corrected sector betas."),
        ("debt", "Debt used in WACC", "USD millions", "reported_input", "VA09;VA10", "Fair value for primary WACC; carrying value for cross-check."),
        ("tax_rate", "Operating tax rate", "decimal", "approved_assumption", "VA16", "Approved normalized operating tax rate."),
        ("levered_beta", "Levered beta", "x", "calculated", "VA09;VA10;VA16", "Unlevered beta * [1 + (1-tax) * debt/market equity]."),
        ("risk_free_rate", "Risk-free rate", "decimal", "reported_input", "VA13", "September 4 2026 ten-year Treasury rate."),
        ("equity_risk_premium", "Equity risk premium", "decimal", "reported_input", "VA14", "September 1 2026 implied US ERP."),
        ("cost_of_equity", "Cost of equity", "decimal", "calculated", "VA13;VA14", "Risk-free rate + levered beta * ERP."),
        ("default_spread", "Default spread", "decimal", "market_proxy", "VA15", "Conservative A2/A default spread."),
        ("pretax_cost_of_debt", "Pretax cost of debt", "decimal", "calculated", "VA13;VA15", "Risk-free rate + default spread."),
        ("after_tax_cost_of_debt", "After-tax cost of debt", "decimal", "calculated", "VA15;VA16", "Pretax cost of debt * (1-tax)."),
        ("equity_weight", "Equity weight", "decimal", "calculated", "VA03;VA04;VA05;VA09;VA10", "Market equity / (market equity + debt)."),
        ("debt_weight", "Debt weight", "decimal", "calculated", "VA03;VA04;VA05;VA09;VA10", "Debt / (market equity + debt)."),
        ("wacc", "Calculated WACC", "decimal", "calculated", "VA13;VA14;VA15;VA16", "Equity weight * cost of equity + debt weight * after-tax cost of debt."),
    )
    rows: list[dict[str, str]] = []
    for build in (model.wacc_primary, model.wacc_carrying_cross_check):
        for order, (metric, display, unit, status, input_ids, notes) in enumerate(definitions, start=1):
            rows.append(
                {
                    "case": build.case,
                    "line_order": str(order),
                    "metric": metric,
                    "display_name": display,
                    "value": _text(getattr(build, metric)),
                    "unit": unit,
                    "status": status,
                    "input_ids": input_ids,
                    "notes": notes,
                }
            )
    return rows


def build_cash_flow_rows(model: ValuationModel) -> list[dict[str, str]]:
    """Build explicit forecast and FY2032 terminal-transition rows."""

    forecast = _forecast_index(model.forecast_rows)
    rows: list[dict[str, str]] = []
    fields = (
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
    )
    for valuation in model.scenario_valuations:
        cash_flow_by_year = {item.fiscal_year: item for item in valuation.explicit_cash_flows}
        for year in FORECAST_YEARS:
            flow = cash_flow_by_year[year]
            row = {
                "scenario": valuation.scenario,
                "fiscal_year": year,
                "cash_flow_date": flow.cash_flow_date,
                "period_class": "explicit_forecast",
                **{field: _text(forecast[(valuation.scenario, year, field)]) for field in fields},
                "terminal_growth": "",
                "terminal_value_at_fy2031": "",
                "discount_exponent": _text(flow.discount_exponent),
                "discount_factor": _text(flow.discount_factor),
                "present_value_fcff": _text(flow.present_value),
                "present_value_terminal_value": "",
                "status": "forecast_calculated",
                "source_ids": "VS01",
                "notes": "Approved Phase 4 operating forecast; discounted at its May 31 fiscal-year-end date.",
            }
            rows.append(row)
        terminal = valuation.terminal
        terminal_exponent = valuation.explicit_cash_flows[-1].discount_exponent
        terminal_factor = valuation.explicit_cash_flows[-1].discount_factor
        rows.append(
            {
                "scenario": valuation.scenario,
                "fiscal_year": "FY2032",
                "cash_flow_date": terminal.cash_flow_date,
                "period_class": "terminal_transition",
                **{field: _text(getattr(terminal, field)) for field in fields},
                "terminal_growth": _text(valuation.terminal_growth),
                "terminal_value_at_fy2031": _text(valuation.terminal_value),
                "discount_exponent": _text(terminal_exponent),
                "discount_factor": _text(terminal_factor),
                "present_value_fcff": "",
                "present_value_terminal_value": _text(valuation.pv_terminal_value),
                "status": "valuation_calculated",
                "source_ids": "VS01;VS09;VS10;VS11",
                "notes": "FY2032 is the explicit stable-state transition. Terminal value is measured at May 31 2031 and discounted using the FY2031 factor.",
            }
        )
    return rows


def build_summary_rows(model: ValuationModel) -> list[dict[str, str]]:
    """Build the recruiter-facing headline valuation summary."""

    rows: list[dict[str, str]] = []
    for value in model.scenario_valuations:
        warning = (
            "strong_warning"
            if value.terminal_value_share_of_ev > Decimal("0.80")
            else "warning"
            if value.terminal_value_share_of_ev > Decimal("0.75")
            else "pass"
        )
        rows.append(
            {
                "scenario": value.scenario,
                "model_date": model.model_date,
                "reference_market_date": model.reference_market_date,
                "timing_convention": "Exact fiscal-year-end dates; 365-day XNPV-equivalent exponents",
                "wacc": _text(value.wacc),
                "terminal_growth": _text(value.terminal_growth),
                "pv_explicit_fcff": _text(value.pv_explicit_fcff),
                "terminal_value_at_fy2031": _text(value.terminal_value),
                "pv_terminal_value": _text(value.pv_terminal_value),
                "enterprise_value": _text(value.enterprise_value),
                "cash_and_short_term_investments": _text(model.cash_and_short_term_investments),
                "carrying_interest_bearing_debt": _text(model.carrying_debt),
                "redeemable_preferred_stock": _text(model.preferred_stock),
                "other_adjustments": "0",
                "operating_lease_liabilities_memorandum": _text(model.operating_lease_liabilities),
                "equity_value": _text(value.equity_value),
                "diluted_proxy_shares": _text(model.diluted_proxy_shares),
                "illustrative_value_per_share": _text(value.value_per_share),
                "basic_share_value_cross_check": _text(value.basic_share_value_cross_check),
                "carrying_debt_wacc_cross_check": _text(model.wacc_carrying_cross_check.wacc),
                "carrying_wacc_value_per_share_cross_check": _text(value.carrying_wacc_value_per_share_cross_check),
                "reference_market_price": _text(value.reference_market_price),
                "premium_discount_to_reference": _text(value.premium_discount_to_reference),
                "terminal_value_share_of_enterprise_value": _text(value.terminal_value_share_of_ev),
                "implied_terminal_ev_ebitda": _text(value.implied_terminal_ev_ebitda),
                "terminal_value_observation": warning,
                "status": "valuation_calculated",
                "notes": "Illustrative intrinsic value from project analyst scenarios; not a price target or investment recommendation.",
            }
        )
    return rows


def build_sensitivity_rows(model: ValuationModel) -> list[dict[str, str]]:
    """Build the 5x5 direct-growth Base DCF sensitivity table."""

    return [
        {
            "wacc_row": str(cell.wacc_row),
            "growth_column": str(cell.growth_column),
            "wacc_delta": _text(cell.wacc_delta),
            "wacc": _text(cell.wacc),
            "displayed_wacc": _text(cell.displayed_wacc),
            "terminal_growth": _text(cell.terminal_growth),
            "illustrative_value_per_share": _text(cell.value_per_share),
            "is_center": str(cell.is_center).lower(),
            "status": "valuation_calculated",
            "notes": "Each cell recalculates the Base DCF at the stated full-precision WACC and terminal growth rate.",
        }
        for cell in model.sensitivity_cells
    ]


def build_validation_rows(checks: Iterable[ValuationCheck]) -> list[dict[str, str]]:
    """Convert valuation checks to a stable CSV schema."""

    return [
        {
            "check_id": check.check_id,
            "category": check.category,
            "scope": check.scope,
            "status": check.status,
            "actual": check.actual,
            "expected": check.expected,
            "difference": check.difference,
            "tolerance": check.tolerance,
            "details": check.details,
        }
        for check in checks
    ]


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write deterministic UTF-8 CSV output."""

    if not rows:
        raise ValueError(f"Cannot write empty valuation output: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def generate_valuation_artifacts(
    repository_root: Path,
    *,
    exports_dir: Path | None = None,
    charts_dir: Path | None = None,
) -> dict[str, object]:
    """Generate the complete deterministic Phase 5A output set."""

    model = build_valuation_model(repository_root)
    export_root = exports_dir or repository_root / DEFAULT_EXPORTS_DIR
    chart_root = charts_dir or repository_root / DEFAULT_CHARTS_DIR
    tables = (
        build_wacc_rows(model),
        build_cash_flow_rows(model),
        build_summary_rows(model),
        build_sensitivity_rows(model),
        build_validation_rows(model.checks),
    )
    table_paths: list[Path] = []
    for filename, rows in zip(VALUATION_EXPORT_FILENAMES, tables, strict=True):
        path = export_root / filename
        write_csv_rows(path, rows)
        table_paths.append(path)
    from nike_financial_analysis.charts import generate_valuation_charts

    chart_paths = generate_valuation_charts(tables[2], chart_root)
    return {
        "model": model,
        "table_paths": tuple(table_paths),
        "chart_paths": tuple(chart_paths),
        "checks": len(model.checks),
        "warnings": sum(
            check.status in {"warning", "strong_warning"} for check in model.checks
        ),
    }


def _parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 5A Python DCF valuation artifacts."
    )
    return parser.parse_args(arguments)


def main(arguments: Iterable[str] | None = None) -> int:
    _parse_args(arguments)
    root = find_repository_root(Path.cwd())
    result = generate_valuation_artifacts(root)
    model = result["model"]
    assert isinstance(model, ValuationModel)
    print("Phase 5A valuation artifacts generated without network access.")
    print(
        f"WACC: {model.wacc_primary.wacc:.6%} "
        f"(displayed {model.wacc_primary.wacc:.1%})"
    )
    for value in model.scenario_valuations:
        print(
            f"{value.scenario.title()}: USD {value.value_per_share:.2f} per share; "
            f"terminal value {value.terminal_value_share_of_ev:.1%} of enterprise value."
        )
    print(
        f"Validation: {result['checks']} checks; {result['warnings']} disclosed observations; 0 failures."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
