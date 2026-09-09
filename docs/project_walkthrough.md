# Project walkthrough

## Purpose

I built this independent portfolio project to connect Nike's reported performance
with explicit operating assumptions, reinvestment requirements, and valuation
inputs. It traces five historical years through three consolidated scenarios and an
illustrative DCF; it does not recommend whether Nike's shares should be bought or
sold.

The historical period is FY2022-FY2026, the explicit forecast covers
FY2027-FY2031, the DCF model date is May 31, 2026, and the information cutoff is
September 7, 2026. The separately dated comparison price is $38.40 on September 4,
2026.

## Architecture

The repository keeps source evidence, calculations, narrative, and presentation
separate. Official SEC facts flow into a reconciled historical dataset and documented
performance metrics. Approved Bear, Base, and Bull assumptions then drive the
five-year operating forecast and FCFF calculation.

Python is the calculation source of record for WACC, the terminal bridge, scenario
valuations, and sensitivity outputs. The Excel workbook presents the same model in
visible native formulas and checks its results against Python.

The main implementation lives in
[`src/nike_financial_analysis/`](../src/nike_financial_analysis/). Published
outputs are under [`outputs/`](../outputs/), and the formula-driven workbook is
[`model/nike_valuation_model.xlsx`](../model/nike_valuation_model.xlsx).

## SEC extraction and reconciliation

The historical pipeline uses SEC EDGAR filings and SEC XBRL APIs as its primary
accounting sources. It verifies Nike's issuer identity and fiscal periods, then
evaluates candidate facts by form, duration or instant context, unit, period end,
filing date, accession number, amendment status, and duplicate context.

Selection is not based on the first matching tag. The pipeline preserves competing
facts and later comparative presentations, applies documented tag substitutions,
and blocks uncertain inputs rather than filling gaps. Each selected or calculated
observation is traceable through the 339-row
[`source_manifest.csv`](../data/metadata/source_manifest.csv). Core values were also
reconciled to SEC-rendered consolidated face statements.

Important historical judgments include:

- Derived operating income is gross profit less total SG&A because Nike does not
  report a consolidated operating-income subtotal. It is not segment EBIT.
- The D&A series visibly bridges `Depreciation` in FY2022 to
  `DepreciationDepletionAndAmortization` in FY2023-FY2026.
- Interest-bearing debt includes short-term borrowings plus current and noncurrent
  long-term debt. Operating lease liabilities remain separate.
- Capital expenditure is stored as a positive investment amount.

The detailed rules are documented in the
[`methodology`](methodology.md), [`data dictionary`](data_dictionary.md), and
[`decision log`](decision_log.md).

## Historical analysis

The historical analysis covers revenue, profitability, cash generation, working
capital, liquidity, and capital structure.

The five-year record shows:

- Revenue reached $51,362 million in FY2024 and declined 9.7% to $46,398 million in
  FY2026. The FY2026 endpoint was 0.7% below FY2022.
- Gross margin declined from 46.0% in FY2022 to 42.9% in FY2026. Derived operating
  margin declined from 14.3% to 8.2%, while SG&A increased from 31.7% to 34.7% of
  revenue over the same period.
- Free cash flow declined from a $6,617 million FY2024 peak to $2,184 million in
  FY2026. FY2026 FCF margin was 4.7% and cash conversion was 0.92x.
- Cash plus short-term investments declined to $9,027 million by FY2026, while the
  net-cash buffer narrowed to $1,085 million.
- The receivables-days proxy increased from 36.0 days in FY2025 to 41.9 days in
  FY2026. It is not called DSO because total revenue, rather than disclosed credit
  sales, is the denominator.

These are observed relationships, not unsupported causal conclusions. The complete
narrative is in the
[`historical-analysis notebook`](../notebooks/01_historical_analysis.ipynb) and
[`historical findings`](historical_findings.md).

## Scenario construction

The forecast is consolidated and driver-based rather than a full three-statement,
segment, geography, or channel model. For each scenario and forecast year, approved
assumptions specify revenue growth, gross margin, SG&A as a percentage of revenue,
normalized operating tax, D&A, capex, and operating NWC.

The operating bridge is:

```text
Revenue
  -> gross profit
  -> total SG&A
  -> derived operating income
  -> NOPAT
  + D&A
  - capital expenditures
  - change in operating NWC
  = FCFF
```

The Base case assumes near-term revenue pressure followed by gradual recovery. The
Bull case assumes faster revenue and margin normalization with reinvestment
consistent with higher growth. The Bear case assumes longer weakness and greater
cost rigidity while retaining maintenance investment. The cases are project analyst
scenarios, not Nike guidance, consensus estimates, probabilities, or predictions.

FY2026 reported gross margin remains unchanged at 42.9%. Nike's disclosed tariff-
recovery benefit is context for the FY2027 margin assumptions, not an adjusted
historical actual. FY2027 FCFF is also supported by modeled working-capital
normalization and should not be described as purely operating-driven.

See the [`scenario notebook`](../notebooks/02_scenario_forecast.ipynb),
[`forecast methodology`](forecast_methodology.md), and
[`scenario rationale`](scenario_rationale.md).

## DCF and WACC methodology

The DCF values FCFF available to all capital providers. It therefore discounts FCFF
with WACC and does not subtract interest expense, debt repayment, dividends, or
repurchases.

The primary WACC is 8.4874% and is built from:

- a risk-free rate;
- an implied equity-risk premium;
- product-revenue-weighted unlevered beta proxies;
- relevering based on market equity and fair-value debt;
- a ratings-based debt spread; and
- an operating tax shield on debt cost.

Carrying debt provides a WACC cross-check but does not replace the approved primary
fair-value-debt weighting. Market observations, dates, source IDs, and proxy choices
remain visible in the valuation input and source registers.

Cash flows are discounted from May 31, 2026 to their exact May 31 fiscal-year-end
dates using 365-day exponents. The FY2032 terminal bridge applies the common 2.5%
perpetual-growth rate and holds the selected FY2031 operating ratios stable. The
Gordon-growth terminal value is calculated from FY2032 FCFF.

Enterprise value equals the present value of explicit FCFF plus the present value
of terminal value. The equity bridge adds $9,027 million of cash and short-term
investments and subtracts $7,942 million of carrying interest-bearing debt and $0.3
million of redeemable preferred stock. Operating leases remain memorandum-only.
Equity value is divided by 1,484.698703 million diluted-proxy shares; basic shares
provide a denominator cross-check.

The resulting illustrative values are $29.44 for Bear, $46.81 for Base, and $58.30
for Bull. Terminal value represents 76.7%-79.1% of enterprise value across the
cases, which makes WACC, perpetual growth, and the FY2031 operating state especially
important. Full calculations and limitations appear in the
[`valuation methodology`](valuation_methodology.md) and
[`valuation outputs`](../outputs/model_exports/valuation_summary.csv).

## Python and Excel relationship

Python is the calculation source of record. It preserves Decimal precision, produces
the valuation exports, and supplies the reconciliation benchmark.

The Excel workbook is a transparent translation for reviewers. Its eight visible
worksheets expose sources, historical inputs, all three scenarios, both WACC builds,
the selected-scenario DCF, sensitivity, and independent checks. The workbook uses
native formulas, an explicit present-value schedule, and an `XNPV` cross-check. It
contains no macros, external workbook links, or live data connections.

The publication script recalculates a temporary candidate in a dedicated Windows
desktop Excel instance, reopens it in formula and data-only modes, and checks it
against Python before publishing. A failed package, formula, cache, or reconciliation
check stops publication. The
[`Excel model guide`](excel_model_guide.md) explains how to use and regenerate it.

## Validation controls

The controls focus on fact selection, units, signs, fiscal periods, missing inputs,
and financial identities. Status propagation prevents unresolved inputs from
entering calculations, while protected hashes detect changes to approved upstream
artifacts. The test suite also checks repeatable artifact generation, notebook
execution, and Excel-to-Python reconciliation, including the explicit-PV versus
`XNPV` comparison.

The three workbook warnings disclose terminal-value dependence above 75%; they are
analytical warnings rather than calculation failures.

## Limitations and extensions

Five annual observations cannot establish causation or reveal quarterly
seasonality. The forecast is consolidated and assumption-dependent. Operating NWC,
unlevered beta, diluted shares, and other model elements use documented proxies.
The information cutoff prevents later facts from entering the analysis. Terminal
value represents most of enterprise value, and operating leases are excluded from
net debt because lease expense remains operating.

The full limitations are in [`limitations.md`](limitations.md). Possible extensions
include refreshed filings, consistent segment or geographic
analysis where disclosures permit, and a separately sourced comparable-company
cross-check. They remain outside the current scope.

This independent portfolio project is not affiliated with Nike and does not provide
an investment recommendation, price target, or prediction of future stock
performance.
