"""Validate the independent Phase 3 synthetic fixture's declared invariants.

These tests check fixture integrity, not end-to-end supplier-scorecard behavior.
They intentionally avoid inventing upstream risk signals or asserting pilot success.
"""
import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "samples/phase3/synthetic-incomparable-offers.json"


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_is_explicitly_synthetic():
    data = _load()
    assert data["synthetic"] is True
    assert len(data["offers"]) == 4
    assert len({offer["id"] for offer in data["offers"]}) == 4
    assert all(offer["id"].startswith("SYN-") for offer in data["offers"])


def test_known_landed_costs_and_unknown_delivery():
    data = _load()
    for offer in data["offers"]:
        expected = data["expected_known_landed_cost_gbp"][offer["id"]]
        actual = (offer["unit_price_gbp"] * offer["quantity"] + offer["delivery_gbp"]
                  if offer["delivery_gbp"] is not None else None)
        assert actual == expected
    assert "LANDED_COST_INCOMPARABLE" in data["expected_review_flags"]["SYN-B"]


def test_technical_deviation_and_ambiguous_terms_are_visible():
    data = _load()
    by_id = {offer["id"]: offer for offer in data["offers"]}
    assert by_id["SYN-C"]["width_mm"] < data["requirement"]["minimum_width_mm"]
    assert "DIMENSIONAL_DEVIATION_REQUIRES_ENGINEERING_APPROVAL" in data["expected_review_flags"]["SYN-C"]
    assert by_id["SYN-D"]["payment_risk_numeric"] is None
    assert "FAIL_CLOSED_UNTIL_VALID_RISK_SIGNAL" in data["expected_review_flags"]["SYN-D"]


def test_no_vendor_risk_is_fabricated():
    data = _load()
    assert all(offer["vendor_risk_numeric"] is None for offer in data["offers"])
