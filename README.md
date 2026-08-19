# supplier-scorecard

A transparent Python CLI for combining quotation, payment/commercial and vendor-risk signals into a composite supplier scorecard.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## Why supplier-scorecard

Procurement decisions rarely depend on quotation price and terms alone. A supplier can have a strong commercial offer while still carrying high payment exposure or operational, quality, compliance and dependency risk.

`supplier-scorecard` is the integration layer for the procurement-tooling suite. It can still accept manual scores, but v0.2 can also read the machine-readable outputs of `rfqdiff`, `payment-terms-parser` and `vendor-risk-engine` directly.

## Features

- Combine quotation score, commercial risk and vendor risk
- Produce a transparent weighted 0–100 composite score
- Assign PREFERRED / ACCEPTABLE / REVIEW / HIGH RISK
- Score one supplier manually
- Score/rank a portfolio from CSV
- Read `rfqdiff` JSON directly
- Read `payment-terms-parser` JSON directly
- Read single or batch `vendor-risk-engine` JSON directly
- Validate supplier names across tool outputs
- Preserve source/provenance metadata in JSON output
- Run with Python only — no third-party runtime dependencies

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

## Manual mode

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12
```

## Connected pipeline mode

The actual architecture is a three-input decision pipeline:

```text
currency-normalizer ──> rfqdiff ───────────────┐
                                               │
payment-terms-parser ──────────────────────────┼─> supplier-scorecard
                                               │
vendor-risk-engine ────────────────────────────┘
```

### 1. Normalize mixed-currency quotations when needed

```bash
python ../currency-normalizer/main.py \
  --quote supplier_b_usd.json \
  --target-currency EUR \
  --output supplier_b_eur.json
```

### 2. Compare quotations and write the RFQ result

```bash
python ../rfqdiff/main.py \
  supplier_a_eur.json \
  supplier_b_eur.json \
  --output rfq.json
```

### 3. Parse the selected supplier's payment terms

```bash
python ../payment-terms-parser/main.py \
  "30% advance, 70% after delivery" \
  --supplier "Supplier A" \
  --output payment.json
```

### 4. Produce the vendor-risk JSON

```bash
python ../vendor-risk-engine/main.py "Supplier A" \
  --on-time-delivery 85 \
  --defect-rate 3 \
  --prepayment-exposure 40 \
  --compliance-incidents 1 \
  --dependency-share 50 \
  --json > vendor-risk.json
```

### 5. Build the composite scorecard from those outputs

```bash
python main.py "Supplier A" \
  --rfq-json rfq.json \
  --payment-json payment.json \
  --vendor-risk-json vendor-risk.json
```

Example result:

```text
SUPPLIER SCORECARD v0.2
------------------------------------------------------
Supplier             : Supplier A
Composite score      : 83.25 / 100
Recommendation       : PREFERRED
```

The same command with `--json` includes source metadata for the three upstream files.

## Bundled pipeline sample

The repository includes three ready-made upstream outputs:

```bash
python main.py "Supplier A" \
  --rfq-json samples/pipeline/rfq.json \
  --payment-json samples/pipeline/payment.json \
  --vendor-risk-json samples/pipeline/vendor-risk.json
```

## CSV portfolio mode

Manual portfolio input remains supported:

```bash
python main.py --csv samples/suppliers.csv
```

Required columns:

```text
supplier,quotation_score,commercial_risk,vendor_risk
```

## Integration contracts

`supplier-scorecard` expects:

- `rfqdiff`: a JSON object containing a `suppliers` list with supplier `name` and `score`
- `payment-terms-parser`: `commercial_risk` or `buyer_exposure`, optionally with `supplier`
- `vendor-risk-engine`: a single result object with `vendor` + `score`, or a batch list containing matching vendor records

Supplier matching is case-insensitive. Conflicting supplier names are rejected instead of silently combining unrelated data.

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the same suite automatically on Python 3.11, 3.12 and 3.13.

## Procurement tooling suite

| Tool | Role |
| --- | --- |
| [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) | Normalize quotation values across currencies |
| [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) | Compare and score normalized quotations |
| [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) | Convert payment terms into commercial-risk signals |
| [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) | Score operational, quality, compliance and dependency risk |
| **[`supplier-scorecard`](https://github.com/yigitcan-ozturk/supplier-scorecard)** | Combine upstream signals into one supplier recommendation |

## Roadmap

- Configurable scorecard weights
- Pipeline portfolio mode across many suppliers
- CSV/JSON export of integrated scorecards
- Explainable warning flags
- Historical supplier trend scoring
- Single-command orchestration across sibling repositories

## Status

Early-stage project, currently at **v0.2**. The scorecard now consumes the structured outputs of the upstream procurement tools directly, turning the separate repositories into a working decision pipeline.

## License

MIT License. See [`LICENSE`](LICENSE).
