from datetime import date

import pytest

from nike_financial_analysis.extract import (
    CompanyIdentity,
    FilingSelectionError,
    build_annual_filings,
    find_company_by_ticker,
    normalize_cik,
    select_recent_10k_rows,
)


def make_submissions(rows):
    columns = {
        "accessionNumber": [],
        "filingDate": [],
        "reportDate": [],
        "form": [],
        "primaryDocument": [],
    }
    for row in rows:
        for column in columns:
            columns[column].append(row[column])
    return {"filings": {"recent": columns}}


def filing(accession, filed, period, form="10-K", document="annual.htm"):
    return {
        "accessionNumber": accession,
        "filingDate": filed,
        "reportDate": period,
        "form": form,
        "primaryDocument": document,
    }


def test_normalize_cik():
    assert normalize_cik(123456) == "0000123456"


def test_find_company_by_ticker_requires_one_exact_match():
    mapping = {
        "0": {"cik_str": 123456, "ticker": "NKE", "title": "NIKE Test Fixture"},
        "1": {"cik_str": 1, "ticker": "OTHER", "title": "Other Company"},
    }

    identity = find_company_by_ticker(mapping, "nke")

    assert identity == CompanyIdentity(
        ticker="NKE",
        cik="0000123456",
        company_name="NIKE Test Fixture",
    )


def test_select_recent_10k_rows_filters_and_deduplicates():
    submissions = make_submissions(
        [
            filing("0001-26-000001", "2026-07-24", "2026-05-31"),
            filing("0001-25-000002", "2025-07-25", "2025-05-31"),
            filing("0001-25-000001", "2025-07-20", "2025-05-31"),
            filing("0001-24-000001", "2024-07-25", "2024-05-31"),
            filing("0001-23-000001", "2023-07-24", "2023-05-31"),
            filing("0001-22-000001", "2022-07-21", "2022-05-31"),
            filing("0001-21-000001", "2021-07-22", "2021-05-31"),
            filing("0001-26-000002", "2026-08-01", "2026-05-31", form="10-K/A"),
            filing("0001-26-000003", "2026-08-02", "2026-07-31", form="10-Q"),
            filing("0001-27-000001", "2027-07-20", "2027-05-31"),
        ]
    )

    selected = select_recent_10k_rows(
        submissions,
        count=5,
        as_of_date=date(2026, 9, 6),
    )

    assert [row["period_end"] for row in selected] == [
        "2022-05-31",
        "2023-05-31",
        "2024-05-31",
        "2025-05-31",
        "2026-05-31",
    ]
    assert selected[-2]["accession_number"] == "0001-25-000002"
    assert all(row["form"] == "10-K" for row in selected)


def test_select_recent_10k_rows_requires_requested_count():
    submissions = make_submissions(
        [filing("0001-26-000001", "2026-07-24", "2026-05-31")]
    )

    with pytest.raises(FilingSelectionError, match="Expected 5"):
        select_recent_10k_rows(
            submissions,
            count=5,
            as_of_date=date(2026, 9, 6),
        )


def test_build_annual_filings_uses_auditable_urls():
    identity = CompanyIdentity("NKE", "0000123456", "NIKE Test Fixture")
    rows = [
        {
            "accession_number": "0000123456-26-000001",
            "filing_date": "2026-07-24",
            "period_end": "2026-05-31",
            "form": "10-K",
            "primary_document": "test-20260531.htm",
        }
    ]

    result = build_annual_filings(
        identity,
        rows,
        selection_as_of_date=date(2026, 9, 6),
        ticker_mapping_url="https://www.sec.gov/files/company_tickers.json",
        ticker_mapping_retrieval_timestamp="2026-09-06T11:59:00+00:00",
        ticker_mapping_sha256="a" * 64,
        submissions_url="https://data.sec.gov/submissions/CIK0000123456.json",
        submissions_retrieval_timestamp="2026-09-06T12:00:00+00:00",
        submissions_sha256="b" * 64,
        generated_at="2026-09-06T12:01:00+00:00",
    )

    assert result[0].fiscal_year == 2026
    assert result[0].fiscal_year_basis == "period_end_year_provisional"
    assert result[0].selection_as_of_date == "2026-09-06"
    assert result[0].filing_url.endswith("/test-20260531.htm")
    assert result[0].index_url.endswith(
        "/0000123456-26-000001-index.html"
    )
