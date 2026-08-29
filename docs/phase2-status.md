# Phase 2 status

Status: **implemented on `main`; release preparation remains separate**.

Phase 2 extends the frozen v1.0 scoring core with operational safety, provenance and auditability without changing the deterministic scoring semantics.

## Completed

- [x] Payment-term review safety prevents automatic scoring when commercial exposure is unknown, invalid or explicitly review-required.
- [x] Versioned decision-record contract.
- [x] SHA-256 provenance for retained pipeline artifacts.
- [x] Upstream version capture for currency-normalizer, rfqdiff, payment-terms-parser and vendor-risk-engine.
- [x] Deterministic decision payload integrity.
- [x] Explicit operational human-review state.
- [x] Installed pipeline CLI `--decision-record` output.
- [x] Unit/regression coverage for integrity and provenance.
- [x] Sanitized three-supplier `critical-machining` pilot.
- [x] Multi-repository Phase 2 Pilot GitHub Actions gate.
- [x] README and candidate release-note documentation.
- [x] Persistence/API boundary documented in `docs/operational-boundaries.md`.

## Verified pilot behavior

The canonical pilot deliberately proves that ranking and policy are separate:

- `Pilot Supplier A` is the numerical leader but is held at `REVIEW` by a compliance policy gate.
- `Pilot Supplier B` is the highest-scoring policy-eligible supplier and is automatically recommended.
- `Pilot Supplier C` is held at `REVIEW` by the minimum automatic-score gate.

The final audit record retains and hashes 11 pipeline artifacts, including three currency-normalizer outputs and all supplier payment/vendor-risk outputs.

## Remaining release gate

The latest stable public release remains **v1.0.0**. A stable Phase 2 release must be performed as a separate explicit release change that:

1. bumps the package version to the selected stable semver;
2. keeps the deterministic scoring/result contract at v1.0 unless intentionally changed;
3. passes `main` CI;
4. creates the corresponding stable GitHub tag/release through the guarded release workflow.

The v1.0 weights, score bands, category semantics and policy gates remain unchanged.
