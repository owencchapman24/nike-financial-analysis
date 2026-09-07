# Nike Financial Analysis

Reproducible Python and Excel analysis of Nike's five-year financial performance,
operating trends, scenario forecasts, and discounted cash flow valuation using SEC
filing data.

> **Project status:** Phase 1 foundation and SEC filing discovery completed.
> Historical accounting values, forecasts, and valuation conclusions have not yet
> been completed or reviewed.

This is an independent educational portfolio project, not investment advice.

## Project objective

The finished project will answer six business questions:

1. How have Nike's revenue, profitability, and cash generation changed?
2. What operating factors appear to explain changes in margins?
3. What do inventory, receivables, working capital, and cash conversion suggest?
4. How effectively has accounting income translated into cash flow?
5. What assumptions support coherent base, bull, and bear operating scenarios?
6. What valuation range follows from those assumptions, and which matter most?

## Phase 1 scope

Phase 1 establishes a reproducible Python environment and a small SEC client that:

- reads a descriptive SEC user agent from an untracked `.env` file;
- verifies the requested ticker against the SEC's official ticker-to-CIK file;
- retrieves the company's submissions history;
- selects five unique, most-recent filed 10-K periods as of a stated date;
- caches successful SEC responses to avoid unnecessary repeat requests; and
- writes an auditable filing index without selecting accounting facts yet.

## Windows PowerShell setup

The environment is tested with CPython 3.14.5 managed by
[uv](https://docs.astral.sh/uv/). From a fresh clone:

```powershell
uv sync --locked --python 3.14.5
.\.venv\Scripts\Activate.ps1
```

`pyproject.toml` defines dependencies and `uv.lock` pins the resolved environment.
There is intentionally no hand-maintained `requirements.txt`.

## Configure SEC access

After setup, copy `.env.example` to `.env` and replace the placeholder with a
descriptive identifier and contact address. Never commit `.env`.

```powershell
Copy-Item .env.example .env
```

The SEC client never prints the configured user-agent value. It limits requests to
two per second by default, retries temporary failures, uses timeouts, and caches
successful JSON responses under `data/raw/sec/`.

## Run Phase 1

```powershell
uv run nike-sec-filings --ticker NKE --count 5
uv run pytest
```

The discovery command writes `data/metadata/filing_index.csv`. See
`docs/methodology.md` for the selection rules and `docs/decision_log.md` for the
decisions made so far.

As of 2026-09-06, the official SEC sources identify the five selected annual periods
as FY2022 through FY2026, all ending May 31. These are filing-discovery results only;
Phase 2 must still verify fiscal-year metadata and reconcile accounting facts to the
annual reports.

## Data policy

- Historical accounting data will come primarily from SEC EDGAR filings and SEC
  XBRL APIs.
- Downloaded raw responses remain ignored; cleaned data and source metadata will be
  committed for reviewer access.
- Ambiguous historical facts will be flagged for manual review rather than guessed.
- Forecast assumptions and analytical conclusions will remain distinct from
  reported historical facts and require owner review.
