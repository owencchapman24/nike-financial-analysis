"""Build deterministic Phase 3 historical-analysis tables and charts."""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import pandas as pd

from nike_financial_analysis.metrics import (
    VALID_INPUT_STATUSES,
    MetricValue,
    add,
    revenue_growth,
    safe_ratio,
    subtract,
)


EXPECTED_FISCAL_YEARS = ("FY2022", "FY2023", "FY2024", "FY2025", "FY2026")
EXPECTED_PERIOD_ENDS = (
    "2022-05-31",
    "2023-05-31",
    "2024-05-31",
    "2025-05-31",
    "2026-05-31",
)
ALLOWED_STATUSES = VALID_INPUT_STATUSES | {
    "manual_review",
    "missing",
    "not_applicable",
}
DAY_COUNT_CONVENTION = Decimal("365")

DEFAULT_INPUT = Path("data/processed/nike_financials.csv")
DEFAULT_TABLES_DIR = Path("outputs/tables")
DEFAULT_CHARTS_DIR = Path("outputs/charts")

PROTECTED_PHASE2_HASHES = {
    Path("data/processed/nike_financials.csv"): (
        "4a6f2b44cacff50cddb7819c10144e388e83fd5d04c5a4c1edd1eac30d3d1a8e"
    ),
    Path("data/metadata/source_manifest.csv"): (
        "21d359174084953620833c72264fd2d4acde2fd256d663268d9f7602fa871198"
    ),
    Path("data/metadata/validation_summary.csv"): (
        "1de2419c03904b8ef603ba2e0657665c29ee8d6109ee2b29e775276c39cc84f8"
    ),
}


@dataclass(frozen=True)
class KpiDefinition:
    """Document one historical KPI and its presentation contract."""

    category: str
    metric: str
    display_name: str
    formula: str
    input_metrics: str
    unit: str
    applicable_years: str
    presentation_rounding: str
    notes: str = ""
    phase: str = "phase2"


@dataclass(frozen=True)
class HistoricalAnalysis:
    """Validated Phase 2 rows plus status-aware Phase 3 calculations."""

    source: pd.DataFrame
    phase3_metrics: dict[tuple[str, str], MetricValue]
    dynamic_notes: dict[tuple[str, str], str]


KPI_DEFINITIONS = (
    KpiDefinition("Revenue", "revenue", "Revenue", "Reported", "revenue", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Revenue", "revenue_growth", "Revenue growth", "(revenue_t / revenue_t-1) - 1", "revenue", "decimal", "FY2023-FY2026", "1 decimal percentage point"),
    KpiDefinition("Revenue", "revenue_cagr_five_observations", "Revenue CAGR", "(revenue_FY2026 / revenue_FY2022)^(1/4) - 1", "revenue", "decimal", "FY2026 endpoint", "1 decimal percentage point", "Five observations contain four growth intervals."),
    KpiDefinition("Revenue", "revenue_cumulative_change", "Revenue cumulative change", "revenue_FY2026 - revenue_FY2022", "revenue", "USD millions", "FY2026 endpoint", "Whole USD millions", phase="phase3"),
    KpiDefinition("Revenue", "revenue_cumulative_change_percent", "Revenue cumulative change", "(revenue_FY2026 / revenue_FY2022) - 1", "revenue", "decimal", "FY2026 endpoint", "1 decimal percentage point", phase="phase3"),
    KpiDefinition("Revenue", "peak_revenue", "Peak revenue", "maximum annual revenue", "revenue", "USD millions", "FY2022-FY2026 period", "Whole USD millions", "The associated fiscal year is retained in the row note.", "phase3"),
    KpiDefinition("Profitability", "gross_profit", "Gross profit", "Reported", "gross_profit", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Profitability", "gross_margin", "Gross margin", "gross_profit / revenue", "gross_profit; revenue", "decimal", "FY2022-FY2026", "1 decimal percentage point"),
    KpiDefinition("Profitability", "total_selling_and_administrative_expense", "Total SG&A", "Reported", "total_selling_and_administrative_expense", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Profitability", "sga_as_percent_of_revenue", "SG&A as a percentage of revenue", "total_selling_and_administrative_expense / revenue", "total_selling_and_administrative_expense; revenue", "decimal", "FY2022-FY2026", "1 decimal percentage point", phase="phase3"),
    KpiDefinition("Profitability", "derived_operating_income", "Derived operating income", "gross_profit - total_selling_and_administrative_expense", "gross_profit; total_selling_and_administrative_expense", "USD millions", "FY2022-FY2026", "Whole USD millions", "Calculated consolidated measure; Nike does not report this subtotal, and it is not segment EBIT."),
    KpiDefinition("Profitability", "operating_margin", "Derived operating margin", "derived_operating_income / revenue", "derived_operating_income; revenue", "decimal", "FY2022-FY2026", "1 decimal percentage point", "Uses derived operating income."),
    KpiDefinition("Profitability", "net_income", "Net income", "Reported", "net_income", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Profitability", "net_margin", "Net margin", "net_income / revenue", "net_income; revenue", "decimal", "FY2022-FY2026", "1 decimal percentage point"),
    KpiDefinition("Cash generation", "operating_cash_flow", "Operating cash flow", "Reported", "operating_cash_flow", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Cash generation", "capital_expenditures", "Capital expenditures", "Reported cash outflow normalized as a positive investment amount", "capital_expenditures", "USD millions", "FY2022-FY2026", "Whole USD millions", "Positive values represent investment spending."),
    KpiDefinition("Cash generation", "free_cash_flow", "Free cash flow", "operating_cash_flow - capital_expenditures", "operating_cash_flow; capital_expenditures", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Cash generation", "free_cash_flow_margin", "Free cash flow margin", "free_cash_flow / revenue", "free_cash_flow; revenue", "decimal", "FY2022-FY2026", "1 decimal percentage point"),
    KpiDefinition("Cash generation", "cash_conversion", "Cash conversion", "operating_cash_flow / net_income", "operating_cash_flow; net_income", "x", "FY2022-FY2026", "2 decimal places", "A value of 1.12 means 1.12x, not 1.12%."),
    KpiDefinition("Working capital and liquidity", "cash_and_cash_equivalents", "Cash and cash equivalents", "Reported", "cash_and_cash_equivalents", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "short_term_investments", "Short-term investments", "Reported", "short_term_investments", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "cash_and_short_term_investments", "Cash plus short-term investments", "cash_and_cash_equivalents + short_term_investments", "cash_and_cash_equivalents; short_term_investments", "USD millions", "FY2022-FY2026", "Whole USD millions", phase="phase3"),
    KpiDefinition("Working capital and liquidity", "current_assets", "Current assets", "Reported", "current_assets", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "current_liabilities", "Current liabilities", "Reported", "current_liabilities", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "current_ratio", "Current ratio", "current_assets / current_liabilities", "current_assets; current_liabilities", "x", "FY2022-FY2026", "2 decimal places", phase="phase3"),
    KpiDefinition("Working capital and liquidity", "net_working_capital", "Net working capital", "current_assets - current_liabilities", "current_assets; current_liabilities", "USD millions", "FY2022-FY2026", "Whole USD millions", "Broad balance-sheet measure, not operating net working capital.", "phase3"),
    KpiDefinition("Working capital and liquidity", "accounts_receivable", "Accounts receivable", "Reported", "accounts_receivable", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "accounts_receivable_growth", "Accounts receivable growth", "(accounts_receivable_t / accounts_receivable_t-1) - 1", "accounts_receivable", "decimal", "FY2023-FY2026", "1 decimal percentage point", phase="phase3"),
    KpiDefinition("Working capital and liquidity", "receivables_days_proxy", "Receivables days proxy", "average accounts_receivable / revenue * 365", "accounts_receivable; revenue", "days", "FY2023-FY2026", "1 decimal day", "Uses total revenue rather than separately disclosed credit sales; 365 is a consistent analytical convention.", "phase3"),
    KpiDefinition("Working capital and liquidity", "inventory", "Inventory", "Reported", "inventory", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Working capital and liquidity", "inventory_growth", "Inventory growth", "(inventory_t / inventory_t-1) - 1", "inventory", "decimal", "FY2023-FY2026", "1 decimal percentage point", phase="phase3"),
    KpiDefinition("Working capital and liquidity", "inventory_days", "Inventory days", "average inventory / cost_of_revenue * 365", "inventory; cost_of_revenue", "days", "FY2023-FY2026", "1 decimal day", "365 is a consistent analytical convention.", "phase3"),
    KpiDefinition("Capital structure", "notes_payable_and_short_term_borrowings", "Notes payable and short-term borrowings", "Reported or filing-supported documented zero", "notes_payable_and_short_term_borrowings", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Capital structure", "current_portion_long_term_debt", "Current portion of long-term debt", "Reported", "current_portion_long_term_debt", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Capital structure", "noncurrent_long_term_debt", "Noncurrent long-term debt", "Reported", "noncurrent_long_term_debt", "USD millions", "FY2022-FY2026", "Whole USD millions"),
    KpiDefinition("Capital structure", "total_interest_bearing_debt", "Total interest-bearing debt", "notes payable and short-term borrowings + current portion of long-term debt + noncurrent long-term debt", "notes_payable_and_short_term_borrowings; current_portion_long_term_debt; noncurrent_long_term_debt", "USD millions", "FY2022-FY2026", "Whole USD millions", "Excludes operating lease liabilities."),
    KpiDefinition("Capital structure", "total_operating_lease_liabilities", "Total operating lease liabilities", "current_operating_lease_liabilities + noncurrent_operating_lease_liabilities", "current_operating_lease_liabilities; noncurrent_operating_lease_liabilities", "USD millions", "FY2022-FY2026", "Whole USD millions", "Shown separately from base interest-bearing debt."),
    KpiDefinition("Capital structure", "net_debt_after_cash_and_short_term_investments", "Net debt after cash and short-term investments", "total_interest_bearing_debt - cash_and_cash_equivalents - short_term_investments", "total_interest_bearing_debt; cash_and_cash_equivalents; short_term_investments", "USD millions", "FY2022-FY2026", "Whole USD millions", "A negative value means net cash; operating lease liabilities are excluded.", "phase3"),
    KpiDefinition("Per share", "diluted_eps", "Diluted EPS", "Reported", "diluted_eps", "USD per share", "FY2022-FY2026", "2 decimal places"),
    KpiDefinition("Per share", "diluted_eps_growth", "Diluted EPS growth", "(diluted_eps_t / diluted_eps_t-1) - 1", "diluted_eps", "decimal", "FY2023-FY2026", "1 decimal percentage point", phase="phase3"),
    KpiDefinition("Per share", "diluted_weighted_average_shares", "Diluted weighted-average shares", "Reported", "diluted_weighted_average_shares", "millions", "FY2022-FY2026", "1 decimal million shares"),
)

DEFINITIONS_BY_METRIC = {item.metric: item for item in KPI_DEFINITIONS}
PHASE3_METRICS = frozenset(
    item.metric for item in KPI_DEFINITIONS if item.phase == "phase3"
)
SUMMARY_METRICS = (
    "revenue",
    "revenue_growth",
    "gross_margin",
    "sga_as_percent_of_revenue",
    "derived_operating_income",
    "operating_margin",
    "net_income",
    "net_margin",
    "operating_cash_flow",
    "capital_expenditures",
    "free_cash_flow",
    "free_cash_flow_margin",
    "cash_conversion",
    "cash_and_short_term_investments",
    "current_ratio",
    "net_working_capital",
    "accounts_receivable",
    "accounts_receivable_growth",
    "receivables_days_proxy",
    "inventory",
    "inventory_growth",
    "inventory_days",
    "total_interest_bearing_debt",
    "total_operating_lease_liabilities",
    "net_debt_after_cash_and_short_term_investments",
    "diluted_eps",
    "diluted_eps_growth",
    "diluted_weighted_average_shares",
)


def find_repository_root(start: Path | None = None) -> Path:
    """Find the repository root without embedding a machine-specific path."""

    current = (start or Path.cwd()).resolve()
    candidates = (current, *current.parents)
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / DEFAULT_INPUT
        ).is_file():
            return candidate
    raise FileNotFoundError(
        "Could not locate the repository root containing pyproject.toml and "
        "the committed historical dataset."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_phase2_hashes(repository_root: Path) -> dict[str, str]:
    """Confirm that all protected Phase 2 outputs remain byte-for-byte unchanged."""

    verified: dict[str, str] = {}
    for relative_path, expected in PROTECTED_PHASE2_HASHES.items():
        path = repository_root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Required Phase 2 input is missing: {relative_path}")
        actual = _sha256(path)
        if actual != expected:
            raise ValueError(
                f"Protected Phase 2 file changed unexpectedly: {relative_path}"
            )
        verified[relative_path.as_posix()] = actual
    return verified


def _required_source_metrics() -> set[str]:
    metrics = {
        metric
        for definition in KPI_DEFINITIONS
        for metric in definition.input_metrics.split("; ")
        if metric and metric not in PHASE3_METRICS
    }
    metrics.update(
        definition.metric
        for definition in KPI_DEFINITIONS
        if definition.phase == "phase2"
    )
    metrics.add("cost_of_revenue")
    return metrics


def load_historical_data(path: Path) -> pd.DataFrame:
    """Load Phase 2 data as strings and enforce the Phase 3 input contract."""

    if not path.is_file():
        raise FileNotFoundError(f"Historical dataset not found: {path.name}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required_columns = {"fiscal_year", "period_end"}
    for metric in _required_source_metrics():
        required_columns.update({metric, f"{metric}_status"})
    missing_columns = sorted(required_columns - set(frame.columns))
    if missing_columns:
        raise ValueError(
            "Historical dataset is missing required columns: "
            + ", ".join(missing_columns)
        )
    years = tuple(frame["fiscal_year"].tolist())
    period_ends = tuple(frame["period_end"].tolist())
    if years != EXPECTED_FISCAL_YEARS:
        raise ValueError(
            f"Expected fiscal years {EXPECTED_FISCAL_YEARS}; found {years}."
        )
    if period_ends != EXPECTED_PERIOD_ENDS:
        raise ValueError(
            f"Expected period ends {EXPECTED_PERIOD_ENDS}; found {period_ends}."
        )
    if frame["fiscal_year"].duplicated().any() or frame["period_end"].duplicated().any():
        raise ValueError("Fiscal years and period ends must be unique.")

    for metric in sorted(_required_source_metrics()):
        for year, value, status in frame[
            ["fiscal_year", metric, f"{metric}_status"]
        ].itertuples(index=False, name=None):
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"Unsupported status for {metric} in {year}: {status}")
            if status in VALID_INPUT_STATUSES:
                if value == "":
                    raise ValueError(
                        f"Validated metric {metric} in {year} has no value."
                    )
                try:
                    Decimal(value)
                except InvalidOperation as exc:
                    raise ValueError(
                        f"Metric {metric} in {year} is not a valid decimal."
                    ) from exc
            elif value != "":
                raise ValueError(
                    f"Blocked metric {metric} in {year} must not contain a value."
                )
    return frame


def _metric_value(row: dict[str, str], metric: str) -> MetricValue:
    status = row[f"{metric}_status"]
    raw = row[metric]
    return MetricValue(
        Decimal(raw) if raw != "" else None,
        status,
        f"Loaded from the committed Phase 2 field {metric}.",
    )


def _blocked_status(*inputs: MetricValue) -> str:
    return (
        "manual_review"
        if any(item.status == "manual_review" for item in inputs)
        else "missing"
    )


def _average(first: MetricValue, second: MetricValue) -> MetricValue:
    total = add(first, second)
    if total.status not in VALID_INPUT_STATUSES or total.value is None:
        return total
    return MetricValue(
        total.value / Decimal("2"),
        "calculated",
        "Calculated as the arithmetic average of validated opening and closing balances.",
    )


def _days_metric(
    opening: MetricValue,
    closing: MetricValue,
    denominator: MetricValue,
) -> MetricValue:
    average_balance = _average(opening, closing)
    ratio = safe_ratio(average_balance, denominator)
    if ratio.status not in VALID_INPUT_STATUSES or ratio.value is None:
        return ratio
    return MetricValue(
        ratio.value * DAY_COUNT_CONVENTION,
        "calculated",
        "Calculated from average balances using the approved 365-day convention.",
    )


def _not_applicable(reason: str) -> MetricValue:
    return MetricValue(None, "not_applicable", reason)


def calculate_phase3_metrics(
    frame: pd.DataFrame,
) -> tuple[dict[tuple[str, str], MetricValue], dict[tuple[str, str], str]]:
    """Calculate only approved Phase 3 KPIs using Decimal-compatible logic."""

    rows = frame.to_dict(orient="records")
    results: dict[tuple[str, str], MetricValue] = {}
    notes: dict[tuple[str, str], str] = {}

    for index, row in enumerate(rows):
        year = row["fiscal_year"]
        get = lambda metric: _metric_value(row, metric)

        results[(year, "sga_as_percent_of_revenue")] = safe_ratio(
            get("total_selling_and_administrative_expense"), get("revenue")
        )
        liquidity = add(
            get("cash_and_cash_equivalents"), get("short_term_investments")
        )
        results[(year, "cash_and_short_term_investments")] = liquidity
        results[(year, "current_ratio")] = safe_ratio(
            get("current_assets"), get("current_liabilities")
        )
        results[(year, "net_working_capital")] = subtract(
            get("current_assets"), get("current_liabilities")
        )
        results[(year, "net_debt_after_cash_and_short_term_investments")] = subtract(
            get("total_interest_bearing_debt"), liquidity
        )

        if index == 0:
            opening_note = (
                "FY2021 opening balances are not present; FY2022 is not applicable "
                "and is not estimated from ending balances."
            )
            for metric in (
                "accounts_receivable_growth",
                "receivables_days_proxy",
                "inventory_growth",
                "inventory_days",
            ):
                results[(year, metric)] = _not_applicable(opening_note)
                notes[(year, metric)] = opening_note
            eps_note = (
                "FY2022 is the first observation and has no prior-year diluted EPS "
                "in the committed dataset."
            )
            results[(year, "diluted_eps_growth")] = _not_applicable(eps_note)
            notes[(year, "diluted_eps_growth")] = eps_note
            continue

        prior = rows[index - 1]
        results[(year, "accounts_receivable_growth")] = revenue_growth(
            get("accounts_receivable"), _metric_value(prior, "accounts_receivable")
        )
        results[(year, "inventory_growth")] = revenue_growth(
            get("inventory"), _metric_value(prior, "inventory")
        )
        results[(year, "diluted_eps_growth")] = revenue_growth(
            get("diluted_eps"), _metric_value(prior, "diluted_eps")
        )
        results[(year, "receivables_days_proxy")] = _days_metric(
            _metric_value(prior, "accounts_receivable"),
            get("accounts_receivable"),
            get("revenue"),
        )
        results[(year, "inventory_days")] = _days_metric(
            _metric_value(prior, "inventory"),
            get("inventory"),
            get("cost_of_revenue"),
        )

    first_year = rows[0]["fiscal_year"]
    last_year = rows[-1]["fiscal_year"]
    first_revenue = _metric_value(rows[0], "revenue")
    last_revenue = _metric_value(rows[-1], "revenue")
    change = subtract(last_revenue, first_revenue)
    cumulative_percent = safe_ratio(change, first_revenue)
    for year in EXPECTED_FISCAL_YEARS[:-1]:
        for metric in (
            "revenue_cumulative_change",
            "revenue_cumulative_change_percent",
            "peak_revenue",
        ):
            results[(year, metric)] = _not_applicable(
                "This period-wide KPI is displayed only on the FY2026 endpoint row."
            )
    results[(last_year, "revenue_cumulative_change")] = change
    results[(last_year, "revenue_cumulative_change_percent")] = cumulative_percent

    revenues = [_metric_value(row, "revenue") for row in rows]
    if any(
        item.status not in VALID_INPUT_STATUSES or item.value is None
        for item in revenues
    ):
        status = _blocked_status(*revenues)
        results[(last_year, "peak_revenue")] = MetricValue(
            None, status, "A required annual revenue input is unavailable."
        )
    else:
        peak_index, peak_value = max(
            enumerate(revenues), key=lambda pair: pair[1].value
        )
        results[(last_year, "peak_revenue")] = MetricValue(
            peak_value.value,
            "calculated",
            "Maximum of the five validated annual revenue observations.",
        )
        notes[(last_year, "peak_revenue")] = (
            f"Peak revenue occurred in {rows[peak_index]['fiscal_year']}."
        )

    return results, notes


def build_analysis(frame: pd.DataFrame) -> HistoricalAnalysis:
    """Return a reusable, validated historical-analysis object."""

    phase3_metrics, notes = calculate_phase3_metrics(frame)
    return HistoricalAnalysis(frame, phase3_metrics, notes)


def _result_for(
    analysis: HistoricalAnalysis, row: dict[str, str], metric: str
) -> MetricValue:
    year = row["fiscal_year"]
    if metric in PHASE3_METRICS:
        return analysis.phase3_metrics[(year, metric)]
    return _metric_value(row, metric)


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _value_source(definition: KpiDefinition, result: MetricValue) -> str:
    if result.status == "documented_zero":
        return "filing_supported_documented_zero"
    if definition.phase == "phase3":
        return (
            "phase3_calculated"
            if result.status == "calculated"
            else "phase3_not_applicable_or_blocked"
        )
    if result.status == "selected":
        return "sec_reported"
    if result.status == "calculated":
        return "phase2_calculated"
    return "phase2_not_applicable_or_blocked"


def build_kpi_rows(analysis: HistoricalAnalysis) -> list[dict[str, str]]:
    """Create an audit-friendly long table with formula and status lineage."""

    rows: list[dict[str, str]] = []
    for source_row in analysis.source.to_dict(orient="records"):
        year = source_row["fiscal_year"]
        for definition in KPI_DEFINITIONS:
            result = _result_for(analysis, source_row, definition.metric)
            note_parts = [definition.notes]
            dynamic_note = analysis.dynamic_notes.get((year, definition.metric), "")
            if dynamic_note and dynamic_note not in note_parts:
                note_parts.append(dynamic_note)
            rows.append(
                {
                    "category": definition.category,
                    "metric": definition.metric,
                    "display_name": definition.display_name,
                    "fiscal_year": year,
                    "period_end": source_row["period_end"],
                    "value": _decimal_text(result.value),
                    "unit": definition.unit,
                    "status": result.status,
                    "value_source": _value_source(definition, result),
                    "formula": definition.formula,
                    "input_metrics": definition.input_metrics,
                    "applicable_fiscal_years": definition.applicable_years,
                    "presentation_rounding": definition.presentation_rounding,
                    "notes": " ".join(part for part in note_parts if part),
                }
            )
    return rows


def build_summary_rows(analysis: HistoricalAnalysis) -> list[dict[str, str]]:
    """Create a five-row wide historical summary with adjacent statuses."""

    rows: list[dict[str, str]] = []
    for source_row in analysis.source.to_dict(orient="records"):
        row = {
            "company_name": source_row["company_name"],
            "ticker": source_row["ticker"],
            "fiscal_year": source_row["fiscal_year"],
            "period_end": source_row["period_end"],
            "monetary_unit": "USD millions",
            "cash_conversion_unit": "x",
            "day_count_convention": "365",
            "net_debt_sign_convention": "negative value means net cash",
        }
        for metric in SUMMARY_METRICS:
            result = _result_for(analysis, source_row, metric)
            row[metric] = _decimal_text(result.value)
            row[f"{metric}_status"] = result.status
        rows.append(row)
    return rows


def format_presentation_value(value: str, unit: str) -> str:
    """Round a Decimal string only for human-facing notebook and README tables."""

    if value == "":
        return "N/A"
    number = Decimal(value)
    if unit == "USD millions":
        sign = "-" if number < 0 else ""
        return f"{sign}${abs(number):,.0f}"
    if unit == "USD per share":
        return f"${number:,.2f}"
    if unit == "decimal":
        return f"{number * Decimal('100'):.1f}%"
    if unit == "x":
        return f"{number:.2f}x"
    if unit == "days":
        return f"{number:.1f} days"
    if unit == "millions":
        return f"{number:,.1f}"
    return format(number, "f")


def build_presentation_table(
    kpi_rows: list[dict[str, str]], metrics: Iterable[str]
) -> pd.DataFrame:
    """Create a compact fiscal-year table without recalculating any KPI."""

    lookup = {
        (row["metric"], row["fiscal_year"]): row
        for row in kpi_rows
    }
    output: list[dict[str, str]] = []
    for metric in metrics:
        definition = DEFINITIONS_BY_METRIC[metric]
        row = {"Metric": definition.display_name}
        for year in EXPECTED_FISCAL_YEARS:
            observation = lookup[(metric, year)]
            row[year] = format_presentation_value(
                observation["value"], observation["unit"]
            )
        output.append(row)
    return pd.DataFrame(output)


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    """Write stable UTF-8 CSV output using the first row's field order."""

    if not rows:
        raise ValueError("Cannot write an empty analysis table.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_artifacts(
    repository_root: Path,
    *,
    input_path: Path | None = None,
    tables_dir: Path | None = None,
    charts_dir: Path | None = None,
) -> dict[str, object]:
    """Build both tables and all five charts without network access."""

    verify_phase2_hashes(repository_root)
    source_path = input_path or repository_root / DEFAULT_INPUT
    table_output = tables_dir or repository_root / DEFAULT_TABLES_DIR
    chart_output = charts_dir or repository_root / DEFAULT_CHARTS_DIR
    analysis = build_analysis(load_historical_data(source_path))
    summary_rows = build_summary_rows(analysis)
    kpi_rows = build_kpi_rows(analysis)

    table_paths = (
        table_output / "historical_summary.csv",
        table_output / "historical_kpis.csv",
    )
    write_csv_rows(table_paths[0], summary_rows)
    write_csv_rows(table_paths[1], kpi_rows)

    from nike_financial_analysis.charts import generate_all_charts

    chart_paths = generate_all_charts(kpi_rows, chart_output)
    return {
        "fiscal_years": EXPECTED_FISCAL_YEARS,
        "summary_rows": len(summary_rows),
        "kpi_rows": len(kpi_rows),
        "table_paths": table_paths,
        "chart_paths": chart_paths,
    }


def _parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Nike FY2022-FY2026 historical-analysis tables and charts."
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        help="Repository root; defaults to automatic discovery from the current directory.",
    )
    return parser.parse_args(arguments)


def main(arguments: Iterable[str] | None = None) -> int:
    """Run the local, network-free Phase 3 artifact pipeline."""

    args = _parse_args(arguments)
    root = find_repository_root(args.repository_root)
    result = generate_artifacts(root)
    print("Phase 3 historical-analysis artifacts generated.")
    print("Fiscal periods: FY2022-FY2026")
    print(f"Tables: {len(result['table_paths'])}; charts: {len(result['chart_paths'])}")
    print(
        f"Rows: {result['summary_rows']} summary; {result['kpi_rows']} KPI observations"
    )
    print("Input integrity: passed; network access: not used")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
