# supplier-scorecard

**Explainable supplier decision infrastructure for engineering procurement.**

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`supplier-scorecard` combines quotation competitiveness, payment exposure, supplier risk and optional technical-compliance evidence into transparent, policy-aware supplier decisions.

> **Status: v1.0 stable.** The public scoring model and orchestration contract are intentionally explicit and reviewable. The tool supports both installed CLI usage and a stable Python import namespace.

`bidlint` is the technical-compliance source in the wider toolchain; commercial scoring, payment exposure and supplier risk remain independently inspectable rather than being hidden inside one opaque model.

## Install

Requirements: Python 3.11+.

From a source checkout:

```bash
git clone https://github.com/yigitcan-ozturk/supplier-scorecard.git
cd supplier-scorecard
python -m pip install .
```

Verify the installed commands:

```bash
supplier-scorecard --list-profiles
supplier-scorecard-pipeline --help
```

The repository is package-ready, but a PyPI release is not claimed until the package is actually published there.

## Quick start

Score one supplier:

```bash
supplier-scorecard "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35 \
  --technical-compliance 94 \
  --category-profile critical-machining
```

Legacy three-component scoring remains valid when technical compliance is unavailable:

```bash
supplier-scorecard "Supplier A" \
  --quotation-score 88 \
  --commercial-risk 20 \
  --vendor-risk 35
```

Consume upstream JSON signals:

```bash
supplier-scorecard "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json \
  --technical-compliance 92 \
  --category-profile critical-machining \
  --json
```

CSV portfolio scoring is also supported:

```bash
supplier-scorecard --csv samples/suppliers.csv
```

## Python API

The installable package exposes the stable scoring namespace as `supplier_scorecard`:

```python
import supplier_scorecard

result = supplier_scorecard.score_supplier(
    "Supplier A",
    quotation_score=88,
    commercial_risk=20,
    vendor_risk=35,
    technical_compliance=94,
    category_profile="critical-machining",
)

print(result["final_decision"])
```

Existing source-checkout workflows using `python main.py ...` remain supported for backward compatibility.

## Decision model

The score uses four normalized components:

| Component | Direction |
| --- | --- |
| Quotation competitiveness | higher is better |
| Commercial/payment | `100 - commercial risk` |
| Vendor risk | `100 - vendor risk` |
| Technical compliance | higher is better |

Technical compliance is optional. When it is omitted, non-technical profile weights are re-normalized so established three-component inputs retain their previous scoring ratio. Results expose either `legacy-3-component` or `4-component` in `scoring_mode`.

Base score recommendations are:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | `PREFERRED` |
| 65–79.99 | `ACCEPTABLE` |
| 50–64.99 | `REVIEW` |
| 0–49.99 | `HIGH RISK` |

Policy gates are evaluated after the numeric score. A supplier can therefore rank first numerically while still being withheld from automatic recommendation because of commercial, vendor-risk or compliance policy.

## Built-in profiles

| Profile | Quotation | Commercial | Vendor risk | Technical | Min. auto score |
| --- | ---: | ---: | ---: | ---: | ---: |
| `general-procurement` | 40% | 16% | 24% | 20% | 65 |
| `office-supplies` | 58.5% | 18% | 13.5% | 10% | 65 |
| `critical-machining` | 21% | 10.5% | 38.5% | 30% | 80 |
| `single-source` | 24% | 16% | 40% | 20% | 80 |
| `high-value-capex` | 34% | 25.5% | 25.5% | 15% | 80 |

External JSON profiles can change weights and policy without editing Python code. Bundled examples cover marble sourcing, technical ceramics, gears and machinery CAPEX.

```bash
supplier-scorecard "Supplier A" \
  --quotation-score 86 \
  --commercial-risk 20 \
  --vendor-risk 30 \
  --technical-compliance 93 \
  --profile-file samples/profiles/technical-ceramics.json
```

Custom profiles are validated: unknown fields are rejected, weights must be valid and policy values remain explicit for auditability.

## Engineering procurement toolchain

```text
currency-normalizer ──> rfqdiff ────────────────┐
                                                 │
payment-terms-parser ───────────────────────────┼──> supplier-scorecard
                                                 │
vendor-risk-engine ─────────────────────────────┤
                                                 │
bidlint ──> technical compliance ───────────────┘
```

| Tool | Responsibility |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation currencies with FX provenance |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score commercial quotation signals |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into buyer-exposure signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score delivery, quality, commercial, compliance-event and dependency risk |
| [`bidlint`](https://github.com/yigitcan-ozturk/bidlint) | Produce evidence-backed technical-compliance findings and hand-off data |
| **`supplier-scorecard`** | Combine independently inspectable signals into a policy-aware supplier decision |

## End-to-end pipeline

The orchestration command can run the local procurement toolchain from one JSON input:

```bash
supplier-scorecard-pipeline \
  samples/procurement-technical-input.json \
  --tools-root /path/to/procurement-tools \
  --work-dir pipeline-output \
  --output decision.json \
  --json
```

`--tools-root` should contain sibling checkouts of `currency-normalizer`, `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine`.

For technical bid evaluation, `bidlint` can emit a versioned supplier-scorecard hand-off. A numeric technical-compliance value is supplied only when technical findings are safe to reduce to that signal; unresolved engineering review remains explicit rather than silently affecting ranking.

## Explainability

Every supplier result can expose deterministic:

- strengths and warnings;
- primary weighted score driver;
- policy triggers and final-decision reason;
- technical-compliance strength or warning when present;
- winner-vs-runner-up portfolio explanation.

The goal is not to automate procurement judgment away. It is to make the decision path visible, reproducible and reviewable.

## Quality gates

CI runs on Python 3.11, 3.12 and 3.13 and validates:

- the existing source-level unit test suite;
- the public `supplier_scorecard` Python namespace;
- wheel and source-distribution construction;
- package metadata with `twine check`;
- installation of the built wheel;
- installed `supplier-scorecard` CLI execution;
- installed `supplier-scorecard-pipeline` CLI execution.

No third-party runtime dependencies are required.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [`CHANGELOG.md`](CHANGELOG.md) for project history and [`RELEASE_NOTES.md`](RELEASE_NOTES.md) for the v1.0 release summary.

## Contributing

External contributions are welcome when they preserve deterministic scoring, explicit policy behavior and public-contract clarity. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and use the structured issue templates for reproducible bugs or deliberately scoped feature requests. Do not include confidential supplier, quotation or project data in public issues, fixtures or pull requests.

## Scope

`supplier-scorecard` is a decision-support engine, not an automatic contractual acceptance system. Technical compliance remains owned by `bidlint`; currency normalization, quotation comparison, payment exposure and supplier risk remain separate responsibilities with explicit hand-off contracts.

## License

MIT License. See [`LICENSE`](LICENSE).
