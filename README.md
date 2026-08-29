# supplier-scorecard

**Explainable supplier decision infrastructure for engineering procurement.**

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/v/release/yigitcan-ozturk/supplier-scorecard)](https://github.com/yigitcan-ozturk/supplier-scorecard/releases)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`supplier-scorecard` combines quotation competitiveness, payment exposure, supplier risk and optional technical-compliance evidence into transparent, policy-aware supplier decisions.

> **Latest stable release: v1.1.0.** The package adds tamper-evident decision records, fail-closed commercial review safety and optional vendor-risk trend decision signals around the frozen deterministic v1.0 scoring contract.

`bidlint` remains the technical-compliance source in the wider toolchain. Currency normalization, quotation comparison, payment exposure and supplier risk remain independently inspectable rather than being hidden inside one opaque model.

## Install

Requirements: Python 3.11+.

Install the exact stable **v1.1.0** release directly from GitHub:

```bash
python -m pip install "supplier-scorecard @ git+https://github.com/yigitcan-ozturk/supplier-scorecard.git@v1.1.0"
```

Verify the installed commands:

```bash
supplier-scorecard --list-profiles
supplier-scorecard-pipeline --help
```

A PyPI release is not claimed until the package is actually published there.

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

The deterministic score uses four normalized components:

| Component | Direction |
| --- | --- |
| Quotation competitiveness | higher is better |
| Commercial/payment | `100 - commercial risk` |
| Vendor risk | `100 - vendor risk` |
| Technical compliance | higher is better |

Technical compliance is optional. When omitted, non-technical profile weights are re-normalized so established three-component inputs retain their previous scoring ratio. Results expose either `legacy-3-component` or `4-component` in `scoring_mode`.

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
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score current supplier risk and optionally produce historical trend artifacts |
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

## v1.1 operational decision records

v1.1.0 adds an **opt-in operational provenance wrapper** around the unchanged v1.0 deterministic score/policy result.

Retain pipeline artifacts and write a decision record with:

```bash
supplier-scorecard-pipeline \
  samples/phase2/three-supplier-engineering-pilot.json \
  --tools-root /path/to/procurement-tools \
  --work-dir pipeline-output \
  --output decision.json \
  --decision-record decision-record.json \
  --json
```

The decision record contains:

- an unchanged snapshot of the deterministic supplier or portfolio result;
- exact resolved profile and policy snapshots with canonical SHA-256 hashes;
- SHA-256 hashes for retained input and upstream output artifacts;
- explicit non-retained markers when temporary artifacts were used;
- an integrity hash over the decision payload;
- an operational review state (`NOT_REQUIRED`, `PENDING`, `APPROVED_EXCEPTION` or `REJECTED`).

Human review metadata is governance state outside the scoring core. An approved exception never rewrites the embedded score or policy result.

The sanitized canonical pilot in `samples/phase2/three-supplier-engineering-pilot.json` proves a deliberate score-vs-policy case: the numerical leader is held for review because of a compliance incident, while the highest-scoring policy-eligible supplier is automatically recommended. `.github/workflows/phase2-pilot.yml` executes this case across the real local toolchain and verifies the resulting audit record.

## v1.1 vendor-risk trend decision layer

Historical trend is an optional review signal from `vendor-risk-engine`; it does **not** alter the numeric supplier score.

The integration validates supplier identity and current-score consistency across current-risk and trend artifacts, then exposes explicit decision signals:

| Current risk + trend | Decision signal |
| --- | --- |
| `HIGH` / `CRITICAL` + deteriorating | `ESCALATE` |
| `MEDIUM` + deteriorating | `REVIEW` |
| `LOW` + deteriorating | `OBSERVE` |
| improving | `IMPROVING` |
| stable | `STABLE` |
| one observation / insufficient history | `INSUFFICIENT_HISTORY` |

Improvement never erases current vendor risk, compliance findings or existing policy gates. Numeric trend score adjustment is explicitly `0.0`.

## Fail-closed commercial safety

Automatic scoring stops when payment terms are ambiguous, unsupported or explicitly require review and a reliable numeric commercial-risk signal is unavailable.

This prevents unknown commercial exposure from being silently treated as low risk.

## Version contract

| Contract | Stable value |
| --- | --- |
| Package / GitHub release | `1.1.0` |
| Deterministic scoring/result contract | `1.0` |
| Pipeline/portfolio result semantics | `1.0` |
| Decision-record schema | `1.0` |
| Vendor trend integration contract | `1.0` |

Existing v1.0 scoring inputs, weights, recommendation bands, category profiles and policy gates remain unchanged.

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

- source-level unit tests;
- the public `supplier_scorecard` Python namespace;
- wheel and source-distribution construction;
- package metadata with `twine check`;
- installation of the built wheel;
- installed `supplier-scorecard` CLI execution;
- installed `supplier-scorecard-pipeline` CLI execution;
- multi-repository three-supplier pilot verification;
- decision-record integrity and retained-artifact provenance;
- vendor-risk trend contract, mismatch and decision-gate behavior.

No third-party runtime dependencies are required by `supplier-scorecard` itself.

## Development

For development from source:

```bash
git clone https://github.com/yigitcan-ozturk/supplier-scorecard.git
cd supplier-scorecard
python -m pip install -e .
python -m unittest discover -s tests -v
```

See [`CHANGELOG.md`](CHANGELOG.md), [`RELEASE_NOTES.md`](RELEASE_NOTES.md) and the [GitHub Releases](https://github.com/yigitcan-ozturk/supplier-scorecard/releases) page for project history.

## Contributing

External contributions are welcome when they preserve deterministic scoring, explicit policy behavior and public-contract clarity. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) and use the structured issue templates for reproducible bugs or deliberately scoped feature requests. Do not include confidential supplier, quotation or project data in public issues, fixtures or pull requests.

## Scope

`supplier-scorecard` is decision-support infrastructure, not an automatic contractual acceptance system. Authentication, authorization, digital signatures, persistence and application APIs remain hosting-layer responsibilities.

Historical trend is a review signal, not a forecasting claim. Current supplier-risk evidence remains authoritative for the numeric score.

## License

MIT License. See [`LICENSE`](LICENSE).
