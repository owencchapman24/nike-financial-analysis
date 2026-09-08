# Data Dictionary

This document defines the tracked Phase 2 datasets. Monetary values in the cleaned
dataset are USD millions. Ratios are decimals rather than formatted percentages.
Blank values are intentional and must be interpreted together with the adjacent
status column.

## Status vocabulary

| Status | Meaning |
|---|---|
| `selected` | A reported annual fact passed context, unit, duplicate, and reconciliation checks. |
| `calculated` | A formula used only validated `selected`, `calculated`, or `documented_zero` inputs. |
| `documented_zero` | Company Facts omitted the annual instant fact, but the mapped SEC filing evidence affirmatively supports zero. |
| `manual_review` | An accounting or source conflict requires owner judgment; no value flows onward. |
| `missing` | No validated input is available or a calculation denominator is zero. |
| `not_applicable` | The metric does not apply to that row, such as first-year growth. |

The source manifest also uses `candidate_not_selected` for an eligible comparative
fact retained as provenance after another agreeing presentation was selected.

## `data/processed/nike_financials.csv`

### Identity and units

| Field | Definition |
|---|---|
| `company_name` | SEC issuer name. |
| `ticker` | Verified exchange ticker. |
| `cik` | Ten-digit SEC Central Index Key, retained as text. |
| `fiscal_year` | Nike fiscal-year label based on the verified May 31 period end. |
| `period_start` | June 1 start of the annual duration. |
| `period_end` | Actual May 31 fiscal period end. |
| `monetary_unit` | `USD millions` for monetary fields. |
| `shares_unit` | Millions of diluted weighted-average shares. |
| `ratio_unit` | Decimal storage convention. Margins and growth are displayed as percentages; cash conversion retains ratio unit `x`. |

Every metric field has an adjacent `<metric>_status` field using the vocabulary
above.

### Reported fields

| Field | Definition and source convention |
|---|---|
| `revenue` | Revenue recognized from customer contracts. |
| `cost_of_revenue` | Nike's face-statement “Cost of sales,” reported as a positive expense. |
| `gross_profit` | Reported gross profit; also checked against revenue less cost of revenue. |
| `total_selling_and_administrative_expense` | Reported total selling and administrative expense; used to calculate derived operating income. |
| `income_before_income_taxes` | Reported consolidated pretax income; used in the independent operating-income bridge. |
| `interest_income_expense_nonoperating_net` | Signed non-operating amount: positive is income and negative is expense. The source face-statement expense label displays the opposite sign. |
| `other_nonoperating_income_expense` | Signed non-operating amount: positive is income and negative is expense. The source face-statement expense label displays the opposite sign. |
| `net_income` | Net income attributable to Nike. |
| `diluted_eps` | Diluted earnings per common share in USD per share; not scaled. |
| `diluted_weighted_average_shares` | Annual diluted weighted-average shares, scaled to millions. |
| `cash_and_cash_equivalents` | Balance-sheet cash and equivalents. |
| `short_term_investments` | Current available-for-sale debt securities presented as short-term investments. |
| `accounts_receivable` | Current accounts receivable, net. |
| `inventory` | Inventories; Nike's verified XBRL concept is finished goods net of reserves. |
| `current_assets` | Total current assets. |
| `current_liabilities` | Total current liabilities. |
| `total_assets` | Total assets. |
| `notes_payable_and_short_term_borrowings` | Notes payable or other short-term borrowings. FY2022-FY2025 are Company Facts values corroborated to the debt note; FY2026 is an explicitly documented zero. |
| `current_portion_long_term_debt` | Current maturities of long-term debt only; it is not a label for all current interest-bearing borrowings. |
| `noncurrent_long_term_debt` | Noncurrent long-term debt; excludes current maturities and operating lease liabilities. |
| `current_operating_lease_liabilities` | Current operating lease liabilities, presented separately from base debt. |
| `noncurrent_operating_lease_liabilities` | Noncurrent operating lease liabilities, presented separately from base debt. |
| `shareholders_equity` | Shareholders' equity attributable to Nike. |
| `operating_cash_flow` | Net cash provided by operating activities. |
| `capital_expenditures` | Cash additions to property, plant, and equipment, shown as a positive investment amount. |
| `depreciation_and_amortization` | Consistent cleaned cash-flow add-back. FY2022 uses `Depreciation`; FY2023-FY2026 use `DepreciationDepletionAndAmortization`. Overlapping observations agree, but the source tag is not treated as constant. |

### Calculated fields

| Field | Formula |
|---|---|
| `derived_operating_income` | `gross_profit - total_selling_and_administrative_expense`. This is a calculated consolidated measure because Nike does not report the subtotal; it is not segment EBIT. |
| `gross_margin` | `gross_profit / revenue` |
| `operating_margin` | `derived_operating_income / revenue` |
| `net_margin` | `net_income / revenue` |
| `operating_cash_flow_margin` | `operating_cash_flow / revenue` |
| `free_cash_flow` | `operating_cash_flow - capital_expenditures` |
| `free_cash_flow_margin` | `free_cash_flow / revenue` |
| `cash_conversion` | `operating_cash_flow / net_income`; ratio unit `x`, so `1.12` means `1.12x`, not `1.12%`. |
| `total_interest_bearing_debt` | `notes_payable_and_short_term_borrowings + current_portion_long_term_debt + noncurrent_long_term_debt`. Operating lease liabilities are excluded. |
| `total_operating_lease_liabilities` | `current_operating_lease_liabilities + noncurrent_operating_lease_liabilities`; informational and excluded from base debt. |
| `revenue_growth` | `(current revenue / prior revenue) - 1`; FY2022 is not applicable. |
| `revenue_cagr_five_observations` | `(FY2026 revenue / FY2022 revenue)^(1/4) - 1`; shown only in FY2026. |

The derived operating-income result is also checked independently as income before
taxes less signed net interest and signed other non-operating income or expense.
This bridge is a validation relationship, not the primary calculation formula.

## `data/metadata/source_manifest.csv`

| Field | Definition |
|---|---|
| `metric` | Stable metric identifier used in the cleaned dataset. |
| `fiscal_year_label` | Target Nike fiscal year. |
| `period_start`, `period_end` | Exact XBRL duration or instant dates. |
| `reported_value` | Value as returned by Company Facts before scaling or sign handling. |
| `normalized_value` | Cleaned value or calculated result. |
| `reported_unit`, `normalized_unit` | Source and presentation units. |
| `taxonomy`, `xbrl_concept` | XBRL namespace and concept. |
| `sec_form` | Source form; selected reported facts must be exact `10-K`. |
| `filing_date`, `accession_number` | Filing identity attached to the fact. |
| `source_url` | Direct SEC filing URL for the reported fact. |
| `company_facts_url` | Official SEC API endpoint used for the fact collection. |
| `retrieval_timestamp` | Stable timestamp from the cached Company Facts response. |
| `selection_status`, `selection_reason` | Outcome and plain-language deterministic rationale. |
| `value_type` | `reported` or `calculated`; no value is labeled restated or recast without evidence. |
| `presentation_type` | Originally reported, later comparative, or calculated. |
| `transformation_notes` | Unit scaling, sign handling, or formula. |
| `statement_type`, `period_type` | Expected financial statement and duration/instant classification. |
| `fact_fiscal_year`, `fact_fiscal_period` | Company Facts `fy` and `fp` metadata. |
| `frame` | SEC frame when present; retained but not used as the sole selection key. |
| `candidate_priority` | Ordered tag priority from `config/xbrl_tags.csv`. |
| `face_statement_url` | SEC-rendered statement used for reconciliation. |
| `face_statement_retrieval_timestamp`, `face_statement_sha256` | Retrieval time and content hash for the rendered statement evidence. |
| `face_statement_label`, `face_statement_value` | Visible label and displayed value. |
| `face_reconciliation_status`, `face_reconciliation_note` | Direct match, component check, unavailable presentation, or mismatch explanation. |
| `supporting_source_url` | Direct official filing-note URL used to corroborate or document a value. |
| `supporting_source_retrieval_timestamp`, `supporting_source_sha256` | Stable cache metadata for the filing-note evidence. |
| `supporting_source_label`, `supporting_source_notes` | Human-readable note identity and evidence explanation. |
| `content_sha256` | Hash of the cached Company Facts response. |

## `data/metadata/validation_summary.csv`

| Field | Definition |
|---|---|
| `check_id` | Stable validation identifier. |
| `scope` | Dataset or statement area checked. |
| `status` | `pass`, `warning`, or `fail`. |
| `details` | Human-readable outcome. |

## `config/xbrl_tags.csv`

The tag map is a reviewed input, not a generated output. It records each candidate's
metric, statement, duration/instant type, expected unit, priority, taxonomy, concept,
verification status, sign convention, acceptable face-statement labels, and notes.
Only `verified` and `verified_fallback` rows are eligible for selection.

## `config/documented_values.csv`

This reviewed input maps a narrowly scoped filing-note value to its fiscal year,
filing identity, direct SEC URL, local cache key, unit, evidence status, and notes.
It currently corroborates notes payable or short-term borrowings for FY2022-FY2025
and documents the FY2026 zero. It is not a general mechanism for manually typing
historical values: nonzero values must agree with selected Company Facts, while an
absent fact can be filled only by an affirmatively supported `documented_zero`.

## Phase 3 analytical outputs

Phase 3 reads the committed processed dataset as strings and performs new financial
calculations with Decimal-compatible logic. The long KPI table preserves the full
available Decimal result. Rounding is limited to notebook tables, chart annotations,
and narrative text.

### New KPI definitions

| Field | Formula, unit, and status behavior |
|---|---|
| `sga_as_percent_of_revenue` | `total_selling_and_administrative_expense / revenue`; decimal displayed as a percentage; FY2022-FY2026. |
| `cash_and_short_term_investments` | `cash_and_cash_equivalents + short_term_investments`; USD millions; FY2022-FY2026. |
| `current_ratio` | `current_assets / current_liabilities`; unit `x`; FY2022-FY2026. A zero denominator produces no value. |
| `net_working_capital` | `current_assets - current_liabilities`; USD millions; FY2022-FY2026. This is a broad balance-sheet measure, not operating net working capital. |
| `accounts_receivable_growth` | `(accounts_receivable_t / accounts_receivable_t_minus_1) - 1`; decimal displayed as a percentage; FY2023-FY2026. FY2022 is `not_applicable`. |
| `receivables_days_proxy` | `average accounts_receivable / revenue * 365`; days; FY2023-FY2026. FY2022 is `not_applicable` because FY2021 opening receivables are unavailable. Uses total revenue rather than disclosed credit sales, so it is not DSO. |
| `inventory_growth` | `(inventory_t / inventory_t_minus_1) - 1`; decimal displayed as a percentage; FY2023-FY2026. FY2022 is `not_applicable`. |
| `inventory_days` | `average inventory / cost_of_revenue * 365`; days; FY2023-FY2026. FY2022 is `not_applicable` because FY2021 opening inventory is unavailable. |
| `net_debt_after_cash_and_short_term_investments` | `total_interest_bearing_debt - cash_and_cash_equivalents - short_term_investments`; USD millions; FY2022-FY2026. Negative values mean net cash. Operating lease liabilities are excluded. |
| `diluted_eps_growth` | `(diluted_eps_t / diluted_eps_t_minus_1) - 1`; decimal displayed as a percentage; FY2023-FY2026. FY2022 is `not_applicable`. |
| `revenue_cumulative_change` | `revenue_FY2026 - revenue_FY2022`; USD millions; displayed only on the FY2026 endpoint row. |
| `revenue_cumulative_change_percent` | `(revenue_FY2026 / revenue_FY2022) - 1`; decimal displayed as a percentage; displayed only on the FY2026 endpoint row. |
| `peak_revenue` | Maximum of the five validated revenue observations; USD millions; displayed on the FY2026 endpoint row with the associated fiscal year in `notes`. |

The 365-day factor is a consistent analytical convention rather than a claim about
the exact number of days in each Nike fiscal reporting period. All new calculations
require inputs with `selected`, `calculated`, or `documented_zero` status. Missing or
`manual_review` inputs do not produce calculated values.

## `outputs/tables/historical_summary.csv`

This recruiter-readable table has one row per fiscal year and selected value/status
pairs. Its metadata fields are:

| Field | Definition |
|---|---|
| `company_name`, `ticker` | Company identity retained from Phase 2. |
| `fiscal_year`, `period_end` | Nike fiscal-year label and actual May 31 period end. |
| `monetary_unit` | `USD millions`. |
| `cash_conversion_unit` | `x`. |
| `day_count_convention` | `365`. |
| `net_debt_sign_convention` | Negative value means net cash. |
| `<metric>`, `<metric>_status` | Full-precision value and adjacent quality status for each selected summary KPI. |

## `outputs/tables/historical_kpis.csv`

This audit-friendly table contains one row for every defined KPI and fiscal year.

| Field | Definition |
|---|---|
| `category` | Revenue, profitability, cash generation, working capital and liquidity, capital structure, or per share. |
| `metric`, `display_name` | Stable code identifier and readable label. |
| `fiscal_year`, `period_end` | Observation period. Period-wide metrics appear only on the FY2026 endpoint row. |
| `value`, `unit`, `status` | Full-precision Decimal text, semantic unit, and quality status. |
| `value_source` | `sec_reported`, `filing_supported_documented_zero`, `phase2_calculated`, `phase3_calculated`, or a disclosed blocked/not-applicable classification. |
| `formula`, `input_metrics` | Calculation lineage or reported-value designation. |
| `applicable_fiscal_years` | Intended availability period. |
| `presentation_rounding` | Display-only rounding convention. |
| `notes` | Relevant accounting, sign, opening-balance, or interpretation limitation. |

## Phase 4 configuration and outputs

### `config/scenario_assumptions.csv`

One row represents one documented scenario-year-driver assumption. Its fields
are `scenario`, `fiscal_year`, `driver`, full-precision decimal `value`, `unit`,
`historical_anchor`, `rationale`, `source_id`, `source_type`, `owner_status`, and
`notes`. Final generation requires exactly base, bull, and bear; exactly
FY2027-FY2031; all seven required drivers; no duplicates; and
`owner_status=approved`.

### `config/forecast_sources.csv`

The normalized source register stores `source_id`, title, publisher, source type,
publication or filing date, information cutoff, URL or accession reference, the
decision supported, and notes. It separates company evidence from analyst judgment.

### Phase 4 metric definitions

| Metric | Formula and unit |
|---|---|
| `revenue_growth` | Documented annual scenario driver; decimal. |
| `revenue` | Prior-year revenue multiplied by one plus growth; USD millions. |
| `gross_margin` | Documented annual scenario driver; decimal. FY2026 remains reported at 42.9%. |
| `gross_profit` | Revenue multiplied by gross margin; USD millions. |
| `sga_percent_revenue` | Documented annual scenario driver; decimal. |
| `total_selling_and_administrative_expense` | Revenue multiplied by SG&A/revenue; USD millions. |
| `derived_operating_income` | Gross profit less total SG&A; USD millions. Project-derived consolidated subtotal, not Nike-reported EBIT or segment EBIT. |
| `operating_margin` | Derived operating income divided by revenue; decimal. |
| `normalized_tax_rate` | Documented 21.0% operating tax assumption; decimal. |
| `normalized_operating_tax_expense` | Positive derived operating income multiplied by tax rate; zero for an operating loss absent an NOL schedule. |
| `nopat` | Derived operating income less normalized operating tax expense; USD millions. |
| `da_percent_revenue` | Documented D&A/revenue driver; decimal. |
| `depreciation_and_amortization` | Revenue multiplied by D&A/revenue; USD millions. |
| `capex_percent_revenue` | Documented capital-expenditures/revenue driver; decimal. |
| `capital_expenditures` | Revenue multiplied by capex/revenue; positive investment amount in USD millions. |
| `operating_nwc_percent_revenue` | Documented aggregate operating-NWC driver; decimal. |
| `operating_nwc_proxy` | Revenue multiplied by operating-NWC/revenue; USD millions. Historical formula excludes cash, short-term investments, short-term financing, current debt, and current lease liabilities. |
| `change_in_operating_nwc` | Closing operating NWC less prior-year closing balance; USD millions. Positive is a use of cash. |
| `fcff` | NOPAT plus D&A less capex less change in operating NWC; USD millions. |
| `fcff_margin` | FCFF divided by revenue; decimal. |

`outputs/tables/scenario_forecast_long.csv` preserves actual and forecast
classification, status, value source, formula lineage, source IDs, units, and full
Decimal text. `scenario_forecast_summary.csv` provides an FY2026 actual anchor and
FY2027-FY2031 columns, rounded to whole USD millions and one decimal percentage
point for recruiter-facing presentation; it is not the authoritative calculation
source. Metric-specific notes explain forecast conventions. `scenario_assumptions_resolved.csv` joins each assumption to
source metadata. `forecast_validation_summary.csv` provides human-readable checks.
