import json
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
                {"name":"Supplier A","currency":"EUR","price":100,"lead_time_weeks":4,"payment_days":30},
                {"name":"Supplier B","currency":"USD","price":120,"lead_time_weeks":5,"payment_days":10},
            ],
            "payment_terms": "20% advance, 80% after delivery",
            "vendor_risk": {"on_time_delivery":92,"defect_rate":1.5,"compliance_incidents":0,"dependency_share":30},
        }

    def valid_portfolio_payload(self):
        return {
            "target_currency": "EUR",
            "quotes": [
                {"name":"Supplier A","currency":"EUR","price":100,"lead_time_weeks":4,"payment_days":30},
                {"name":"Supplier B","currency":"EUR","price":90,"lead_time_weeks":6,"payment_days":10},
            ],
            "supplier_profiles": [
                {"supplier":"Supplier A","payment_terms":"Net 30 days","vendor_risk":{"on_time_delivery":95,"defect_rate":1,"compliance_incidents":0,"dependency_share":20}},
                {"supplier":"Supplier B","payment_terms":"50% advance, 50% before shipment","vendor_risk":{"on_time_delivery":80,"defect_rate":4,"compliance_incidents":1,"dependency_share":60}},
            ],
        }

    def test_validate_input_accepts_complete_payload(self):
        pipeline.validate_input(self.valid_payload())

    def test_validate_input_requires_target_supplier_in_quotes(self):
        payload = self.valid_payload()
        payload["supplier"] = "Missing Supplier"
        with self.assertRaisesRegex(ValueError, "do not contain target supplier"):
            pipeline.validate_input(payload)

    def test_validate_input_requires_vendor_fields(self):
        payload = self.valid_payload()
        del payload["vendor_risk"]["defect_rate"]
        with self.assertRaisesRegex(ValueError, "defect_rate"):
            pipeline.validate_input(payload)

    def test_validate_portfolio_accepts_matching_profiles(self):
        payload = self.valid_portfolio_payload()
        pipeline.validate_input(payload)
        self.assertEqual(pipeline.input_mode(payload), "portfolio")

    def test_validate_portfolio_requires_profile_for_every_quote(self):
        payload = self.valid_portfolio_payload()
        payload["supplier_profiles"].pop()
        with self.assertRaisesRegex(ValueError, "missing supplier profile"):
            pipeline.validate_input(payload)

    def test_validate_portfolio_rejects_duplicate_profiles(self):
        payload = self.valid_portfolio_payload()
        payload["supplier_profiles"][1]["supplier"] = "supplier a"
        with self.assertRaisesRegex(ValueError, "duplicate supplier profile"):
            pipeline.validate_input(payload)


class OrchestrationTests(unittest.TestCase):
    def make_tool(self, root, name, code):
        directory = root / name
        directory.mkdir(parents=True)
        path = directory / "main.py"
        path.write_text(textwrap.dedent(code), encoding="utf-8")
        return path

    def install_tools(self, root):
        self.make_tool(
            root,
            "currency-normalizer",
            """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('--quote'); p.add_argument('--target-currency'); p.add_argument('--output'); a=p.parse_args()
            q=json.loads(Path(a.quote).read_text()); q['currency']=a.target_currency; Path(a.output).write_text(json.dumps(q))
            """,
        )
        self.make_tool(
            root,
            "rfqdiff",
            """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('quotes', nargs='+'); p.add_argument('--output'); a=p.parse_args()
            qs=[json.loads(Path(x).read_text()) for x in a.quotes]
            for q in qs: q['score']=92.0 if q['name']=='Supplier A' else 70.0
            Path(a.output).write_text(json.dumps({'tool':'rfqdiff','version':'test','suppliers':qs}))
            """,
        )
        self.make_tool(
            root,
            "payment-terms-parser",
            """
            import argparse, json
            from pathlib import Path
            p=argparse.ArgumentParser(); p.add_argument('terms'); p.add_argument('--supplier'); p.add_argument('--output'); a=p.parse_args()
            risk=0 if 'Net' in a.terms else 20 if a.supplier=='Supplier A' else 100
            Path(a.output).write_text(json.dumps({'tool':'payment-terms-parser','version':'test','supplier':a.supplier,'commercial_risk':risk}))
            """,
        )
        self.make_tool(
            root,
            "vendor-risk-engine",
            """
            import argparse, json
            p=argparse.ArgumentParser(); p.add_argument('vendor'); p.add_argument('--on-time-delivery'); p.add_argument('--defect-rate'); p.add_argument('--prepayment-exposure'); p.add_argument('--compliance-incidents'); p.add_argument('--dependency-share'); p.add_argument('--json', action='store_true'); a=p.parse_args()
            score=10.0 if a.vendor=='Supplier A' else 50.0
            print(json.dumps({'vendor':a.vendor,'score':score,'risk':'LOW' if score<25 else 'HIGH'}))
            """,
        )

    def test_resolve_tools_requires_all_sibling_repositories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(ValueError, "currency-normalizer"):
                pipeline.resolve_tools(tmpdir)

    def test_end_to_end_orchestration_with_tool_contracts(self):
        payload = PipelineInputTests().valid_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.install_tools(root)
            tools = pipeline.resolve_tools(root)
            scorecard_main = Path(__file__).resolve().parents[1] / "main.py"
            work = root / "work"
            result = pipeline.run_pipeline(payload, tools, scorecard_main, work)
            self.assertEqual(result["supplier"], "Supplier A")
            self.assertEqual(result["orchestration"]["mode"], "single")
            self.assertEqual(result["recommendation"], "PREFERRED")
            self.assertTrue((work / "rfq.json").exists())

    def test_end_to_end_portfolio_ranks_all_suppliers(self):
        payload = PipelineInputTests().valid_portfolio_payload()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.install_tools(root)
            tools = pipeline.resolve_tools(root)
            scorecard_main = Path(__file__).resolve().parents[1] / "main.py"
            work = root / "work"
            result = pipeline.run_pipeline(payload, tools, scorecard_main, work)
            self.assertEqual(result["tool"], "supplier-scorecard-portfolio")
            self.assertEqual(result["supplier_count"], 2)
            self.assertEqual(result["recommended_supplier"], "Supplier A")
            self.assertEqual([x["rank"] for x in result["suppliers"]], [1, 2])
            self.assertEqual(result["suppliers"][0]["supplier"], "Supplier A")
            self.assertTrue((work / "suppliers" / "Supplier-A" / "payment.json").exists())
            self.assertTrue((work / "suppliers" / "Supplier-B" / "vendor-risk.json").exists())


if __name__ == "__main__":
    unittest.main()
