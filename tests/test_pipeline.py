import tempfile
import textwrap
import unittest
from pathlib import Path

import pipeline


class PipelineInputTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "supplier": "Supplier A",
            "target_currency": "EUR",
            "quotes": [
                {"name": "Supplier A", "currency": "EUR", "price": 100, "lead_time_weeks": 4, "payment_days": 30},
                {"name": "Supplier B", "currency": "USD", "price": 120, "lead_time_weeks": 5, "payment_days": 10},
            ],
            "payment_terms": "20% advance, 80% after delivery",
            "vendor_risk": {
                "on_time_delivery": 92,
                "defect_rate": 1.5,
                "compliance_incidents": 0,
                "dependency_share": 30,
            },
        }

    def valid_portfolio_payload(self):
        return {
            "target_currency": "EUR",
            "quotes": [
                {"name": "Supplier A", "currency": "EUR", "price": 100, "lead_time_weeks": 4, "payment_days": 30},
                {"name": "Supplier B", "currency": "EUR", "price": 90, "lead_time_weeks": 6, "payment_days": 10},
            ],
            "supplier_profiles": [
                {
                    "supplier": "Supplier A",
                    "payment_terms": "Net 30 days",
                    "vendor_risk": {
                        "on_time_delivery": 95,
                        "defect_rate": 1,
                        "compliance_incidents": 0,
                        "dependency_share": 20,
                    },
                },
                {
                    "supplier": "Supplier B",
                    "payment_terms": "50% advance, 50% before shipment",
                    "vendor_risk": {
                        "on_time_delivery": 80,
                        "defect_rate": 4,
                        "compliance_incidents": 1,
                        "dependency_share": 60,
                    },
                },
            ],
        }

    def test_validate_input_accepts_complete_payload(self):
        pipeline.validate_input(self.valid_payload())

    def test_validate_input_requires_target_supplier_in_quotes(self):
        payload = self.valid_payload(); payload["supplier"] = "Missing Supplier"
        with self.assertRaisesRegex(ValueError, "do not contain target supplier"):
            pipeline.validate_input(payload)

    def test_validate_input_requires_vendor_fields(self):
        payload = self.valid_payload(); del payload["vendor_risk"]["defect_rate"]
        with self.assertRaisesRegex(ValueError, "defect_rate"):
            pipeline.validate_input(payload)

    def test_validate_portfolio_accepts_matching_profiles(self):
        payload = self.valid_portfolio_payload()
        pipeline.validate_input(payload)
        self.assertEqual(pipeline.input_mode(payload), "portfolio")

    def test_validate_portfolio_requires_profile_for_every_quote(self):
        payload = self.valid_portfolio_payload(); payload["supplier_profiles"].pop()
        with self.assertRaisesRegex(ValueError, "missing supplier profile"):
            pipeline.validate_input(payload)

    def test_validate_portfolio_rejects_duplicate_profiles(self):
        payload = self.valid_portfolio_payload(); payload["supplier_profiles"][1]["supplier"] = "supplier a"
        with self.assertRaisesRegex(ValueError, "duplicate supplier profile"):
            pipeline.validate_input(payload)

    def test_validate_input_accepts_custom_policy(self):
        payload = self.valid_portfolio_payload()
        payload["policy"] = {"commercial_review_threshold": 90, "compliance_block_incidents": 4}
        pipeline.validate_input(payload)

    def test_validate_input_rejects_bad_policy(self):
        payload = self.valid_portfolio_payload(); payload["policy"] = {"magic": 1}
        with self.assertRaisesRegex(ValueError, "unknown policy field"):
            pipeline.validate_input(payload)

    def test_validate_input_accepts_category_profile(self):
        payload = self.valid_portfolio_payload(); payload["category_profile"] = "critical-machining"
        pipeline.validate_input(payload)

    def test_validate_input_rejects_unknown_category_profile(self):
        payload = self.valid_portfolio_payload(); payload["category_profile"] = "moon-rocks"
        with self.assertRaisesRegex(ValueError, "unknown category profile"):
            pipeline.validate_input(payload)


class OrchestrationTests(unittest.TestCase):
    def make_tool(self, root, name, code):
        directory = root / name
        directory.mkdir(parents=True)
        path = directory / "main.py"
        path.write_text(textwrap.dedent(code), encoding="utf-8")
        return path

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
            for q in qs: q['score']=92.0 if q['name']=='Supplier A' else 96.0
            Path(a.output).write_text(json.dumps({'tool':'rfqdiff','version':'test','suppliers':qs}))
        """)
        self.make_tool(root, "payment-terms-parser", """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('terms'); p.add_argument('--supplier'); p.add_argument('--output'); a=p.parse_args()
            if 'Net' in a.terms: risk=0
            elif '100%' in a.terms: risk=100
            elif '50% advance' in a.terms: risk=100
            else: risk=20
            Path(a.output).write_text(json.dumps({'tool':'payment-terms-parser','version':'test','supplier':a.supplier,'commercial_risk':risk}))
        """)
        self.make_tool(root, "vendor-risk-engine", """
            import argparse, json
            p=argparse.ArgumentParser(); p.add_argument('vendor'); p.add_argument('--on-time-delivery'); p.add_argument('--defect-rate'); p.add_argument('--prepayment-exposure'); p.add_argument('--compliance-incidents'); p.add_argument('--dependency-share'); p.add_argument('--json', action='store_true'); a=p.parse_args()
            score=10.0 if a.vendor=='Supplier A' else 12.0
            print(json.dumps({'vendor':a.vendor,'score':score,'risk':'LOW','inputs':{'compliance_incidents':int(a.compliance_incidents)}}))
        """)

    def run_pipeline_case(self, payload, root):
        self.install_tools(root)
        return pipeline.run_pipeline(
            payload,
            pipeline.resolve_tools(root),
            Path(__file__).resolve().parents[1] / "main.py",
            root / "work",
        )

    def test_resolve_tools_requires_all_sibling_repositories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "currency-normalizer"):
                pipeline.resolve_tools(tmpdir)

    def test_end_to_end_single_supplier_policy_pass(self):
        payload = PipelineInputTests().valid_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["supplier"], "Supplier A")
            self.assertEqual(result["orchestration"]["mode"], "single")
            self.assertEqual(result["policy"]["status"], "PASS")
            self.assertEqual(result["final_decision"], "PREFERRED")
            self.assertEqual(result["category_profile"], "general-procurement")

    def test_single_supplier_compliance_block_overrides_score(self):
        payload = PipelineInputTests().valid_payload(); payload["vendor_risk"]["compliance_incidents"] = 3
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["recommendation"], "PREFERRED")
            self.assertEqual(result["policy"]["status"], "BLOCKED")
            self.assertEqual(result["final_decision"], "BLOCKED")

    def test_end_to_end_portfolio_ranks_all_suppliers(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir); result = self.run_pipeline_case(payload, root)
            self.assertEqual(result["tool"], "supplier-scorecard-portfolio")
            self.assertEqual(result["supplier_count"], 2)
            self.assertEqual(result["version"], "0.4")
            self.assertEqual(result["orchestration"]["version"], "0.5")
            self.assertEqual([x["rank"] for x in result["suppliers"]], [1, 2])
            self.assertIn("policy_decision", result)
            self.assertTrue((root / "work" / "suppliers" / "Supplier-A" / "payment.json").exists())

    def test_policy_can_select_lower_scoring_pass_supplier(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["supplier_profiles"][1]["payment_terms"] = "Net 30 days"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["top_scoring_supplier"], "Supplier B")
            self.assertEqual(result["recommended_supplier"], "Supplier A")
            b = next(x for x in result["suppliers"] if x["supplier"] == "Supplier B")
            self.assertEqual(b["policy"]["status"], "REVIEW")

    def test_blocked_top_supplier_is_never_auto_recommended(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["supplier_profiles"][1]["payment_terms"] = "Net 30 days"
        payload["supplier_profiles"][1]["vendor_risk"]["compliance_incidents"] = 3
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["top_scoring_supplier"], "Supplier B")
            self.assertEqual(result["recommended_supplier"], "Supplier A")
            b = next(x for x in result["suppliers"] if x["supplier"] == "Supplier B")
            self.assertEqual(b["final_decision"], "BLOCKED")

    def test_no_auto_eligible_supplier_withholds_recommendation(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["supplier_profiles"][0]["vendor_risk"]["compliance_incidents"] = 1
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertIsNone(result["recommended_supplier"])
            self.assertEqual(result["decision_status"], "NO AUTO-APPROVED SUPPLIER")

    def test_custom_policy_can_raise_compliance_review_threshold(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["supplier_profiles"][1]["payment_terms"] = "Net 30 days"
        payload["policy"] = {"compliance_review_incidents": 2}
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            b = next(x for x in result["suppliers"] if x["supplier"] == "Supplier B")
            self.assertEqual(b["policy"]["status"], "PASS")

    def test_critical_machining_profile_flows_to_all_suppliers(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["category_profile"] = "critical-machining"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["category_profile"], "critical-machining")
            self.assertEqual(result["profile"]["weights"]["vendor_risk"], 0.55)
            self.assertTrue(all(x["category_profile"] == "critical-machining" for x in result["suppliers"]))
            self.assertEqual(result["orchestration"]["category_profile"], "critical-machining")

    def test_high_value_capex_minimum_score_gate_can_withhold(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["category_profile"] = "high-value-capex"
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["profile"]["policy"]["minimum_auto_score"], 80.0)
            self.assertEqual(result["category_profile"], "high-value-capex")

    def test_profile_policy_override_preserves_profile_weights(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        payload["category_profile"] = "critical-machining"
        payload["policy"] = {"vendor_review_threshold": 70}
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.run_pipeline_case(payload, Path(tmpdir))
            self.assertEqual(result["profile"]["weights"]["vendor_risk"], 0.55)
            self.assertEqual(result["policy"]["vendor_review_threshold"], 70.0)
            self.assertEqual(result["policy"]["compliance_block_incidents"], 2)


if __name__ == "__main__":
    unittest.main()
