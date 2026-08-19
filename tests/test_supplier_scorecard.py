import json
import tempfile
import unittest
from pathlib import Path

from main import (
    explain_portfolio,
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
        self.assertEqual(result["version"], "0.5")

    def test_supplier_explanation_contains_strengths_and_primary_driver(self):
        result = score_supplier("Strong Supplier", 92, 10, 12)
        explanation = result["explanation"]
        self.assertTrue(explanation["strengths"])
        self.assertEqual(explanation["warnings"], [])
        self.assertEqual(explanation["primary_driver"]["component"], "quotation")
        self.assertIn("Strong quotation competitiveness", explanation["strengths"][0])

    def test_supplier_explanation_flags_material_risks(self):
        result = score_supplier("Risky Supplier", 55, 80, 75)
        explanation = result["explanation"]
        self.assertGreaterEqual(len(explanation["warnings"]), 3)
        self.assertTrue(any("commercial/payment" in item for item in explanation["warnings"]))
        self.assertTrue(any("vendor risk" in item for item in explanation["warnings"]))

    def test_portfolio_explanation_compares_winner_and_runner_up(self):
        winner = score_supplier("Winner", 82, 10, 10)
        runner = score_supplier("Runner", 90, 55, 45)
        explanation = explain_portfolio([runner, winner])
        self.assertEqual(explanation["winner"], "Winner")
        self.assertEqual(explanation["runner_up"], "Runner")
        self.assertGreater(explanation["score_gap"], 0)
        self.assertTrue(explanation["advantages"])
        self.assertTrue(explanation["tradeoffs"])
        self.assertIn("ranks first", explanation["summary"])

    def test_acceptable_supplier(self):
        self.assertEqual(score_supplier("B", 78, 25, 30)["recommendation"], "ACCEPTABLE")

    def test_review_supplier(self):
        self.assertEqual(score_supplier("C", 65, 50, 55)["recommendation"], "REVIEW")

    def test_high_risk_supplier(self):
        self.assertEqual(score_supplier("D", 45, 80, 85)["recommendation"], "HIGH RISK")

    def test_risk_inputs_are_inverted(self):
        result = score_supplier("E", 80, 30, 40)
        self.assertEqual(result["components"]["commercial"], 70.0)
        self.assertEqual(result["components"]["vendor_risk"], 60.0)

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            score_supplier("F", 101, 0, 0)

    def test_empty_supplier_rejected(self):
        with self.assertRaises(ValueError):
            score_supplier("   ", 80, 10, 10)

    def test_recommendation_thresholds(self):
        self.assertEqual(recommendation(49.99), "HIGH RISK")
        self.assertEqual(recommendation(50), "REVIEW")
        self.assertEqual(recommendation(65), "ACCEPTABLE")
        self.assertEqual(recommendation(80), "PREFERRED")

    def test_json_serializable(self):
        self.assertIn('"supplier": "JSON"', json.dumps(score_supplier("JSON", 80, 20, 20)))

    def test_rank_results_highest_first(self):
        ranked = rank_results([score_supplier("B", 60, 40, 40), score_supplier("A", 90, 10, 10)])
        self.assertEqual(ranked[0]["supplier"], "A")

    def test_score_csv_multiple_suppliers(self):
        text = "supplier,quotation_score,commercial_risk,vendor_risk\nA,92,10,12\nB,78,25,30\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"; path.write_text(text)
            results = score_csv(path)
        self.assertEqual(results[0]["supplier"], "A")

    def test_score_csv_invalid_row_reports_number(self):
        text = "supplier,quotation_score,commercial_risk,vendor_risk\nA,x,10,12\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"; path.write_text(text)
            with self.assertRaisesRegex(ValueError, "CSV row 2"):
                score_csv(path)

    def test_score_csv_missing_column(self):
        text = "supplier,quotation_score,commercial_risk\nA,92,10\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.csv"; path.write_text(text)
            with self.assertRaisesRegex(ValueError, "vendor_risk"):
                score_csv(path)

    def test_extract_rfq_score(self):
        payload = {"suppliers": [{"name": "Supplier A", "score": 97.1}]}
        self.assertEqual(extract_rfq_score(payload, "supplier a"), 97.1)

    def test_extract_commercial_risk(self):
        payload = {"supplier": "Supplier A", "commercial_risk": 30}
        self.assertEqual(extract_commercial_risk(payload, "Supplier A"), 30)

    def test_extract_vendor_risk_object(self):
        self.assertEqual(extract_vendor_risk({"vendor": "A", "score": 31}, "A"), 31)

    def test_extract_vendor_risk_batch(self):
        payload = [{"vendor": "A", "score": 31}, {"vendor": "B", "score": 44}]
        self.assertEqual(extract_vendor_risk(payload, "B"), 44)

    def test_source_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            extract_commercial_risk({"supplier": "B", "commercial_risk": 20}, "A")

    def test_score_from_tools_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfq = root / "rfq.json"; pay = root / "pay.json"; vendor = root / "vendor.json"
            rfq.write_text(json.dumps({"tool":"rfqdiff","version":"0.2","suppliers":[{"name":"A","score":97.1}]}))
            pay.write_text(json.dumps({"tool":"payment-terms-parser","version":"0.2","supplier":"A","commercial_risk":30}))
            vendor.write_text(json.dumps({"vendor":"A","score":31}))
            result = score_from_tools("A", rfq, pay, vendor)
        self.assertEqual(result["recommendation"], "PREFERRED")
        self.assertEqual(result["sources"]["rfqdiff"]["version"], "0.2")

    def test_score_from_tools_missing_supplier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfq = root / "rfq.json"; pay = root / "pay.json"; vendor = root / "vendor.json"
            rfq.write_text(json.dumps({"suppliers":[{"name":"B","score":70}]}))
            pay.write_text(json.dumps({"commercial_risk":20}))
            vendor.write_text(json.dumps({"vendor":"A","score":20}))
            with self.assertRaisesRegex(ValueError, "does not contain"):
                score_from_tools("A", rfq, pay, vendor)


if __name__ == "__main__":
    unittest.main()
