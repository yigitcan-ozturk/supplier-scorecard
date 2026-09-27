"""Report observed field coverage from Phase 3 OCDS extracted JSONL.

Public awards are never reclassified as submitted bids. Unknowns remain unknown.
Usage: python scripts/phase3_coverage_report.py public_records.jsonl coverage_report.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("award_amount", "award_currency", "submitted_bid_price", "payment_terms",
          "delivery_cost", "technical_compliance", "supplier_risk")


def report(source, target):
    rows = [json.loads(line) for line in Path(source).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("No extracted award rows; cannot claim real-data coverage")
    for row in rows:
        if not row.get("ocid") or not row.get("release_id"):
            raise ValueError("Missing provenance identifier")
        if row.get("submitted_bid_price") is not None and row.get("award_amount") == row.get("submitted_bid_price"):
            raise ValueError("Potential award-as-bid substitution requires independent review")
    counts = Counter({field: sum(row.get(field) is not None for row in rows) for field in FIELDS})
    result = {"record_type": "published_awards_not_competing_supplier_quotes",
              "total_award_rows": len(rows), "distinct_ocids": len({r["ocid"] for r in rows}),
              "observed_fields": dict(counts),
              "missing_fields": {field: len(rows) - counts[field] for field in FIELDS},
              "real_private_multi_bid_pilot_validated": False}
    Path(target).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"award_rows={len(rows)} distinct_ocids={result['distinct_ocids']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: phase3_coverage_report.py public_records.jsonl coverage_report.json")
    report(*sys.argv[1:])
