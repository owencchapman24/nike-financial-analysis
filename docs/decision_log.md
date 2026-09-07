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

## Phase 2 decisions

## D009 — Prefer agreed later comparative presentations

- **Status:** Accepted by project owner
- **Decision:** Retain every eligible originally reported and later comparative
  fact. Select the latest face-statement-visible presentation only when all
  comparable candidates agree. Otherwise mark the metric-year `manual_review`.
- **Result:** No selected core concept changed value across the repeated comparative
  presentations reviewed for FY2022–FY2026.

## D010 — Reconcile selected facts to SEC-rendered face statements

- **Status:** Implemented
- **Decision:** A reported fact does not enter the cleaned dataset unless it agrees
  with the applicable consolidated face statement within displayed precision.
  Calculated subtotals use documented component and bridge checks because Nike does
  not present them directly.
- **Reason:** Company Facts is an aggregation API; the filing remains the accounting
  source of record.

## D011 — Use Nike-specific verified tag substitutions

- **Status:** Accepted by project owner
- **Decision:** Use `CostOfGoodsAndServicesSold` for cost of sales,
  `InventoryFinishedGoodsNetOfReserves` for inventories, and
  `DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent` for short-term
  investments. The generic candidates have no matching annual facts for these five
  periods.
- **Validation:** Each selected substitution reconciles to the face-statement line.

## D012 — Bridge the D&A tag transition without estimating

- **Status:** Accepted by project owner
- **Decision:** Use `Depreciation` for FY2022 and
  `DepreciationDepletionAndAmortization` for FY2023–FY2026. The overlapping FY2023
  and FY2024 values agree, and all selected values reconcile to the cash-flow line
  displayed as either “Depreciation” or “Depreciation and amortization.”

## D013 — Derive consolidated operating income

- **Status:** Accepted by project owner
- **Decision:** Calculate `derived_operating_income` as gross profit less total
  selling and administrative expense, and calculate operating margin from that
  derived measure.
- **Validation:** For every year, bridge derived operating income to income before
  taxes using signed net interest and other non-operating income or expense.
- **Boundary:** This is a consolidated calculation because Nike does not show the
  subtotal on its consolidated income statement. It is not segment-level EBIT.

## D014 — Define debt scope narrowly and visibly

- **Status:** Accepted by project owner
- **Decision:** Present notes payable or short-term borrowings, current maturities
  of long-term debt, and noncurrent long-term debt separately. Define total
  interest-bearing debt as the sum of all three. Do not rely on `LongTermDebt` alone
  when separately reported notes payable exist.
- **Evidence:** FY2022 Note 7 reports $10 million of non-U.S. notes payable. The
  annual notes disclose $6 million, $6 million, $5 million, and $0 for
  FY2023-FY2026; FY2026's zero is separately documented because Company Facts omits
  the consolidated annual fact.

## D015 — Confirm Nike fiscal-year labels

- **Status:** Verified
- **Decision:** Use FY2022–FY2026 for the periods ending May 31, 2022 through
  May 31, 2026. Each originally reported annual fact has `fp=FY`, and its `fy`
  metadata agrees with the verified filing year.
- **Reason:** This replaces the provisional Phase 1 period-end labels with verified
  Nike fiscal-year labels while retaining the actual dates.

## D016 — Keep operating leases outside base debt

- **Status:** Accepted by project owner
- **Decision:** Report current, noncurrent, and total operating lease liabilities as
  informational metrics, but exclude them from base total interest-bearing debt.
- **Reason:** Historical operating metrics retain lease expense in cost of sales and
  operating overhead. Treating lease liabilities as debt without corresponding
  operating-profit and cash-flow adjustments would mix conventions.
- **Valuation handoff:** Version one will keep lease expense operating and exclude
  lease liabilities from the enterprise-to-equity bridge unless a complete lease
  capitalization adjustment is later justified and approved.

## Decisions still deferred after Phase 2

- Inventory-days and broader working-capital definitions
- Base, bull, and bear assumptions
- Forecast tax, reinvestment, and terminal economics
- Year-end versus mid-year DCF discounting
- WACC, terminal growth, and enterprise-to-equity bridge inputs
- Optional segment or geography analysis
