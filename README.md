# supplier-scorecard

A transparent Python procurement decision engine that combines quotation, payment-term, vendor-risk and technical-compliance signals into an explainable, policy-aware supplier recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

**Status: v1.0 stable.** The scoring and orchestration scope is intentionally complete for this portfolio project. v1.0 freezes the public decision model established through v0.9 and focuses on a clear, auditable interface rather than adding more features.

> `supplier-scorecard` is the procurement decision layer in an explainable engineering toolchain. [`bidlint`](https://github.com/yigitcan-ozturk/bidlint) supplies the technical-compliance signal; the commercial and risk tools remain independently inspectable.

## What it does

`supplier-scorecard` can:

- score one supplier or rank a full RFQ portfolio
- combine quotation competitiveness, commercial/payment risk, vendor risk and optional technical compliance
- normalize weights when technical data is unavailable, preserving legacy three-component scores
- apply built-in category profiles or external JSON procurement profiles
- enforce deterministic policy gates (`PASS`, `REVIEW`, `BLOCKED`)
- separate numeric score ranking from automatic approval eligibility
- explain supplier strengths, warnings, score drivers and winner-vs-runner-up trade-offs
- orchestrate `currency-normalizer`, `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine` from one input file
- consume versioned technical-compliance hand-off data from `bidlint`
- emit machine-readable JSON and retain intermediate audit artifacts when requested

No third-party runtime dependencies are required.

## Decision model

The score uses four normalized components:

| Component | Direction |
| --- | --- |
| Quotation competitiveness | higher is better |
| Commercial/payment | `100 - commercial risk` |
| Vendor risk | `100 - vendor risk` |
| Technical compliance | higher is better |

Technical compliance is optional. If it is omitted, non-technical profile weights are automatically re-normalized so existing three-component inputs retain their previous scoring ratio. Results expose either `legacy-3-component` or `4-component` in `scoring_mode`.

Base score recommendations are:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | `PREFERRED` |
| 65–79.99 | `ACCEPTABLE` |
| 50–64.99 | `REVIEW` |
| 0–49.99 | `HIGH RISK` |

Policy gates are evaluated after the numeric score and may move a supplier to `REVIEW` or `BLOCKED` or prevent automatic recommendation.

## Built-in profiles

| Profile | Quotation | Commercial | Vendor risk | Technical | Min. auto score |
| --- | ---: | ---: | ---: | ---: | ---: |
| `general-procurement` | 40% | 16% | 24% | 20% | 65 |
| `office-supplies` | 58.5% | 18% | 13.5% | 10% | 65 |
| `critical-machining` | 21% | 10.5% | 38.5% | 30% | 80 |
| `single-source` | 24% | 16% | 40% | 20% | 80 |
| `high-value-capex` | 34% | 25.5% | 25.5% | 15% | 80 |

List them with:

```bash
python main.py --list-profiles
```

## Quick start

Four-component manual scoring:

```bash
python main.py "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35 \
  --technical-compliance 94 \
  --category-profile critical-machining
```

Legacy three-component scoring remains valid:

```bash
python main.py "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35
```

Connected upstream JSON mode:

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json \
  --technical-compliance 92 \
  --category-profile critical-machining
```

CSV mode supports the original four required columns plus optional technical compliance:

```text
supplier,quotation_score,commercial_risk,vendor_risk,technical_compliance
Supplier A,91,20,18,95
Supplier B,94,10,25,68
```

```bash
python main.py --csv samples/suppliers.csv
```

## End-to-end portfolio pipeline

The complete toolchain is intentionally split by responsibility:

```text
currency-normalizer ──> rfqdiff ────────────────┐
                                                 │
payment-terms-parser ───────────────────────────┼──> supplier-scorecard
                                                 │
vendor-risk-engine ─────────────────────────────┤
                                                 │
bidlint ──> technical compliance ───────────────┘
```

Clone the repositories side-by-side when running the local portfolio pipeline:

```text
procurement-tools/
├── currency-normalizer/
├── rfqdiff/
├── payment-terms-parser/
├── vendor-risk-engine/
├── bidlint/
└── supplier-scorecard/
```

Run the technical sample:

```bash
python pipeline.py samples/procurement-technical-input.json
```

A portfolio supplier profile can contain:

```json
{
  "supplier": "Supplier A",
  "payment_terms": "20% advance, 80% after delivery",
  "technical_compliance": 94,
  "vendor_risk": {
    "on_time_delivery": 94,
    "defect_rate": 1.0,
    "compliance_incidents": 0,
    "dependency_share": 25
  }
}
```

The pipeline normalizes quotation currencies, runs RFQ comparison once, evaluates payment and vendor risk for each supplier, applies technical compliance and the selected profile, enforces policy gates, ranks suppliers and returns the highest-scoring auto-eligible recommendation.

For technical bid evaluation, `bidlint` can emit a versioned supplier-scorecard hand-off. A numeric technical-compliance value is only supplied when the technical findings are safe to reduce to that signal; unresolved engineering review remains explicit rather than silently affecting ranking.

Keep intermediate artifacts for audit:

```bash
python pipeline.py samples/procurement-technical-input.json \
  --work-dir pipeline-output \
  --output decision.json \
  --json
```

## Custom procurement profiles

External JSON profiles let teams change scoring and policy without editing Python code. The bundled examples are:

| File | Quotation | Commercial | Vendor risk | Technical | Typical use |
| --- | ---: | ---: | ---: | ---: | --- |
| `marble-sourcing.json` | 26.25% | 15% | 33.75% | 25% | bespoke marble / stone sourcing |
| `technical-ceramics.json` | 16.25% | 9.75% | 39% | 35% | technical ceramics |
| `gears.json` | 21% | 10.5% | 38.5% | 30% | gears / precision drivetrain |
| `machinery-capex.json` | 28% | 24% | 28% | 20% | machinery / capital equipment |

Example:

```bash
python main.py "Supplier A" \
  --quotation-score 86 \
  --commercial-risk 20 \
  --vendor-risk 30 \
  --technical-compliance 93 \
  --profile-file samples/profiles/technical-ceramics.json
```

A pipeline input can reference a profile file relative to itself:

```json
{
  "profile_file": "profiles/marble-sourcing.json",
  "target_currency": "EUR",
  "quotes": [],
  "supplier_profiles": []
}
```

Custom profiles are validated: weights must be valid, unknown fields are rejected and policy values are explicit for auditability.

## Policy-aware selection

The default policy checks commercial risk, vendor risk, compliance incidents and the minimum score required for automatic approval. Category and custom profiles can tighten or relax these rules.

A supplier may therefore be the numeric score leader but not the automatic recommendation:

```text
Top-scoring supplier : Supplier B
Recommended supplier : Supplier A
Decision status      : AUTO-RECOMMENDED
```

If no supplier is auto-eligible, automatic recommendation is withheld rather than silently selecting a policy-failing supplier.

## Explainability

Every supplier result includes deterministic:

- strengths and warnings
- primary weighted score driver
- policy triggers and final-decision reason
- technical-compliance strength/warning when present

Portfolio output also explains why the score leader beat the runner-up and why policy may select a different supplier.

## Engineering procurement toolchain

| Tool | Role |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation currencies |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score quotations |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into commercial-risk signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score delivery, quality, commercial, compliance and dependency risk |
| [`bidlint`](https://github.com/yigitcan-ozturk/bidlint) | Produce evidence-backed technical-compliance findings and hand-off data |
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Combine commercial, risk and technical signals into a policy-aware supplier decision |

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.11, 3.12 and 3.13.

## Release documentation

See [`CHANGELOG.md`](CHANGELOG.md) for the project history and [`RELEASE_NOTES.md`](RELEASE_NOTES.md) for the v1.0 release summary.

## Project scope

v1.0 is the completed portfolio release. Future changes, if any, should be maintenance, bug fixes or deliberately scoped extensions rather than an open-ended feature roadmap.

## License

MIT License. See [`LICENSE`](LICENSE).
