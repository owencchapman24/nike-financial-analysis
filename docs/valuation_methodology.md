# DCF valuation methodology

## Scope

Phase 5A applies a transparent discounted-cash-flow calculation to the approved
FY2027-FY2031 Base, Bull, and Bear operating scenarios. The valuation and discount
anchor is September 4, 2026, and the information cutoff is September 7, 2026. The
September 4 closing price is a dated reference comparison, not a price target or
investment recommendation. The equity bridge uses Nike's latest completed reporting-
period balance sheet, dated May 31, 2026; no interim roll-forward is inferred.

The Python model is the authoritative Phase 5A calculation engine. It creates
auditable CSV exports. The separately documented Phase 5B workbook translates and
reconciles to this calculation rather than replacing it.

## Input lineage

[`valuation_assumptions.csv`](../config/valuation_assumptions.csv) is the canonical
input register. Each row records an identifier, category, value, unit, observation
date, source IDs, source type, approval status, and notes.
[`valuation_sources.csv`](../config/valuation_sources.csv) resolves those IDs to
the Phase 4 forecast, Nike's FY2026 10-K, official rate data, market-reference
evidence, general methodology sources, or documented project judgment.

Historical facts, market inputs, analyst assumptions, calculated results, and
cross-checks remain separately labelled. All financial arithmetic uses `Decimal`;
floating-point conversion occurs only when Matplotlib renders the chart.

## WACC build

The primary WACC uses a product-weighted bottom-up beta and fair-value debt for
capital weighting:

```text
Unlevered beta = sum(product revenue × product beta) / classified product revenue
Levered beta = unlevered beta × [1 + (1 − tax rate) × debt / market equity]
Cost of equity = risk-free rate + levered beta × equity-risk premium
Pretax cost of debt = risk-free rate + default spread
After-tax cost of debt = pretax cost of debt × (1 − tax rate)
WACC = equity weight × cost of equity + debt weight × after-tax cost of debt
```

The inputs are a 4.78% risk-free rate, 4.14% equity-risk premium, 0.78% debt
spread, 21.0% tax rate, approximately USD 6,800 million of fair-value debt, and a
product-weighted unlevered beta of approximately 0.9262. The resulting WACC is
8.4874438275% at full calculation precision and 8.5% when displayed.

A second build substitutes USD 7,942 million of carrying debt. It is a validation
cross-check only and does not create another headline valuation.

## Cash-flow timing and present value

The valuation date is September 4, 2026. FY2027-FY2031 FCFF remains assigned to
each May 31 fiscal-year-end date. The discount exponent follows Excel XNPV's 365-day
convention:

```text
Discount exponent = (cash-flow date − model date) / 365
Discount factor = 1 / (1 + WACC) ^ discount exponent
Present value = FCFF × discount factor
```

The FY2027 exponent is 269/365 and the leap day produces an FY2028 exponent of
635/365 rather than an assumed integer period. No interim balance-sheet roll-forward,
mid-year convention, interest expense, debt
repayment, dividend, or repurchase enters FCFF.

This exact date arithmetic is still an annual-model approximation, not a fully
rolled-forward September 4 valuation. FY2027 FCFF covers the complete June 2026-May
2027 fiscal year, September 4 is the discount anchor and reference market date, and
the equity bridge retains May 31 balances. The model does not estimate interim
retained cash, distributions, seasonality, a residual-year forecast, or balance-sheet
changes between those dates.

As a limited timing diagnostic, May 31 to September 4 contains 96 elapsed days and
269 days remain until the next May 31. Hypothetically removing 96/365 of full-year
FY2027 FCFF, discounting that amount with the FY2027 factor, and leaving the equity
bridge unchanged would reduce value per diluted-proxy share by approximately $0.424
in Bear, $0.522 in Base, and $0.575 in Bull. These are not corrected fair values.
Interim retained cash, distributions, seasonality, and balance-sheet changes could
alter or offset the isolated effect.

## FY2032 terminal transition

FY2032 is an explicit transition into a stable terminal state. Revenue grows at the
common 2.5% perpetual rate. Each scenario retains its FY2031 gross margin,
SG&A/revenue, normalized tax rate, D&A/revenue, capex/revenue, and operating-NWC /
revenue ratio. The bridge recalculates FY2032 revenue, derived operating income,
NOPAT, D&A, capex, operating NWC, change in operating NWC, and FCFF.

```text
Terminal value at May 31, 2031 = FY2032 FCFF / (WACC − terminal growth)
```

The model requires WACC to exceed terminal growth. A terminal-value present-value
share above 75% of enterprise value is shown as a warning and above 80% as a strong
warning. These are visible dependence observations, not automatic calculation
failures.

The FY2032 bridge also implies a useful steady-state reinvestment diagnostic. Net
reinvestment (capex less D&A plus the change in operating NWC) is approximately USD
133.2 million in Bear, USD 181.3 million in Base, and USD 188.1 million in Bull. That
equals 4.33%, 3.63%, and 3.00% of NOPAT, respectively; dividing the 2.5% terminal
growth rate by those reinvestment rates implies incremental-return diagnostics of
approximately 57.7%, 68.9%, and 83.4%. This relationship is neither Nike-reported
ROIC nor measured historical ROIC. It reflects substantial modeled growth relative
to simplified capex, D&A, operating-NWC, and operating-expense assumptions; high
results do not by themselves indicate a formula error. If net reinvestment were zero
or negative, this diagnostic would be reported as not applicable rather than forced.

## Enterprise-to-equity bridge

The bridge adds all USD 9,027 million of cash and short-term investments, subtracts
USD 7,942 million of carrying-value interest-bearing debt, and subtracts USD 0.3
million of redeemable preferred stock. It makes no unsupported adjustments.

Operating lease liabilities of USD 3,091 million remain a memorandum item and are
not deducted. This matches the operating treatment in which lease expense remains
within forecast operating costs. A future change would require a complete,
internally consistent lease-capitalization adjustment.

Headline value per share uses a 1,484.698703 million diluted-share proxy. The
1,483.498703 million basic share count is a denominator cross-check only.

## Scenario and sensitivity presentation

Bear, Base, and Bull are valued independently with the same WACC and 2.5% terminal
growth rate. Scenario differences therefore come from approved operating and
reinvestment forecasts, not from different terminal-growth assumptions. No
probabilities are assigned.

The Base-case 5×5 table uses terminal-growth columns of 1.5%, 2.0%, 2.5%, 3.0%,
and 3.5%. WACC rows are the exact formula-derived WACC minus 1.0 percentage point,
minus 0.5 points, unchanged, plus 0.5 points, and plus 1.0 point. Row labels are
rounded for presentation while every cell uses the full-precision rate. The center
cell uses the same coordinate-driven formula as the other 24 cells. Its independent
headline reconciliation is performed only when the displayed center WACC and growth
match the headline assumptions; otherwise the check is explicitly not applicable.
Duplicate or unordered coordinates are disclosed separately from calculation
integrity.

## Reproduction

Phase 5A needs no network access or `.env`:

```powershell
uv run nike-dcf-valuation
uv run pytest
```

The command validates all protected Phase 2-4 artifacts before writing five CSV
exports under `outputs/model_exports/` and one static comparison chart under
`outputs/charts/`.
