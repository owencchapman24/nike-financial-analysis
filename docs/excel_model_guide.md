# Excel valuation model guide

## Purpose and scope

`model/nike_valuation_model.xlsx` is the formula-driven Excel translation of the
approved Phase 5A Python DCF. It uses committed FY2022-FY2026 history, approved
FY2027-FY2031 analyst scenarios, and the documented valuation-input register. Python
remains the authoritative calculation engine; Excel provides a transparent model a
reviewer can navigate and audit. This independent portfolio analysis is not an
investment recommendation or price target.

The DCF valuation and discount-anchor date is September 4, 2026. The information
cutoff is September 7, 2026, and the USD 38.40 reference price is observed on the
valuation date. The equity bridge uses the latest completed balance sheet, dated
May 31, 2026, without an unsupported interim roll-forward.

## Worksheet map

1. `Cover` — scenario selector, headline outputs, comparison chart, status, and
   navigation.
2. `Sources` — valuation inputs, valuation sources, approved operating assumptions,
   and local source-file references.
3. `Historical` — the limited historical and FY2026 balance-sheet inputs needed to
   understand the DCF.
4. `Scenarios` — Bear, Base, and Bull operating schedules from FY2026A through
   FY2031E, calculated with native copy-across formulas.
5. `WACC` — primary fair-value-debt build and carrying-debt cross-check.
6. `DCF` — selected-scenario explicit forecast, FY2032 terminal bridge, equity
   bridge, `XNPV` cross-check, and compact all-scenario calculations.
7. `Sensitivity` — formula-driven Base-case 5x5 WACC/perpetual-growth table.
8. `Checks` — independent assertions and terminal-value-dependence warnings.

Every worksheet is visible. Navigation links on `Cover` open the main schedules.

## Scenario selector and calculation flow

Select `Bear`, `Base`, or `Bull` in `Cover!D6`; `Base` is the default. The selector
uses exact-match, nonvolatile formulas. It controls the detailed DCF and selected
Cover outputs but does not change assumptions or the compact all-scenario block.

The model flows from embedded sources to operating scenarios, then WACC and the DCF.
Derived operating income remains gross profit less total SG&A; it is a project-derived
consolidated subtotal, not Nike-reported operating income or segment EBIT. FCFF is
NOPAT plus D&A less capital expenditures and the change in operating NWC. Capex is a
positive investment amount. No tax benefit is created from negative derived
operating income without an NOL schedule.

The DCF discounts May 31 cash flows from September 4, 2026 using exact 365-day
exponents. The primary visible PV schedule reconciles with native `XNPV`.
FY2032 holds selected FY2031 operating ratios stable and applies the common 2.5%
perpetual-growth rate. The equity bridge adds cash and short-term investments and
subtracts carrying interest-bearing debt and redeemable preferred stock. Operating
lease liabilities are shown only as a memorandum item.

## Formatting conventions

- Blue font with pale yellow fill: genuinely editable inputs and the selector.
- Green font: internal cross-sheet links in working schedules.
- Black or dark neutral text: formulas, source facts, and Cover outputs.
- Red font is reserved for prohibited external-workbook links; none should exist.
- `A` denotes actual fiscal years and `E` denotes analyst estimates.
- Financial statement and valuation totals use USD millions unless labelled
  otherwise; percentages, multiples, shares, dates, and per-share values have
  dedicated formats.

## Rebuild, recalculate, and verify

From the repository root in Windows PowerShell:

```powershell
uv sync --locked --python 3.14.5
uv run nike-excel-model
uv run nike-excel-model --verify-only
uv run pytest tests/test_excel_model.py tests/test_excel_model_artifacts.py
```

The build never writes directly to the tracked workbook. It creates a temporary
candidate, inspects its structure, performs a full desktop Excel recalculation,
reopens formula and data-only states, reconciles material values to Python, scans the
OOXML package, and publishes atomically only after blocking checks pass. Desktop
Excel is required for regeneration. The PowerShell script opens and closes only the
candidate through its dedicated hidden Excel instance; it never terminates Excel
processes globally.

Python-seeded caches make the temporary pre-Excel candidate readable but are not
accepted as recalculation evidence. The `Checks` sheet includes a formula sentinel
whose initial cache is deliberately invalid; post-Excel verification requires the
correct calculated value.

## Checks and interpretation

`PASS WITH WARNINGS` is the expected aggregate status when all blocking assertions
pass and terminal-value dependence remains above 75%. A terminal-value warning is a
material valuation observation, not a formula failure. Any `FAIL` means the workbook
must not be published until corrected.

Excel and Python are reconciled within USD 0.1 million for totals, USD 0.01 per
share, 0.000001 million shares, and 1E-9 for rates, ratios, discount exponents, and
discount factors. The workbook also checks formula errors, sources, approved
assumptions, WACC mechanics, FCFF identities, dates, terminal mechanics, equity
bridge, sensitivity direction, and package safety.

The model contains no external workbook link, live refresh, data connection, macro,
or VBA. Its conclusions remain conditional on the approved scenarios, WACC inputs,
terminal growth, diluted-share proxy, operating-NWC proxy, and lease convention.
