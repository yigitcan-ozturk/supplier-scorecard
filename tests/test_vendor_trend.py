import json
import tempfile
import unittest
from pathlib import Path

from supplier_scorecard.vendor_trend import (
    apply_vendor_trend,
    normalize_vendor_trend,
    score_from_tools_with_trend,
    vendor_trend_decision,
)
from main import score_supplier


def trend_payload(
    *,
    vendor="Supplier A",
    current_score=55.0,
    current_risk="HIGH",
    direction="DETERIORATING",
    latest_delta=7.5,
    observations=3,
):
    return {
        "vendor": vendor,
        "current_score": current_score,
        "current_risk": current_risk,
        "direction": direction,
        "latest_delta": latest_delta,
        "change_from_first": 12.0,
        "observations": observations,
        "first_as_of_date": "2026-06-01",
        "current_as_of_date": "2026-08-01",
        "trend_tolerance": 2.0,
        "meta": {
            "engine": "vendor-risk-engine",
            "engine_version": "0.5.0",
            "model_version": "vendor-risk-trend-v1",
            "schema_version": "1.0",
        },
        "policy": {
            "weights": {
                "delivery": 0.3,
                "quality": 0.25,
                "commercial": 0.2,
                "compliance": 0.15,
                "dependency": 0.1,
            },
            "thresholds": {"medium": 25.0, "high": 50.0, "critical": 75.0},
        },
        "history": [
            {"as_of_date": "2026-06-01", "score": 43.0, "risk": "MEDIUM"},
            {"as_of_date": "2026-07-01", "score": 47.5, "risk": "MEDIUM"},
            {"as_of_date": "2026-08-01", "score": current_score, "risk": current_risk},
        ],
    }


class VendorTrendContractTests(unittest.TestCase):
    def test_supplier_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "supplier mismatch"):
            normalize_vendor_trend(trend_payload(vendor="Supplier B"), "Supplier A")

    def test_current_score_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            normalize_vendor_trend(
                trend_payload(current_score=55),
                "Supplier A",
                current_vendor_risk=40,
            )

    def test_insufficient_history_requires_null_delta(self):
        payload = trend_payload(
            current_score=20,
            current_risk="LOW",
            direction="INSUFFICIENT_HISTORY",
            latest_delta=None,
            observations=1,
        )
        normalized = normalize_vendor_trend(payload, "Supplier A", current_vendor_risk=20)
        self.assertEqual(normalized["direction"], "INSUFFICIENT_HISTORY")


class VendorTrendDecisionTests(unittest.TestCase):
    def test_deteriorating_high_escalates_without_changing_score(self):
        base = score_supplier("Supplier A", 95, 10, 55)
        trend = normalize_vendor_trend(
            trend_payload(current_score=55, current_risk="HIGH"),
            "Supplier A",
            current_vendor_risk=55,
        )
        result = apply_vendor_trend(base, trend)
        self.assertEqual(result["score"], base["score"])
        self.assertEqual(result["vendor_trend"]["score_adjustment"], 0.0)
        self.assertEqual(result["vendor_trend"]["decision"]["status"], "ESCALATE")
        self.assertEqual(result["policy"]["status"], "REVIEW")
        self.assertFalse(result["policy"]["auto_eligible"])
        self.assertEqual(result["final_decision"], "REVIEW")

    def test_deteriorating_medium_requires_review(self):
        base = score_supplier("Supplier A", 95, 10, 35)
        trend = normalize_vendor_trend(
            trend_payload(current_score=35, current_risk="MEDIUM", latest_delta=4),
            "Supplier A",
            current_vendor_risk=35,
        )
        result = apply_vendor_trend(base, trend)
        self.assertEqual(result["vendor_trend"]["decision"]["status"], "REVIEW")
        self.assertEqual(result["policy"]["status"], "REVIEW")
        self.assertEqual(result["score"], base["score"])

    def test_deteriorating_low_is_observe_only(self):
        base = score_supplier("Supplier A", 95, 10, 20)
        trend = normalize_vendor_trend(
            trend_payload(current_score=20, current_risk="LOW", latest_delta=3),
            "Supplier A",
            current_vendor_risk=20,
        )
        result = apply_vendor_trend(base, trend)
        self.assertEqual(result["vendor_trend"]["decision"]["status"], "OBSERVE")
        self.assertEqual(result["policy"], base["policy"])
        self.assertEqual(result["final_decision"], base["final_decision"])

    def test_improving_never_erases_current_high_risk_gate(self):
        base = score_supplier("Supplier A", 95, 10, 80)
        self.assertEqual(base["policy"]["status"], "REVIEW")
        trend = normalize_vendor_trend(
            trend_payload(
                current_score=80,
                current_risk="CRITICAL",
                direction="IMPROVING",
                latest_delta=-8,
            ),
            "Supplier A",
            current_vendor_risk=80,
        )
        result = apply_vendor_trend(base, trend)
        self.assertEqual(result["vendor_trend"]["decision"]["status"], "IMPROVING")
        self.assertEqual(result["policy"]["status"], "REVIEW")
        self.assertEqual(result["final_decision"], base["final_decision"])

    def test_decision_function_has_no_hidden_penalty(self):
        normalized = normalize_vendor_trend(
            trend_payload(current_score=55, current_risk="HIGH"),
            "Supplier A",
            current_vendor_risk=55,
        )
        decision = vendor_trend_decision(normalized)
        self.assertNotIn("score_adjustment", decision)
        self.assertTrue(decision["review_required"])


class ConnectedTrendTests(unittest.TestCase):
    def test_connected_artifacts_include_trend_source_and_keep_score_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfq = root / "rfq.json"
            pay = root / "payment.json"
            vendor = root / "vendor.json"
            trend = root / "trend.json"

            rfq.write_text(
                json.dumps(
                    {
                        "tool": "rfqdiff",
                        "version": "0.2",
                        "suppliers": [{"name": "Supplier A", "score": 95}],
                    }
                ),
                encoding="utf-8",
            )
            pay.write_text(
                json.dumps(
                    {
                        "tool": "payment-terms-parser",
                        "version": "0.3",
                        "supplier": "Supplier A",
                        "commercial_risk": 10,
                    }
                ),
                encoding="utf-8",
            )
            vendor.write_text(
                json.dumps(
                    {
                        "tool": "vendor-risk-engine",
                        "version": "0.5",
                        "vendor": "Supplier A",
                        "score": 55,
                        "inputs": {"compliance_incidents": 0},
                    }
                ),
                encoding="utf-8",
            )
            trend.write_text(json.dumps(trend_payload(current_score=55)), encoding="utf-8")

            baseline = score_supplier("Supplier A", 95, 10, 55)
            result = score_from_tools_with_trend(
                "Supplier A",
                rfq,
                pay,
                vendor,
                trend,
            )

        self.assertEqual(result["score"], baseline["score"])
        self.assertEqual(result["inputs"]["vendor_risk"], 55)
        self.assertEqual(result["vendor_trend"]["decision"]["status"], "ESCALATE")
        self.assertEqual(result["sources"]["vendor_risk_trend"]["model_version"], "vendor-risk-trend-v1")


if __name__ == "__main__":
    unittest.main()
