# supplier-scorecard

A transparent Python CLI and orchestration layer for turning quotation, payment-term and vendor-risk signals into one composite supplier recommendation.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## Why supplier-scorecard

Procurement decisions rarely depend on quotation price and terms alone. A supplier can have a strong commercial offer while still carrying high payment exposure or operational, quality, compliance and dependency risk.

`supplier-scorecard` is the integration layer for the procurement-tooling suite. v0.3 keeps the existing manual, CSV and upstream-JSON modes and adds **single-command orchestration** across the sibling repositories.

## One-command procurement pipeline

Clone the five repositories side-by-side:

```text
procurement-tools/
├── currency-normalizer/
├── rfqdiff/
├── payment-terms-parser/
├── vendor-risk-engine/
└── supplier-scorecard/
```

Then run from `supplier-scorecard`:

```bash
python pipeline.py samples/procurement-input.json
```

That one command executes:

```text
quotation JSON
      │
      ▼
currency-normalizer
      │
      ▼
    rfqdiff ─────────────────────────────┐
                                         │
payment terms ─> payment-terms-parser ──┼─> supplier-scorecard
                                         │
vendor metrics ─> vendor-risk-engine ───┘
```

`payment-terms-parser` automatically supplies pre-delivery payment exposure to `vendor-risk-engine`, so that commercial-risk value does not have to be entered twice.

Example output:

```text
PROCUREMENT DECISION PIPELINE v0.1
----------------------------------------------------------
Supplier             : Supplier A
Composite score      : <score> / 100
Recommendation       : <recommendation>
Target currency      : EUR

Pipeline
----------------------------------------------------------
currency-normalizer  : completed
rfqdiff              : completed
payment-terms-parser : completed
vendor-risk-engine   : completed
supplier-scorecard   : completed
```

### Unified input

The pipeline takes one JSON file:

```json
{
  "supplier": "Supplier A",
  "target_currency": "EUR",
  "quotes": [
    {
      "name": "Supplier A",
      "currency": "EUR",
      "price": 84200,
      "lead_time_weeks": 8,
      "payment_days": 30
    },
    {
      "name": "Supplier B",
      "currency": "EUR",
      "price": 79400,
      "lead_time_weeks": 14,
      "payment_days": 0
    }
  ],
  "payment_terms": "20% advance, 80% after delivery",
  "vendor_risk": {
    "on_time_delivery": 92,
    "defect_rate": 1.5,
    "compliance_incidents": 0,
    "dependency_share": 30
  }
}
```

The target supplier must appear in the quotation set. At least two quotations are required because `rfqdiff` scores suppliers comparatively.

### Keep intermediate artifacts

By default, intermediate JSON files are temporary. Keep them for audit/review with:

```bash
python pipeline.py samples/procurement-input.json \
  --work-dir pipeline-output
```

This preserves:

```text
pipeline-output/
├── quote-1-raw.json
├── quote-1-normalized.json
├── quote-2-raw.json
├── quote-2-normalized.json
├── rfq.json
├── payment.json
└── vendor-risk.json
```

Write the final scorecard to JSON:

```bash
python pipeline.py samples/procurement-input.json \
  --output final-scorecard.json \
  --json
```

If the repositories are not side-by-side, point to the directory containing the upstream repositories:

```bash
python pipeline.py input.json --tools-root /path/to/procurement-tools
```

## Scoring model

| Component | Input | Weight |
| --- | --- | ---: |
| Quotation | `rfqdiff` quotation score | 50% |
| Commercial | `100 - commercial risk` | 20% |
| Vendor risk | `100 - vendor risk` | 30% |

Recommendation thresholds:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | PREFERRED |
| 65–79.99 | ACCEPTABLE |
| 50–64.99 | REVIEW |
| 0–49.99 | HIGH RISK |

## Existing modes

Single-supplier manual scoring remains supported:

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12
```

Direct upstream JSON ingestion remains supported:

```bash
python main.py "Supplier A" \
  --rfq-json samples/pipeline/rfq.json \
  --payment-json samples/pipeline/payment.json \
  --vendor-risk-json samples/pipeline/vendor-risk.json
```

CSV portfolio scoring remains supported:

```bash
python main.py --csv samples/suppliers.csv
```

## Integration contracts

`supplier-scorecard` expects:

- `rfqdiff`: a JSON object containing a `suppliers` list with supplier `name` and `score`
- `payment-terms-parser`: `commercial_risk` or `buyer_exposure`, optionally with `supplier`
- `vendor-risk-engine`: a single result object with `vendor` + `score`, or a batch list containing matching vendor records

Supplier matching is case-insensitive. Conflicting supplier names are rejected instead of silently combining unrelated data.

## Procurement tooling suite

| Tool | Role |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation values across currencies |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score normalized quotations |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into commercial-risk signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score operational, quality, compliance and dependency risk |
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Orchestrate the tools and produce the final supplier recommendation |

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the same suite automatically on Python 3.11, 3.12 and 3.13.

## Roadmap

- Pipeline portfolio mode across many suppliers
- Configurable scorecard weights
- CSV/JSON export of integrated portfolio scorecards
- Explainable warning flags and hard-stop rules
- Historical supplier trend scoring
- Optional package/installer for easier multi-repo setup

## Status

Early-stage project, currently at **v0.3**. This version adds one-command orchestration across the procurement-tooling repositories while preserving the explicit scoring contracts and reviewable intermediate outputs.

## License

MIT License. See [`LICENSE`](LICENSE).
