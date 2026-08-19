# supplier-scorecard

A transparent Python CLI for combining quotation, payment/commercial and vendor-risk signals into a composite supplier scorecard.

[![Tests](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml/badge.svg)](https://github.com/yigitcan-ozturk/supplier-scorecard/actions/workflows/tests.yml)

## Why supplier-scorecard

Procurement decisions rarely depend on quotation price and terms alone. A supplier can have a strong commercial offer while still carrying high payment exposure, delivery, quality, compliance or dependency risk.

`supplier-scorecard` combines upstream procurement signals into one transparent 0–100 supplier score and a clear recommendation. The scoring logic is explicit and intended to support procurement judgment rather than replace it.

## Features

- Combine quotation score, commercial risk and vendor risk
- Convert risk inputs into positive supplier-score components
- Produce a transparent weighted 0–100 composite score
- Assign PREFERRED / ACCEPTABLE / REVIEW / HIGH RISK recommendations
- Score one supplier from the CLI
- Score and rank a supplier portfolio from CSV
- Return structured JSON output
- Run with Python only — no third-party runtime dependencies

## Quick start

### Requirements

- Python 3.11+

### Score one supplier

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12
```

Example output:

```text
SUPPLIER SCORECARD v0.1
------------------------------------------------------
Supplier             : Supplier A
Composite score      : 90.40 / 100
Recommendation       : PREFERRED

Score breakdown
------------------------------------------------------
Quotation score    :  92.00 / 100 x 50% =  46.00
Commercial score   :  90.00 / 100 x 20% =  18.00
Vendor-risk score  :  88.00 / 100 x 30% =  26.40
```

### JSON output

```bash
python main.py "Supplier A" \
  --quotation-score 92 \
  --commercial-risk 10 \
  --vendor-risk 12 \
  --json
```

## CSV portfolio scoring

```bash
python main.py --csv samples/suppliers.csv
```

Required columns:

```text
supplier,quotation_score,commercial_risk,vendor_risk
```

The portfolio is ranked from highest to lowest composite supplier score.

## Scoring model

The v0.1 model uses three inputs:

| Component | Input | Weight |
| --- | --- | ---: |
| Quotation | quotation comparison score | 50% |
| Commercial | `100 - commercial risk` | 20% |
| Vendor risk | `100 - vendor risk` | 30% |

This means quotation quality remains the largest factor, while commercial/payment exposure and operational/vendor risk can materially change the recommendation.

Recommendation thresholds:

| Composite score | Recommendation |
| ---: | --- |
| 80–100 | PREFERRED |
| 65–79.99 | ACCEPTABLE |
| 50–64.99 | REVIEW |
| 0–49.99 | HIGH RISK |

## Procurement tooling suite

`supplier-scorecard` is the composite decision layer in a small procurement-tooling suite:

1. [`currency-normalizer`](https://github.com/yigitcan-ozturk/currency-normalizer) — normalize supplier quotations into a common currency.
2. [`payment-terms-parser`](https://github.com/yigitcan-ozturk/payment-terms-parser) — convert free-text payment terms into structured buyer-exposure signals.
3. [`rfqdiff`](https://github.com/yigitcan-ozturk/rfqdiff) — compare quotations and produce a quotation decision score.
4. [`vendor-risk-engine`](https://github.com/yigitcan-ozturk/vendor-risk-engine) — score supplier operational, commercial, compliance and dependency risk.
5. **`supplier-scorecard`** — combine those decision signals into one supplier recommendation.

Conceptually:

```text
currency-normalizer
        ↓
payment-terms-parser
        ↓
      rfqdiff
        ↓
vendor-risk-engine
        ↓
supplier-scorecard
```

## Tests

Run locally with:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs the same suite automatically on Python 3.11, 3.12 and 3.13.

## Roadmap

- Configurable component weights
- CSV export of ranked scorecards
- Direct JSON ingestion from `rfqdiff` and `vendor-risk-engine`
- Automatic commercial-risk input from `payment-terms-parser`
- Explainable recommendation flags and risk warnings
- Supplier trend scoring across review periods

## Status

Early-stage project, currently at **v0.1**. The first version provides a deterministic composite supplier score from three procurement decision signals, with single-supplier, CSV portfolio and JSON output modes.

## License

MIT License. See [`LICENSE`](LICENSE).
