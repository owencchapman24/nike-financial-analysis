# Limitations

## Phase 2 accounting and data limitations

- Nike does not present an operating-income subtotal in the consolidated statements
  of income, and Company Facts has no directly reported `OperatingIncomeLoss` fact
  for the requested years. The project therefore labels the measure
  `derived_operating_income`, calculates it as gross profit less total selling and
  administrative expense, and cross-checks it through the non-operating lines to
  income before taxes. It must not be described as directly reported or confused
  with Nike's segment EBIT.
- The D&A series crosses a taxonomy/presentation change. FY2022 uses
  `Depreciation`; FY2023–FY2026 use `DepreciationDepletionAndAmortization`. The
  overlapping values agree, but the label change should remain visible to reviewers.
- The selected inventory concept is `InventoryFinishedGoodsNetOfReserves`. It
  reconciles to Nike's “Inventories” face line, but the concept name reflects Nike's
  predominantly finished-goods inventory structure rather than a generic inventory
  total tag.
- Short-term investments use a current available-for-sale debt-securities concept.
  The SEC Company Facts object has no friendly label for that concept, so the
  consolidated balance-sheet label is the presentation cross-check.
- Total interest-bearing debt includes notes payable or short-term borrowings,
  current maturities of long-term debt, and noncurrent long-term debt. FY2026 notes
  payable is a documented zero based on the debt note and omitted balance-sheet
  line, not a silent assumption. A future filing refresh could change that evidence.
- Operating lease liabilities are shown separately but excluded from base debt.
  Later valuation work must either keep lease expense operating and exclude lease
  liabilities from the enterprise-to-equity bridge, as currently intended, or make
  a complete lease-capitalization adjustment.
- SEC-rendered face statements display rounded USD millions. Reconciliation uses a
  tolerance consistent with that precision while retaining unscaled reported values
  in the manifest.
- Company Facts can add new filings or amended facts after retrieval. The committed
  outputs remain reproducible from the cached source metadata, but a deliberate
  refresh may produce a new evidence set that requires review.
- Raw SEC payloads and rendered statement files are intentionally ignored to keep
  the repository small and private. Reviewers can audit the committed manifest or
  rerun retrieval with their own local SEC user agent.

## Work intentionally outside Phase 2

- No ROIC or advanced operating-working-capital metrics
- No segment or geography analysis
- No operating scenarios, forecast, DCF, market inputs, or Excel model
- No unofficial historical accounting source

## Phase 3 analytical limitations

- The analysis contains five annual observations. It cannot show quarterly
  seasonality, distinguish shorter operating changes within a year, or establish a
  durable long-run trend by itself.
- Historical relationships do not prove causation. The notebook and findings state
  observed changes without attributing them to pricing, mix, demand, foreign
  exchange, strategy, or another driver unless a specific official disclosure is
  separately cited.
- `net_working_capital` is current assets less current liabilities. It is a broad
  liquidity measure, not an operating net-working-capital definition for forecasting
  or free-cash-flow valuation.
- Inventory days and `receivables_days_proxy` use average beginning and ending
  balances and a consistent 365-day convention. The convention is not a claim about
  the exact length of each fiscal reporting period.
- FY2022 inventory and receivables days are `not_applicable` because FY2021 opening
  balances are not present. The project does not estimate them from ending balances.
- The receivables-days proxy divides average receivables by total revenue because
  separately disclosed credit sales are unavailable. It must not be described as
  DSO.
- Signed net debt excludes operating lease liabilities. A negative value indicates
  net cash under this convention, not negative debt. The later valuation phase must
  preserve this treatment or perform a complete lease-capitalization adjustment.
- Phase 2 ratios are reused at their committed precision. New Phase 3 calculations
  retain Decimal precision from the available committed inputs, but no analysis can
  recover precision that the source dataset does not contain.

## Work intentionally outside Phase 3

- No forecasts, scenarios, WACC, DCF, terminal value, or price target
- No peer comparison, stock-price series, macroeconomic series, or third-party API
- No segment or geographic analysis
- No machine learning, predictive model, interactive dashboard, or Excel valuation
  workbook
- No investment recommendation

## Phase 4 forecast limitations

- Base, bull, and bear are project analyst scenarios, not Nike guidance, consensus
  estimates, probabilities, or predictions. The five-year paths depend materially
  on documented analyst assumptions.
- The information cutoff is September 7, 2026. Nike's FY2027 first-quarter results,
  scheduled after that date, are deliberately excluded.
- The forecast is consolidated and driver-based, not a segment, geography, channel,
  product, or full three-statement model. Qualitative disclosures inform assumptions
  but do not support fabricated detailed forecasts.
- FY2026 gross margin remains the reported 42.9% and includes an approximately
  210-basis-point IEEPA tariff-recovery benefit. Nike's disclosed approximately
  40.8% counterfactual excluding that benefit is context, not an adjusted actual.
- The operating-NWC proxy uses aggregate current balances after excluding identifiable
  cash, investments, financing, current debt, and current lease liabilities. Tax,
  dividends payable, and other non-operating balances may remain embedded.
- FY2027 working-capital normalization materially supports FCFF in every scenario.
  Forecast FY2027 FCFF therefore should not be described as a purely operating-driven
  improvement from FY2026.
- The FY2026 tariff receivable is treated as embedded in opening operating NWC. No
  separate future cash receipt is added to FCFF.
- The 21.0% normalized tax rate is an operating assumption, not a cash-tax schedule.
  No automatic loss-related tax benefit is recognized without an NOL schedule.
- D&A and capex are simplified revenue-based drivers. The forecast does not include
  a detailed fixed-asset roll-forward.
- Lease expense remains operating, while operating lease liabilities are excluded
  from debt, operating NWC, and separate FCFF adjustments. A later valuation must
  keep this convention or perform a complete lease-capitalization adjustment.

## Work intentionally outside Phase 4

- No WACC, discount factors, terminal growth, terminal value, enterprise value,
  equity bridge, market price, or implied share price
- No forecast interest, debt repayment, dividends, repurchases, diluted shares, or EPS
- No probability-weighted scenario, peer comparison, Monte Carlo simulation, or
  investment recommendation
- Phase 4 itself contains no valuation or Excel model; those are separate Phase 5
  deliverables.

## Phase 5A valuation limitations

- The DCF is conditional on three project analyst operating scenarios. It is not a
  prediction, price target, or investment recommendation.
- The September 4, 2026 valuation date uses the latest completed balance-sheet
  inputs from May 31, 2026. No unsupported interim balance-sheet roll-forward is
  inferred.
- WACC depends on market observations and proxy choices, including product-level
  sector betas, fair-value debt, an implied equity-risk premium, and a ratings-based
  spread. The carrying-debt build is only a cross-check.
- The terminal calculation assumes a common 2.5% perpetual-growth rate and stable
  FY2031 operating ratios. Terminal value represents more than 75% of enterprise
  value in each scenario, increasing sensitivity to WACC, terminal growth, and the
  FY2031 operating state.
- The diluted-share denominator is a proxy, not a forecast option schedule.
- Operating leases remain outside net debt because lease expense remains operating.
- No unsupported enterprise-to-equity bridge adjustments are included.

## Phase 5B Excel-model limitations

- The workbook translates the approved Python valuation and does not provide an
  independent second set of economic assumptions. Python remains authoritative.
- Rebuilding requires Windows desktop Microsoft Excel because formula-cache
  verification depends on a dedicated COM recalculation. Reviewers without Excel can
  inspect the committed recalculated workbook but cannot reproduce that step locally.
- Excel stores numeric calculations as binary floating-point values, while the Python
  engine uses Decimal arithmetic. Reconciliation therefore uses explicit tolerances;
  observed differences are expected to be materially smaller than those limits.
- Terminal value exceeds 75% of enterprise value in all three scenarios. The model
  displays those observations as warnings rather than suppressing the valuation.
- The September 4, 2026 valuation date uses May 31, 2026 balance-sheet inputs. The
  workbook does not infer an interim balance-sheet roll-forward.
- Operating leases are memorandum-only and external workbook links, macros, live
  data connections, and scenario probabilities are intentionally absent.
