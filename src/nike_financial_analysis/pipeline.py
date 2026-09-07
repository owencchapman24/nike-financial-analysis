"""Build the five-year historical dataset, manifest, and validation summary."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from nike_financial_analysis.company_facts import (
    FactCandidate,
    FactSelectionError,
    FilingRecord,
    SelectionResult,
    TagRule,
    apply_documented_evidence,
    load_documented_evidence,
    load_filing_records,
    load_tag_rules,
    retrieve_company_facts,
    select_metric_fact,
)
from nike_financial_analysis.filing_statements import (
    extract_statement_value,
    find_face_statement_files,
    parse_statement_rows,
)
from nike_financial_analysis.metrics import (
    MetricValue,
    add,
    cagr,
    revenue_growth,
    safe_ratio,
    subtract,
)
from nike_financial_analysis.sec_client import SecClient, SecRequestError
from nike_financial_analysis.validation import (
    ValidationCheck,
    scan_generated_text,
    validate_historical_rows,
    validation_rows,
)


DEFAULT_FILING_INDEX = Path("data/metadata/filing_index.csv")
DEFAULT_TAG_MAP = Path("config/xbrl_tags.csv")
DEFAULT_DOCUMENTED_VALUES = Path("config/documented_values.csv")
DEFAULT_FINANCIALS = Path("data/processed/nike_financials.csv")
DEFAULT_MANIFEST = Path("data/metadata/source_manifest.csv")
DEFAULT_VALIDATION = Path("data/metadata/validation_summary.csv")

REPORTED_METRICS = (
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "total_selling_and_administrative_expense",
    "income_before_income_taxes",
    "interest_income_expense_nonoperating_net",
    "other_nonoperating_income_expense",
    "net_income",
    "diluted_eps",
    "diluted_weighted_average_shares",
    "cash_and_cash_equivalents",
    "short_term_investments",
    "accounts_receivable",
    "inventory",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "notes_payable_and_short_term_borrowings",
    "current_portion_long_term_debt",
    "noncurrent_long_term_debt",
    "current_operating_lease_liabilities",
    "noncurrent_operating_lease_liabilities",
    "shareholders_equity",
    "operating_cash_flow",
    "capital_expenditures",
    "depreciation_and_amortization",
)

CALCULATED_METRICS = (
    "derived_operating_income",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "operating_cash_flow_margin",
    "free_cash_flow",
    "free_cash_flow_margin",
    "cash_conversion",
    "total_interest_bearing_debt",
    "total_operating_lease_liabilities",
    "revenue_growth",
    "revenue_cagr_five_observations",
)

CALCULATION_FORMULAS = {
    "derived_operating_income": (
        "gross_profit - total_selling_and_administrative_expense"
    ),
    "gross_margin": "gross_profit / revenue",
    "operating_margin": "derived_operating_income / revenue",
    "net_margin": "net_income / revenue",
    "operating_cash_flow_margin": "operating_cash_flow / revenue",
    "free_cash_flow": "operating_cash_flow - capital_expenditures",
    "free_cash_flow_margin": "free_cash_flow / revenue",
    "cash_conversion": "operating_cash_flow / net_income",
    "total_interest_bearing_debt": (
        "notes_payable_and_short_term_borrowings + "
        "current_portion_long_term_debt + noncurrent_long_term_debt"
    ),
    "total_operating_lease_liabilities": (
        "current_operating_lease_liabilities + "
        "noncurrent_operating_lease_liabilities"
    ),
    "revenue_growth": "(revenue_t / revenue_t_minus_1) - 1",
    "revenue_cagr_five_observations": "(revenue_FY2026 / revenue_FY2022)^(1/4) - 1",
}


@dataclass(frozen=True)
class StatementEvidence:
    """One cached SEC-rendered statement used for face-value reconciliation."""

    statement_type: str
    accession_number: str
    source_url: str
    retrieval_timestamp: str
    content_sha256: str
    rows: list[list[str]]


def _archive_base(filing: FilingRecord) -> str:
    return filing.filing_url.rsplit("/", 1)[0]


def retrieve_statement_evidence(
    client: SecClient,
    filings: list[FilingRecord],
    *,
    force_refresh: bool = False,
) -> dict[tuple[str, str], StatementEvidence]:
    """Retrieve the three core face statements for each selected 10-K."""

    evidence: dict[tuple[str, str], StatementEvidence] = {}
    for filing in filings:
        compact_accession = filing.accession_number.replace("-", "")
        archive_base = _archive_base(filing)
        summary = client.get_text(
            f"{archive_base}/FilingSummary.xml",
            cache_key=f"filing_summary_{compact_accession}",
            force_refresh=force_refresh,
        )
        statement_files = find_face_statement_files(summary.text)
        for statement_type, file_name in statement_files.items():
            response = client.get_text(
                f"{archive_base}/{file_name}",
                cache_key=(
                    f"statement_{compact_accession}_{file_name.replace('.', '_')}"
                ),
                force_refresh=force_refresh,
            )
            evidence[(filing.accession_number, statement_type)] = StatementEvidence(
                statement_type=statement_type,
                accession_number=filing.accession_number,
                source_url=response.source_url,
                retrieval_timestamp=response.retrieved_at,
                content_sha256=response.content_sha256,
                rows=parse_statement_rows(response.text),
            )
    return evidence


def _reconciliation_tolerance(unit: str) -> Decimal:
    if unit == "USD per share":
        return Decimal("0.005")
    if unit == "shares millions":
        return Decimal("0.05")
    return Decimal("0.5")


def reconcile_selection(
    result: SelectionResult,
    evidence: dict[tuple[str, str], StatementEvidence],
) -> SelectionResult:
    """Require a face-statement match and prefer the latest visible presentation."""

    if result.status != "selected" or result.selected_candidate is None:
        return result

    best_priority = min(candidate.rule.priority for candidate in result.candidates)
    comparable = [
        candidate
        for candidate in result.candidates
        if candidate.rule.priority == best_priority
    ]
    for candidate in comparable:
        labels = candidate.rule.face_statement_labels
        if not labels:
            candidate.face_reconciliation_status = "component_check"
            candidate.face_reconciliation_note = (
                "No direct face line; validated against selected debt components."
            )
            continue
        statement = evidence.get(
            (candidate.source_filing.accession_number, candidate.rule.statement_type)
        )
        if statement is None:
            candidate.face_reconciliation_status = "unavailable"
            candidate.face_reconciliation_note = "Required rendered statement was unavailable."
            continue
        candidate.face_statement_url = statement.source_url
        candidate.face_statement_retrieval_timestamp = statement.retrieval_timestamp
        candidate.face_statement_sha256 = statement.content_sha256
        match = extract_statement_value(
            statement.rows,
            labels=labels,
            period_end=candidate.target_filing.period_end,
        )
        if match is None:
            candidate.face_reconciliation_status = "not_visible"
            candidate.face_reconciliation_note = (
                "The target period or label is not visible in this filing's face statement."
            )
            continue
        label, face_value = match
        candidate.face_statement_label = label
        candidate.face_statement_value = face_value
        if candidate.rule.sign_convention == "processed_positive":
            comparable_face_value = abs(face_value)
        elif candidate.rule.sign_convention == "reported_signed_face_opposite":
            comparable_face_value = -face_value
        else:
            comparable_face_value = face_value
        difference = abs(candidate.normalized_value - comparable_face_value)
        if difference <= _reconciliation_tolerance(candidate.normalized_unit):
            candidate.face_reconciliation_status = "verified"
            candidate.face_reconciliation_note = (
                "Company Facts value agrees with the SEC-rendered face statement "
                "within its displayed precision."
            )
        else:
            candidate.face_reconciliation_status = "mismatch"
            candidate.face_reconciliation_note = (
                f"Normalized fact differs from the face value by {difference}."
            )

    verified = [
        candidate
        for candidate in comparable
        if candidate.face_reconciliation_status in {"verified", "component_check"}
    ]
    if not verified:
        result.status = "manual_review"
        result.reason = "No eligible candidate could be reconciled to face-statement evidence."
        result.value = None
        result.normalized_unit = ""
        result.selected_candidate = None
        return result

    selected = max(
        verified,
        key=lambda candidate: (
            candidate.source_filing.filing_date,
            candidate.source_filing.accession_number,
            str(candidate.fact.get("frame", "")),
        ),
    )
    result.selected_candidate = selected
    result.value = selected.normalized_value
    result.normalized_unit = selected.normalized_unit
    result.reason = (
        "Comparable candidates agree; selected the latest highest-priority "
        "presentation that is visible in SEC face-statement evidence."
    )
    return result


def _metric_value(result: SelectionResult) -> MetricValue:
    return MetricValue(result.value, result.status, result.reason)


def calculate_metrics(
    selections: dict[tuple[int, str], SelectionResult],
    filings: list[FilingRecord],
) -> dict[tuple[int, str], MetricValue]:
    """Calculate requested metrics without allowing blocked inputs to flow through."""

    calculated: dict[tuple[int, str], MetricValue] = {}
    for index, filing in enumerate(filings):
        year = filing.fiscal_year
        get = lambda metric: _metric_value(selections[(year, metric)])
        revenue = get("revenue")
        gross_profit = get("gross_profit")
        selling_and_administrative = get(
            "total_selling_and_administrative_expense"
        )
        net_income = get("net_income")
        operating_cash_flow = get("operating_cash_flow")
        capital_expenditures = get("capital_expenditures")
        notes_payable = get("notes_payable_and_short_term_borrowings")
        current_long_term_debt = get("current_portion_long_term_debt")
        noncurrent_long_term_debt = get("noncurrent_long_term_debt")
        current_lease_liabilities = get("current_operating_lease_liabilities")
        noncurrent_lease_liabilities = get(
            "noncurrent_operating_lease_liabilities"
        )

        derived_operating_income = subtract(
            gross_profit, selling_and_administrative
        )
        free_cash_flow = subtract(operating_cash_flow, capital_expenditures)
        calculated[(year, "derived_operating_income")] = derived_operating_income
        calculated[(year, "gross_margin")] = safe_ratio(gross_profit, revenue)
        calculated[(year, "operating_margin")] = safe_ratio(
            derived_operating_income, revenue
        )
        calculated[(year, "net_margin")] = safe_ratio(net_income, revenue)
        calculated[(year, "operating_cash_flow_margin")] = safe_ratio(
            operating_cash_flow, revenue
        )
        calculated[(year, "free_cash_flow")] = free_cash_flow
        calculated[(year, "free_cash_flow_margin")] = safe_ratio(
            free_cash_flow, revenue
        )
        calculated[(year, "cash_conversion")] = safe_ratio(
            operating_cash_flow, net_income
        )
        calculated[(year, "total_interest_bearing_debt")] = add(
            notes_payable,
            current_long_term_debt,
            noncurrent_long_term_debt,
        )
        calculated[(year, "total_operating_lease_liabilities")] = add(
            current_lease_liabilities,
            noncurrent_lease_liabilities,
        )
        if index == 0:
            calculated[(year, "revenue_growth")] = MetricValue(
                None,
                "not_applicable",
                "The first observation has no prior-year value in this dataset.",
            )
        else:
            prior = _metric_value(
                selections[(filings[index - 1].fiscal_year, "revenue")]
            )
            calculated[(year, "revenue_growth")] = revenue_growth(revenue, prior)

        calculated[(year, "revenue_cagr_five_observations")] = MetricValue(
            None,
            "not_applicable",
            "The five-observation CAGR is displayed only on the final fiscal year.",
        )

    first_year = filings[0].fiscal_year
    last_year = filings[-1].fiscal_year
    calculated[(last_year, "revenue_cagr_five_observations")] = cagr(
        _metric_value(selections[(first_year, "revenue")]),
        _metric_value(selections[(last_year, "revenue")]),
        intervals=4,
    )
    return calculated


def _decimal_text(value: Decimal | None, *, ratio: bool = False) -> str:
    if value is None:
        return ""
    if ratio:
        value = value.quantize(Decimal("0.000001"))
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def build_financial_rows(
    filings: list[FilingRecord],
    selections: dict[tuple[int, str], SelectionResult],
    calculated: dict[tuple[int, str], MetricValue],
) -> list[dict[str, str]]:
    """Create a wide, recruiter-readable dataset with adjacent status columns."""

    rows: list[dict[str, str]] = []
    ratio_metrics = {
        "gross_margin",
        "operating_margin",
        "net_margin",
        "operating_cash_flow_margin",
        "free_cash_flow_margin",
        "cash_conversion",
        "revenue_growth",
        "revenue_cagr_five_observations",
    }
    for filing in filings:
        row = {
            "company_name": filing.company_name,
            "ticker": filing.ticker,
            "cik": filing.cik,
            "fiscal_year": f"FY{filing.fiscal_year}",
            "period_start": filing.period_start,
            "period_end": filing.period_end,
            "monetary_unit": "USD millions",
            "shares_unit": "millions",
            "ratio_unit": "decimal",
        }
        for metric in REPORTED_METRICS:
            result = selections[(filing.fiscal_year, metric)]
            row[metric] = _decimal_text(result.value)
            row[f"{metric}_status"] = result.status
        for metric in CALCULATED_METRICS:
            result = calculated[(filing.fiscal_year, metric)]
            row[metric] = _decimal_text(result.value, ratio=metric in ratio_metrics)
            row[f"{metric}_status"] = result.status
        rows.append(row)
    return rows


def _manifest_candidate_row(
    result: SelectionResult,
    candidate: FactCandidate,
    *,
    company_facts_url: str,
    retrieval_timestamp: str,
    content_sha256: str,
) -> dict[str, str]:
    is_selected = candidate is result.selected_candidate and result.status == "selected"
    selection_status = "selected" if is_selected else "candidate_not_selected"
    if result.status == "manual_review":
        selection_status = "manual_review"
    transformation = (
        f"{candidate.rule.expected_unit} divided by 1,000,000."
        if candidate.rule.expected_unit in {"USD", "shares"}
        else "Per-share value retained without scaling."
    )
    if candidate.rule.sign_convention == "processed_positive":
        transformation += " Absolute value retained as a positive investment amount."
    elif candidate.rule.sign_convention == "reported_signed_face_opposite":
        transformation += (
            " Positive normalized values represent income and negative values "
            "represent expense; the face-statement expense label uses the opposite sign."
        )
    supporting = result.documented_evidence
    return {
        "metric": result.metric,
        "fiscal_year_label": f"FY{result.filing.fiscal_year}",
        "period_start": str(candidate.fact.get("start", "")),
        "period_end": str(candidate.fact.get("end", "")),
        "reported_value": _decimal_text(candidate.reported_value),
        "normalized_value": _decimal_text(candidate.normalized_value),
        "reported_unit": candidate.rule.expected_unit,
        "normalized_unit": candidate.normalized_unit,
        "taxonomy": candidate.rule.taxonomy,
        "xbrl_concept": candidate.rule.tag,
        "sec_form": str(candidate.fact.get("form", "")),
        "filing_date": candidate.source_filing.filing_date,
        "accession_number": candidate.source_filing.accession_number,
        "source_url": candidate.source_filing.filing_url,
        "company_facts_url": company_facts_url,
        "retrieval_timestamp": retrieval_timestamp,
        "selection_status": selection_status,
        "selection_reason": result.reason,
        "value_type": "reported",
        "presentation_type": candidate.presentation_type,
        "transformation_notes": transformation,
        "statement_type": candidate.rule.statement_type,
        "period_type": candidate.rule.period_type,
        "fact_fiscal_year": str(candidate.fact.get("fy", "")),
        "fact_fiscal_period": str(candidate.fact.get("fp", "")),
        "frame": str(candidate.fact.get("frame", "")),
        "candidate_priority": str(candidate.rule.priority),
        "face_statement_url": candidate.face_statement_url,
        "face_statement_retrieval_timestamp": candidate.face_statement_retrieval_timestamp,
        "face_statement_sha256": candidate.face_statement_sha256,
        "face_statement_label": candidate.face_statement_label,
        "face_statement_value": _decimal_text(candidate.face_statement_value),
        "face_reconciliation_status": candidate.face_reconciliation_status,
        "face_reconciliation_note": candidate.face_reconciliation_note,
        "supporting_source_url": supporting.source_url if supporting else "",
        "supporting_source_retrieval_timestamp": (
            supporting.retrieval_timestamp if supporting else ""
        ),
        "supporting_source_sha256": supporting.content_sha256 if supporting else "",
        "supporting_source_label": supporting.source_label if supporting else "",
        "supporting_source_notes": supporting.notes if supporting else "",
        "content_sha256": content_sha256,
    }


def build_manifest_rows(
    filings: list[FilingRecord],
    selections: dict[tuple[int, str], SelectionResult],
    calculated: dict[tuple[int, str], MetricValue],
    *,
    company_facts_url: str,
    retrieval_timestamp: str,
    content_sha256: str,
) -> list[dict[str, str]]:
    """Retain selected facts, competing presentations, and calculation lineage."""

    rows: list[dict[str, str]] = []
    for filing in filings:
        for metric in REPORTED_METRICS:
            result = selections[(filing.fiscal_year, metric)]
            if result.candidates:
                rows.extend(
                    _manifest_candidate_row(
                        result,
                        candidate,
                        company_facts_url=company_facts_url,
                        retrieval_timestamp=retrieval_timestamp,
                        content_sha256=content_sha256,
                    )
                    for candidate in sorted(
                        result.candidates,
                        key=lambda item: (
                            item.rule.priority,
                            item.source_filing.filing_date,
                            item.source_filing.accession_number,
                            item.rule.tag,
                            str(item.fact.get("frame", "")),
                        ),
                    )
                )
            else:
                supporting = result.documented_evidence
                rows.append(
                    {
                        "metric": metric,
                        "fiscal_year_label": f"FY{filing.fiscal_year}",
                        "period_start": filing.period_start,
                        "period_end": filing.period_end,
                        "reported_value": (
                            _decimal_text(supporting.normalized_value)
                            if supporting
                            else ""
                        ),
                        "normalized_value": _decimal_text(result.value),
                        "reported_unit": supporting.normalized_unit if supporting else "",
                        "normalized_unit": result.normalized_unit,
                        "taxonomy": "",
                        "xbrl_concept": "",
                        "sec_form": "10-K" if supporting else "",
                        "filing_date": supporting.filing_date if supporting else "",
                        "accession_number": (
                            supporting.accession_number if supporting else ""
                        ),
                        "source_url": supporting.source_url if supporting else "",
                        "company_facts_url": company_facts_url,
                        "retrieval_timestamp": (
                            supporting.retrieval_timestamp
                            if supporting
                            else retrieval_timestamp
                        ),
                        "selection_status": result.status,
                        "selection_reason": result.reason,
                        "value_type": (
                            "documented_reported_zero" if supporting else "reported"
                        ),
                        "presentation_type": (
                            "documented_zero" if supporting else ""
                        ),
                        "transformation_notes": (
                            supporting.notes
                            if supporting
                            else "No normalized value produced."
                        ),
                        "statement_type": "balance_sheet" if supporting else "",
                        "period_type": "instant" if supporting else "",
                        "fact_fiscal_year": "",
                        "fact_fiscal_period": "",
                        "frame": "",
                        "candidate_priority": "",
                        "face_statement_url": "",
                        "face_statement_retrieval_timestamp": "",
                        "face_statement_sha256": "",
                        "face_statement_label": "",
                        "face_statement_value": "",
                        "face_reconciliation_status": (
                            "documented_zero" if supporting else "not_applicable"
                        ),
                        "face_reconciliation_note": result.reason,
                        "supporting_source_url": supporting.source_url if supporting else "",
                        "supporting_source_retrieval_timestamp": (
                            supporting.retrieval_timestamp if supporting else ""
                        ),
                        "supporting_source_sha256": (
                            supporting.content_sha256 if supporting else ""
                        ),
                        "supporting_source_label": (
                            supporting.source_label if supporting else ""
                        ),
                        "supporting_source_notes": supporting.notes if supporting else "",
                        "content_sha256": (
                            supporting.content_sha256 if supporting else content_sha256
                        ),
                    }
                )

        for metric in CALCULATED_METRICS:
            result = calculated[(filing.fiscal_year, metric)]
            face_url = ""
            face_retrieval_timestamp = ""
            face_sha256 = ""
            face_label = ""
            face_value: Decimal | None = None
            face_status = "not_applicable"
            face_note = "Calculated from selected inputs only."
            supporting = None
            if metric == "derived_operating_income":
                pretax = selections[
                    (filing.fiscal_year, "income_before_income_taxes")
                ]
                interest = selections[
                    (
                        filing.fiscal_year,
                        "interest_income_expense_nonoperating_net",
                    )
                ]
                other = selections[
                    (filing.fiscal_year, "other_nonoperating_income_expense")
                ]
                if (
                    pretax.value is not None
                    and interest.value is not None
                    and other.value is not None
                ):
                    face_value = pretax.value - interest.value - other.value
                candidate = pretax.selected_candidate
                if candidate is not None:
                    face_url = candidate.face_statement_url
                    face_retrieval_timestamp = (
                        candidate.face_statement_retrieval_timestamp
                    )
                    face_sha256 = candidate.face_statement_sha256
                face_label = (
                    "Income before taxes adjusted for signed interest and other "
                    "non-operating income or expense"
                )
                if result.value is not None and face_value == result.value:
                    face_status = "verified_cross_check"
                    face_note = (
                        "The independent pretax bridge equals derived operating "
                        "income. This is a consolidated calculation, not segment EBIT."
                    )
                else:
                    face_status = "mismatch"
                    face_note = "The independent pretax bridge does not reconcile."
            elif metric == "total_interest_bearing_debt":
                supporting = selections[
                    (
                        filing.fiscal_year,
                        "notes_payable_and_short_term_borrowings",
                    )
                ].documented_evidence
                face_note = (
                    "Calculated from the three validated interest-bearing debt "
                    "components; operating lease liabilities are excluded."
                )
            elif metric == "total_operating_lease_liabilities":
                face_note = (
                    "Calculated from current and noncurrent operating lease "
                    "liabilities and excluded from base interest-bearing debt."
                )
            rows.append(
                {
                    "metric": metric,
                    "fiscal_year_label": f"FY{filing.fiscal_year}",
                    "period_start": filing.period_start,
                    "period_end": filing.period_end,
                    "reported_value": "",
                    "normalized_value": _decimal_text(result.value, ratio=True),
                    "reported_unit": "",
                    "normalized_unit": (
                        "USD millions"
                        if metric
                        in {
                            "derived_operating_income",
                            "free_cash_flow",
                            "total_interest_bearing_debt",
                            "total_operating_lease_liabilities",
                        }
                        else "decimal"
                    ),
                    "taxonomy": "",
                    "xbrl_concept": "",
                    "sec_form": "",
                    "filing_date": "",
                    "accession_number": "",
                    "source_url": "",
                    "company_facts_url": company_facts_url,
                    "retrieval_timestamp": retrieval_timestamp,
                    "selection_status": result.status,
                    "selection_reason": result.reason,
                    "value_type": "calculated",
                    "presentation_type": "calculated",
                    "transformation_notes": CALCULATION_FORMULAS[metric],
                    "statement_type": "calculated",
                    "period_type": "duration",
                    "fact_fiscal_year": "",
                    "fact_fiscal_period": "",
                    "frame": "",
                    "candidate_priority": "",
                    "face_statement_url": face_url,
                    "face_statement_retrieval_timestamp": face_retrieval_timestamp,
                    "face_statement_sha256": face_sha256,
                    "face_statement_label": face_label,
                    "face_statement_value": _decimal_text(face_value),
                    "face_reconciliation_status": face_status,
                    "face_reconciliation_note": face_note,
                    "supporting_source_url": supporting.source_url if supporting else "",
                    "supporting_source_retrieval_timestamp": (
                        supporting.retrieval_timestamp if supporting else ""
                    ),
                    "supporting_source_sha256": (
                        supporting.content_sha256 if supporting else ""
                    ),
                    "supporting_source_label": (
                        supporting.source_label if supporting else ""
                    ),
                    "supporting_source_notes": supporting.notes if supporting else "",
                    "content_sha256": content_sha256,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write stable UTF-8 CSV output with explicit headers."""

    if not rows:
        raise FactSelectionError(f"Cannot write an empty CSV: {path}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _pipeline_checks(
    selections: dict[tuple[int, str], SelectionResult],
) -> list[ValidationCheck]:
    selected = [result for result in selections.values() if result.status == "selected"]
    annual_context_ok = all(
        result.selected_candidate is not None
        and result.selected_candidate.fact.get("form") == "10-K"
        and result.selected_candidate.fact.get("fp") == "FY"
        for result in selected
    )
    face_ok = all(
        result.selected_candidate is not None
        and result.selected_candidate.face_reconciliation_status
        in {"verified", "component_check"}
        for result in selected
    )
    documented_zeros = [
        result for result in selections.values() if result.status == "documented_zero"
    ]
    documented_zero_ok = all(
        result.value == 0
        and result.documented_evidence is not None
        and result.documented_evidence.evidence_status == "documented_zero"
        for result in documented_zeros
    )
    manual_metrics = sorted({result.metric for result in selections.values() if result.status == "manual_review"})
    return [
        ValidationCheck(
            "annual_context_selection",
            "source_manifest",
            "pass" if annual_context_ok else "fail",
            "Every selected reported fact is exact-form 10-K with fiscal period FY.",
        ),
        ValidationCheck(
            "face_statement_reconciliation",
            "source_manifest",
            "pass" if face_ok else "fail",
            "Every selected reported fact has direct face-statement or component evidence.",
        ),
        ValidationCheck(
            "documented_zero_evidence",
            "source_manifest",
            "pass" if documented_zero_ok else "fail",
            "Every documented zero is supported by a cached official SEC filing disclosure.",
        ),
        ValidationCheck(
            "manual_review_metrics",
            "source_manifest",
            "warning" if manual_metrics else "pass",
            "Metrics requiring owner review: " + ", ".join(manual_metrics)
            if manual_metrics
            else "No metrics require manual review.",
        ),
    ]


def run_pipeline(
    *,
    filing_index: Path = DEFAULT_FILING_INDEX,
    tag_map: Path = DEFAULT_TAG_MAP,
    documented_values: Path = DEFAULT_DOCUMENTED_VALUES,
    financials_output: Path = DEFAULT_FINANCIALS,
    manifest_output: Path = DEFAULT_MANIFEST,
    validation_output: Path = DEFAULT_VALIDATION,
    force_refresh: bool = False,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[ValidationCheck]]:
    """Run the complete Phase 2 pipeline and return generated records."""

    filings = load_filing_records(filing_index)
    rules = load_tag_rules(tag_map)
    client = SecClient.from_env()
    response = retrieve_company_facts(
        client,
        cik=filings[0].cik,
        force_refresh=force_refresh,
    )
    entity_name = str(response.data.get("entityName", "")).casefold()
    if "nike" not in entity_name:
        raise FactSelectionError("Company Facts entity name does not identify Nike.")
    evidence = retrieve_statement_evidence(
        client,
        filings,
        force_refresh=force_refresh,
    )
    documented = load_documented_evidence(
        documented_values,
        client=client,
        filings=filings,
        force_refresh=force_refresh,
    )

    selections: dict[tuple[int, str], SelectionResult] = {}
    for filing in filings:
        for metric in REPORTED_METRICS:
            result = select_metric_fact(
                response.data,
                metric=metric,
                rules=rules,
                target=filing,
                filings=filings,
            )
            reconciled = reconcile_selection(result, evidence)
            selections[(filing.fiscal_year, metric)] = apply_documented_evidence(
                reconciled,
                documented.get((filing.fiscal_year, metric)),
            )

    calculated = calculate_metrics(selections, filings)
    financial_rows = build_financial_rows(filings, selections, calculated)
    manifest_rows = build_manifest_rows(
        filings,
        selections,
        calculated,
        company_facts_url=response.source_url,
        retrieval_timestamp=response.retrieved_at,
        content_sha256=response.content_sha256,
    )
    write_csv(financials_output, financial_rows)
    write_csv(manifest_output, manifest_rows)

    checks = validate_historical_rows(financial_rows)
    checks.extend(_pipeline_checks(selections))
    checks.append(scan_generated_text([financials_output, manifest_output]))
    write_csv(validation_output, validation_rows(checks))
    return financial_rows, manifest_rows, checks


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Nike's reconciled five-year historical financial dataset."
    )
    parser.add_argument("--filing-index", type=Path, default=DEFAULT_FILING_INDEX)
    parser.add_argument("--tag-map", type=Path, default=DEFAULT_TAG_MAP)
    parser.add_argument(
        "--documented-values", type=Path, default=DEFAULT_DOCUMENTED_VALUES
    )
    parser.add_argument("--financials-output", type=Path, default=DEFAULT_FINANCIALS)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--force-refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Command-line entry point for the historical data pipeline."""

    args = _parse_args()
    try:
        financials, manifest, checks = run_pipeline(
            filing_index=args.filing_index,
            tag_map=args.tag_map,
            documented_values=args.documented_values,
            financials_output=args.financials_output,
            manifest_output=args.manifest_output,
            validation_output=args.validation_output,
            force_refresh=args.force_refresh,
        )
    except (FactSelectionError, SecRequestError, ValueError) as exc:
        raise SystemExit(f"Historical pipeline failed: {exc}") from exc
    failures = sum(check.status == "fail" for check in checks)
    warnings = sum(check.status == "warning" for check in checks)
    print(
        f"Wrote {len(financials)} fiscal years and {len(manifest)} manifest rows; "
        f"validation has {failures} failures and {warnings} warnings."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
