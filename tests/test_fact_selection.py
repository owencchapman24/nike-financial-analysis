from decimal import Decimal

import pytest

from nike_financial_analysis.company_facts import (
    DocumentedEvidence,
    FactSelectionError,
    FilingRecord,
    SelectionResult,
    TagRule,
    apply_documented_evidence,
    normalize_reported_value,
    select_metric_fact,
)


def filing(year: int, accession: str) -> FilingRecord:
    return FilingRecord(
        company_name="NIKE, Inc.",
        ticker="NKE",
        cik="0000320187",
        fiscal_year=year,
        period_start=f"{year - 1}-06-01",
        period_end=f"{year}-05-31",
        form="10-K",
        filing_date=f"{year}-07-20",
        accession_number=accession,
        filing_url=f"https://www.sec.gov/{accession}.htm",
    )


def rule(*, period_type: str = "duration", unit: str = "USD") -> TagRule:
    return TagRule(
        metric="revenue",
        statement_type="income_statement",
        period_type=period_type,
        expected_unit=unit,
        priority=1,
        taxonomy="us-gaap",
        tag="Revenue",
        verification_status="verified",
        sign_convention="reported_positive",
        face_statement_labels=("Revenues",),
        notes="test fixture",
    )


def fact(
    *,
    accession: str,
    fiscal_year: int,
    value: int = 100_000_000,
    form: str = "10-K",
    fiscal_period: str = "FY",
    start: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "end": "2024-05-31",
        "val": value,
        "accn": accession,
        "fy": fiscal_year,
        "fp": fiscal_period,
        "form": form,
        "filed": f"{fiscal_year}-07-20",
    }
    if start is not None:
        row["start"] = start
    return row


def payload(rows: list[dict[str, object]], *, unit: str = "USD") -> dict:
    return {
        "facts": {
            "us-gaap": {
                "Revenue": {
                    "units": {unit: rows},
                }
            }
        }
    }


def test_duration_selection_excludes_quarters_amendments_and_wrong_spans():
    original = filing(2024, "2024-original")
    later = filing(2025, "2025-comparative")
    rows = [
        fact(
            accession="2024-original",
            fiscal_year=2024,
            start="2023-06-01",
        ),
        fact(
            accession="2025-comparative",
            fiscal_year=2025,
            start="2023-06-01",
        ),
        fact(
            accession="2024-original",
            fiscal_year=2024,
            form="10-Q",
            fiscal_period="Q4",
            start="2024-03-01",
        ),
        fact(
            accession="2024-original",
            fiscal_year=2024,
            form="10-K/A",
            start="2023-06-01",
        ),
        fact(
            accession="2024-original",
            fiscal_year=2024,
            start="2022-06-01",
        ),
    ]

    result = select_metric_fact(
        payload(rows),
        metric="revenue",
        rules=[rule()],
        target=original,
        filings=[original, later],
    )

    assert result.status == "selected"
    assert len(result.candidates) == 2
    assert result.selected_candidate.source_filing.accession_number == "2025-comparative"


def test_conflicting_comparative_values_require_manual_review():
    original = filing(2024, "2024-original")
    later = filing(2025, "2025-comparative")
    rows = [
        fact(
            accession="2024-original",
            fiscal_year=2024,
            start="2023-06-01",
        ),
        fact(
            accession="2025-comparative",
            fiscal_year=2025,
            value=101_000_000,
            start="2023-06-01",
        ),
    ]

    result = select_metric_fact(
        payload(rows),
        metric="revenue",
        rules=[rule()],
        target=original,
        filings=[original, later],
    )

    assert result.status == "manual_review"
    assert result.value is None
    assert len(result.candidates) == 2


def test_instant_selection_rejects_duration_context():
    target = filing(2024, "2024-original")
    rows = [
        fact(accession="2024-original", fiscal_year=2024),
        fact(
            accession="2024-original",
            fiscal_year=2024,
            start="2023-06-01",
        ),
    ]

    result = select_metric_fact(
        payload(rows),
        metric="revenue",
        rules=[rule(period_type="instant")],
        target=target,
        filings=[target],
    )

    assert result.status == "selected"
    assert len(result.candidates) == 1


def test_unit_and_sign_normalization():
    usd, usd_unit = normalize_reported_value(
        Decimal("-758000000"),
        reported_unit="USD",
        sign_convention="processed_positive",
    )
    shares, shares_unit = normalize_reported_value(
        Decimal("1610800000"),
        reported_unit="shares",
        sign_convention="reported_positive",
    )

    assert usd == Decimal("758")
    assert usd_unit == "USD millions"
    assert shares == Decimal("1610.8")
    assert shares_unit == "shares millions"

    signed_income, _ = normalize_reported_value(
        Decimal("-205000000"),
        reported_unit="USD",
        sign_convention="reported_signed_face_opposite",
    )
    assert signed_income == Decimal("-205")


def test_unsupported_unit_fails_clearly():
    with pytest.raises(FactSelectionError, match="Unsupported Company Facts unit"):
        normalize_reported_value(
            Decimal("1"),
            reported_unit="EUR",
            sign_convention="reported_positive",
        )


def test_fact_in_wrong_unit_is_not_selected():
    target = filing(2024, "2024-original")
    rows = [
        fact(
            accession="2024-original",
            fiscal_year=2024,
            start="2023-06-01",
        )
    ]

    result = select_metric_fact(
        payload(rows, unit="EUR"),
        metric="revenue",
        rules=[rule(unit="USD")],
        target=target,
        filings=[target],
    )

    assert result.status == "missing"
    assert result.value is None


def documented_evidence(value: str, status: str) -> DocumentedEvidence:
    return DocumentedEvidence(
        metric="notes_payable_and_short_term_borrowings",
        fiscal_year=2024,
        period_end="2024-05-31",
        normalized_value=Decimal(value),
        normalized_unit="USD millions",
        evidence_status=status,
        filing_date="2024-07-20",
        accession_number="2024-original",
        source_url="https://www.sec.gov/Archives/test.htm",
        cache_key="test_note",
        source_label="Note 5",
        notes="fixture",
    )


def test_documented_zero_can_fill_an_absent_company_fact():
    target = filing(2024, "2024-original")
    missing = SelectionResult(
        metric="notes_payable_and_short_term_borrowings",
        filing=target,
        status="missing",
        reason="fixture",
    )

    result = apply_documented_evidence(
        missing, documented_evidence("0", "documented_zero")
    )

    assert result.status == "documented_zero"
    assert result.value == Decimal("0")


def test_documented_note_disagreement_requires_manual_review():
    target = filing(2024, "2024-original")
    selected_result = SelectionResult(
        metric="notes_payable_and_short_term_borrowings",
        filing=target,
        status="selected",
        reason="fixture",
        value=Decimal("6"),
        normalized_unit="USD millions",
    )

    result = apply_documented_evidence(
        selected_result, documented_evidence("5", "corroborating")
    )

    assert result.status == "manual_review"
    assert result.value is None
