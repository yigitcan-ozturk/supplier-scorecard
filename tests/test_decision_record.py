import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from supplier_scorecard.decision_record import (
    artifact_record,
    canonical_json,
    create_decision_record,
    refresh_integrity,
    sha256_json,
    verify_decision_record,
)


class DecisionRecordTests(unittest.TestCase):
    def single_result(self, *, status="PASS"):
        final = "PREFERRED" if status == "PASS" else status
        return {
            "tool": "supplier-scorecard",
            "version": "1.0",
            "supplier": "Supplier A",
            "score": 88.5,
            "recommendation": "PREFERRED",
            "final_decision": final,
            "profile": {
                "name": "critical-machining",
                "weights": {"quotation": 0.21, "commercial": 0.105, "vendor_risk": 0.385, "technical": 0.30},
                "policy": {"minimum_auto_score": 80.0},
                "source": {"type": "builtin", "name": "critical-machining"},
            },
            "policy": {
                "status": status,
                "rules": {"minimum_auto_score": 80.0},
                "triggers": [] if status == "PASS" else [{"rule": "vendor_risk"}],
            },
        }

    def test_canonical_hash_is_key_order_independent(self):
        left = {"b": 2, "a": {"y": 1, "x": 0}}
        right = {"a": {"x": 0, "y": 1}, "b": 2}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(sha256_json(left), sha256_json(right))

    def test_record_does_not_mutate_source_result(self):
        result = self.single_result()
        before = deepcopy(result)
        record = create_decision_record(result)
        record["result"]["score"] = 0
        record["provenance"]["profile"]["snapshot"]["name"] = "changed"
        self.assertEqual(result, before)

    def test_pass_initializes_review_as_not_required(self):
        record = create_decision_record(self.single_result(status="PASS"))
        self.assertFalse(record["review"]["required"])
        self.assertEqual(record["review"]["status"], "NOT_REQUIRED")
        self.assertTrue(verify_decision_record(record)["valid"])

    def test_review_initializes_pending(self):
        record = create_decision_record(self.single_result(status="REVIEW"))
        self.assertTrue(record["review"]["required"])
        self.assertEqual(record["review"]["status"], "PENDING")
        self.assertTrue(verify_decision_record(record)["valid"])

    def test_payload_mutation_is_detected(self):
        record = create_decision_record(self.single_result())
        record["result"]["score"] = 12.0
        verification = verify_decision_record(record)
        self.assertFalse(verification["valid"])
        self.assertIn("decision payload hash mismatch", verification["errors"])

    def test_review_change_requires_integrity_refresh(self):
        record = create_decision_record(self.single_result(status="REVIEW"))
        record["review"].update({"status": "REJECTED", "reviewer": "procurement-owner"})
        self.assertFalse(verify_decision_record(record)["valid"])
        refreshed = refresh_integrity(record)
        self.assertTrue(verify_decision_record(refreshed)["valid"])

    def test_artifact_byte_change_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rfq.json"
            path.write_text(json.dumps({"score": 88}), encoding="utf-8")
            artifact = artifact_record("rfqdiff-output", path, tool="rfqdiff", version="1.0")
            record = create_decision_record(self.single_result(), artifacts=[artifact])
            self.assertTrue(verify_decision_record(record)["valid"])

            path.write_text(json.dumps({"score": 89}), encoding="utf-8")
            verification = verify_decision_record(record)
            self.assertFalse(verification["valid"])
            self.assertTrue(any(error.startswith("artifact hash mismatch:") for error in verification["errors"]))

    def test_non_retained_artifact_is_explicit_and_valid(self):
        artifact = artifact_record("temporary-rfq", "temporary", retained=False)
        record = create_decision_record(self.single_result(), artifacts=[artifact])
        self.assertFalse(record["provenance"]["artifacts"][0]["retained"])
        self.assertIsNone(record["provenance"]["artifacts"][0]["sha256"])
        self.assertTrue(verify_decision_record(record)["valid"])

    def test_portfolio_with_auto_recommendation_does_not_force_review(self):
        result = {
            "tool": "supplier-scorecard-portfolio",
            "version": "1.0",
            "recommended_supplier": "Supplier B",
            "top_scoring_supplier": "Supplier A",
            "decision_status": "AUTO-RECOMMENDED",
            "profile": {"name": "critical-machining", "policy": {"minimum_auto_score": 80}},
            "policy": {"minimum_auto_score": 80},
            "suppliers": [
                {"supplier": "Supplier A", "policy": {"status": "REVIEW"}},
                {"supplier": "Supplier B", "policy": {"status": "PASS"}},
            ],
        }
        record = create_decision_record(result)
        self.assertEqual(record["review"]["status"], "NOT_REQUIRED")

    def test_portfolio_without_auto_approved_supplier_requires_review(self):
        result = {
            "tool": "supplier-scorecard-portfolio",
            "version": "1.0",
            "recommended_supplier": None,
            "top_scoring_supplier": "Supplier A",
            "decision_status": "NO AUTO-APPROVED SUPPLIER",
            "profile": {"name": "critical-machining", "policy": {"minimum_auto_score": 80}},
            "policy": {"minimum_auto_score": 80},
            "suppliers": [{"supplier": "Supplier A", "policy": {"status": "REVIEW"}}],
        }
        record = create_decision_record(result)
        self.assertEqual(record["review"]["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
