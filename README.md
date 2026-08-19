# supplier-scorecard

A transparent Python CLI and orchestration layer for turning quotation, payment-term and vendor-risk signals into an explainable, policy-aware procurement recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## What v0.8 adds

v0.8 adds **user-defined procurement profile files**. Teams can create company-, category- or project-specific scoring and approval rules in standalone JSON files without editing Python code.

A custom profile defines:

- profile name and description
- quotation, commercial and vendor-risk weights
- commercial/vendor-risk review thresholds
- compliance review and block thresholds
- minimum score required for automatic approval

Built-in category profiles remain available and the default is still `general-procurement`.

## Built-in category profiles

| Profile | Quotation | Commercial | Vendor risk | Minimum auto score | Typical use |
| --- | ---: | ---: | ---: | ---: | --- |
| `general-procurement` | 50% | 20% | 30% | 65 | balanced default |
| `office-supplies` | 65% | 20% | 15% | 65 | lower-complexity, replaceable supply |
| `critical-machining` | 30% | 15% | 55% | 80 | quality-sensitive engineered components |
| `single-source` | 30% | 20% | 50% | 80 | dependency-heavy sourcing |
| `high-value-capex` | 40% | 30% | 30% | 80 | capital expenditure / approval-heavy buying |

List the active built-in profiles from the CLI:

```bash
python main.py --list-profiles
```

## Custom JSON profiles

Create a standalone profile file such as `profiles/marble-sourcing.json`:

```json
{
  "name": "marble-sourcing",
  "description": "Custom profile for bespoke marble and stone sourcing.",
  "weights": {
    "quotation": 0.35,
    "commercial": 0.20,
    "vendor_risk": 0.45
  },
  "policy": {
    "commercial_review_threshold": 65,
    "vendor_review_threshold": 60,
    "compliance_review_incidents": 1,
    "compliance_block_incidents": 2,
    "minimum_auto_score": 75
  }
}
```

The three weights must total exactly `1.0`. Custom profile files must explicitly contain all policy fields so the approval logic is auditable and does not depend on hidden defaults. Unknown fields are rejected.

Use a profile directly with the scorecard:

```bash
python main.py "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35 \
  --profile-file samples/profiles/marble-sourcing.json
```

`--profile-file` and `--category-profile` are mutually exclusive. JSON output records whether the active profile came from a built-in profile or an external file, including the resolved profile path for auditability.

## Bundled custom profile pack

The repository includes ready-to-edit custom profiles under `samples/profiles/`:

| Profile file | Quotation | Commercial | Vendor risk | Min. auto score | Intended use |
| --- | ---: | ---: | ---: | ---: | --- |
| `marble-sourcing.json` | 35% | 20% | 45% | 75 | bespoke marble / stone sourcing |
| `technical-ceramics.json` | 25% | 15% | 60% | 82 | capability- and consistency-sensitive technical ceramics |
| `gears.json` | 30% | 15% | 55% | 80 | precision gears / drivetrain components |
| `machinery-capex.json` | 35% | 30% | 35% | 82 | machinery and capital-equipment purchases |

Examples:

```bash
python main.py "Supplier A" \
  --quotation-score 86 \
  --commercial-risk 20 \
  --vendor-risk 30 \
  --profile-file samples/profiles/technical-ceramics.json
```

```bash
python main.py "Supplier A" \
  --quotation-score 90 \
  --commercial-risk 25 \
  --vendor-risk 35 \
  --profile-file samples/profiles/gears.json
```

```bash
python main.py "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 35 \
  --vendor-risk 25 \
  --profile-file samples/profiles/machinery-capex.json
```

These files are examples, not universal procurement standards. Their values are deliberately explicit so teams can review and adapt them to actual category risk appetite, approval authority and supplier-management policy.

## Category-aware scoring

Manual scoring with a built-in profile:

```bash
python main.py "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35 \
  --category-profile critical-machining
```

The result includes the selected profile, its weights, policy status, final decision and explainability output.

A supplier can therefore be `PREFERRED` under `office-supplies` but require `REVIEW` under `critical-machining` because the second profile puts more weight on vendor risk and requires a higher automatic-approval score.

## End-to-end category pipeline

Clone the five repositories side-by-side:

```text
procurement-tools/
├── currency-normalizer/
├── rfqdiff/
├── payment-terms-parser/
├── vendor-risk-engine/
└── supplier-scorecard/
```

Run a built-in category profile:

```bash
python pipeline.py samples/procurement-category-input.json
```

The input selects the profile once:

```json
{
  "category_profile": "critical-machining",
  "target_currency": "EUR",
  "quotes": [],
  "supplier_profiles": []
}
```

That profile is applied consistently to every supplier in the RFQ.

A pipeline can also reference a custom file:

```json
{
  "profile_file": "profiles/marble-sourcing.json",
  "target_currency": "EUR",
  "quotes": [],
  "supplier_profiles": []
}
```

Paths inside the pipeline input are resolved relative to the input JSON file, so the bundled sample works directly:

```bash
python pipeline.py samples/procurement-custom-profile-input.json
```

A command-line custom profile can override the profile selection in an input file:

```bash
python pipeline.py procurement-input.json \
  --profile-file company-profiles/technical-ceramics.json
```

## Procurement decision flow

```text
quotation JSONs ─> currency-normalizer ─> rfqdiff ───────────────┐
                                                                 │
payment terms ───────────────> payment-terms-parser ─────────────┼─> supplier-scorecard
                                                                 │
vendor metrics ──────────────> vendor-risk-engine ───────────────┘
                                                                 │
                                                                 ▼
                                            category weights + policy gates
                                                                 │
                                                                 ▼
                                                ranked / explainable decision
```

Payment exposure from `payment-terms-parser` is passed automatically into `vendor-risk-engine`, so it is not entered twice.

## Policy gates

The general profile uses these defaults:

| Rule | Default |
| --- | ---: |
| Commercial risk review | 80 / 100 |
| Vendor risk review | 75 / 100 |
| Compliance review | 1 incident |
| Compliance block | 3 incidents |
| Minimum automatic score | 65 / 100 |

Profiles can tighten or relax these values. For example, `critical-machining` blocks at 2 compliance incidents and requires a score of at least 80 for automatic approval.

A score can therefore remain visible while policy changes the final decision:

```text
Composite score       : 78.00 / 100
Score recommendation  : ACCEPTABLE
Category profile      : high-value-capex
Policy status         : REVIEW
Final decision        : REVIEW
Auto eligible         : NO
```

## Optional policy override

A pipeline input may override selected profile rules without changing its scoring weights:

```json
{
  "category_profile": "critical-machining",
  "policy": {
    "vendor_review_threshold": 65,
    "minimum_auto_score": 85
  }
}
```

Unspecified rules continue to come from the selected category profile.

## Portfolio behavior

Portfolio mode separates **score ranking** from **automatic recommendation**. If the score leader fails the active category policy, the pipeline selects the highest-scoring supplier that is auto-eligible. If no supplier passes, the recommendation is withheld.

Output includes:

- `top_scoring_supplier`
- `recommended_supplier`
- `decision_status`
- selected profile name
- profile source (`builtin` or `file`)
- active profile weights and policy
- ranked supplier scorecards
- policy exclusions and reasons
- winner-vs-runner-up explanation

## Existing modes remain supported

Default single-supplier pipeline:

```bash
python pipeline.py samples/procurement-input.json
```

Policy-gate sample:

```bash
python pipeline.py samples/procurement-policy-input.json
```

Manual CSV scoring:

```bash
python main.py --csv samples/suppliers.csv
```

Connected upstream JSON mode:

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json \
  --category-profile high-value-capex
```

## Composite scoring model

The score always uses the same three normalized components; the profile changes their relative weights:

- quotation score: higher is better
- commercial score: `100 - commercial risk`
- vendor score: `100 - vendor risk`

Base score recommendations remain:

| Composite score | Score recommendation |
| ---: | --- |
| 80–100 | PREFERRED |
| 65–79.99 | ACCEPTABLE |
| 50–64.99 | REVIEW |
| 0–49.99 | HIGH RISK |

Policy gates are evaluated after the score recommendation.

## Explainability

Every supplier result includes deterministic:

- strengths
- warnings
- primary score driver
- policy triggers
- final-decision reason

Portfolio output also explains why the score leader beat the runner-up and why policy may select a different supplier.

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
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Apply category profiles, policy gates and final supplier ranking |

## Roadmap

- Technical-compliance score as a fourth composite component
- Approval workflow / sign-off metadata
- Historical supplier trend scoring
- Export ranked decision packs to CSV/JSON
- Profile versioning and governance metadata

## Status

Current version: **v0.8**. The project supports built-in and user-defined JSON procurement profiles, a bundled editable profile pack, category-aware scoring, policy gates, explainability, and end-to-end portfolio orchestration without third-party runtime dependencies.

## License

MIT License. See [`LICENSE`](LICENSE).
