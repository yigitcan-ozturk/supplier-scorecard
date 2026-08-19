# supplier-scorecard

A transparent Python CLI and orchestration layer for turning quotation, payment-term and vendor-risk signals into an explainable, policy-aware procurement recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## What v0.6 adds

v0.6 adds **procurement policy gates** on top of the score and explainability layers.

A supplier can now have a strong numeric score but still be automatically moved to `REVIEW` or `BLOCKED` when a deterministic procurement rule is triggered.

The result keeps separate fields for:

- numeric composite score
- score-based recommendation
- policy status: `PASS`, `REVIEW`, or `BLOCKED`
- final decision after policy gates
- exact rule(s) that triggered
- automatic-selection eligibility

The score is never hidden or overwritten. Commercial scoring and governance remain separate and auditable.

## Default policy gates

| Rule | Default action |
| --- | --- |
| Commercial/payment risk `>= 80` | `REVIEW` |
| Vendor-risk score `>= 75` | `REVIEW` |
| Compliance incidents `>= 1` | `REVIEW` |
| Compliance incidents `>= 3` | `BLOCKED` |

A supplier is **auto-eligible** only when all policy gates return `PASS` and the score-based recommendation is `PREFERRED` or `ACCEPTABLE`.

Suppliers already scoring `REVIEW` or `HIGH RISK` are therefore not automatically recommended even when no additional policy rule fires.

## Portfolio selection behavior

The portfolio still shows the pure score ranking first.

Policy gates are then applied as a separate selection layer:

```text
score ranking
     │
     ▼
policy gates
     │
     ├── PASS    ──> can be auto-selected
     ├── REVIEW  ──> human review required
     └── BLOCKED ──> excluded from automatic recommendation
```

If the top-scoring supplier is under `REVIEW` or `BLOCKED`, the pipeline selects the highest-scoring **auto-eligible** supplier instead.

If no supplier is auto-eligible, `recommended_supplier` is `null` and the decision status becomes:

```text
NO AUTO-APPROVED SUPPLIER
```

This prevents a risky supplier from being silently recommended only because its weighted score is high.

## One-command portfolio pipeline

Clone the five repositories side-by-side:

```text
procurement-tools/
├── currency-normalizer/
├── rfqdiff/
├── payment-terms-parser/
├── vendor-risk-engine/
└── supplier-scorecard/
```

Then run:

```bash
python pipeline.py samples/procurement-portfolio-input.json
```

The orchestration flow is:

```text
quotation JSONs -> currency-normalizer -> rfqdiff ------------------┐
                                                                   │
payment terms -> payment-terms-parser ------------------------------┼-> supplier-scorecard
                                                                   │
vendor metrics -> vendor-risk-engine -------------------------------┘
                                                                   │
                                                                   ▼
                                                            policy gates
                                                                   │
                                                                   ▼
                                                      final supplier decision
```

`payment-terms-parser` supplies pre-delivery exposure directly to `vendor-risk-engine`, so the same commercial exposure is not entered twice.

## Example policy-aware output

```text
PROCUREMENT PORTFOLIO PIPELINE v0.4
--------------------------------------------------------------------------------------------------------------------
  # Supplier                        Score   Score rec.     Policy        Final
--------------------------------------------------------------------------------------------------------------------
  1 Supplier B                     97.35    PREFERRED     REVIEW       REVIEW
  2 Supplier A                     93.62    PREFERRED       PASS    PREFERRED
--------------------------------------------------------------------------------------------------------------------
Top-scoring supplier : Supplier B
Recommended supplier : Supplier A
Decision status      : AUTO-RECOMMENDED
```

The numeric ranking is preserved, but the automatic recommendation respects policy.

## Custom policy

Add an optional top-level `policy` object to a single-supplier or portfolio input:

```json
{
  "target_currency": "EUR",
  "policy": {
    "commercial_review_threshold": 85,
    "vendor_review_threshold": 80,
    "compliance_review_incidents": 2,
    "compliance_block_incidents": 4
  },
  "quotes": [],
  "supplier_profiles": []
}
```

Supported fields:

| Field | Default |
| --- | ---: |
| `commercial_review_threshold` | 80 |
| `vendor_review_threshold` | 75 |
| `compliance_review_incidents` | 1 |
| `compliance_block_incidents` | 3 |

Commercial and vendor-risk thresholds must be between 0 and 100. Compliance thresholds must be non-negative integers, and the review threshold cannot exceed the block threshold. Unknown policy fields are rejected.

## Policy-gate sample

The repository includes a sample where the highest-scoring supplier is put under policy review and the next compliant supplier is selected:

```bash
python pipeline.py samples/procurement-policy-input.json
```

## Explainable decisions

The v0.5 explainability layer remains intact.

Each supplier result includes:

- strengths
- warnings
- primary weighted score driver
- score-based recommendation
- policy trigger reasons
- final decision

Portfolio output keeps the score-based winner-vs-runner-up explanation separately from the policy-selection explanation.

That means downstream systems can answer both:

> Why did this supplier score highest?

and:

> Why was a different supplier actually recommended?

## JSON output

```bash
python pipeline.py samples/procurement-policy-input.json \
  --json \
  --output final-decision.json
```

Important portfolio fields include:

```json
{
  "top_scoring_supplier": "Supplier B",
  "recommended_supplier": "Supplier A",
  "decision_status": "AUTO-RECOMMENDED",
  "policy_decision": {
    "status": "AUTO-RECOMMENDED",
    "summary": "..."
  }
}
```

Each supplier also contains its score recommendation, `policy`, `final_decision`, explanation and upstream source metadata.

## Direct scorecard modes

Manual mode:

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12
```

Connected upstream JSON mode:

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json
```

CSV mode:

```bash
python main.py --csv samples/suppliers.csv
```

Direct modes enforce commercial-risk and vendor-risk gates. Compliance gates are applied by the orchestration pipeline because compliance incidents come from the raw vendor profile.

## Keep audit artifacts

```bash
python pipeline.py samples/procurement-policy-input.json \
  --work-dir pipeline-output
```

The work directory keeps normalized quotations, the shared `rfq.json`, supplier payment-analysis JSON and supplier vendor-risk JSON.

## Composite scoring model

| Component | Input | Weight |
| --- | --- | ---: |
| Quotation | `rfqdiff` quotation score | 50% |
| Commercial | `100 - commercial risk` | 20% |
| Vendor risk | `100 - vendor risk` | 30% |

Score recommendations:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | `PREFERRED` |
| 65–79.99 | `ACCEPTABLE` |
| 50–64.99 | `REVIEW` |
| 0–49.99 | `HIGH RISK` |

Policy gates are evaluated **after** the score calculation.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers composite scoring, JSON/CSV ingestion, explainable decision reasons, default/custom policies, commercial and vendor-risk review gates, compliance review/block gates, automatic-selection eligibility, blocked supplier exclusion and no-auto-approved-supplier behavior.

GitHub Actions runs the suite on Python 3.11, 3.12 and 3.13.

## Procurement tooling suite

| Tool | Role |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation currencies |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score quotations |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into commercial-risk signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score delivery, quality, commercial, compliance and dependency risk |
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Orchestrate, explain, govern and rank supplier decisions |

## Roadmap

- Configurable scorecard weights
- Policy profiles by category / sourcing strategy
- CSV export of integrated portfolio decisions
- Historical supplier trend scoring
- Technical-compliance scoring
- Approval workflow / procurement sign-off states

## Status

Current version: **v0.6**.

The project now separates **score**, **explanation**, and **policy governance** into three inspectable decision layers.

## License

MIT License. See [`LICENSE`](LICENSE).
