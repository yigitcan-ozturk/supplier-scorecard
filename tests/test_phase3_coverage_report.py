"""Offline unit tests for Phase 3 public-record field coverage."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.phase3_coverage_report import report


class CoverageReportTests(unittest.TestCase):
    def test_unknowns_remain_missing_and_award_is_not_a_bid(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "rows.jsonl", Path(tmp) / "coverage.json"
            src.write_text(json.dumps({"ocid": "ocds-test-1", "release_id": "release-1",
                                       "award_amount": 2000, "award_currency": "GBP",
                                       "submitted_bid_price": None, "payment_terms": None,
                                       "delivery_cost": None, "technical_compliance": None,
                                       "supplier_risk": None}) + "\n")
            report(src, dst)
            result = json.loads(dst.read_text())
            self.assertEqual(result["total_award_rows"], 1)
            self.assertEqual(result["observed_fields"]["award_amount"], 1)
            self.assertEqual(result["observed_fields"]["submitted_bid_price"], 0)
            self.assertEqual(result["missing_fields"]["payment_terms"], 1)
            self.assertFalse(result["real_private_multi_bid_pilot_validated"])

    def test_empty_records_cannot_claim_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "rows.jsonl", Path(tmp) / "coverage.json"
            src.write_text("")
            with self.assertRaises(ValueError):
                report(src, dst)
            self.assertFalse(dst.exists())


if __name__ == "__main__":
    unittest.main()
