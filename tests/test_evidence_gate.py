"""Synthetic-only tests: no confidential RFQs or supplier quotations."""
import unittest
from supplier_scorecard.evidence_gate import assess_evidence


def complete():
    return {
        "supplier": "Synthetic Vendor", "quantity": 4,
        "equipment_total": 12000, "delivery": 500,
        "indicative_total": 12500, "currency": "GBP", "target_currency": "GBP",
        "quote_validity_confirmed": True, "technical_evidence_verified": True,
        "payment_terms_verified": True,
        "vendor_risk_evidence": {
            "on_time_delivery": 96, "defect_rate": 1,
            "compliance_incidents": 0, "dependency_share": 20,
        },
    }


class EvidenceGateTests(unittest.TestCase):
    def test_complete_synthetic_record_passes(self):
        self.assertTrue(assess_evidence(complete())["eligible_for_pipeline"])

    def test_missing_quote_and_technical_fail_closed(self):
        item = complete()
        item["quote_validity_confirmed"] = False
        item["technical_evidence_verified"] = False
        result = assess_evidence(item)
        self.assertFalse(result["eligible_for_pipeline"])
        self.assertIn("current_quote_unconfirmed", result["blockers"])
        self.assertIn("technical_evidence_unverified", result["blockers"])

    def test_missing_vendor_risk_never_imputed(self):
        item = complete()
        item["vendor_risk_evidence"] = None
        self.assertIn("vendor_risk_evidence_missing", assess_evidence(item)["blockers"])

    def test_cross_currency_requires_fx_provenance(self):
        item = complete()
        item["currency"] = "EUR"
        self.assertIn("fx_provenance_missing", assess_evidence(item)["blockers"])
        item["fx_rate_source"] = "Synthetic reference"
        item["fx_rate_timestamp"] = "2026-01-01T12:00:00Z"
        self.assertNotIn("fx_provenance_missing", assess_evidence(item)["blockers"])

    def test_inconsistent_total_is_blocked(self):
        item = complete()
        item["indicative_total"] = 12000
        self.assertIn("total_inconsistent", assess_evidence(item)["blockers"])

    def test_missing_payment_terms_is_blocked(self):
        item = complete()
        item["payment_terms_verified"] = False
        self.assertIn("payment_terms_unverified", assess_evidence(item)["blockers"])


if __name__ == "__main__":
    unittest.main()
