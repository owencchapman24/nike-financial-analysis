"""Verify an SEC issuer identity and discover its most recent annual filings."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable

from nike_financial_analysis.sec_client import SecClient, SecRequestError


COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_URL_TEMPLATE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}"
DEFAULT_OUTPUT_PATH = Path("data/metadata/filing_index.csv")


class FilingSelectionError(ValueError):
    """Raised when issuer or annual-filing selection is incomplete or ambiguous."""


@dataclass(frozen=True)
class CompanyIdentity:
    """SEC identity confirmed through the official company ticker mapping."""

    ticker: str
    cik: str
    company_name: str


@dataclass(frozen=True)
class AnnualFiling:
    """Auditable metadata for one selected annual report."""

    company_name: str
    ticker: str
    cik: str
    fiscal_year: int
    fiscal_year_basis: str
    period_end: str
    form: str
    filing_date: str
    accession_number: str
    primary_document: str
    filing_url: str
    index_url: str
    selection_as_of_date: str
    ticker_mapping_url: str
    ticker_mapping_retrieval_timestamp: str
    ticker_mapping_sha256: str
    submissions_url: str
    submissions_retrieval_timestamp: str
    submissions_sha256: str
    generated_at: str


def normalize_cik(value: int | str) -> str:
    """Return a ten-digit SEC CIK and reject malformed identifiers."""

    text = str(value).strip()
    if not text.isdigit() or len(text) > 10:
        raise FilingSelectionError(f"Invalid SEC CIK: {value!r}.")
    return text.zfill(10)


def find_company_by_ticker(mapping: Any, ticker: str) -> CompanyIdentity:
    """Resolve one ticker from the SEC's official ticker-to-CIK mapping."""

    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise FilingSelectionError("Ticker cannot be blank.")
    if not isinstance(mapping, dict):
        raise FilingSelectionError("SEC company ticker data has an unexpected format.")

    matches: list[CompanyIdentity] = []
    for item in mapping.values():
        if not isinstance(item, dict):
            continue
        if str(item.get("ticker", "")).strip().upper() == normalized_ticker:
            matches.append(
                CompanyIdentity(
                    ticker=normalized_ticker,
                    cik=normalize_cik(item.get("cik_str", "")),
                    company_name=str(item.get("title", "")).strip(),
                )
            )
    if len(matches) != 1:
        raise FilingSelectionError(
            f"Expected exactly one SEC company match for ticker {normalized_ticker}; "
            f"found {len(matches)}."
        )
    if not matches[0].company_name:
        raise FilingSelectionError("SEC company mapping returned a blank company name.")
    return matches[0]


def _recent_rows(submissions: Any) -> Iterable[dict[str, Any]]:
    try:
        recent = submissions["filings"]["recent"]
    except (KeyError, TypeError) as exc:
        raise FilingSelectionError(
            "SEC submissions data is missing filings.recent."
        ) from exc
    if not isinstance(recent, dict) or not recent:
        raise FilingSelectionError("SEC submissions recent filings are empty.")

    required_columns = {
        "accessionNumber",
        "filingDate",
        "reportDate",
        "form",
        "primaryDocument",
    }
    missing = required_columns.difference(recent)
    if missing:
        raise FilingSelectionError(
            f"SEC submissions data is missing columns: {', '.join(sorted(missing))}."
        )
    lengths = {len(recent[column]) for column in required_columns}
    if len(lengths) != 1:
        raise FilingSelectionError("SEC submissions columns have inconsistent lengths.")

    for index in range(lengths.pop()):
        yield {column: recent[column][index] for column in required_columns}


def select_recent_10k_rows(
    submissions: Any,
    *,
    count: int = 5,
    as_of_date: date | None = None,
) -> list[dict[str, str]]:
    """Select unique filed 10-K periods deterministically and return them oldest-first."""

    if count <= 0:
        raise FilingSelectionError("Annual filing count must be positive.")
    cutoff = as_of_date or date.today()
    candidates: list[dict[str, str]] = []
    for row in _recent_rows(submissions):
        if str(row["form"]).strip() != "10-K":
            continue
        try:
            filing_date = date.fromisoformat(str(row["filingDate"]))
            report_date = date.fromisoformat(str(row["reportDate"]))
        except ValueError as exc:
            raise FilingSelectionError(
                "SEC returned an invalid filingDate or reportDate for a 10-K."
            ) from exc
        if filing_date > cutoff:
            continue
        accession = str(row["accessionNumber"]).strip()
        primary_document = str(row["primaryDocument"]).strip()
        if not accession or not primary_document:
            raise FilingSelectionError(
                "A candidate 10-K is missing its accession number or primary document."
            )
        candidates.append(
            {
                "accession_number": accession,
                "filing_date": filing_date.isoformat(),
                "period_end": report_date.isoformat(),
                "form": "10-K",
                "primary_document": primary_document,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["period_end"],
            row["filing_date"],
            row["accession_number"],
        ),
        reverse=True,
    )
    unique_periods: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        unique_periods.setdefault(candidate["period_end"], candidate)
    selected = list(unique_periods.values())[:count]
    if len(selected) != count:
        raise FilingSelectionError(
            f"Expected {count} unique filed 10-K periods on or before {cutoff}; "
            f"found {len(selected)}."
        )
    return sorted(selected, key=lambda row: row["period_end"])


def build_annual_filings(
    identity: CompanyIdentity,
    rows: Iterable[dict[str, str]],
    *,
    selection_as_of_date: date,
    ticker_mapping_url: str,
    ticker_mapping_retrieval_timestamp: str,
    ticker_mapping_sha256: str,
    submissions_url: str,
    submissions_retrieval_timestamp: str,
    submissions_sha256: str,
    generated_at: str | None = None,
) -> list[AnnualFiling]:
    """Attach issuer, URL, and retrieval metadata to selected filing rows."""

    generated = generated_at or datetime.now(UTC).isoformat()
    cik_archive = str(int(identity.cik))
    filings: list[AnnualFiling] = []
    for row in rows:
        accession_compact = row["accession_number"].replace("-", "")
        archive_base = ARCHIVES_URL_TEMPLATE.format(
            cik=cik_archive,
            accession=accession_compact,
        )
        filings.append(
            AnnualFiling(
                company_name=identity.company_name,
                ticker=identity.ticker,
                cik=identity.cik,
                fiscal_year=date.fromisoformat(row["period_end"]).year,
                fiscal_year_basis="period_end_year_provisional",
                period_end=row["period_end"],
                form=row["form"],
                filing_date=row["filing_date"],
                accession_number=row["accession_number"],
                primary_document=row["primary_document"],
                filing_url=f"{archive_base}/{row['primary_document']}",
                index_url=f"{archive_base}/{row['accession_number']}-index.html",
                selection_as_of_date=selection_as_of_date.isoformat(),
                ticker_mapping_url=ticker_mapping_url,
                ticker_mapping_retrieval_timestamp=ticker_mapping_retrieval_timestamp,
                ticker_mapping_sha256=ticker_mapping_sha256,
                submissions_url=submissions_url,
                submissions_retrieval_timestamp=submissions_retrieval_timestamp,
                submissions_sha256=submissions_sha256,
                generated_at=generated,
            )
        )
    return filings


def discover_annual_filings(
    client: SecClient,
    *,
    ticker: str = "NKE",
    count: int = 5,
    as_of_date: date | None = None,
    force_refresh: bool = False,
) -> list[AnnualFiling]:
    """Verify the issuer and obtain its most recent unique filed 10-K periods."""

    ticker_response = client.get_json(
        COMPANY_TICKERS_URL,
        cache_key="company_tickers",
        force_refresh=force_refresh,
    )
    identity = find_company_by_ticker(ticker_response.data, ticker)
    submissions_url = SUBMISSIONS_URL_TEMPLATE.format(cik=identity.cik)
    submissions_response = client.get_json(
        submissions_url,
        cache_key=f"submissions_CIK{identity.cik}",
        force_refresh=force_refresh,
    )
    rows = select_recent_10k_rows(
        submissions_response.data,
        count=count,
        as_of_date=as_of_date,
    )
    return build_annual_filings(
        identity,
        rows,
        selection_as_of_date=as_of_date or date.today(),
        ticker_mapping_url=ticker_response.source_url,
        ticker_mapping_retrieval_timestamp=ticker_response.retrieved_at,
        ticker_mapping_sha256=ticker_response.content_sha256,
        submissions_url=submissions_response.source_url,
        submissions_retrieval_timestamp=submissions_response.retrieved_at,
        submissions_sha256=submissions_response.content_sha256,
    )


def write_filing_index(filings: list[AnnualFiling], output_path: Path) -> None:
    """Write a chronological filing index as UTF-8 CSV."""

    if not filings:
        raise FilingSelectionError("Cannot write an empty filing index.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(filings[0]).keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(filing) for filing in filings)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify an SEC issuer and write its recent 10-K filing index."
    )
    parser.add_argument("--ticker", default="NKE", help="SEC-listed ticker symbol")
    parser.add_argument("--count", type=int, default=5, help="Number of unique 10-K periods")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Latest filing date to include (YYYY-MM-DD); defaults to today",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output CSV path",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Download fresh SEC responses and replace the exact cache files",
    )
    return parser.parse_args()


def main() -> int:
    """Command-line entry point for Phase 1 SEC filing discovery."""

    args = _parse_args()
    try:
        client = SecClient.from_env()
        filings = discover_annual_filings(
            client,
            ticker=args.ticker,
            count=args.count,
            as_of_date=args.as_of,
            force_refresh=args.force_refresh,
        )
        write_filing_index(filings, args.output)
    except (FilingSelectionError, SecRequestError, ValueError) as exc:
        raise SystemExit(f"SEC filing discovery failed: {exc}") from exc
    print(f"Wrote {len(filings)} annual filings to {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
