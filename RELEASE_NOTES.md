# supplier-scorecard v1.1.0

## Summary

v1.1.0 adds an operational audit and provenance layer around the frozen v1.0 supplier decision model. The package can now produce a tamper-evident decision record that preserves the deterministic score/policy result while recording the exact profile, policy, upstream tool versions and retained artifacts that produced it.

This is intentionally **not a scoring-model change**. The deterministic supplier-scorecard result contract remains version `1.0`; v1.1.0 is the package/release version for the new operational capabilities.

## New in v1.1.0

- Versioned `supplier-scorecard.decision-record` envelope.
- Canonical SHA-256 hashes for resolved profile and policy snapshots.
- Exact byte-level SHA-256 provenance for retained pipeline artifacts.
- Upstream version provenance for `currency-normalizer`, `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine` outputs.
- Deterministic integrity hash over the complete operational decision payload.
- Explicit operational review states: `NOT_REQUIRED`, `PENDING`, `APPROVED_EXCEPTION` and `REJECTED`.
- Opt-in `--decision-record` output on the installed `supplier-scorecard-pipeline` CLI.
- Payment-term safety that stops automatic supplier scoring when commercial exposure is unknown, invalid or explicitly review-required.
- Sanitized three-supplier engineering procurement pilot with multi-repository GitHub Actions verification.
- Documented persistence/API/application boundaries that keep database/framework concerns outside the deterministic scoring core.

## Pilot proof

The canonical `critical-machining` pilot intentionally separates numeric ranking from policy eligibility:

- `Pilot Supplier A` ranks first numerically but is held at `REVIEW` by a compliance-incident policy gate.
- `Pilot Supplier B` is the highest-scoring policy-eligible supplier and is automatically recommended.
- `Pilot Supplier C` is held at `REVIEW` by the profile's minimum automatic-score gate.

The final decision record retains and hashes 11 artifacts, including three currency-normalizer outputs, the rfqdiff result, and each supplier's payment and vendor-risk outputs.

## Version contract

| Contract | v1.1.0 value |
| --- | --- |
| Package / GitHub release | `1.1.0` |
| Deterministic scoring/result contract | `1.0` |
| Pipeline/portfolio result semantics | `1.0` |
| Decision-record schema | `1.0` |
| Upstream tool versions | recorded per artifact |

Existing v1.0 scoring inputs, weights, recommendation bands, category profiles and policy gates remain unchanged.

## Compatibility

- Existing manual, CSV, connected-JSON and portfolio scoring workflows remain valid.
- Existing source-checkout workflows through `main.py` and `pipeline.py` remain supported.
- Decision-record output is opt-in; existing callers do not need to consume the new envelope.
- The runtime remains Python standard-library-only for `supplier-scorecard` itself.

## Verification

The Phase 2 implementation passed:

- the Python 3.11 / 3.12 / 3.13 source and installed-wheel test matrix;
- installed CLI smoke tests;
- deterministic decision-record integrity tests;
- retained-artifact mutation/provenance tests;
- the multi-repository three-supplier end-to-end pilot;
- post-merge `main` CI after both runtime and operational-boundary merges.

Stable release creation remains guarded by the repository release workflow, which requires the release source to be `main` and derives the tag directly from the package version in `pyproject.toml`.

## Scope

`supplier-scorecard` remains decision-support infrastructure, not an automatic contractual acceptance system. Human exception approval is governance state outside the deterministic score, and authentication, authorization, digital signatures, persistence and application APIs remain hosting-layer responsibilities.

---

# v1.0 history

v1.0 established the stable deterministic supplier decision engine: four-component scoring with backward-compatible three-component behavior, category profiles, explicit policy gates, explainability, portfolio ranking and orchestration across quotation, payment and vendor-risk inputs.
