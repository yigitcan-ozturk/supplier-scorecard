import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import pipeline


class PipelineTests(unittest.TestCase):
    def payload(self):
        return {
            "target_currency": "EUR",
            "quotes": [
                {"name": "Supplier A", "currency": "EUR", "price": 100, "lead_time_weeks": 4, "payment_days": 30},
                {"name": "Supplier B", "currency": "EUR", "price": 90, "lead_time_weeks": 6, "payment_days": 10},
            ],
            "supplier_profiles": [
                {"supplier": "Supplier A", "payment_terms": "Net 30 days", "vendor_risk": {"on_time_delivery": 95, "defect_rate": 1, "compliance_incidents": 0, "dependency_share": 20}},
                {"supplier": "Supplier B", "payment_terms": "50% advance, 50% before shipment", "vendor_risk": {"on_time_delivery": 80, "defect_rate": 4, "compliance_incidents": 1, "dependency_share": 60}},
            ],
        }

    def profile_payload(self):
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

    def write_profile(self, root):
        path = Path(root) / "profile.json"
        path.write_text(json.dumps(self.profile_payload()))
        return path

    def make_tool(self, root, name, code):
        directory = Path(root) / name
        directory.mkdir(parents=True)
        (directory / "main.py").write_text(textwrap.dedent(code))

    def install_tools(self, root):
        self.make_tool(root, "currency-normalizer", """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('--quote'); p.add_argument('--target-currency'); p.add_argument('--output'); a=p.parse_args()
            q=json.loads(Path(a.quote).read_text()); q['currency']=a.target_currency; Path(a.output).write_text(json.dumps(q))
        """)
        self.make_tool(root, "rfqdiff", """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('quotes', nargs='+'); p.add_argument('--output'); a=p.parse_args()
            qs=[json.loads(Path(x).read_text()) for x in a.quotes]
            for q in qs: q['score']=92 if q['name']=='Supplier A' else 96
            Path(a.output).write_text(json.dumps({'tool':'rfqdiff','version':'test','suppliers':qs}))
        """)
        self.make_tool(root, "payment-terms-parser", """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('terms'); p.add_argument('--supplier'); p.add_argument('--output'); a=p.parse_args()
            risk=0 if 'Net' in a.terms else 100
            Path(a.output).write_text(json.dumps({'tool':'payment-terms-parser','version':'test','supplier':a.supplier,'commercial_risk':risk}))
        """)
        self.make_tool(root, "vendor-risk-engine", """
            import argparse, json
            p=argparse.ArgumentParser(); p.add_argument('vendor'); p.add_argument('--on-time-delivery'); p.add_argument('--defect-rate'); p.add_argument('--prepayment-exposure'); p.add_argument('--compliance-incidents'); p.add_argument('--dependency-share'); p.add_argument('--json', action='store_true'); a=p.parse_args()
            score=10 if a.vendor=='Supplier A' else 12
            print(json.dumps({'vendor':a.vendor,'score':score,'inputs':{'compliance_incidents':int(a.compliance_incidents)}}))
        """)

    def run_case(self, payload, root):
        self.install_tools(root)
        return pipeline.run_pipeline(
            payload,
            pipeline.resolve_tools(root),
            Path(__file__).resolve().parents[1] / "main.py",
            Path(root) / "work",
        )

    def test_validate_portfolio(self):
        pipeline.validate_input(self.payload())

    def test_missing_profile_for_quote(self):
        payload = self.payload(); payload["supplier_profiles"].pop()
        with self.assertRaises(ValueError):
            pipeline.validate_input(payload)

    def test_relative_profile_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/"profiles").mkdir()
            profile = root/"profiles"/"marble.json"; profile.write_text(json.dumps(self.profile_payload()))
            payload = self.payload(); payload["profile_file"] = "profiles/marble.json"
            input_path = root/"input.json"; input_path.write_text(json.dumps(payload))
            loaded = pipeline.load_input(input_path)
        self.assertEqual(loaded["profile_file"], str(profile.resolve()))

    def test_cli_profile_override_removes_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); profile = self.write_profile(root)
            payload = self.payload(); payload["category_profile"] = "office-supplies"
            input_path = root/"input.json"; input_path.write_text(json.dumps(payload))
            loaded = pipeline.load_input(input_path, profile_file=profile)
        self.assertNotIn("category_profile", loaded)

    def test_builtin_and_file_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = self.payload(); payload["category_profile"] = "critical-machining"; payload["profile_file"] = str(self.write_profile(tmp))
            with self.assertRaises(ValueError):
                pipeline.validate_input(payload)

    def test_builtin_profile_pipeline(self):
        payload = self.payload(); payload["category_profile"] = "critical-machining"
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_case(payload, Path(tmp))
        self.assertEqual(result["version"], "1.0")
        self.assertEqual(result["orchestration"]["version"], "1.0")
        self.assertEqual(result["category_profile"], "critical-machining")
        self.assertEqual(result["profile"]["weights"]["vendor_risk"], .385)
        self.assertEqual(result["profile"]["weights"]["technical"], .30)
        self.assertEqual(result["suppliers"][0]["scoring_mode"], "legacy-3-component")

    def test_custom_profile_pipeline(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); payload["profile_file"] = str(self.write_profile(root))
            result = self.run_case(payload, root)
        self.assertEqual(result["category_profile"], "marble-sourcing")
        self.assertEqual(result["profile"]["source"]["type"], "file")
        self.assertEqual(result["profile"]["weights"]["vendor_risk"], .45)
        self.assertTrue(all(item["category_profile"] == "marble-sourcing" for item in result["suppliers"]))

    def test_custom_profile_policy_override(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); payload["profile_file"] = str(self.write_profile(root)); payload["policy"] = {"vendor_review_threshold": 70}
            result = self.run_case(payload, root)
        self.assertEqual(result["policy"]["vendor_review_threshold"], 70)
        self.assertEqual(result["profile"]["weights"]["vendor_risk"], .45)

    def test_policy_selects_eligible_supplier(self):
        payload = self.payload()
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_case(payload, Path(tmp))
        self.assertEqual(result["recommended_supplier"], "Supplier A")
        self.assertIn(result["decision_status"], {"AUTO-RECOMMENDED", "NO AUTO-APPROVED SUPPLIER"})

    def test_portfolio_technical_compliance_is_scored_per_supplier(self):
        payload = self.payload()
        payload["category_profile"] = "critical-machining"
        payload["supplier_profiles"][0]["technical_compliance"] = 95
        payload["supplier_profiles"][1]["technical_compliance"] = 60
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_case(payload, Path(tmp))
        by_name = {item["supplier"]: item for item in result["suppliers"]}
        self.assertEqual(by_name["Supplier A"]["scoring_mode"], "4-component")
        self.assertEqual(by_name["Supplier A"]["inputs"]["technical_compliance"], 95)
        self.assertEqual(by_name["Supplier B"]["inputs"]["technical_compliance"], 60)
        self.assertEqual(by_name["Supplier A"]["weights"]["technical"], .30)

    def test_pipeline_rejects_invalid_technical_score(self):
        payload = self.payload()
        payload["supplier_profiles"][0]["technical_compliance"] = 120
        with self.assertRaises(ValueError):
            pipeline.validate_input(payload)

    def test_pipeline_allows_mixed_technical_availability(self):
        payload = self.payload()
        payload["category_profile"] = "critical-machining"
        payload["supplier_profiles"][0]["technical_compliance"] = 90
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_case(payload, Path(tmp))
        by_name = {item["supplier"]: item for item in result["suppliers"]}
        self.assertEqual(by_name["Supplier A"]["scoring_mode"], "4-component")
        self.assertEqual(by_name["Supplier B"]["scoring_mode"], "legacy-3-component")
        self.assertAlmostEqual(by_name["Supplier B"]["weights"]["vendor_risk"], .55)


if __name__ == "__main__":
    unittest.main()
