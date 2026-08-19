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
