"""Decimal-based consolidated operating scenarios and unlevered FCFF forecast."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
from pathlib import Path
from typing import Iterable, Mapping

from nike_financial_analysis.analysis import find_repository_root, verify_phase2_hashes
from nike_financial_analysis.forecast_validation import (
    FORECAST_YEARS,
    REQUIRED_DRIVERS,
    SCENARIOS,
    ForecastCheck,
    require_passing,
    validate_assumption_rows,
    validate_forecast_rows,
)


INFORMATION_CUTOFF = "2026-09-07"
DEFAULT_HISTORICAL = Path("data/processed/nike_financials.csv")
DEFAULT_ASSUMPTIONS = Path("config/scenario_assumptions.csv")
DEFAULT_SOURCES = Path("config/forecast_sources.csv")
DEFAULT_TABLES_DIR = Path("outputs/tables")
DEFAULT_CHARTS_DIR = Path("outputs/charts")
PROTECTED_PHASE3_HASHES = {
    Path("outputs/tables/historical_summary.csv"): "109a874cda3da2ea3e58df05e243f5199f05c1efbc5755b6a154d152e0c21c27",
    Path("outputs/tables/historical_kpis.csv"): "cdc3d03dddf413c025c1ee0aa3bbe50f6159798deeff54bb1abcb9093b909060",
    Path("outputs/charts/01_revenue_and_growth.png"): "be2f204f92af59220b71c48d77eda31b442d1f471cc9ef47cc175db81679dbbf",
    Path("outputs/charts/02_margin_trends.png"): "d0dc582af284c9338920689b6d08b293f1d14d605f705697c7b6716dd9ad35d5",
    Path("outputs/charts/03_cash_generation.png"): "a2276144ef3f3f9188166ca06b02ba73fe4b10e1c2bee60ca66e97d5100632cc",
    Path("outputs/charts/04_working_capital_and_liquidity.png"): "eb49f61a87ff03d40bdc6ed3147978e0861b59fbafad658c1b96d0d8eabba8ec",
    Path("outputs/charts/05_capital_structure.png"): "4353c2ee4b281aa708326ec84e28e3ffca8cb86ac5d482eb1fc3a360d4b4f2e3",
    Path("notebooks/01_historical_analysis.ipynb"): "87ece80cc170079185bbdc050b5627135c128206dbae08d1c732e00e7a739a15",
}
FORECAST_TABLE_FILENAMES = (
    "scenario_forecast_long.csv",
    "scenario_forecast_summary.csv",
    "scenario_assumptions_resolved.csv",
    "forecast_validation_summary.csv",
)
VALID_HISTORICAL_STATUSES = frozenset({"selected", "calculated", "documented_zero"})


@dataclass(frozen=True)
class ForecastRow:
    """One scenario-year forecast calculated without presentation rounding."""

    scenario: str
    fiscal_year: str
    period_end: str
    revenue_growth: Decimal
    revenue: Decimal
    gross_margin: Decimal
    gross_profit: Decimal
    sga_percent_revenue: Decimal
    total_selling_and_administrative_expense: Decimal
    derived_operating_income: Decimal
    operating_margin: Decimal
    normalized_tax_rate: Decimal
    normalized_operating_tax_expense: Decimal
    nopat: Decimal
    da_percent_revenue: Decimal
    depreciation_and_amortization: Decimal
    capex_percent_revenue: Decimal
    capital_expenditures: Decimal
    operating_nwc_percent_revenue: Decimal
    operating_nwc_proxy: Decimal
    change_in_operating_nwc: Decimal
    fcff: Decimal
    fcff_margin: Decimal


@dataclass(frozen=True)
class ForecastModel:
    """Historical inputs, approved assumptions, forecast rows, and checks."""

    historical_rows: tuple[dict[str, str], ...]
    assumption_rows: tuple[dict[str, str], ...]
    source_rows: tuple[dict[str, str], ...]
    forecast_rows: tuple[ForecastRow, ...]
    checks: tuple[ForecastCheck, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_phase3_hashes(repository_root: Path) -> dict[str, str]:
    """Protect every committed Phase 3 table, chart, and notebook."""

    verified: dict[str, str] = {}
    for relative, expected in PROTECTED_PHASE3_HASHES.items():
        path = repository_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required Phase 3 artifact is missing: {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(f"Protected Phase 3 artifact changed: {relative}")
        verified[relative.as_posix()] = actual
    return verified


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required forecast input is missing: {path.name}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _decimal_text(value: Decimal | None) -> str:
    return "" if value is None else format(value, "f")


def _summary_text(value: Decimal | None, unit: str) -> str:
    """Round only the presentation-oriented summary, never model calculations."""

    if value is None:
        return ""
    quantum = Decimal("0.001") if unit == "decimal" else Decimal("1")
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return format(rounded, ".3f") if unit == "decimal" else format(rounded, "f")


def _number(row: Mapping[str, str], metric: str) -> Decimal:
    status = row.get(f"{metric}_status", "")
    if status not in VALID_HISTORICAL_STATUSES:
        raise ValueError(f"Historical input {metric} has invalid status {status!r}.")
    try:
        return Decimal(row[metric])
    except (InvalidOperation, KeyError) as exc:
        raise ValueError(f"Historical input {metric} is not a valid Decimal.") from exc


def operating_nwc_proxy(row: Mapping[str, str]) -> Decimal:
    """Calculate noncash, nondebt, nonlease current working capital."""

    operating_assets = (
        _number(row, "current_assets")
        - _number(row, "cash_and_cash_equivalents")
        - _number(row, "short_term_investments")
    )
    operating_liabilities = (
        _number(row, "current_liabilities")
        - _number(row, "notes_payable_and_short_term_borrowings")
        - _number(row, "current_portion_long_term_debt")
        - _number(row, "current_operating_lease_liabilities")
    )
    return operating_assets - operating_liabilities


def historical_effective_tax_rate(row: Mapping[str, str]) -> Decimal:
    """Derive tax expense from pretax income less net income."""

    pretax = _number(row, "income_before_income_taxes")
    if pretax == 0:
        raise ValueError("Historical effective tax rate has a zero pretax denominator.")
    return (pretax - _number(row, "net_income")) / pretax


def normalized_tax_expense(derived_operating_income: Decimal, tax_rate: Decimal) -> Decimal:
    """Apply tax only to positive operating income absent an explicit NOL schedule."""

    if derived_operating_income <= 0:
        return Decimal("0")
    return derived_operating_income * tax_rate


def load_assumption_rows(path: Path, *, require_approved: bool = True) -> list[dict[str, str]]:
    """Load and validate the canonical long-form assumption register."""

    rows = _read_csv(path)
    checks = validate_assumption_rows(rows, require_approved=require_approved)
    require_passing(checks)
    return rows


def _assumption_index(rows: Iterable[Mapping[str, str]]) -> dict[tuple[str, str, str], Decimal]:
    return {
        (row["scenario"], row["fiscal_year"], row["driver"]): Decimal(row["value"])
        for row in rows
    }


def calculate_forecast_rows(
    historical_rows: Iterable[Mapping[str, str]],
    assumption_rows: Iterable[Mapping[str, str]],
) -> list[ForecastRow]:
    """Calculate three five-year operating forecasts from the FY2026 opening state."""

    history = {row["fiscal_year"]: row for row in historical_rows}
    if tuple(sorted(history)) != ("FY2022", "FY2023", "FY2024", "FY2025", "FY2026"):
        raise ValueError("Historical input must contain exactly FY2022-FY2026.")
    opening = history["FY2026"]
    opening_revenue = _number(opening, "revenue")
    opening_onwc = operating_nwc_proxy(opening)
    assumptions = _assumption_index(assumption_rows)
    forecasts: list[ForecastRow] = []
    for scenario in SCENARIOS:
        prior_revenue = opening_revenue
        prior_onwc = opening_onwc
        for year in FORECAST_YEARS:
            value = lambda driver: assumptions[(scenario, year, driver)]
            growth = value("revenue_growth")
            revenue = prior_revenue * (Decimal("1") + growth)
            gross_margin = value("gross_margin")
            gross_profit = revenue * gross_margin
            sga_rate = value("sga_percent_revenue")
            sga = revenue * sga_rate
            derived = gross_profit - sga
            operating_margin = derived / revenue
            tax_rate = value("normalized_tax_rate")
            tax_expense = normalized_tax_expense(derived, tax_rate)
            nopat = derived - tax_expense
            da_rate = value("da_percent_revenue")
            da = revenue * da_rate
            capex_rate = value("capex_percent_revenue")
            capex = revenue * capex_rate
            onwc_rate = value("operating_nwc_percent_revenue")
            onwc = revenue * onwc_rate
            change_onwc = onwc - prior_onwc
            fcff = nopat + da - capex - change_onwc
            forecasts.append(
                ForecastRow(
                    scenario=scenario,
                    fiscal_year=year,
                    period_end=f"{year[2:]}-05-31",
                    revenue_growth=growth,
                    revenue=revenue,
                    gross_margin=gross_margin,
                    gross_profit=gross_profit,
                    sga_percent_revenue=sga_rate,
                    total_selling_and_administrative_expense=sga,
                    derived_operating_income=derived,
                    operating_margin=operating_margin,
                    normalized_tax_rate=tax_rate,
                    normalized_operating_tax_expense=tax_expense,
                    nopat=nopat,
                    da_percent_revenue=da_rate,
                    depreciation_and_amortization=da,
                    capex_percent_revenue=capex_rate,
                    capital_expenditures=capex,
                    operating_nwc_percent_revenue=onwc_rate,
                    operating_nwc_proxy=onwc,
                    change_in_operating_nwc=change_onwc,
                    fcff=fcff,
                    fcff_margin=fcff / revenue,
                )
            )
            prior_revenue = revenue
            prior_onwc = onwc
    return forecasts


def build_forecast_model(repository_root: Path) -> ForecastModel:
    """Load protected inputs, calculate forecasts, and run all model checks."""

    verify_phase2_hashes(repository_root)
    verify_phase3_hashes(repository_root)
    historical = _read_csv(repository_root / DEFAULT_HISTORICAL)
    assumptions = _read_csv(repository_root / DEFAULT_ASSUMPTIONS)
    sources = _read_csv(repository_root / DEFAULT_SOURCES)
    assumption_checks = validate_assumption_rows(assumptions)
    require_passing(assumption_checks)
    source_ids = {row["source_id"] for row in sources}
    unknown_sources = sorted({row["source_id"] for row in assumptions} - source_ids)
    cutoff_valid = all(
        row.get("information_cutoff") == INFORMATION_CUTOFF
        and date.fromisoformat(row["publication_date"])
        <= date.fromisoformat(INFORMATION_CUTOFF)
        for row in sources
    )
    source_check = ForecastCheck(
        "source_register",
        "sources",
        "pass" if not unknown_sources else "fail",
        "Every assumption source_id resolves in the forecast source register."
        if not unknown_sources
        else f"Unknown assumption source IDs: {', '.join(unknown_sources)}.",
    )
    forecasts = calculate_forecast_rows(historical, assumptions)
    forecast_checks = validate_forecast_rows([asdict(row) for row in forecasts])
    opening_revenue = _number(historical[-1], "revenue")
    opening_onwc = operating_nwc_proxy(historical[-1])
    roll_forward_valid = True
    for scenario in SCENARIOS:
        prior_revenue = opening_revenue
        prior_onwc = opening_onwc
        for forecast in (row for row in forecasts if row.scenario == scenario):
            if (
                forecast.revenue
                != prior_revenue * (Decimal("1") + forecast.revenue_growth)
                or forecast.change_in_operating_nwc
                != forecast.operating_nwc_proxy - prior_onwc
            ):
                roll_forward_valid = False
            prior_revenue = forecast.revenue
            prior_onwc = forecast.operating_nwc_proxy
    roll_forward_check = ForecastCheck(
        "forecast_roll_forwards",
        "forecast",
        "pass" if roll_forward_valid else "fail",
        "Revenue and operating-NWC roll-forwards, including the FY2026 opening balance, hold exactly."
        if roll_forward_valid
        else "A revenue or operating-NWC roll-forward failed.",
    )
    cutoff_check = ForecastCheck(
        "information_cutoff",
        "sources",
        "pass" if cutoff_valid else "fail",
        "Every source was available on or before September 7, 2026."
        if cutoff_valid
        else "A forecast source violates the approved information cutoff.",
    )
    checks = [
        *assumption_checks,
        source_check,
        cutoff_check,
        *forecast_checks,
        roll_forward_check,
    ]
    require_passing(checks)
    return ForecastModel(
        historical_rows=tuple(historical),
        assumption_rows=tuple(assumptions),
        source_rows=tuple(sources),
        forecast_rows=tuple(forecasts),
        checks=tuple(checks),
    )


FORECAST_METRICS = (
    ("revenue_growth", "Revenue growth", "decimal"),
    ("revenue", "Revenue", "USD millions"),
    ("gross_margin", "Gross margin", "decimal"),
    ("gross_profit", "Gross profit", "USD millions"),
    ("sga_percent_revenue", "SG&A as a percentage of revenue", "decimal"),
    ("total_selling_and_administrative_expense", "Total SG&A", "USD millions"),
    ("derived_operating_income", "Derived operating income", "USD millions"),
    ("operating_margin", "Derived operating margin", "decimal"),
    ("normalized_tax_rate", "Normalized operating tax rate", "decimal"),
    ("normalized_operating_tax_expense", "Normalized operating tax expense", "USD millions"),
    ("nopat", "NOPAT", "USD millions"),
    ("depreciation_and_amortization", "Depreciation and amortization", "USD millions"),
    ("da_percent_revenue", "D&A as a percentage of revenue", "decimal"),
    ("capital_expenditures", "Capital expenditures", "USD millions"),
    ("capex_percent_revenue", "Capital expenditures as a percentage of revenue", "decimal"),
    ("operating_nwc_proxy", "Operating NWC proxy", "USD millions"),
    ("operating_nwc_percent_revenue", "Operating NWC as a percentage of revenue", "decimal"),
    ("change_in_operating_nwc", "Change in operating NWC", "USD millions"),
    ("fcff", "Free cash flow to the firm", "USD millions"),
    ("fcff_margin", "FCFF margin", "decimal"),
)
FORECAST_FORMULAS = {
    "revenue_growth": "Approved project analyst scenario assumption.",
    "revenue": "revenue_t_minus_1 * (1 + revenue_growth)",
    "gross_margin": "Approved project analyst scenario assumption.",
    "gross_profit": "revenue * gross_margin",
    "sga_percent_revenue": "Approved project analyst scenario assumption.",
    "total_selling_and_administrative_expense": "revenue * sga_percent_revenue",
    "derived_operating_income": "gross_profit - total_selling_and_administrative_expense",
    "operating_margin": "derived_operating_income / revenue",
    "normalized_tax_rate": "Approved project analyst scenario assumption.",
    "normalized_operating_tax_expense": "max(derived_operating_income, 0) * normalized_tax_rate",
    "nopat": "derived_operating_income - normalized_operating_tax_expense",
    "da_percent_revenue": "Approved project analyst scenario assumption.",
    "depreciation_and_amortization": "revenue * da_percent_revenue",
    "capex_percent_revenue": "Approved project analyst scenario assumption.",
    "capital_expenditures": "revenue * capex_percent_revenue",
    "operating_nwc_percent_revenue": "Approved project analyst scenario assumption.",
    "operating_nwc_proxy": "revenue * operating_nwc_percent_revenue",
    "change_in_operating_nwc": "operating_nwc_proxy_t - operating_nwc_proxy_t_minus_1",
    "fcff": "nopat + depreciation_and_amortization - capital_expenditures - change_in_operating_nwc",
    "fcff_margin": "fcff / revenue",
}
FORECAST_INPUTS = {
    "revenue_growth": "revenue_growth",
    "revenue": "prior_year_revenue;revenue_growth",
    "gross_margin": "gross_margin",
    "gross_profit": "revenue;gross_margin",
    "sga_percent_revenue": "sga_percent_revenue",
    "total_selling_and_administrative_expense": "revenue;sga_percent_revenue",
    "derived_operating_income": "gross_profit;total_selling_and_administrative_expense",
    "operating_margin": "derived_operating_income;revenue",
    "normalized_tax_rate": "normalized_tax_rate",
    "normalized_operating_tax_expense": "derived_operating_income;normalized_tax_rate",
    "nopat": "derived_operating_income;normalized_operating_tax_expense",
    "da_percent_revenue": "da_percent_revenue",
    "depreciation_and_amortization": "revenue;da_percent_revenue",
    "capex_percent_revenue": "capex_percent_revenue",
    "capital_expenditures": "revenue;capex_percent_revenue",
    "operating_nwc_percent_revenue": "operating_nwc_percent_revenue",
    "operating_nwc_proxy": "revenue;operating_nwc_percent_revenue",
    "change_in_operating_nwc": "operating_nwc_proxy_t;operating_nwc_proxy_t_minus_1",
    "fcff": "nopat;depreciation_and_amortization;capital_expenditures;change_in_operating_nwc",
    "fcff_margin": "fcff;revenue",
}
METRIC_DRIVER_LINEAGE = {
    "revenue_growth": ("revenue_growth",),
    "revenue": ("revenue_growth",),
    "gross_margin": ("gross_margin",),
    "gross_profit": ("revenue_growth", "gross_margin"),
    "sga_percent_revenue": ("sga_percent_revenue",),
    "total_selling_and_administrative_expense": ("revenue_growth", "sga_percent_revenue"),
    "derived_operating_income": ("revenue_growth", "gross_margin", "sga_percent_revenue"),
    "operating_margin": ("gross_margin", "sga_percent_revenue"),
    "normalized_tax_rate": ("normalized_tax_rate",),
    "normalized_operating_tax_expense": (
        "revenue_growth",
        "gross_margin",
        "sga_percent_revenue",
        "normalized_tax_rate",
    ),
    "nopat": (
        "revenue_growth",
        "gross_margin",
        "sga_percent_revenue",
        "normalized_tax_rate",
    ),
    "da_percent_revenue": ("da_percent_revenue",),
    "depreciation_and_amortization": ("revenue_growth", "da_percent_revenue"),
    "capex_percent_revenue": ("capex_percent_revenue",),
    "capital_expenditures": ("revenue_growth", "capex_percent_revenue"),
    "operating_nwc_percent_revenue": ("operating_nwc_percent_revenue",),
    "operating_nwc_proxy": ("revenue_growth", "operating_nwc_percent_revenue"),
    "change_in_operating_nwc": ("revenue_growth", "operating_nwc_percent_revenue"),
    "fcff": REQUIRED_DRIVERS,
    "fcff_margin": REQUIRED_DRIVERS,
}


def _historical_calculations(rows: Iterable[Mapping[str, str]]) -> dict[str, dict[str, Decimal | None]]:
    output: dict[str, dict[str, Decimal | None]] = {}
    prior_onwc: Decimal | None = None
    for row in rows:
        year = row["fiscal_year"]
        revenue = _number(row, "revenue")
        onwc = operating_nwc_proxy(row)
        change = None if prior_onwc is None else onwc - prior_onwc
        tax_rate = historical_effective_tax_rate(row)
        derived = _number(row, "derived_operating_income")
        tax_expense = normalized_tax_expense(derived, tax_rate)
        nopat = derived - tax_expense
        fcff = None
        if change is not None:
            fcff = (
                nopat
                + _number(row, "depreciation_and_amortization")
                - _number(row, "capital_expenditures")
                - change
            )
        output[year] = {
            "revenue_growth": None if row["revenue_growth"] == "" else _number(row, "revenue_growth"),
            "revenue": revenue,
            "gross_margin": _number(row, "gross_margin"),
            "gross_profit": _number(row, "gross_profit"),
            "sga_percent_revenue": _number(row, "total_selling_and_administrative_expense") / revenue,
            "total_selling_and_administrative_expense": _number(row, "total_selling_and_administrative_expense"),
            "derived_operating_income": derived,
            "operating_margin": _number(row, "operating_margin"),
            "normalized_tax_rate": tax_rate,
            "normalized_operating_tax_expense": tax_expense,
            "nopat": nopat,
            "depreciation_and_amortization": _number(row, "depreciation_and_amortization"),
            "da_percent_revenue": _number(row, "depreciation_and_amortization") / revenue,
            "capital_expenditures": _number(row, "capital_expenditures"),
            "capex_percent_revenue": _number(row, "capital_expenditures") / revenue,
            "operating_nwc_proxy": onwc,
            "operating_nwc_percent_revenue": onwc / revenue,
            "change_in_operating_nwc": change,
            "fcff": fcff,
            "fcff_margin": None if fcff is None else fcff / revenue,
        }
        prior_onwc = onwc
    return output


def build_long_rows(model: ForecastModel) -> list[dict[str, str]]:
    """Create auditable actual and forecast observations with formula lineage."""

    rows: list[dict[str, str]] = []
    actuals = _historical_calculations(model.historical_rows)
    actual_periods = {row["fiscal_year"]: row["period_end"] for row in model.historical_rows}
    actual_source_rows = {row["fiscal_year"]: row for row in model.historical_rows}
    directly_reported = {
        "revenue",
        "gross_profit",
        "total_selling_and_administrative_expense",
        "depreciation_and_amortization",
        "capital_expenditures",
    }
    for year, values in actuals.items():
        source_row = actual_source_rows[year]
        for metric, display_name, unit in FORECAST_METRICS:
            value = values[metric]
            source_status = source_row.get(f"{metric}_status", "")
            if value is None:
                status = "not_applicable"
            elif metric in directly_reported:
                status = source_status
            else:
                status = "calculated"
            rows.append(
                {
                    "scenario": "actual",
                    "fiscal_year": year,
                    "period_end": actual_periods[year],
                    "period_class": "actual",
                    "metric": metric,
                    "display_name": (
                        "Historical effective tax rate"
                        if metric == "normalized_tax_rate"
                        else display_name
                    ),
                    "value": _decimal_text(value),
                    "unit": unit,
                    "status": status,
                    "value_source": (
                        "committed_sec_reported_history"
                        if metric in directly_reported
                        else "committed_sec_derived_history"
                    ),
                    "formula": "See Phase 2-3 lineage and Phase 4 historical bridge.",
                    "input_metrics": "data/processed/nike_financials.csv",
                    "source_ids": "FS01;FS02;FS03",
                    "notes": "Derived operating income is not Nike-reported EBIT or segment EBIT.",
                }
            )
    for forecast in model.forecast_rows:
        values = asdict(forecast)
        assumption_sources = {
            row["driver"]: row["source_id"]
            for row in model.assumption_rows
            if row["scenario"] == forecast.scenario
            and row["fiscal_year"] == forecast.fiscal_year
        }
        for metric, display_name, unit in FORECAST_METRICS:
            source_ids = sorted(
                {assumption_sources[driver] for driver in METRIC_DRIVER_LINEAGE[metric]}
            )
            rows.append(
                {
                    "scenario": forecast.scenario,
                    "fiscal_year": forecast.fiscal_year,
                    "period_end": forecast.period_end,
                    "period_class": "forecast",
                    "metric": metric,
                    "display_name": display_name,
                    "value": _decimal_text(values[metric]),
                    "unit": unit,
                    "status": "forecast_calculated",
                    "value_source": "project_analyst_scenario",
                    "formula": FORECAST_FORMULAS[metric],
                    "input_metrics": FORECAST_INPUTS[metric],
                    "source_ids": ";".join(source_ids),
                    "notes": "Project analyst scenario; no valuation or probability assigned.",
                }
            )
    return rows


def build_summary_rows(model: ForecastModel) -> list[dict[str, str]]:
    """Create a readable scenario-by-metric table with an FY2026 actual anchor."""

    actual = _historical_calculations(model.historical_rows)["FY2026"]
    by_key = {(row.scenario, row.fiscal_year): row for row in model.forecast_rows}
    metric_notes = {
        "revenue_growth": "Nominal reported-basis consolidated revenue growth.",
        "revenue": "Nominal reported-basis consolidated revenue in USD millions.",
        "gross_margin": "FY2026 reported gross margin includes an approximately 210-basis-point IEEPA tariff-recovery benefit; no adjusted actual is substituted.",
        "sga_percent_revenue": "Total consolidated SG&A as a percentage of revenue.",
        "derived_operating_income": "Project-derived operating income equals gross profit less total SG&A; it is not Nike-reported EBIT or segment EBIT.",
        "operating_margin": "Uses project-derived operating income, not a Nike-reported consolidated subtotal.",
        "normalized_tax_rate": "FY2026 is the historical effective rate; forecasts use the project's normalized 21.0% operating tax rate within Nike's low-20% outlook range.",
        "normalized_operating_tax_expense": "No automatic tax benefit is recognized for an operating loss without a documented NOL schedule.",
        "nopat": "Derived operating income less normalized operating tax expense; interest is excluded.",
        "capital_expenditures": "Positive values represent investment spending.",
        "capex_percent_revenue": "Positive capital-expenditure reinvestment rate.",
        "operating_nwc_proxy": "Aggregate noncash, nondebt, nonlease current-balance proxy; some tax and other balances may remain embedded.",
        "operating_nwc_percent_revenue": "Aggregate operating-NWC proxy divided by revenue.",
        "change_in_operating_nwc": "Closing less opening operating NWC; a positive change uses cash and reduces FCFF.",
        "fcff": "Historical project FCFF and scenario FCFF use NOPAT + D&A - capex - change in operating NWC; this differs from Phase 3 historical FCF.",
        "fcff_margin": "FCFF divided by revenue. Operating leases remain in operating expense and are not separately adjusted.",
    }
    rows: list[dict[str, str]] = []
    for scenario in SCENARIOS:
        for metric, display_name, unit in FORECAST_METRICS:
            if metric == "normalized_tax_rate":
                display_name = "Historical effective / forecast normalized operating tax rate"
            row = {
                "scenario": scenario,
                "metric": metric,
                "display_name": display_name,
                "unit": unit,
                "FY2026_actual": _summary_text(actual[metric], unit),
                "presentation_rounding": (
                    "Decimal ratio rounded to 0.001 (one decimal percentage point); authoritative precision in scenario_forecast_long.csv"
                    if unit == "decimal"
                    else "Whole USD millions; authoritative precision in scenario_forecast_long.csv"
                ),
                "notes": metric_notes.get(metric, ""),
            }
            for year in FORECAST_YEARS:
                row[year] = _summary_text(
                    getattr(by_key[(scenario, year)], metric), unit
                )
            rows.append(row)
    return rows


def build_resolved_assumption_rows(model: ForecastModel) -> list[dict[str, str]]:
    """Join approved assumptions to normalized source metadata."""

    sources = {row["source_id"]: row for row in model.source_rows}
    rows: list[dict[str, str]] = []
    for assumption in model.assumption_rows:
        source = sources[assumption["source_id"]]
        rows.append(
            {
                **assumption,
                "source_title": source["title"],
                "publisher": source["publisher"],
                "publication_date": source["publication_date"],
                "information_cutoff": source["information_cutoff"],
                "source_url_or_reference": source["url_or_accession"],
                "validation_status": "approved_and_resolved",
            }
        )
    return rows


def validation_rows(checks: Iterable[ForecastCheck]) -> list[dict[str, str]]:
    return [
        {
            "check_id": check.check_id,
            "scope": check.scope,
            "scenario": "all",
            "fiscal_year": "FY2027-FY2031",
            "status": check.status,
            "details": check.details,
        }
        for check in checks
    ]


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write deterministic UTF-8 CSV output with stable field ordering."""

    if not rows:
        raise ValueError(f"Cannot write an empty forecast table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def generate_forecast_artifacts(
    repository_root: Path,
    *,
    tables_dir: Path | None = None,
    charts_dir: Path | None = None,
) -> dict[str, object]:
    """Generate all Phase 4 tables and charts without network access."""

    model = build_forecast_model(repository_root)
    table_dir = tables_dir or repository_root / DEFAULT_TABLES_DIR
    chart_dir = charts_dir or repository_root / DEFAULT_CHARTS_DIR
    table_rows = (
        build_long_rows(model),
        build_summary_rows(model),
        build_resolved_assumption_rows(model),
        validation_rows(model.checks),
    )
    table_paths = tuple(table_dir / name for name in FORECAST_TABLE_FILENAMES)
    for path, rows in zip(table_paths, table_rows, strict=True):
        write_csv_rows(path, rows)
    from nike_financial_analysis.charts import generate_forecast_charts

    chart_paths = tuple(generate_forecast_charts(build_long_rows(model), chart_dir))
    return {
        "model": model,
        "table_paths": table_paths,
        "chart_paths": chart_paths,
        "forecast_rows": len(model.forecast_rows),
        "assumption_rows": len(model.assumption_rows),
        "validation_checks": len(model.checks),
    }


def _parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Nike FY2027-FY2031 operating scenarios.")
    parser.add_argument("--tables-dir", type=Path)
    parser.add_argument("--charts-dir", type=Path)
    return parser.parse_args(arguments)


def main(arguments: Iterable[str] | None = None) -> int:
    args = _parse_args(arguments)
    root = find_repository_root(Path.cwd())
    result = generate_forecast_artifacts(
        root,
        tables_dir=args.tables_dir,
        charts_dir=args.charts_dir,
    )
    print("Phase 4 operating-scenario artifacts generated.")
    print("Forecast periods: FY2027-FY2031; scenarios: base, bull, bear")
    print(
        f"Assumptions: {result['assumption_rows']}; forecast rows: {result['forecast_rows']}; "
        f"validation checks: {result['validation_checks']}"
    )
    print("Tables: 4; charts: 4; network access: not used; valuation: not included")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
