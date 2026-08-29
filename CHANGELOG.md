# Changelog

All notable project milestones are summarized here.

## Unreleased

- No unreleased changes.

## [1.1.0] - 2026-08-29

### Operational provenance and safety

- Added opt-in tamper-evident decision records around the unchanged v1.0 scoring result.
- Added canonical SHA-256 profile/policy snapshots and retained artifact hashes.
- Added upstream version provenance for currency normalization, quotation comparison, payment parsing and vendor-risk outputs.
- Added deterministic decision-payload integrity verification.
- Added explicit operational human-review states without modifying deterministic score/policy outputs.
- Added `--decision-record` to the installed pipeline CLI.
- Stopped automatic scoring when payment terms require human review or commercial exposure is not safely numeric.
- Added a sanitized three-supplier engineering procurement pilot and multi-repository CI gate.
- Documented persistence/API/application boundaries outside the deterministic scoring core.

### Version contract

- Advanced the package/release version to `1.1.0`.
- Kept the deterministic scoring/result contract at version `1.0`.
- Kept the decision-record schema at version `1.0`.

### Packaging and distribution

- Retained `pyproject.toml` metadata for the installable Python distribution.
- Retained the stable `supplier_scorecard` Python import namespace.
- Retained `supplier-scorecard` and `supplier-scorecard-pipeline` console entry points.
- CI continues to build and install wheels across Python 3.11, 3.12 and 3.13 and smoke-test installed commands.
- `main.py` and `pipeline.py` source-checkout workflows remain backward compatible.

## [1.0] - 2026-08-19

### Stable release

- Finalized the public supplier scorecard and portfolio orchestration contracts.
- Standardized engine, portfolio and orchestration version identifiers at `1.0`.
- Confirmed four-component scoring with backward-compatible three-component behavior.
- Retained built-in and external JSON procurement profiles, policy gates and explainability.
- Added stable release documentation and removed the open-ended feature roadmap.

## [0.9] - 2026-08-19

- Added technical compliance as an optional fourth scoring component.
- Added technical weighting to built-in and bundled custom profiles.
- Preserved previous scores when technical data is omitted through weight re-normalization.
- Added technical compliance to manual, CSV, connected-JSON and portfolio pipeline modes.

## [0.8] - 2026-08-19

- Added user-defined procurement profile JSON files.
- Added profile path provenance and validation.
- Added bundled profiles for marble sourcing, technical ceramics, gears and machinery CAPEX.

## [0.7] - 2026-08-19

- Added category-specific built-in profiles with category-specific weights and policy thresholds.

## [0.6] - 2026-08-19

- Added deterministic procurement policy gates with `PASS`, `REVIEW` and `BLOCKED` states.
- Separated numeric score leadership from automatic recommendation eligibility.

## [0.5] - 2026-08-19

- Added deterministic supplier and portfolio explainability.
- Added winner-vs-runner-up weighted advantages and trade-offs.

## [0.4] - 2026-08-19

- Added portfolio orchestration across all suppliers in an RFQ.
- Added automatic ranking and recommended-supplier selection.

## [0.3] - 2026-08-19

- Added one-command end-to-end procurement orchestration across the sibling tools.

## [0.2] - 2026-08-19

- Added direct ingestion of `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine` JSON outputs.

## [0.1] - 2026-08-19

- Initial transparent supplier scorecard with quotation, commercial and vendor-risk signals.
- Added manual and CSV scoring, JSON output, tests and GitHub Actions.
