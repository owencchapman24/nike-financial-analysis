# Decision Log

This log records material choices so the project owner can explain and review the
work. Analytical conclusions and forecast assumptions require explicit owner review.

## D001 — Select Nike as the subject

- **Status:** Accepted before repository implementation
- **Reason:** Nike offers a recognizable operating business, public SEC filings, and
  relevant questions involving revenue, margins, inventory, cash conversion, and
  valuation.
- **Limitation:** The project is educational and will not issue an investment
  recommendation.

## D002 — Use primary SEC sources for historical accounting data

- **Status:** Accepted
- **Decision:** Use SEC submissions, company facts, and filed annual reports as the
  primary sources. Secondary sources are reserved for dated market inputs later.
- **Reason:** This provides traceability and avoids treating an unofficial finance
  website as the accounting source of record.

## D003 — Use a hybrid Python, notebook, CSV, and Excel architecture

- **Status:** Accepted
- **Decision:** Keep extraction, transformation, metrics, and validation in Python
  modules; use a notebook for narrative; publish processed CSV files; and build a
  formula-driven Excel forecast and DCF later.
- **Reason:** The design remains reproducible while keeping the financial logic easy
  to inspect and defend.

## D004 — Use uv with a canonical project file and lock

- **Status:** Accepted by project owner on 2026-09-06
- **Decision:** Use `pyproject.toml` as the dependency definition and commit
  `uv.lock`. Do not maintain a hand-edited `requirements.txt`.
- **Interpreter:** Test the existing uv-managed CPython 3.14.5 first; fall back to
  Python 3.13 only if a required dependency lacks a compatible Windows wheel or a
  compatibility check fails.
- **Validation result:** CPython 3.14.5 resolved the lock, installed all Phase 1
  dependencies, imported the runtime packages, compiled the source, and passed the
  Phase 1 test suite. The Python 3.13 fallback was not needed.

## D005 — Keep SEC contact information local

- **Status:** Accepted
- **Decision:** Read `SEC_USER_AGENT` from `.env`, commit only a placeholder in
  `.env.example`, ignore the real file, and never print the configured value.
- **Reason:** SEC requests need an identifiable automated client without exposing a
  personal address in the repository.

## D006 — Use conservative SEC access and raw-response caching

- **Status:** Accepted
- **Decision:** Default to two requests per second, below the SEC's current aggregate
  ceiling of 10 requests per second. Cache successful JSON and avoid repeated
  downloads.
- **Guidance reviewed:** 2026-09-06

## D007 — Treat the initial XBRL map as unverified candidates

- **Status:** Accepted for Phase 1
- **Decision:** Record likely concepts and fallbacks in a visible CSV, but mark every
  entry `to_verify`. Phase 2 must validate tags, contexts, units, filings, and face
  statements before facts enter the historical dataset.

## D008 — Select the five annual periods dynamically

- **Status:** Verified on 2026-09-06
- **Decision:** Resolve NKE through the official SEC ticker mapping and select the
  five newest unique exact-form `10-K` report periods filed by the as-of date.
- **Result:** The selected provisional fiscal years are FY2022–FY2026, with actual
  period ends retained in the filing index. The label remains provisional until
  Phase 2 verifies filing and XBRL fiscal-year metadata.

## Decisions intentionally deferred

- Historical fact selections and recast treatment
- Cash-conversion and working-capital presentation details
- Base, bull, and bear assumptions
- Forecast tax, reinvestment, and terminal economics
- Year-end versus mid-year DCF discounting
- WACC, terminal growth, and enterprise-to-equity bridge inputs
- Optional segment or geography analysis
