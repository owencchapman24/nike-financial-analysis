# Forecast methodology

## Scope and information boundary

Phase 4 is a consolidated, driver-based operating forecast for FY2027-FY2031. It
uses Nike information available on or before September 7, 2026, and the committed
FY2022-FY2026 SEC-derived history. Nike's FY2027 first-quarter results were scheduled
for October 1, 2026 and are outside the information cutoff. The model contains no
discount rate, present value, terminal value, market price, or other valuation input.

The source register in `config/forecast_sources.csv` distinguishes reported facts,
company forward-looking commentary, committed project calculations, and project
analyst assumptions. The long-form assumption register contains exactly 105
documented scenario-year-driver inputs.

Official company evidence used for the forecast context is Nike's
[FY2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/320187/000032018726000088/nke-20260531.htm),
[FY2026 results release](https://investors.nike.com/investors/news-events-and-reports/investor-news/investor-news-details/2026/NIKE-Inc--Reports-Fiscal-2026-Fourth-Quarter-and-Full-Year-Results/default.aspx),
[official FY2026 earnings-call transcript](https://s1.q4cdn.com/806093406/files/doc_financials/2026/q4/NIKE-Inc-Q4FY26-OFFICIAL-Transcript_-FINAL.pdf),
and the [FY2027 first-quarter reporting-date announcement](https://investors.nike.com/investors/news-events-and-reports/investor-news/investor-news-details/2026/NIKE-Inc--Announces-First-Quarter-Fiscal-2027-Earnings-and-Conference-Call/default.aspx).
The last source enforces the cutoff: those results were scheduled after September 7
and are not used.

## Historical driver anchors

These presentation-rounded anchors are calculated from the committed data. The
historical FCFF bridge uses the Phase 4 formula and therefore differs from Phase 2
free cash flow, which is operating cash flow less capex.

| Driver | FY2022 | FY2023 | FY2024 | FY2025 | FY2026 |
|---|---:|---:|---:|---:|---:|
| Revenue growth | N/A | 9.6% | 0.3% | -9.8% | 0.2% |
| Gross margin | 46.0% | 43.5% | 44.6% | 42.7% | 42.9% |
| SG&A / revenue | 31.7% | 32.0% | 32.3% | 34.7% | 34.7% |
| Derived operating margin | 14.3% | 11.5% | 12.3% | 8.0% | 8.2% |
| Effective tax rate | 9.1% | 18.2% | 14.9% | 17.1% | 20.3% |
| D&A / revenue | 1.54% | 1.37% | 1.55% | 1.67% | 1.61% |
| Capex / revenue | 1.62% | 1.89% | 1.58% | 0.93% | 1.47% |
| Operating NWC proxy (USDm) | 5,416 | 5,702 | 4,690 | 4,152 | 5,507 |
| Operating NWC / revenue | 11.6% | 11.1% | 9.1% | 9.0% | 11.9% |
| Change in operating NWC (USDm) | N/A | 286 | -1,012 | -538 | 1,355 |
| Historical FCFF bridge (USDm) | N/A | 4,284 | 6,365 | 3,950 | 1,734 |

| Rate driver | 3-year average | 3-year median | Full-period average | Full-period median | Range | Forecast use |
|---|---:|---:|---:|---:|---:|---|
| Revenue growth | -3.1% | 0.2% | 0.1% | 0.2% | -9.8%-9.6% | Context only; four growth observations are volatile. |
| Gross margin | 43.4% | 42.9% | 43.9% | 43.5% | 42.7%-46.0% | Useful range, with FY2026 tariff-benefit context. |
| SG&A / revenue | 33.9% | 34.7% | 33.1% | 32.3% | 31.7%-34.7% | Useful for expense-rigidity and leverage paths. |
| Derived operating margin | 9.5% | 8.2% | 10.9% | 11.5% | 8.0%-14.3% | Output cross-check, not an independent driver. |
| Effective tax rate | 17.5% | 17.1% | 15.9% | 17.1% | 9.1%-20.3% | Requires normalization; individual years include tax-mix and discrete-item effects. |
| D&A / revenue | 1.61% | 1.61% | 1.55% | 1.55% | 1.37%-1.67% | Stable rounded anchor. |
| Capex / revenue | 1.33% | 1.47% | 1.50% | 1.58% | 0.93%-1.89% | Scenario-specific reinvestment anchor. |
| Operating NWC / revenue | 10.0% | 9.1% | 10.5% | 11.1% | 9.0%-11.9% | Approved normalization paths; FY2026 includes tariff receivable. |

## Forecast bridge

All calculations use `Decimal`; CSV outputs retain full available precision and
rounding occurs only in charts, notebook tables, and prose.

```text
Revenue_t = Revenue_(t-1) * (1 + revenue_growth_t)
Gross_profit_t = Revenue_t * gross_margin_t
Total_SG&A_t = Revenue_t * sga_percent_revenue_t
Derived_operating_income_t = Gross_profit_t - Total_SG&A_t
NOPAT_t = Derived_operating_income_t - normalized_operating_tax_expense_t
D&A_t = Revenue_t * da_percent_revenue_t
Capital_expenditures_t = Revenue_t * capex_percent_revenue_t
Operating_NWC_t = Revenue_t * operating_nwc_percent_revenue_t
Change_ONWC_t = Operating_NWC_t - Operating_NWC_(t-1)
FCFF_t = NOPAT_t + D&A_t - Capital_expenditures_t - Change_ONWC_t
```

`derived_operating_income` is the canonical identifier. It is a project-calculated
consolidated subtotal equal to gross profit less total SG&A. Nike does not report
this consolidated subtotal, and it is not Nike-reported EBIT or segment EBIT.

## Revenue, gross margin, and SG&A

Revenue scenarios use nominal reported consolidated revenue. They do not mix
reported and currency-neutral growth. Each scenario uses an annual path that moves
from near-term pressure or stabilization toward a mature-company endpoint rather
than applying one constant growth rate.

FY2026 reported gross margin remains 42.9%. Nike stated that FY2026 included an
approximately 210-basis-point IEEPA tariff-recovery benefit and that gross margin
would have been approximately 40.8% excluding that benefit. The model does not
replace the audited actual with an adjusted value. Instead, FY2027 assumptions of
42.5% in base, 43.0% in bull, and 41.5% in bear imply different degrees of
underlying operational margin recovery relative to the disclosed counterfactual.

SG&A is forecast as a percentage of revenue. The bull scenario allows absolute SG&A
to increase while its revenue percentage declines, preserving the reinvestment
needed to support higher sales. The bear scenario reflects greater expense rigidity.

## Normalized operating tax

Nike provided a low-20% FY2027 full-year effective-tax-rate outlook, which is a range
rather than an exact point estimate. The project selected 21.0% as a normalized
operating tax rate within that context and holds it constant in every year and
scenario. The 21.0% input is not an exact Nike-guided rate and is not a detailed
cash-tax forecast. Interest expense is not included in NOPAT.

Absent a separately documented net-operating-loss schedule, the calculation applies
tax only when derived operating income is positive. Negative derived operating
income therefore produces zero normalized operating tax expense, not an automatic
tax benefit.

## D&A and capital expenditures

D&A and capital expenditures are separate revenue-based drivers. They are not
forced to equal each other. Bull-case capital expenditures are generally the
highest percentage, consistent with faster growth; the bear case retains a positive
maintenance level. Stock-based compensation remains an operating expense and is not
added back to FCFF.

## Aggregate operating-NWC proxy

The project historical proxy is:

```text
Operating current assets = current assets - cash - short-term investments
Operating current liabilities = current liabilities
  - notes payable and short-term borrowings
  - current portion of long-term debt
  - current operating lease liabilities
Operating NWC proxy = operating current assets - operating current liabilities
```

The proxy removes cash, marketable short-term investments, short-term financing,
current debt maturities, and current lease liabilities. It remains aggregate: tax
balances, dividends payable, and other operating or non-operating current balances
may still be embedded because the committed historical dataset does not break them
out. It should not be described as perfectly defined operating working capital.

FY2026 opening operating NWC is USD 5,507 million, or 11.87% of revenue. The FY2026
tariff receivable is already embedded in that balance. The model does not add a
separate subsequent tariff cash collection to FCFF; doing so would double count the
working-capital normalization captured by the declining ONWC percentages.

| Scenario | FY2026 opening ONWC | FY2027 closing ONWC | FY2027 change | FCFF effect |
|---|---:|---:|---:|---:|
| Base | $5,507m | $5,047m | -$460m | +$460m source of cash |
| Bull | $5,507m | $5,036m | -$471m | +$471m source of cash |
| Bear | $5,507m | $5,211m | -$296m | +$296m source of cash |

A positive change in operating NWC is a use of cash and reduces FCFF. A negative
change is a source of cash. This normalization is a material reason forecast FY2027
FCFF exceeds the comparable historical FY2026 FCFF bridge in every scenario; the
increase must not be presented as purely operating-driven.

## Lease convention

Lease expense remains in operating expenses and derived operating income. Operating
lease liabilities remain separate from interest-bearing debt and are excluded from
operating NWC. The forecast does not add separate lease principal or imputed lease
interest to FCFF. A later valuation must preserve this convention unless it applies
a complete, separately documented lease-capitalization adjustment.

## Reproduction and controls

Run `uv run nike-scenario-forecast` from the repository root. Execution reads only
committed project files, requires no network access or `.env`, validates the documented
assumption grid and source IDs, protects Phase 2-3 artifact hashes, and writes four
tables and four static charts deterministically.
