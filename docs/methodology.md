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

### Phase 1 handoff

At the Phase 1 handoff, the XBRL tag map in `config/xbrl_tags.csv` contained
unverified candidates only. Phase 2 replaces those placeholders with explicit
verification outcomes after checking Nike's Company Facts and applicable 10-K face
statements.

## Phase 2: historical data pipeline

### Source retrieval and evidence

The pipeline requests Nike's official SEC Company Facts payload at
`https://data.sec.gov/api/xbrl/companyfacts/CIK0000320187.json`. The CIK is not a
hardcoded assumption: it remains tied to the Phase 1 ticker verification and filing
index. The retrieved payload contains five taxonomies, including 443 US-GAAP
concepts at the retrieval time.

For each selected 10-K, the pipeline also retrieves `FilingSummary.xml`, identifies
the consolidated statements of income, balance sheets, and cash flows, and caches
the SEC-rendered statement HTML. These raw responses remain ignored by Git. Their
URLs, retrieval metadata, and hashes support reconciliation without committing the
large source files.

The debt-note pages listed in `config/documented_values.csv` are also retrieved and
cached. They corroborate notes payable for FY2022-FY2025 and support an explicit
zero for FY2026, when Company Facts has no matching consolidated annual instant
fact. A documented zero is accepted only when the mapped filing disclosure and
balance-sheet presentation affirmatively support it.

### Deterministic annual-fact selection

For a fact to qualify, it must satisfy all of these rules:

1. The configured taxonomy and concept must be marked `verified` or
   `verified_fallback`.
2. The unit must exactly match the configured unit.
3. The form must be exactly `10-K`; `10-Q` and `10-K/A` do not qualify.
4. The fiscal-period metadata must be `fp=FY`.
5. The actual period end must equal the requested May 31 date.
6. Duration facts must begin June 1 of the prior year; instant facts must not have a
   start date.
7. The accession number must map to one of the five verified filings, and the fact's
   filing date and `fy` metadata must agree with that filing.
8. A later filing may supply a repeated comparative fact, but never a filing earlier
   than the target fiscal year.

The `frame` field is retained in the manifest but is not required because SEC frames
may be absent or calendar-oriented for Nike's fiscal-year facts.

All eligible originally reported and later comparative facts are retained. If their
normalized values disagree, the metric-year is marked `manual_review`. When they
agree, the pipeline prefers the latest face-statement-visible presentation for the
highest-priority verified tag. This prevents a fact repeated only in another
statement or note from displacing the applicable face-statement comparison.

### Face-statement reconciliation

Selected Company Facts values must agree with the SEC-rendered face statement within
its displayed precision. The tolerance is USD 0.5 million for monetary values, 0.05
million for weighted-average shares, and $0.005 per share for EPS. Capital
expenditure is compared by absolute value because the cash-flow statement displays
the outflow in parentheses while Company Facts reports the payment amount as a
positive fact.

Debt is selected as three separate components: notes payable or other short-term
borrowings, current maturities of long-term debt, and noncurrent long-term debt.
Total interest-bearing debt is calculated as their sum. This avoids using the
`LongTermDebt` total alone when separately reported notes payable exist. FY2022 Note
7 reports $10 million of non-U.S. notes payable; the corresponding disclosed
balances are $6 million, $6 million, $5 million, and $0 for FY2023-FY2026.

Current and noncurrent operating lease liabilities are selected separately and
summed for information, but they are excluded from base total interest-bearing
debt. Lease expense remains within cost of sales and operating overhead, so adding
lease liabilities to debt without also adjusting operating profit and cash flow
would be internally inconsistent.

### Normalization and calculations

Monetary facts and share counts are divided by one million. EPS remains dollars per
share. Ratios are stored as decimals. Capital expenditure is stored as a positive
investment amount, and free cash flow is:

`operating cash flow - capital expenditure`

Nike does not present an operating-income subtotal on its consolidated income
statement. The approved consolidated measure is therefore clearly labeled derived
operating income and calculated as:

`gross profit - total selling and administrative expense`

For every year, an independent bridge checks that derived operating income plus
signed net interest income or expense plus signed other non-operating income or
expense equals income before taxes. Positive signed non-operating values represent
income and negative values represent expense. The derived consolidated measure is
not Nike's segment-level EBIT presentation.

The cleaned depreciation-and-amortization series deliberately crosses a taxonomy
transition: FY2022 uses `Depreciation`, while FY2023-FY2026 use
`DepreciationDepletionAndAmortization`. Overlapping observations agree and each
selected value reconciles to the annual cash-flow statement. The exact underlying
concept remains visible on every source-manifest row.

Gross, operating, net, operating-cash-flow, and free-cash-flow margins use revenue
as the denominator. Cash conversion is operating cash flow divided by net income.
Year-over-year revenue growth begins in FY2023. The five-observation revenue CAGR is
shown only in FY2026 and uses four growth intervals.

Every calculation checks input statuses. A missing or `manual_review` input produces
no calculated value. A `documented_zero` can flow only when official filing evidence
affirmatively supports zero. Division by zero also produces no value.

For the later valuation phase, the default version-one lease convention is to keep
lease expense operating and exclude operating lease liabilities from the
enterprise-to-equity bridge. The alternative would require a complete lease
capitalization adjustment to operating profit, cash flow, and debt; the two
treatments must not be mixed.

### Reproducibility and privacy

Tracked CSV rows and columns are written in stable order and use cached source
retrieval timestamps rather than run timestamps. Default reruns reuse the exact raw
cache files. The validation summary scans generated tracked outputs for a literal
SEC user-agent variable name, email-address marker, and common user-directory paths.
The real local `.env` and all raw cache content remain ignored.

## Phase 3: historical financial analysis

### Input boundary

Phase 3 reads only the committed `data/processed/nike_financials.csv`. It does not
call the SEC, read `.env`, or refresh the raw cache. Before calculation, the analysis
command verifies the approved SHA-256 hashes of the processed dataset, source
manifest, and validation summary. It also requires exactly FY2022-FY2026 in
chronological order, the expected May 31 period ends, documented status values, and
numeric values for every validated input.

Existing Phase 2 metrics are reused exactly. Phase 3 does not recompute revenue
growth, CAGR, margins, free cash flow, cash conversion, debt, leases, or derived
operating income under new names.

### Decimal calculation discipline

CSV fields are loaded as strings and converted to `Decimal` only when a calculation
requires them. Addition, subtraction, averaging, division, and growth calculations
therefore retain Decimal precision. The audit-friendly KPI table stores the complete
Decimal result available from those inputs. Rounding occurs only in notebook tables,
chart labels, and written narrative. Conversion to floating point occurs only inside
the Matplotlib chart boundary.

A Phase 3 calculation is valid only when all required inputs have `selected`,
`calculated`, or `documented_zero` status. A `manual_review` or missing input produces
no calculated value. A zero denominator produces a missing result rather than a
plausible zero.

### Additional historical KPIs

Phase 3 adds these calculations:

- `sga_as_percent_of_revenue = total_selling_and_administrative_expense / revenue`
- `cash_and_short_term_investments = cash_and_cash_equivalents + short_term_investments`
- `current_ratio = current_assets / current_liabilities`
- `net_working_capital = current_assets - current_liabilities`
- `net_debt_after_cash_and_short_term_investments = total_interest_bearing_debt - cash_and_cash_equivalents - short_term_investments`
- year-over-year growth in accounts receivable, inventory, and diluted EPS
- the FY2022-FY2026 absolute and percentage revenue change
- the maximum revenue observation and its fiscal year

The signed net-debt measure excludes operating lease liabilities. A negative value
means cash and short-term investments exceed interest-bearing debt and is described
as net cash in recruiter-facing material.

### Efficiency-day convention

Inventory days is:

`average inventory / cost of revenue * 365`

The receivables-days proxy is:

`average accounts receivable / revenue * 365`

Both metrics use beginning and ending balances and are therefore calculated only for
FY2023-FY2026. FY2022 is `not_applicable` because the committed dataset does not
contain FY2021 opening receivables or inventory. Ending balances are not used as a
substitute.

The 365-day factor is a consistent analytical convention, not a claim about the
exact number of days in each Nike fiscal reporting period. The receivables measure
uses total revenue rather than separately disclosed credit sales and is therefore
named `receivables_days_proxy`, not DSO.

### Artifact and chart generation

`nike-historical-analysis` validates the Phase 2 input contract, creates a five-row
historical summary, creates a long-form KPI audit table, and saves five static PNG
figures. The command writes no retrieval time, build time, user-agent value, or local
machine path. Repeated runs in the locked environment are required to produce
identical files.

The figures use a centralized colorblind-readable Matplotlib style and a
non-interactive backend. Unlike units are separated into panels instead of combined
through unnecessary secondary axes. Source notes identify Nike 10-K filings, SEC
Company Facts, and project calculations. The margin chart identifies derived
operating margin; the cash chart uses a 1.0x cash-conversion reference; and the
capital-structure chart displays lease liabilities separately from debt.

### Notebook execution and narrative

The historical notebook imports calculations and presentation helpers from `src/`.
It is executed from the repository root through the `nbclient` runner, so a clean
kernel can load repository-relative data and figures. Cell IDs and output metadata
are deterministic, and execution timing metadata is removed. The notebook contains
deliberately written Markdown rather than generated conclusions.

The narrative distinguishes observed changes from causal interpretation. It does not
forecast, value Nike, use stock-price data, or make an investment recommendation.

## Phase 4: consolidated operating scenarios

Phase 4 reads the protected FY2022-FY2026 history and the 105 documented inputs
in `config/scenario_assumptions.csv`. It produces base, bull, and bear forecasts for
FY2027-FY2031 without network access. The information cutoff is September 7, 2026.
Actuals, company commentary, analyst assumptions, and calculated forecast outputs
retain separate source classifications.

The model forecasts revenue, gross profit, total SG&A, `derived_operating_income`,
NOPAT, D&A, capital expenditures, an aggregate operating-NWC proxy, and FCFF. The
canonical operating subtotal remains gross profit less total SG&A. Nike does not
report this consolidated subtotal, and it is neither Nike-reported EBIT nor segment
EBIT.

FY2026 gross margin remains the reported 42.9%. Nike disclosed that the year included
an approximately 210-basis-point IEEPA tariff-recovery benefit and would have been
approximately 40.8% excluding the benefit. The model does not create an adjusted
historical actual; the FY2027 scenario margins represent different degrees of
underlying operational recovery.

The normalized operating tax rate is 21.0% in every scenario. A negative derived
operating result receives no automatic tax benefit unless a future phase adds a
separately documented NOL schedule. D&A and capex are forecast separately as revenue
percentages, and stock-based compensation is not added back.

Operating NWC removes cash, short-term investments, short-term financing, current
long-term debt, and current operating lease liabilities from aggregate current
balances. The FY2026 opening proxy is USD 5,507 million. Its tariff receivable is
already embedded, so the model does not separately add a subsequent tariff cash
collection. Full formulas, limitations, and the FY2027 bridge appear in
`docs/forecast_methodology.md`.

FCFF is unlevered cash flow available to all capital providers:

`NOPAT + D&A - capital expenditures - change in operating NWC`

The model does not subtract interest, debt repayment, dividends, or repurchases.

## Phase 5A valuation layer

The valuation layer consumes the protected full-precision Phase 4 FCFF output
without changing the operating forecast. It calculates a bottom-up WACC, discounts
FY2027-FY2031 FCFF at exact May 31 dates using 365-day XNPV-equivalent exponents,
constructs an explicit FY2032 stable-state bridge, and applies the Gordon-growth
formula. The enterprise-to-equity bridge uses documented cash, investments,
carrying debt, preferred stock, and a diluted-share proxy. Operating leases remain
a memorandum item under the approved operating convention.

The primary WACC uses fair-value debt for capital weighting; carrying debt is a
cross-check. Bear, Base, and Bull use one 2.5% perpetual-growth rate and no
probabilities. A direct-growth 5x5 Base-case sensitivity varies WACC and terminal
growth around the full-precision center. Complete formulas and source lineage are
documented in the valuation methodology.
