"""Opt-in evidence gate for real quotation pilots.

This adapter is deliberately outside the frozen v1.0 scoring contract.
It never invents vendor-risk, technical-compliance or FX signals.
"""
from __future__ import annotations

REQUIRED_VENDOR_FIELDS = (
    "on_time_delivery", "defect_rate", "compliance_incidents", "dependency_share"
)


def assess_evidence(record: dict) -> dict:
    """Return explicit blockers before constructing a scorecard pipeline input."""
    blockers = []
    if not record.get("supplier"):
        blockers.append("supplier_identity_missing")
    if record.get("quantity") is None or record["quantity"] <= 0:
        blockers.append("quantity_missing_or_invalid")
    if record.get("equipment_total") is None:
        blockers.append("equipment_total_missing")
    if record.get("delivery") is None:
        blockers.append("delivery_cost_missing")
    if record.get("equipment_total") is not None and record.get("delivery") is not None:
        expected = round(record["equipment_total"] + record["delivery"], 2)
        if record.get("indicative_total") is None or abs(record["indicative_total"] - expected) > 0.01:
            blockers.append("total_inconsistent")
    if record.get("currency") not in {"GBP", "EUR", "USD"}:
        blockers.append("currency_missing_or_unsupported")
    if record.get("currency") != record.get("target_currency"):
        if not record.get("fx_rate_source") or not record.get("fx_rate_timestamp"):
            blockers.append("fx_provenance_missing")
    if record.get("quote_validity_confirmed") is not True:
        blockers.append("current_quote_unconfirmed")
    if record.get("technical_evidence_verified") is not True:
        blockers.append("technical_evidence_unverified")
    if record.get("payment_terms_verified") is not True:
        blockers.append("payment_terms_unverified")
    vendor = record.get("vendor_risk_evidence")
    if not isinstance(vendor, dict) or any(vendor.get(key) is None for key in REQUIRED_VENDOR_FIELDS):
        blockers.append("vendor_risk_evidence_missing")
    return {"supplier": record.get("supplier"), "eligible_for_pipeline": not blockers, "blockers": blockers}
