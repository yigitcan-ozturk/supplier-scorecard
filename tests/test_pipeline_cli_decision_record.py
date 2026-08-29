import json
import tempfile
import unittest
from pathlib import Path

from supplier_scorecard import pipeline_cli
from supplier_scorecard.decision_record import create_decision_record, verify_decision_record


class PipelineCliDecisionRecordTests(unittest.TestCase):
    def test_parser_exposes_opt_in_decision_record_path(self):
        args = pipeline_cli.build_parser().parse_args(
            ["input.json", "--decision-record", "decision-record.json"]
        )
        self.assertEqual(args.decision_record, "decision-record.json")

    def test_single_retained_pipeline_artifacts_are_hashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            rfq = root / "rfq.json"
            payment = root / "payment.json"
            vendor = root / "vendor.json"
            for path, payload in (
                (input_path, {"input": True}),
                (rfq, {"rfq": True}),
                (payment, {"payment": True}),
                (vendor, {"vendor": True}),
            ):
                path.write_text(json.dumps(payload), encoding="utf-8")

            result = {
                "tool": "supplier-scorecard",
                "version": "1.0",
                "supplier": "Supplier A",
                "profile": {"name": "critical-machining", "policy": {}},
                "policy": {"status": "PASS", "rules": {}},
                "sources": {
                    "rfqdiff": {"version": "1.0"},
                    "payment_terms_parser": {"version": "0.3"},
                    "vendor_risk_engine": {"version": "1.0"},
                },
                "orchestration": {
                    "mode": "single",
                    "artifacts": {
                        "rfq": str(rfq),
                        "payment": str(payment),
                        "vendor_risk": str(vendor),
                    },
                },
            }
            artifacts = pipeline_cli._artifact_records(result, input_path=input_path)
            self.assertEqual(len(artifacts), 4)
            self.assertTrue(all(item["retained"] for item in artifacts))
            self.assertTrue(all(item["sha256"] for item in artifacts))
            record = create_decision_record(result, artifacts=artifacts)
            self.assertTrue(verify_decision_record(record)["valid"])

    def test_vendor_version_falls_back_to_engine_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vendor = root / "vendor.json"
            vendor.write_text(
                json.dumps({"meta": {"engine_version": "0.5.0"}}),
                encoding="utf-8",
            )
            version = pipeline_cli._source_version(
                {"sources": {"vendor_risk_engine": {"version": None}}},
                "vendor_risk_engine",
                path=vendor,
            )
            self.assertEqual(version, "0.5.0")

    def test_currency_normalizer_outputs_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            rfq = root / "rfq.json"
            normalized = root / "quote-1-normalized.json"
            payment = root / "payment.json"
            vendor = root / "vendor.json"
            input_path.write_text("{}", encoding="utf-8")
            rfq.write_text("{}", encoding="utf-8")
            normalized.write_text(
                json.dumps({"normalization": {"version": "0.3.0"}}),
                encoding="utf-8",
            )
            payment.write_text("{}", encoding="utf-8")
            vendor.write_text("{}", encoding="utf-8")

            result = {
                "tool": "supplier-scorecard",
                "version": "1.0",
                "supplier": "Supplier A",
                "profile": {"name": "critical-machining", "policy": {}},
                "policy": {"status": "PASS", "rules": {}},
                "sources": {},
                "orchestration": {
                    "mode": "single",
                    "artifacts": {
                        "rfq": str(rfq),
                        "payment": str(payment),
                        "vendor_risk": str(vendor),
                    },
                },
            }
            artifacts = pipeline_cli._artifact_records(result, input_path=input_path)
            currency = [item for item in artifacts if item["tool"] == "currency-normalizer"]
            self.assertEqual(len(currency), 1)
            self.assertEqual(currency[0]["version"], "0.3.0")
            self.assertTrue(currency[0]["sha256"])

    def test_temporary_outputs_are_explicitly_non_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            input_path.write_text("{}", encoding="utf-8")
            result = {
                "tool": "supplier-scorecard-portfolio",
                "version": "1.0",
                "recommended_supplier": None,
                "decision_status": "NO AUTO-APPROVED SUPPLIER",
                "profile": {"name": "critical-machining", "policy": {}},
                "policy": {},
                "suppliers": [],
                "orchestration": {
                    "mode": "portfolio",
                    "artifacts": {"rfq": "temporary", "supplier_outputs": "temporary"},
                },
            }
            artifacts = pipeline_cli._artifact_records(result, input_path=input_path)
            temporary = [item for item in artifacts if item["path"] == "temporary"]
            self.assertEqual(len(temporary), 3)
            self.assertTrue(all(not item["retained"] for item in temporary))
            self.assertTrue(all(item["sha256"] is None for item in temporary))

    def test_portfolio_expands_supplier_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "input.json"
            rfq = root / "rfq.json"
            input_path.write_text("{}", encoding="utf-8")
            rfq.write_text("{}", encoding="utf-8")
            supplier_outputs = {}
            suppliers = []
            for name in ("Supplier A", "Supplier B"):
                safe = name.replace(" ", "-")
                payment = root / f"{safe}-payment.json"
                vendor = root / f"{safe}-vendor.json"
                payment.write_text("{}", encoding="utf-8")
                vendor.write_text("{}", encoding="utf-8")
                supplier_outputs[name] = {"payment": str(payment), "vendor_risk": str(vendor)}
                suppliers.append(
                    {
                        "supplier": name,
                        "sources": {
                            "payment_terms_parser": {"version": "0.3"},
                            "vendor_risk_engine": {"version": "1.0"},
                            "rfqdiff": {"version": "1.0"},
                        },
                    }
                )

            result = {
                "tool": "supplier-scorecard-portfolio",
                "version": "1.0",
                "recommended_supplier": "Supplier B",
                "decision_status": "AUTO-RECOMMENDED",
                "profile": {"name": "critical-machining", "policy": {}},
                "policy": {},
                "suppliers": suppliers,
                "orchestration": {
                    "mode": "portfolio",
                    "artifacts": {"rfq": str(rfq), "supplier_outputs": supplier_outputs},
                },
            }
            artifacts = pipeline_cli._artifact_records(result, input_path=input_path)
            roles = {item["role"] for item in artifacts}
            self.assertIn("payment-terms-output:Supplier A", roles)
            self.assertIn("vendor-risk-output:Supplier A", roles)
            self.assertIn("payment-terms-output:Supplier B", roles)
            self.assertIn("vendor-risk-output:Supplier B", roles)
            self.assertEqual(len(artifacts), 6)


if __name__ == "__main__":
    unittest.main()
