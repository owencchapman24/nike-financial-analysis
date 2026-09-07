"""Deterministic selection of annual facts from the SEC Company Facts API."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from nike_financial_analysis.sec_client import SecClient, SecJsonResponse


COMPANY_FACTS_URL_TEMPLATE = (
    "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
)
ELIGIBLE_RULE_STATUSES = frozenset({"verified", "verified_fallback"})


class FactSelectionError(ValueError):
    """Raised when fact configuration or SEC metadata is structurally invalid."""


@dataclass(frozen=True)
class FilingRecord:
    """The filing metadata needed to validate Company Facts observations."""

    company_name: str
    ticker: str
    cik: str
    fiscal_year: int
    period_start: str
    period_end: str
    form: str
    filing_date: str
    accession_number: str
    filing_url: str


@dataclass(frozen=True)
class TagRule:
    """One ordered XBRL candidate for a requested historical metric."""

    metric: str
    statement_type: str
    period_type: str
    expected_unit: str
    priority: int
    taxonomy: str
    tag: str
    verification_status: str
    sign_convention: str
    face_statement_labels: tuple[str, ...]
    notes: str


@dataclass
class FactCandidate:
    """One eligible reported fact retained for provenance and comparison."""

    metric: str
    rule: TagRule
    target_filing: FilingRecord
    source_filing: FilingRecord
    fact: dict[str, Any]
    reported_value: Decimal
    normalized_value: Decimal
    normalized_unit: str
    presentation_type: str
    face_statement_url: str = ""
    face_statement_retrieval_timestamp: str = ""
    face_statement_sha256: str = ""
    face_statement_label: str = ""
    face_statement_value: Decimal | None = None
    face_reconciliation_status: str = "not_checked"
    face_reconciliation_note: str = ""


@dataclass
class SelectionResult:
    """The output status and provenance candidates for one metric-year."""

    metric: str
    filing: FilingRecord
    status: str
    reason: str
    value: Decimal | None = None
    normalized_unit: str = ""
    selected_candidate: FactCandidate | None = None
    candidates: list[FactCandidate] = field(default_factory=list)
    documented_evidence: DocumentedEvidence | None = None


@dataclass
class DocumentedEvidence:
    """Primary-source evidence used to corroborate or supply a documented zero."""

    metric: str
    fiscal_year: int
    period_end: str
    normalized_value: Decimal
    normalized_unit: str
    evidence_status: str
    filing_date: str
    accession_number: str
    source_url: str
    cache_key: str
    source_label: str
    notes: str
    retrieval_timestamp: str = ""
    content_sha256: str = ""


def company_facts_url(cik: str) -> str:
    """Build the official SEC Company Facts URL for a ten-digit CIK."""

    if len(cik) != 10 or not cik.isdigit():
        raise FactSelectionError("Company Facts requires a ten-digit numeric CIK.")
    return COMPANY_FACTS_URL_TEMPLATE.format(cik=cik)


def retrieve_company_facts(
    client: SecClient,
    *,
    cik: str,
    force_refresh: bool = False,
) -> SecJsonResponse:
    """Retrieve or reuse the exact cached Company Facts response."""

    return client.get_json(
        company_facts_url(cik),
        cache_key=f"companyfacts_CIK{cik}",
        force_refresh=force_refresh,
    )


def _expected_period_start(period_end: str) -> str:
    end = date.fromisoformat(period_end)
    prior_end = end.replace(year=end.year - 1)
    return (prior_end + timedelta(days=1)).isoformat()


def load_filing_records(path: Path) -> list[FilingRecord]:
    """Load five chronological filing records and verify their key metadata."""

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 5:
        raise FactSelectionError(
            f"Expected exactly five filing-index rows; found {len(rows)}."
        )

    filings: list[FilingRecord] = []
    for row in rows:
        period_end = row["period_end"].strip()
        fiscal_year = int(row["fiscal_year"])
        if fiscal_year != date.fromisoformat(period_end).year:
            raise FactSelectionError(
                f"Fiscal-year label does not match period end {period_end}."
            )
        filings.append(
            FilingRecord(
                company_name=row["company_name"].strip(),
                ticker=row["ticker"].strip(),
                cik=row["cik"].strip().zfill(10),
                fiscal_year=fiscal_year,
                period_start=_expected_period_start(period_end),
                period_end=period_end,
                form=row["form"].strip(),
                filing_date=row["filing_date"].strip(),
                accession_number=row["accession_number"].strip(),
                filing_url=row["filing_url"].strip(),
            )
        )

    period_ends = [filing.period_end for filing in filings]
    if period_ends != sorted(period_ends) or len(set(period_ends)) != len(period_ends):
        raise FactSelectionError("Filing periods must be unique and chronological.")
    if any(filing.form != "10-K" for filing in filings):
        raise FactSelectionError("The historical pipeline accepts exact-form 10-K rows only.")
    if len({filing.cik for filing in filings}) != 1:
        raise FactSelectionError("Filing-index rows must refer to one CIK.")
    return filings


def load_tag_rules(path: Path) -> list[TagRule]:
    """Load and validate the documented XBRL candidate mapping."""

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "metric",
        "statement_type",
        "period_type",
        "expected_unit",
        "priority",
        "taxonomy",
        "tag",
        "verification_status",
        "sign_convention",
        "face_statement_labels",
        "notes",
    }
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise FactSelectionError(
            "XBRL tag map is missing columns: " + ", ".join(sorted(missing))
        )

    rules = [
        TagRule(
            metric=row["metric"].strip(),
            statement_type=row["statement_type"].strip(),
            period_type=row["period_type"].strip(),
            expected_unit=row["expected_unit"].strip(),
            priority=int(row["priority"]),
            taxonomy=row["taxonomy"].strip(),
            tag=row["tag"].strip(),
            verification_status=row["verification_status"].strip(),
            sign_convention=row["sign_convention"].strip(),
            face_statement_labels=tuple(
                label.strip()
                for label in row["face_statement_labels"].split(";")
                if label.strip()
            ),
            notes=row["notes"].strip(),
        )
        for row in rows
    ]
    if any(rule.period_type not in {"duration", "instant"} for rule in rules):
        raise FactSelectionError("Tag-map period_type must be duration or instant.")
    if any(rule.expected_unit not in {"USD", "USD/shares", "shares"} for rule in rules):
        raise FactSelectionError("Tag map contains an unsupported expected unit.")
    return sorted(rules, key=lambda rule: (rule.metric, rule.priority, rule.tag))


def load_documented_evidence(
    path: Path,
    *,
    client: SecClient,
    filings: list[FilingRecord],
    force_refresh: bool = False,
) -> dict[tuple[int, str], DocumentedEvidence]:
    """Load primary-source corroboration and cache each referenced SEC document."""

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "metric",
        "fiscal_year",
        "period_end",
        "normalized_value",
        "normalized_unit",
        "evidence_status",
        "filing_date",
        "accession_number",
        "source_url",
        "cache_key",
        "source_label",
        "notes",
    }
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise FactSelectionError(
            "Documented-value map is missing columns: " + ", ".join(sorted(missing))
        )

    filings_by_year = {filing.fiscal_year: filing for filing in filings}
    evidence: dict[tuple[int, str], DocumentedEvidence] = {}
    for row in rows:
        fiscal_year = int(row["fiscal_year"])
        filing = filings_by_year.get(fiscal_year)
        if filing is None:
            raise FactSelectionError(
                f"Documented evidence refers to unsupported fiscal year {fiscal_year}."
            )
        if (
            row["period_end"].strip() != filing.period_end
            or row["filing_date"].strip() != filing.filing_date
            or row["accession_number"].strip() != filing.accession_number
        ):
            raise FactSelectionError(
                f"Documented evidence does not match the FY{fiscal_year} filing index."
            )
        response = client.get_text(
            row["source_url"].strip(),
            cache_key=row["cache_key"].strip(),
            force_refresh=force_refresh,
        )
        item = DocumentedEvidence(
            metric=row["metric"].strip(),
            fiscal_year=fiscal_year,
            period_end=row["period_end"].strip(),
            normalized_value=Decimal(row["normalized_value"].strip()),
            normalized_unit=row["normalized_unit"].strip(),
            evidence_status=row["evidence_status"].strip(),
            filing_date=row["filing_date"].strip(),
            accession_number=row["accession_number"].strip(),
            source_url=response.source_url,
            cache_key=row["cache_key"].strip(),
            source_label=row["source_label"].strip(),
            notes=row["notes"].strip(),
            retrieval_timestamp=response.retrieved_at,
            content_sha256=response.content_sha256,
        )
        key = (fiscal_year, item.metric)
        if key in evidence:
            raise FactSelectionError(
                f"Duplicate documented evidence for FY{fiscal_year} {item.metric}."
            )
        evidence[key] = item
    return evidence


def apply_documented_evidence(
    result: SelectionResult,
    evidence: DocumentedEvidence | None,
) -> SelectionResult:
    """Corroborate a selected fact or supply an explicitly documented zero."""

    if evidence is None:
        return result
    if (
        evidence.metric != result.metric
        or evidence.fiscal_year != result.filing.fiscal_year
        or evidence.period_end != result.filing.period_end
    ):
        raise FactSelectionError(
            "Documented evidence does not match the selection metric and period."
        )
    result.documented_evidence = evidence
    if result.status == "selected" and result.value == evidence.normalized_value:
        result.reason += " The filing-note evidence independently agrees."
        return result
    if (
        result.status == "missing"
        and evidence.evidence_status == "documented_zero"
        and evidence.normalized_value == 0
    ):
        result.status = "documented_zero"
        result.reason = (
            "No consolidated Company Facts instant fact was present; the filing "
            "affirmatively supports a zero balance through the debt note and "
            "balance-sheet presentation."
        )
        result.value = Decimal("0")
        result.normalized_unit = evidence.normalized_unit
        return result

    result.status = "manual_review"
    result.reason = "Company Facts and documented filing-note evidence do not agree."
    result.value = None
    result.normalized_unit = ""
    result.selected_candidate = None
    return result


def normalize_reported_value(
    value: Decimal,
    *,
    reported_unit: str,
    sign_convention: str,
) -> tuple[Decimal, str]:
    """Normalize monetary and share facts to millions with explicit signs."""

    if reported_unit == "USD":
        normalized = value / Decimal("1000000")
        normalized_unit = "USD millions"
    elif reported_unit == "shares":
        normalized = value / Decimal("1000000")
        normalized_unit = "shares millions"
    elif reported_unit == "USD/shares":
        normalized = value
        normalized_unit = "USD per share"
    else:
        raise FactSelectionError(f"Unsupported Company Facts unit: {reported_unit}.")

    if sign_convention == "processed_positive":
        normalized = abs(normalized)
    elif sign_convention not in {
        "reported_positive",
        "reported_signed",
        "reported_signed_face_opposite",
    }:
        raise FactSelectionError(f"Unsupported sign convention: {sign_convention}.")
    return normalized, normalized_unit


def _eligible_fact(
    fact: dict[str, Any],
    *,
    rule: TagRule,
    target: FilingRecord,
    source_filings: dict[str, FilingRecord],
) -> FilingRecord | None:
    if fact.get("form") != "10-K" or fact.get("fp") != "FY":
        return None
    if fact.get("end") != target.period_end:
        return None
    source = source_filings.get(str(fact.get("accn", "")))
    if source is None or source.fiscal_year < target.fiscal_year:
        return None
    if fact.get("filed") != source.filing_date:
        return None
    try:
        if int(fact.get("fy")) != source.fiscal_year:
            return None
    except (TypeError, ValueError):
        return None
    if rule.period_type == "duration":
        if fact.get("start") != target.period_start:
            return None
    elif fact.get("start") not in {None, ""}:
        return None
    return source


def select_metric_fact(
    company_facts: dict[str, Any],
    *,
    metric: str,
    rules: list[TagRule],
    target: FilingRecord,
    filings: list[FilingRecord],
) -> SelectionResult:
    """Select one annual fact after retaining all comparable candidates."""

    metric_rules = [rule for rule in rules if rule.metric == metric]
    eligible_rules = [
        rule
        for rule in metric_rules
        if rule.verification_status in ELIGIBLE_RULE_STATUSES
    ]
    if not eligible_rules:
        return SelectionResult(
            metric=metric,
            filing=target,
            status="manual_review",
            reason=(
                "No verified Company Facts concept is approved for this metric. "
                "See the tag map and decision log."
            ),
        )

    source_filings = {filing.accession_number: filing for filing in filings}
    candidates: list[FactCandidate] = []
    facts_by_taxonomy = company_facts.get("facts", {})
    for rule in eligible_rules:
        concept = facts_by_taxonomy.get(rule.taxonomy, {}).get(rule.tag, {})
        for fact in concept.get("units", {}).get(rule.expected_unit, []):
            source = _eligible_fact(
                fact,
                rule=rule,
                target=target,
                source_filings=source_filings,
            )
            if source is None:
                continue
            try:
                reported_value = Decimal(str(fact["val"]))
            except (KeyError, ValueError, InvalidOperation) as exc:
                raise FactSelectionError(
                    f"Eligible {metric} fact has an invalid numeric value."
                ) from exc
            normalized_value, normalized_unit = normalize_reported_value(
                reported_value,
                reported_unit=rule.expected_unit,
                sign_convention=rule.sign_convention,
            )
            candidates.append(
                FactCandidate(
                    metric=metric,
                    rule=rule,
                    target_filing=target,
                    source_filing=source,
                    fact=fact,
                    reported_value=reported_value,
                    normalized_value=normalized_value,
                    normalized_unit=normalized_unit,
                    presentation_type=(
                        "originally_reported"
                        if source.fiscal_year == target.fiscal_year
                        else "later_comparative"
                    ),
                )
            )

    if not candidates:
        return SelectionResult(
            metric=metric,
            filing=target,
            status="missing",
            reason="No eligible exact-form annual fact matched period, unit, and filing metadata.",
        )

    distinct_values = {candidate.normalized_value for candidate in candidates}
    if len(distinct_values) != 1:
        return SelectionResult(
            metric=metric,
            filing=target,
            status="manual_review",
            reason="Comparable annual candidates disagree; no value was selected.",
            candidates=candidates,
        )

    best_priority = min(candidate.rule.priority for candidate in candidates)
    primary_candidates = [
        candidate for candidate in candidates if candidate.rule.priority == best_priority
    ]
    selected = max(
        primary_candidates,
        key=lambda candidate: (
            candidate.source_filing.filing_date,
            candidate.source_filing.accession_number,
            str(candidate.fact.get("frame", "")),
        ),
    )
    return SelectionResult(
        metric=metric,
        filing=target,
        status="selected",
        reason=(
            "All eligible annual candidates agree; selected the latest comparable "
            "presentation for the highest-priority verified tag."
        ),
        value=selected.normalized_value,
        normalized_unit=selected.normalized_unit,
        selected_candidate=selected,
        candidates=candidates,
    )
