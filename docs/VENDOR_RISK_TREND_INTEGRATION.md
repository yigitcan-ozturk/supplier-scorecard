# Vendor-risk trend integration

`supplier-scorecard` can consume the historical trend result produced by `vendor-risk-engine` as an **optional decision signal**.

The integration deliberately does **not** change the frozen supplier-scorecard numeric scoring formula. Current vendor risk remains the scored component. Historical trend is attached as explicit evidence and can add a human-review gate when deterioration is material.

## Contract

The upstream trend artifact is expected to follow the `vendor-risk-engine` v0.5 historical trend contract, including:

- `vendor`
- `current_score`
- `current_risk`
- `direction`
- `latest_delta`
- observation count and review dates
- `meta.engine = vendor-risk-engine`
- model/schema provenance

The integration validates supplier identity and, when a current vendor-risk artifact is available, verifies that `current_score` matches that artifact within a small explicit tolerance. A mismatch fails closed.

## Decision mapping

| Current risk | Direction | Trend action | Score adjustment |
| --- | --- | --- | ---: |
| HIGH / CRITICAL | DETERIORATING | `ESCALATE` + human review | 0 |
| MEDIUM | DETERIORATING | `REVIEW` | 0 |
| LOW | DETERIORATING | `OBSERVE` | 0 |
| Any | IMPROVING | Surface improvement; preserve current gates | 0 |
| Any | STABLE | No trend gate | 0 |
| Any | INSUFFICIENT_HISTORY | No trend gate | 0 |

Improvement never cancels a current high-risk decision, compliance gate or other policy trigger.

## Python API

```python
from supplier_scorecard import score_from_tools_with_trend

result = score_from_tools_with_trend(
    "Supplier A",
    "rfq.json",
    "payment.json",
    "vendor-risk.json",
    "vendor-risk-trend.json",
)
```

The result keeps the original numeric `score`, `components`, `weights` and current `vendor_risk` input unchanged. Trend evidence is added under:

```text
vendor_trend.signal
vendor_trend.decision
vendor_trend.score_adjustment
sources.vendor_risk_trend
```

When the trend requires review, the integration appends an explicit policy trigger and disables automatic eligibility. It does not manufacture a numeric penalty.

## Engineering boundary

This layer is intended to answer a narrow question:

> Is the supplier's current risk state becoming materially worse over time in a way that should affect automatic decision eligibility?

It is not a forecasting model, a substitute for supplier due diligence, or a mechanism for rewarding improving suppliers with hidden score bonuses.
