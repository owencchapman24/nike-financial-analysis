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
May 31, 2026, without an unsupported interim roll-forward. FY2027 FCFF remains a
full-fiscal-year amount, so the result is an annual-model approximation rather than a
fully rolled-forward September 4 valuation.

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
8. `Checks` — separate mechanical-integrity, approved-snapshot, warning, and
   package/build-control summaries plus the underlying assertions.

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

- Blue font with pale yellow fill: editable inputs and the scenario selector. An
  assumption edit creates an exploratory, noncanonical workbook until it is reviewed
  and incorporated into the approved source files; Bear/Base/Bull selector changes do
  not alter the approved input snapshot.
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
uv run pytest
uv run pytest --run-excel-integration
uv run pytest --run-excel-integration -m excel_integration
```

The portable command reports 117 passed and three skipped Excel integrations. On a
compatible Windows/Excel machine, the full opt-in command runs all 120 tests; the
integration-only command reports three passed and 117 deselected. An explicit opt-in
fails with an actionable prerequisite error if Windows PowerShell or desktop Excel
is unavailable.

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

`PASS WITH WARNINGS` is the expected canonical publication status when mechanical
integrity and package/build controls pass, the workbook matches the approved snapshot,
and terminal-value dependence remains above 75%. A valid what-if edit can leave
mechanical integrity at `PASS` while approved-snapshot reconciliation reports
`DIFFERS FROM APPROVED`; the aggregate then reads `NOT PUBLISHABLE — DIFFERS FROM
APPROVED`. A formula failure remains blocking and cannot be hidden by an edited-input
state. Missing, unverified, or inapplicable checks are never reported as successful
verification.

Package/build controls cover source-register resolution, recalculation caches, links,
connections, macros, and package conditions. They can remain `PASS` for a mechanically
valid what-if edit. `Checks!H6` is the sole canonical publication gate and also drives
the Cover status.

Excel and Python are reconciled within USD 0.1 million for totals, USD 0.01 per
share, 0.000001 million shares, and 1E-9 for rates, ratios, discount exponents, and
discount factors. The workbook also checks formula errors, sources, approved
assumptions, WACC mechanics, FCFF identities, dates, terminal mechanics, equity
bridge, sensitivity direction, and package safety.

All 25 sensitivity cells calculate from their displayed WACC and terminal-growth
coordinates. Center-to-headline equality is checked only when the center coordinates
match the headline assumptions. Duplicate or unordered coordinates produce a
separate input warning and make strict monotonicity checks inapplicable rather than
misclassifying equal-coordinate outputs as arithmetic failures.

The model contains no external workbook link, live refresh, data connection, macro,
or VBA. Its conclusions remain conditional on the approved scenarios, WACC inputs,
terminal growth, diluted-share proxy, operating-NWC proxy, and lease convention.
