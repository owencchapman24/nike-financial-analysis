# Methodology

## Phase 1: issuer and filing discovery

Phase 1 verifies the issuer and identifies the five most recent completed fiscal
years with filed annual reports. It does not select accounting facts or make
analytical conclusions.

### Primary sources

- SEC company ticker mapping:
  `https://www.sec.gov/files/company_tickers.json`
- SEC submissions API:
  `https://data.sec.gov/submissions/CIK##########.json`
- SEC EDGAR API documentation:
  `https://www.sec.gov/search-filings/edgar-application-programming-interfaces`
- SEC developer and fair-access guidance:
  `https://www.sec.gov/about/developer-resources`

The SEC states that the public submissions and XBRL data APIs do not require an API
key. Current fair-access guidance limits aggregate automated access to no more than
10 requests per second. This project defaults to a substantially lower rate of two
requests per second and caches successful responses.

Guidance reviewed: 2026-09-06.

### Issuer verification

The requested ticker is matched case-insensitively against the SEC's official
ticker-to-CIK mapping. Discovery stops unless exactly one company matches. The CIK
is stored as a ten-digit string for API requests and converted to its unpadded form
only where the EDGAR Archives URL requires it.

### Annual filing selection

The submissions API's `filings.recent` columns are converted into filing rows. A
candidate must:

1. have form exactly equal to `10-K` (not `10-Q` or `10-K/A`);
2. have a valid filing date and report-period end;
3. have been filed on or before the selected as-of date; and
4. include an accession number and primary document.

Candidates are sorted deterministically by report-period end, filing date, and
accession number. Duplicate report periods retain the latest filed candidate. The
five newest unique periods are then returned oldest-first for readable analysis.

The initial fiscal-year label is the report-period-end year and is explicitly marked
`period_end_year_provisional`. Phase 2 must verify this against filing and XBRL fiscal
year metadata before accounting facts are selected.

### Phase 1 filing-discovery result

The pipeline was run with a selection as-of date of 2026-09-06. The SEC's official
ticker mapping returned one NKE issuer, and the CIK agreed with the company
submissions payload. The selected filing periods were:

| Provisional fiscal year | Period end | Filing date | Form |
|---:|---|---|---|
| 2022 | 2022-05-31 | 2022-07-21 | 10-K |
| 2023 | 2023-05-31 | 2023-07-20 | 10-K |
| 2024 | 2024-05-31 | 2024-07-25 | 10-K |
| 2025 | 2025-05-31 | 2025-07-17 | 10-K |
| 2026 | 2026-05-31 | 2026-07-15 | 10-K |

The committed `data/metadata/filing_index.csv` preserves the verified CIK, accession
numbers, primary documents, filing URLs, source URLs, retrieval times, source hashes,
and selection as-of date.

### Cache and privacy behavior

- `SEC_USER_AGENT` is read from an ignored local `.env` file.
- Missing and placeholder values stop execution before a request is made.
- The configured value is never printed or written into output data.
- Only HTTPS requests to `www.sec.gov` and `data.sec.gov` are allowed.
- Successful JSON is cached with its URL, retrieval time, response metadata, and a
  SHA-256 content hash.
- Cache files are reused unless the exact file is deliberately removed.
- Temporary errors use bounded retries, exponential delays, and `Retry-After` when
  supplied.

### Phase 2 boundary

The XBRL tag map in `config/xbrl_tags.csv` contains candidates only. Every tag is
marked `to_verify` and must be checked against Nike's company facts and applicable
10-K face statements. No candidate tag is an approved historical data source merely
because it appears in the mapping.
