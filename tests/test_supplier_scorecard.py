import json
import tempfile
import unittest
from pathlib import Path

from main import (
    CATEGORY_PROFILES,
    DEFAULT_POLICY,
    apply_policy,
    explain_portfolio,
    extract_commercial_risk,
    extract_rfq_score,
    extract_vendor_risk,
    get_category_profile,
    load_profile_file,
    normalize_policy,
    normalize_weights,
    recommendation,
    resolve_profile,
    score_csv,
    score_from_tools,
    score_supplier,
)


class ScoreTests(unittest.TestCase):
    def test_default_score(self):
        result = score_supplier("A", 92, 10, 12)
        self.assertEqual(result["version"], "0.9")
        self.assertAlmostEqual(result["score"], 90.4)
        self.assertEqual(result["final_decision"], "PREFERRED")

    def test_recommendation_thresholds(self):
        self.assertEqual(recommendation(49.99), "HIGH RISK")
        self.assertEqual(recommendation(50), "REVIEW")
        self.assertEqual(recommendation(65), "ACCEPTABLE")
        self.assertEqual(recommendation(80), "PREFERRED")

    def test_invalid_score(self):
        with self.assertRaises(ValueError):
            score_supplier("A", 101, 0, 0)

    def test_risks_are_inverted(self):
        result = score_supplier("A", 80, 30, 40)
        self.assertEqual(result["components"]["commercial"], 70)
        self.assertEqual(result["components"]["vendor_risk"], 60)

    def test_explanation_and_json(self):
        result = score_supplier("A", 92, 10, 12)
        self.assertTrue(result["explanation"]["strengths"])
        self.assertIn('"supplier": "A"', json.dumps(result))

    def test_portfolio_explanation(self):
        a = score_supplier("A", 90, 10, 10)
        b = score_supplier("B", 80, 20, 20)
        explanation = explain_portfolio([b, a])
        self.assertEqual(explanation["winner"], "A")
        self.assertGreater(explanation["score_gap"], 0)

    def test_legacy_three_component_score_is_unchanged(self):
        result = score_supplier("A", 92, 10, 12)
        self.assertEqual(result["scoring_mode"], "legacy-3-component")
        self.assertAlmostEqual(result["score"], 90.4)
        self.assertEqual(result["weights"]["technical"], 0.0)

    def test_technical_compliance_becomes_fourth_component(self):
        result = score_supplier("A", 92, 10, 12, technical_compliance=85)
        self.assertEqual(result["scoring_mode"], "4-component")
        self.assertEqual(result["components"]["technical"], 85)
        self.assertEqual(result["weighted"]["technical"], 17.0)
        self.assertAlmostEqual(result["score"], 89.32)

    def test_technical_compliance_validation(self):
        with self.assertRaises(ValueError):
            score_supplier("A", 90, 10, 10, technical_compliance=101)

    def test_technical_strength_and_warning(self):
        strong = score_supplier("A", 80, 20, 20, technical_compliance=95)
        weak = score_supplier("B", 80, 20, 20, technical_compliance=55)
        self.assertTrue(any("technical compliance" in x.lower() for x in strong["explanation"]["strengths"]))
        self.assertTrue(any("technical compliance" in x.lower() for x in weak["explanation"]["warnings"]))


class PolicyTests(unittest.TestCase):
    def test_default_policy(self):
        self.assertEqual(normalize_policy(), DEFAULT_POLICY)

    def test_commercial_review(self):
        result = score_supplier("A", 100, 80, 0)
        self.assertEqual(result["policy"]["status"], "REVIEW")
        self.assertFalse(result["policy"]["auto_eligible"])

    def test_vendor_review(self):
        self.assertEqual(score_supplier("A", 100, 0, 75)["policy"]["status"], "REVIEW")

    def test_compliance_block(self):
        result = score_supplier("A", 100, 0, 0)
        apply_policy(result, compliance_incidents=3)
        self.assertEqual(result["final_decision"], "BLOCKED")

    def test_policy_override(self):
        result = score_supplier("A", 100, 85, 0)
        apply_policy(result, policy={"commercial_review_threshold": 90})
        self.assertEqual(result["policy"]["status"], "PASS")

    def test_bad_policy(self):
        with self.assertRaises(ValueError):
            normalize_policy({"magic": 1})


class BuiltinProfileTests(unittest.TestCase):
    def test_expected_profiles(self):
        self.assertTrue({"general-procurement", "critical-machining", "high-value-capex"} <= set(CATEGORY_PROFILES))

    def test_unknown_profile(self):
        with self.assertRaises(ValueError):
            get_category_profile("moon-rocks")

    def test_weights_total(self):
        for name in CATEGORY_PROFILES:
            self.assertAlmostEqual(sum(get_category_profile(name)["weights"].values()), 1.0)

    def test_builtin_profiles_define_technical_weight(self):
        self.assertEqual(get_category_profile("general-procurement")["weights"]["technical"], .20)
        self.assertEqual(get_category_profile("critical-machining")["weights"]["technical"], .30)

    def test_invalid_weights(self):
        with self.assertRaises(ValueError):
            normalize_weights({"quotation": .5, "commercial": .2, "vendor_risk": .2})

    def test_profile_changes_score(self):
        general = score_supplier("A", 90, 20, 50)
        critical = score_supplier("A", 90, 20, 50, category_profile="critical-machining")
        self.assertNotEqual(general["score"], critical["score"])
        self.assertEqual(critical["weights"]["vendor_risk"], .55)


class CustomProfileTests(unittest.TestCase):
    def payload(self):
        return {
            "name": "marble-sourcing",
            "description": "Stone sourcing.",
            "weights": {"quotation": .35, "commercial": .20, "vendor_risk": .45},
            "policy": {
                "commercial_review_threshold": 65,
                "vendor_review_threshold": 60,
                "compliance_review_incidents": 1,
                "compliance_block_incidents": 2,
                "minimum_auto_score": 75,
            },
        }

    def write(self, root, payload=None):
        path = Path(root) / "profile.json"
        path.write_text(json.dumps(self.payload() if payload is None else payload), encoding="utf-8")
        return path

    def test_load_custom_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = load_profile_file(self.write(tmp))
        self.assertEqual(profile["name"], "marble-sourcing")
        self.assertEqual(profile["source"]["type"], "file")
        self.assertEqual(profile["weights"]["vendor_risk"], .45)

    def test_custom_profile_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = score_supplier("A", 90, 20, 50, profile_file=self.write(tmp))
        self.assertEqual(result["category_profile"], "marble-sourcing")
        self.assertEqual(result["profile"]["source"]["type"], "file")

    def test_custom_profile_requires_full_policy(self):
        payload = self.payload()
        del payload["policy"]["minimum_auto_score"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_profile_file(self.write(tmp, payload))

    def test_custom_profile_rejects_unknown_field(self):
        payload = self.payload(); payload["magic"] = 1
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_profile_file(self.write(tmp, payload))

    def test_builtin_and_file_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                resolve_profile("critical-machining", profile_file=self.write(tmp))

    def test_csv_uses_custom_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.write(tmp)
            csv_path = Path(tmp) / "suppliers.csv"
            csv_path.write_text("supplier,quotation_score,commercial_risk,vendor_risk\nA,90,20,50\n")
            result = score_csv(csv_path, profile_file=profile)[0]
        self.assertEqual(result["category_profile"], "marble-sourcing")

    def test_custom_profile_accepts_four_component_weights(self):
        payload = self.payload()
        payload["weights"] = {
            "quotation": .25,
            "commercial": .15,
            "vendor_risk": .35,
            "technical": .25,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, payload)
            profile = load_profile_file(path)
            result = score_supplier("A", 90, 20, 30, technical_compliance=88, profile_file=path)
        self.assertEqual(profile["weights"]["technical"], .25)
        self.assertEqual(result["weights"]["technical"], .25)

    def test_legacy_custom_profile_gets_zero_technical_weight(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = load_profile_file(self.write(tmp))
        self.assertEqual(profile["weights"]["technical"], 0.0)


class ContractTests(unittest.TestCase):
    def test_extract_contracts(self):
        self.assertEqual(extract_rfq_score({"suppliers": [{"name": "A", "score": 91}]}, "a"), 91)
        self.assertEqual(extract_commercial_risk({"supplier": "A", "commercial_risk": 20}, "A"), 20)
        self.assertEqual(extract_vendor_risk({"vendor": "A", "score": 15}, "A"), 15)

    def test_score_from_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfq, pay, vendor = root/"rfq.json", root/"pay.json", root/"vendor.json"
            rfq.write_text(json.dumps({"tool": "rfqdiff", "version": "0.2", "suppliers": [{"name": "A", "score": 92}]}))
            pay.write_text(json.dumps({"tool": "payment-terms-parser", "version": "0.2", "supplier": "A", "commercial_risk": 10}))
            vendor.write_text(json.dumps({"vendor": "A", "score": 12, "inputs": {"compliance_incidents": 0}}))
            result = score_from_tools("A", rfq, pay, vendor)
        self.assertEqual(result["final_decision"], "PREFERRED")
        self.assertIn("sources", result)

    def test_score_from_tools_accepts_technical_compliance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rfq, pay, vendor = root/"rfq.json", root/"pay.json", root/"vendor.json"
            rfq.write_text(json.dumps({"suppliers": [{"name": "A", "score": 90}]}))
            pay.write_text(json.dumps({"supplier": "A", "commercial_risk": 20}))
            vendor.write_text(json.dumps({"vendor": "A", "score": 25}))
            result = score_from_tools("A", rfq, pay, vendor, technical_compliance=88)
        self.assertEqual(result["inputs"]["technical_compliance"], 88)
        self.assertEqual(result["scoring_mode"], "4-component")


if __name__ == "__main__":
    unittest.main()
