# supplier-scorecard v1.0

Released: 2026-08-19

## Summary

v1.0 marks the completed stable portfolio release of `supplier-scorecard`. It does not introduce a new scoring feature beyond v0.9; it freezes and documents the decision model as a coherent procurement decision engine.

The project now has a clear endpoint: supplier quotation, payment exposure, vendor risk and optional technical compliance can be combined through category-aware weights, deterministic policy gates and explainable portfolio ranking.

## Stable capabilities

- Single-supplier and multi-supplier portfolio scoring.
- Four-component scoring: quotation, commercial/payment, vendor risk and technical compliance.
- Backward-compatible three-component scoring when technical data is absent.
- Built-in category profiles and external JSON profile files.
- Policy gates that can move suppliers to `REVIEW` or `BLOCKED` independently of score.
- Automatic recommendation only from policy-eligible suppliers.
- Deterministic explanation of score drivers, warnings and winner-vs-runner-up trade-offs.
- One-command orchestration with `currency-normalizer`, `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine`.
- Machine-readable JSON outputs and optional audit artifact retention.
- Python standard-library-only runtime.

## Version contract

The v1.0 release aligns the main scorecard, portfolio result and orchestration layer on version `1.0`.

Existing v0.9 input shapes remain valid. Existing three-component inputs continue to use normalized legacy weights when technical compliance is not supplied.

## Verification

Run locally with:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions is configured for Python 3.11, 3.12 and 3.13.

## Scope after v1.0

The portfolio project is considered complete. Further work should be limited to maintenance, bug fixes or intentionally scoped follow-on work rather than continuing an indefinite feature sequence.

---

# Phase 2 / v1.1 candidate notes

Status: development candidate; **not yet a stable release**.

Phase 2 is an intentionally scoped operational follow-on around the frozen v1.0 decision model. The scoring core remains authoritative: weights, score bands, category semantics, policy thresholds and supplier-ranking behavior are not changed by the provenance layer.

## Candidate additions

- Payment-term safety stops automatic supplier scoring when `payment-terms-parser` reports unknown, invalid or review-required commercial exposure.
- A versioned decision-record envelope can wrap the unchanged v1.0 single-supplier or portfolio result.
- Resolved profile and policy snapshots receive deterministic canonical SHA-256 hashes.
- Retained pipeline input/output artifacts receive exact byte-level SHA-256 hashes.
- Temporary/non-retained artifacts remain explicit rather than receiving fabricated provenance.
- The complete operational record receives a deterministic integrity hash.
- Human review state is recorded outside the scoring core as `NOT_REQUIRED`, `PENDING`, `APPROVED_EXCEPTION` or `REJECTED`.
- The installed `supplier-scorecard-pipeline` CLI gains opt-in `--decision-record` output.

## Pilot proof

The sanitized fixture `samples/phase2/three-supplier-engineering-pilot.json` exercises the real multi-repository toolchain under the `critical-machining` profile. It intentionally creates a portfolio in which:

- `Pilot Supplier A` is the numerical score leader but is held at `REVIEW` by the compliance-incident policy gate;
- `Pilot Supplier B` is the highest-scoring policy-eligible supplier and is automatically recommended;
- `Pilot Supplier C` remains below the profile's minimum automatic score and therefore requires review.

The `.github/workflows/phase2-pilot.yml` workflow checks out the real `currency-normalizer`, `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine` repositories, runs the installed pipeline, writes a retained decision record, verifies artifact hashes and asserts the expected policy-aware recommendation.

The first integrated Phase 2 pilot and the normal Python 3.11/3.12/3.13 test matrix both passed on the integrated development branch before merge review.

## Release gate

Phase 2 should become a stable v1.1 release only after the integrated pull request is merged, the final `main` CI remains green, documentation is reviewed and a deliberate v1.1 release/tag is created. Until then, the latest stable release remains **v1.0.0**.
