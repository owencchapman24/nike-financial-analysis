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
| `ratio_unit` | Decimal; multiply by 100 to display a percentage. |

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
| `cash_conversion` | `operating_cash_flow / net_income` |
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
