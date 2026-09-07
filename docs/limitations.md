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

- No charts or analytical conclusions
- No notebook narrative
- No inventory days, ROIC, or advanced working-capital metrics
- No segment or geography analysis
- No operating scenarios, forecast, DCF, market inputs, or Excel model
- No unofficial historical accounting source
