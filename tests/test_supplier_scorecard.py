import json
import tempfile
import unittest
from pathlib import Path

from main import (
    extract_commercial_risk,
    extract_rfq_score,
    extract_vendor_risk,
    recommendation,
    rank_results,
    score_csv,
    score_from_tools,
    score_supplier,
)


class SupplierScorecardTests(unittest.TestCase):
    def test_preferred_supplier(self):
        result = score_supplier("Supplier A", 92, 10, 12)
        self.assertEqual(result["recommendation"], "PREFERRED")
        self.assertAlmostEqual(result["score"], 90.4)
        self.assertEqual(result["version"], "0.3")

    def test_acceptable_supplier(self):
        result = score_supplier("Supplier B", 78, 25, 30)
        self.assertEqual(result["recommendation"], "ACCEPTABLE")
        self.assertAlmostEqual(result["score"], 75.0)

    def test_review_supplier(self):
        result = score_supplier("Supplier C", 65, 50, 55)
        self.assertEqual(result["recommendation"], "REVIEW")
        self.assertAlmostEqual(result["score"], 56.0)

    def test_high_risk_supplier(self):
        result = score_supplier("Supplier D", 45, 80, 85)
        self.assertEqual(result["recommendation"], "HIGH RISK")
        self.assertAlmostEqual(result["score"], 31.0)

    def test_risk_inputs_are_inverted_to_positive_scores(self):
        result = score_supplier("Supplier E", 80, 30, 40)
        self.assertEqual(result["components"]["commercial"], 70.0)
        self.assertEqual(result["components"]["vendor_risk"], 60.0)

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            score_supplier("Supplier F", 101, 0, 0)

    def test_empty_supplier_rejected(self):
        with self.assertRaises(ValueError):
            score_supplier("   ", 80, 10, 10)

    def test_recommendation_thresholds(self):
        self.assertEqual(recommendation(49.99), "HIGH RISK")
        self.assertEqual(recommendation(50), "REVIEW")
        self.assertEqual(recommendation(65), "ACCEPTABLE")
        self.assertEqual(recommendation(80), "PREFERRED")

    def test_result_is_json_serializable(self):
        result = score_supplier("Supplier JSON", 80, 20, 20)
        encoded = json.dumps(result)
        self.assertIn('"supplier": "Supplier JSON"', encoded)

    def test_rank_results_highest_score_first(self):
        results = [
            score_supplier("B", 60, 40, 40),
            score_supplier("A", 90, 10, 10),
        ]
        ranked = rank_results(results)
        self.assertEqual(ranked[0]["supplier"], "A")

    def test_score_csv_multiple_suppliers(self):
        csv_text = (
            "supplier,quotation_score,commercial_risk,vendor_risk\n"
            "Supplier A,92,10,12\n"
            "Supplier B,78,25,30\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppliers.csv"
            path.write_text(csv_text, encoding="utf-8")
            results = score_csv(path)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["supplier"], "Supplier A")
        self.assertEqual(results[0]["recommendation"], "PREFERRED")

    def test_score_csv_invalid_row_reports_row_number(self):
        csv_text = (
            "supplier,quotation_score,commercial_risk,vendor_risk\n"
            "Supplier A,not-a-number,10,12\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppliers.csv"
            path.write_text(csv_text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV row 2"):
                score_csv(path)

    def test_score_csv_missing_column_rejected(self):
        csv_text = (
            "supplier,quotation_score,commercial_risk\n"
            "Supplier A,92,10\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppliers.csv"
            path.write_text(csv_text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "vendor_risk"):
                score_csv(path)

    def test_extract_rfq_score_from_rfqdiff_contract(self):
        payload = {
            "tool": "rfqdiff",
            "suppliers": [
                {"name": "Supplier A", "score": 97.1},
                {"name": "Supplier B", "score": 67.1},
            ],
        }
        self.assertEqual(extract_rfq_score(payload, "supplier a"), 97.1)

    def test_extract_commercial_risk_from_parser_contract(self):
        payload = {
            "tool": "payment-terms-parser",
            "supplier": "Supplier A",
            "commercial_risk": 30,
        }
        self.assertEqual(extract_commercial_risk(payload, "Supplier A"), 30)

    def test_extract_vendor_risk_from_engine_contract(self):
        payload = {"vendor": "Supplier A", "score": 31.0, "risk": "MEDIUM"}
        self.assertEqual(extract_vendor_risk(payload, "Supplier A"), 31.0)

    def test_extract_vendor_risk_from_batch_contract(self):
        payload = [
            {"vendor": "Supplier A", "score": 31.0},
            {"vendor": "Supplier B", "score": 44.0},
        ]
        self.assertEqual(extract_vendor_risk(payload, "Supplier B"), 44.0)

    def test_source_supplier_mismatch_is_rejected(self):
        payload = {"supplier": "Supplier B", "commercial_risk": 20}
        with self.assertRaisesRegex(ValueError, "mismatch"):
            extract_commercial_risk(payload, "Supplier A")

    def test_score_from_tools_end_to_end(self):
        rfq_payload = {
            "tool": "rfqdiff",
            "version": "0.2",
            "suppliers": [
                {"name": "Supplier A", "score": 97.1},
                {"name": "Supplier B", "score": 67.1},
            ],
        }
        payment_payload = {
            "tool": "payment-terms-parser",
            "version": "0.2",
            "supplier": "Supplier A",
            "commercial_risk": 30,
        }
        vendor_payload = {"vendor": "Supplier A", "score": 31.0, "risk": "MEDIUM"}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rfq = root / "rfq.json"
            payment = root / "payment.json"
            vendor = root / "vendor.json"
            rfq.write_text(json.dumps(rfq_payload), encoding="utf-8")
            payment.write_text(json.dumps(payment_payload), encoding="utf-8")
            vendor.write_text(json.dumps(vendor_payload), encoding="utf-8")
            result = score_from_tools("Supplier A", rfq, payment, vendor)

        expected = score_supplier("Supplier A", 97.1, 30, 31.0)
        self.assertAlmostEqual(result["score"], expected["score"])
        self.assertEqual(result["recommendation"], "PREFERRED")
        self.assertIn("sources", result)
        self.assertEqual(result["sources"]["rfqdiff"]["version"], "0.2")

    def test_score_from_tools_missing_supplier_in_rfq_is_rejected(self):
        rfq_payload = {"suppliers": [{"name": "Supplier B", "score": 70}]}
        payment_payload = {"commercial_risk": 20}
        vendor_payload = {"vendor": "Supplier A", "score": 20}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rfq = root / "rfq.json"
            payment = root / "payment.json"
            vendor = root / "vendor.json"
            rfq.write_text(json.dumps(rfq_payload), encoding="utf-8")
            payment.write_text(json.dumps(payment_payload), encoding="utf-8")
            vendor.write_text(json.dumps(vendor_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not contain"):
                score_from_tools("Supplier A", rfq, payment, vendor)


if __name__ == "__main__":
    unittest.main()
