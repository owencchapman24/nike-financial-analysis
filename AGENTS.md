# Repository Working Agreement

These instructions apply to the entire repository.

## Project boundaries

- Treat this as an independent analyst portfolio project, not investment advice.
- Prefer straightforward, explainable Python and Excel over unnecessary complexity.
- Do not write final business conclusions or approve forecast assumptions on behalf
  of the project owner.
- Do not begin valuation work until the historical dataset is reconciled.

## Data and source rules

- Use SEC EDGAR filings and SEC XBRL APIs as the primary accounting sources.
- Verify issuer identity, CIK, filing form, filing date, and fiscal period.
- Never select the first matching XBRL fact without applying documented rules.
- Preserve units, actual period-end dates, accession numbers, tags, and source URLs.
- Flag uncertain historical values for manual review; never silently estimate them.
- Present financial statement values in USD millions unless explicitly documented.
- Store capital expenditure as a positive investment amount in processed data.
- Define free cash flow as operating cash flow minus capital expenditure.

## Privacy and repository safety

- Never commit `.env`, personal contact information, credentials, access tokens,
  machine-specific paths, raw caches, or temporary files.
- Read `SEC_USER_AGENT` from the local environment and never print its value.
- Inspect `git status` before each phase and preserve unrelated user work.
- Do not commit, push, merge, rewrite history, or create releases without explicit
  approval.

## Engineering expectations

- Keep reusable logic under `src/nike_financial_analysis/`.
- Keep notebooks restartable and free of hidden state.
- Give nontrivial functions useful names, type hints, short docstrings, deterministic
  behavior, and friendly errors.
- Add tests for selection, calculation, validation, and valuation logic.
- Update the decision log when a material accounting, data, or valuation judgment is
  made.
