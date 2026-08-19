# supplier-scorecard

A transparent Python CLI and orchestration layer for turning quotation, payment-term and vendor-risk signals into one procurement recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## What v0.4 adds

v0.4 adds **portfolio orchestration**. A single pipeline input can now describe every supplier in an RFQ. The pipeline normalizes quotation currencies, runs the quotation comparison once, evaluates payment and vendor risk for every supplier, builds a composite scorecard for each supplier, ranks the portfolio and returns the recommended supplier.

The existing manual, CSV, connected-JSON and single-supplier orchestration modes remain supported.

## Procurement decision pipeline

Clone the five repositories side-by-side:

```text
procurement-tools/
├── currency-normalizer/
├── rfqdiff/
├── payment-terms-parser/
├── vendor-risk-engine/
└── supplier-scorecard/
```

The orchestration flow is:

```text
quotation JSONs ─> currency-normalizer ─> rfqdiff ───────────────┐
                                                                 │
payment terms ───────────────> payment-terms-parser ─────────────┼─> supplier-scorecard
                                                                 │
vendor metrics ──────────────> vendor-risk-engine ───────────────┘
                                                                 │
                                                                 ▼
                                                       ranked supplier portfolio
```

Payment exposure from `payment-terms-parser` is passed automatically to `vendor-risk-engine`, so the same commercial exposure is not entered twice.

## One supplier

The v0.3 unified input still works:

```bash
python pipeline.py samples/procurement-input.json
```

## Portfolio mode

Run every supplier in one command:

```bash
python pipeline.py samples/procurement-portfolio-input.json
```

Example output format:

```text
PROCUREMENT PORTFOLIO PIPELINE v0.2
------------------------------------------------------------------------------------
  # Supplier                          Score     Recommendation
------------------------------------------------------------------------------------
  1 Supplier C                        93.00          PREFERRED
  2 Supplier A                        87.31          PREFERRED
  3 Supplier B                        49.15          HIGH RISK
------------------------------------------------------------------------------------
Recommended supplier : Supplier C
Suppliers evaluated  : 3
Target currency      : EUR
```

## Portfolio input

Portfolio mode uses one quotation per supplier plus one risk profile per supplier:

```json
{
  "target_currency": "EUR",
  "quotes": [
    {
      "name": "Supplier A",
      "currency": "EUR",
      "price": 84200,
      "lead_time_weeks": 8,
      "payment_days": 30
    }
  ],
  "supplier_profiles": [
    {
      "supplier": "Supplier A",
      "payment_terms": "20% advance, 80% after delivery",
      "vendor_risk": {
        "on_time_delivery": 92,
        "defect_rate": 1.5,
        "compliance_incidents": 0,
        "dependency_share": 30
      }
    }
  ]
}
```

At least two quotations are required. Every quotation supplier must have exactly one matching `supplier_profiles` entry. Duplicate or missing suppliers are rejected rather than silently combined.

## Keep audit artifacts

By default, intermediate files are temporary. Keep them for review with:

```bash
python pipeline.py samples/procurement-portfolio-input.json \
  --work-dir pipeline-output
```

The work directory contains the normalized quotations, one shared `rfq.json`, and separate payment/vendor-risk artifacts for each supplier.

## JSON output

```bash
python pipeline.py samples/procurement-portfolio-input.json \
  --json \
  --output portfolio-scorecard.json
```

The portfolio JSON contains:

- `recommended_supplier`
- `supplier_count`
- `target_currency`
- ranked `suppliers`
- each supplier's composite score and recommendation
- orchestration provenance and artifact paths

## Composite scoring model

| Component | Input | Weight |
| --- | --- | ---: |
| Quotation | `rfqdiff` quotation score | 50% |
| Commercial | `100 - commercial risk` | 20% |
| Vendor risk | `100 - vendor risk` | 30% |

Recommendations:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | PREFERRED |
| 65–79.99 | ACCEPTABLE |
| 50–64.99 | REVIEW |
| 0–49.99 | HIGH RISK |

## Direct scorecard modes

Manual scoring remains available:

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12
```

Connected JSON mode remains available:

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json
```

CSV portfolio scoring remains available:

```bash
python main.py --csv samples/suppliers.csv
```

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
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Orchestrate the suite and rank suppliers |

## Roadmap

- Configurable scorecard weights
- Export ranked portfolio results to CSV
- Explainable warning flags and decision reasons
- Historical supplier trend scoring
- Technical-compliance scoring alongside commercial scoring

## Status

Current version: **v0.4**. The project supports single-supplier and portfolio-level end-to-end procurement orchestration while keeping every scoring step deterministic and inspectable.

## License

MIT License. See [`LICENSE`](LICENSE).
