# Decision Log

This log records material choices so the project owner can explain and review the
work. Analytical conclusions and forecast assumptions require explicit owner review.

## D001 — Select Nike as the subject

- **Status:** Accepted before repository implementation
- **Reason:** Nike offers a recognizable operating business, public SEC filings, and
  relevant questions involving revenue, margins, inventory, cash conversion, and
  valuation.
- **Limitation:** The work is an independent portfolio analysis and will not issue
  an investment recommendation.

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

## Phase 3 decisions

## D017 — Use average-balance efficiency metrics with 365 days

- **Status:** Accepted by project owner
- **Decision:** Calculate inventory days as average inventory divided by cost of
  revenue times 365. Calculate `receivables_days_proxy` as average accounts
  receivable divided by total revenue times 365.
- **Boundary:** Calculate both only for FY2023-FY2026. FY2022 is `not_applicable`
  because FY2021 opening balances are not present and ending balances are not an
  acceptable substitute.
- **Interpretation:** The 365-day factor is a consistent analytical convention. The
  receivables measure is not DSO because total revenue, rather than disclosed credit
  sales, is the denominator.

## D018 — Preserve Decimal calculations through the analysis layer

- **Status:** Accepted by project owner
- **Decision:** Load financial values as strings, calculate with Decimal-compatible
  logic, retain full available precision in CSV output, and convert to floating point
  only at the Matplotlib boundary. Round only for presentation.

## D019 — Present cash conversion as a ratio

- **Status:** Accepted by project owner
- **Decision:** Retain `cash_conversion = operating_cash_flow / net_income` and use
  unit `x` in the KPI table and analysis. Use a 1.0x chart reference and do not
  reinterpret the Phase 2 decimal value as a percentage.

## D020 — Use a signed net-debt convention

- **Status:** Accepted by project owner
- **Decision:** Calculate `net_debt_after_cash_and_short_term_investments` as total
  interest-bearing debt less cash and short-term investments. A negative amount is
  described as net cash. Operating lease liabilities remain excluded and visible
  separately.

## D021 — Limit the historical presentation to five charts

- **Status:** Accepted for Phase 3
- **Decision:** Publish revenue and growth, margin, cash generation, working capital
  and liquidity, and capital structure figures. Keep diluted EPS and share count in
  the notebook and tables because a sixth chart adds limited information.

## Decisions deferred at Phase 3 completion

- Year-end versus mid-year DCF discounting
- WACC, terminal growth, and enterprise-to-equity bridge inputs
- Optional segment or geography analysis

## Phase 4 decisions

## D022 — Use a consolidated driver-based operating forecast

- **Status:** Accepted by project owner
- **Decision:** Forecast FY2027-FY2031 revenue, gross margin, total SG&A, normalized
  operating tax, D&A, capex, aggregate operating NWC, and FCFF for base, bull, and
  bear scenarios. Do not create unsupported segment forecasts or a full
  three-statement model.
- **Boundary:** Phase 4 contains no valuation inputs or outputs.

## D023 — Approve the 105 scenario assumptions

- **Status:** Accepted by project owner
- **Decision:** Use the exact annual paths in `config/scenario_assumptions.csv` for
  seven drivers, five years, and three scenarios. Final generation requires every
  row to remain owner-approved and source-resolved.

## D024 — Use a 21.0% normalized operating tax rate

- **Status:** Accepted by project owner
- **Decision:** Hold the normalized operating tax rate constant across years and
  scenarios. Do not generate an automatic tax benefit from negative derived
  operating income without a separately documented NOL schedule.

## D025 — Use the aggregate operating-NWC proxy

- **Status:** Accepted by project owner
- **Decision:** Exclude cash, short-term investments, notes payable or short-term
  borrowings, current long-term debt, and current lease liabilities from aggregate
  current assets and liabilities. Forecast the resulting proxy as a percentage of
  revenue.
- **Limitation:** Tax, dividend, and other aggregated current balances may remain.
  The proxy is useful but is not perfectly defined operating working capital.

## D026 — Preserve FY2026 reported gross margin and tariff context

- **Status:** Accepted by project owner
- **Decision:** Keep reported FY2026 gross margin at 42.9%; do not create an adjusted
  actual. Disclose Nike's approximately 210-basis-point IEEPA recovery benefit and
  approximately 40.8% counterfactual excluding it when interpreting FY2027 scenario
  assumptions.

## D027 — Avoid double counting tariff-receivable collection

- **Status:** Accepted by project owner
- **Decision:** Treat the FY2026 tariff receivable as already embedded in the USD
  5,507 million opening operating-NWC balance. Do not add a separate subsequent
  collection to FCFF.

## D028 — Adopt the bounded Phase 5A DCF methodology

- **Status:** Accepted by project owner
- **Decision:** Use a May 31, 2026 model date and exact May 31 fiscal-year-end cash-flow dates.
  D032 later supersedes only the model-date choice; forecast cash-flow dates remain.
- **WACC and terminal value:** Use a formula-derived bottom-up WACC with fair-value
  debt, a common 2.5% perpetual-growth rate, and an explicit FY2032 stable-state bridge.
- **Equity bridge:** Add USD 9,027 million of cash and investments; subtract USD 7,942
  million of carrying debt and USD 0.3 million of preferred stock. Leases are memo only.
- **Shares:** Use 1,484.698703 million diluted-proxy shares for headline value and
  1,483.498703 million basic shares only as a denominator cross-check.

## D029 — Translate the authoritative DCF into a formula-driven Excel model

- **Status:** Accepted by project owner
- **Decision:** Build eight visible worksheets with XlsxWriter, recalculate the
  temporary candidate through a dedicated desktop Excel instance, and inspect it
  read-only with openpyxl before atomic publication.
- **Authority:** Phase 5A Python outputs remain authoritative. Workbook formulas must
  reconcile rather than replace or revise those results.
- **Controls:** Use a Bear/Base/Bull selector, exact fiscal-year-end discounting,
  native `XNPV` and explicit-PV reconciliation, a formula-driven 5x5 Base sensitivity,
  independent check rows, and a recalculation sentinel with an invalid initial cache.
- **Boundary:** No macros, external links, live data, probabilities, new assumptions,
  or Phase 6 work.

## D030 — Package the completed analysis for public portfolio review

- **Status:** Accepted for Phase 6 implementation
- **Decision:** Use the README as the concise recruiter-facing entry point and add
  one public project walkthrough linking the existing detailed methodology,
  decisions, outputs, notebooks, and workbook guide.
- **Presentation:** Surface the historical trajectory, illustrative valuation range,
  workbook download, validation evidence, and reproduction path without changing
  analytical results or presenting the valuation as a recommendation.
- **Boundary:** Keep private interview preparation and knowledge testing outside the
  public repository for Phase 7.

## D031 — Make protected-text verification portable across Git checkouts

- **Status:** Accepted during the Phase 6 fresh-clone gate
- **Decision:** Treat LF and CRLF forms of protected CSV and notebook artifacts as
  hash-equivalent only when their normalized text content is identical.
- **Reason:** The repository enforces LF through `.gitattributes`, while earlier
  approved hashes were recorded from a Windows CRLF working tree. Raw-byte-only
  comparison therefore rejected a valid fresh clone even though Git stored the
  same content.
- **Control:** Binary artifacts remain byte-exact, and a regression test confirms
  that an actual value change still fails verification.

## D032 - Align the DCF discount anchor with the market reference date

- **Status:** Accepted for v0.5.2
- **Decision:** Use September 4, 2026 as the DCF valuation and discount-anchor date.
  Keep May 31, 2026 as the latest completed financial-statement and balance-sheet
  date, and do not infer an interim balance-sheet roll-forward.
- **Reason:** This aligns exact-date discounting with the Treasury-rate and reference-
  price date while retaining the latest reported balance-sheet inputs.
- **Unchanged:** WACC inputs, operating scenarios, FCFF, terminal growth, bridge
  conventions, and share-denominator methodology.

## D033 - Protect visual content rather than PNG containers

- **Status:** Accepted for v0.5.2
- **Decision:** Fingerprint PNG width, height, color mode, and decoded pixels. Apply
  the same rule to embedded notebook PNGs while preserving all substantive notebook
  content. Require project CSV writers to emit LF.
- **Reason:** PNG compression and harmless container metadata may vary across
  supported platforms even when the rendered image is identical.
- **Control:** Any pixel, dimension, mode, notebook-content, or protected-text value
  change still fails. Excel and other non-PNG binary controls are unchanged.
