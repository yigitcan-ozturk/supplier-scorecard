# supplier-scorecard

A transparent Python CLI and orchestration layer for turning quotation, payment-term, vendor-risk and technical-compliance signals into an explainable, policy-aware procurement recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## What v0.9 adds

v0.9 adds **technical compliance as a fourth scoring component**.

The scorecard can now combine:

- quotation competitiveness
- commercial/payment risk
- vendor risk
- technical compliance

Technical compliance is a normalized `0–100` score where higher is better. It can represent drawing/specification compliance, material/process fit, tolerances, testing/documentation or another technical evaluation rubric defined by the buying organization.

### Backward compatibility

Technical compliance is optional. Existing v0.8 inputs that contain only quotation, commercial and vendor-risk signals keep their previous scores.

When `technical_compliance` is omitted, the profile's non-technical weights are automatically re-normalized to preserve the old three-component weighting ratio. When it is supplied, the full four-component profile is used.

The JSON output records this explicitly as:

- `scoring_mode: "legacy-3-component"`
- `scoring_mode: "4-component"`

## Four-component model

Built-in profiles now define a technical weight as well:

| Profile | Quotation | Commercial | Vendor risk | Technical | Min. auto score |
| --- | ---: | ---: | ---: | ---: | ---: |
| `general-procurement` | 40% | 16% | 24% | 20% | 65 |
| `office-supplies` | 58.5% | 18% | 13.5% | 10% | 65 |
| `critical-machining` | 21% | 10.5% | 38.5% | 30% | 80 |
| `single-source` | 24% | 16% | 40% | 20% | 80 |
| `high-value-capex` | 34% | 25.5% | 25.5% | 15% | 80 |

If technical compliance is not supplied, each profile falls back to its previous v0.8 three-component ratio. For example, `critical-machining` becomes 30% quotation / 15% commercial / 55% vendor risk, exactly as before.

## Manual scoring

Four-component scoring:

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
  --vendor-risk 35 \
  --category-profile critical-machining
```

## End-to-end technical pipeline

Use the bundled sample:

```bash
python pipeline.py samples/procurement-technical-input.json
```

A supplier profile can now contain:

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

Technical scores are supplier-specific. A portfolio may contain technical scores for every supplier, none of them, or a mixed set. The result states which scoring mode was used for each supplier.

Example from the bundled technical sample:

```text
Supplier A  technical=94  score=91.33
Supplier B  technical=62  score=82.20

Recommended supplier: Supplier A
```

The explanation layer can identify technical compliance as the reason for the result, for example:

```text
Supplier A ranks first by 9.13 points over Supplier B,
mainly due to stronger technical compliance (+9.60 weighted points),
despite higher commercial/payment risk (-2.10 weighted points).
```

## Connected JSON mode

Technical compliance can also be added while consuming the three upstream JSON contracts:

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json \
  --technical-compliance 92 \
  --category-profile critical-machining
```

## CSV mode

The original CSV columns remain required:

```text
supplier,quotation_score,commercial_risk,vendor_risk
```

An optional fifth column enables technical scoring:

```text
supplier,quotation_score,commercial_risk,vendor_risk,technical_compliance
Supplier A,91,20,18,95
Supplier B,94,10,25,68
```

Rows with a blank technical value use legacy three-component scoring.

## Custom JSON profiles

v0.9 accepts both profile formats.

### Four-component profile

```json
{
  "name": "technical-ceramics",
  "description": "Technical ceramic sourcing profile.",
  "weights": {
    "quotation": 0.1625,
    "commercial": 0.0975,
    "vendor_risk": 0.39,
    "technical": 0.35
  },
  "policy": {
    "commercial_review_threshold": 65,
    "vendor_review_threshold": 50,
    "compliance_review_incidents": 1,
    "compliance_block_incidents": 2,
    "minimum_auto_score": 82
  }
}
```

### Legacy three-component profile

Existing v0.8 files with only:

```json
"weights": {
  "quotation": 0.35,
  "commercial": 0.20,
  "vendor_risk": 0.45
}
```

remain valid. They are interpreted as `technical: 0`.

## Bundled custom profile pack

| File | Quotation | Commercial | Vendor risk | Technical | Typical use |
| --- | ---: | ---: | ---: | ---: | --- |
| `marble-sourcing.json` | 26.25% | 15% | 33.75% | 25% | bespoke marble / stone sourcing |
| `technical-ceramics.json` | 16.25% | 9.75% | 39% | 35% | technical ceramics |
| `gears.json` | 21% | 10.5% | 38.5% | 30% | gears / precision drivetrain |
| `machinery-capex.json` | 28% | 24% | 28% | 20% | machinery / capital equipment |

Use any profile without changing Python code:

```bash
python main.py "Supplier A" \
  --quotation-score 86 \
  --commercial-risk 20 \
  --vendor-risk 30 \
  --technical-compliance 93 \
  --profile-file samples/profiles/technical-ceramics.json
```

Or from a pipeline input:

```json
{
  "profile_file": "profiles/marble-sourcing.json",
  "target_currency": "EUR",
  "quotes": [],
  "supplier_profiles": []
}
```

Profile paths inside a pipeline input are resolved relative to the input file.

## Example technical rubric

`supplier-scorecard` deliberately accepts a normalized technical score instead of imposing one industry-specific checklist. A team can derive that score from a transparent rubric such as:

| Technical area | Example share |
| --- | ---: |
| Mandatory specification compliance | 40% |
| Material / manufacturing-process compliance | 20% |
| Dimensions, tolerances and interface requirements | 25% |
| Testing, certificates and documentation | 15% |

The resulting weighted technical evaluation can then be passed as `technical_compliance`.

## Procurement decision flow

```text
quotation JSONs ─> currency-normalizer ─> rfqdiff ───────────────┐
                                                                 │
payment terms ───────────────> payment-terms-parser ─────────────┤
                                                                 ├─> supplier-scorecard
vendor metrics ──────────────> vendor-risk-engine ───────────────┤
                                                                 │
technical evaluation ───────────────> 0–100 compliance score ────┘
                                                                 │
                                                                 ▼
                                      category weights + policy gates
                                                                 │
                                                                 ▼
                                      ranked / explainable decision
```

Payment exposure from `payment-terms-parser` is passed automatically into `vendor-risk-engine`, so it is not entered twice.

## Policy gates

The general policy still evaluates:

| Rule | Default |
| --- | ---: |
| Commercial risk review | 80 / 100 |
| Vendor risk review | 75 / 100 |
| Compliance review | 1 incident |
| Compliance block | 3 incidents |
| Minimum automatic score | 65 / 100 |

The technical score currently affects the composite score and explainability. Category/company profiles can determine how much weight it receives. A dedicated technical hard-gate can be added later without changing the technical scoring contract.

## Explainability

Every supplier result includes deterministic:

- strengths
- warnings
- primary score driver
- technical-compliance strength/warning when present
- policy triggers
- final-decision reason

Portfolio output compares the score leader with the runner-up across all four components.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the suite on Python 3.11, 3.12 and 3.13.

## Procurement tooling suite

| Tool | Role |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation currencies |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score quotations |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into commercial-risk signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score delivery, quality, commercial, compliance and dependency risk |
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Combine commercial, risk and technical signals into a policy-aware supplier decision |

## Roadmap

- Dedicated technical-compliance checklist/parser
- Technical hard gates for mandatory requirements
- Approval workflow / sign-off metadata
- Historical supplier trend scoring
- Export ranked decision packs to CSV/JSON
- Profile versioning and governance metadata

## Status

Current version: **v0.9**. The project supports four-component supplier scoring, backward-compatible three-component scoring, built-in and custom category profiles, policy gates, explainability and end-to-end portfolio orchestration without third-party runtime dependencies.

## License

MIT License. See [`LICENSE`](LICENSE).
