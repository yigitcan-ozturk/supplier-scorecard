import json
import tempfile
import unittest
from pathlib import Path

from main import recommendation, rank_results, score_csv, score_supplier


class SupplierScorecardTests(unittest.TestCase):
    def test_preferred_supplier(self):
        result = score_supplier("Supplier A", 92, 10, 12)
        self.assertEqual(result["recommendation"], "PREFERRED")
        self.assertAlmostEqual(result["score"], 90.4)

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


if __name__ == "__main__":
    unittest.main()
