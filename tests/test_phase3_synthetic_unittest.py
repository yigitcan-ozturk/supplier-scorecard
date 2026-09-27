"""unittest discovery coverage for independently synthetic Phase 3 input fixture.

This checks fixture integrity only, not toolchain integration or a real pilot.
"""
import json
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "samples/phase3/synthetic-incomparable-offers.json"


class Phase3SyntheticFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls.offers = {offer["id"]: offer for offer in cls.data["offers"]}

    def test_fixture_is_independently_synthetic(self):
        self.assertIs(self.data["synthetic"], True)
        self.assertEqual(len(self.offers), 4)
        self.assertEqual(set(self.offers), {"SYN-A", "SYN-B", "SYN-C", "SYN-D"})

    def test_landed_cost_never_assumes_free_delivery(self):
        for offer in self.offers.values():
            actual = (offer["unit_price_gbp"] * offer["quantity"] + offer["delivery_gbp"]
                      if offer["delivery_gbp"] is not None else None)
            self.assertEqual(actual, self.data["expected_known_landed_cost_gbp"][offer["id"]])
        self.assertIn("LANDED_COST_INCOMPARABLE", self.data["expected_review_flags"]["SYN-B"])

    def test_dimension_deviation_requires_engineering_review(self):
        self.assertLess(self.offers["SYN-C"]["width_mm"], self.data["requirement"]["minimum_width_mm"])
        self.assertIn("DIMENSIONAL_DEVIATION_REQUIRES_ENGINEERING_APPROVAL",
                      self.data["expected_review_flags"]["SYN-C"])

    def test_ambiguous_payment_terms_fail_closed(self):
        self.assertIsNone(self.offers["SYN-D"]["payment_risk_numeric"])
        self.assertIn("FAIL_CLOSED_UNTIL_VALID_RISK_SIGNAL",
                      self.data["expected_review_flags"]["SYN-D"])

    def test_missing_vendor_risk_is_not_fabricated(self):
        self.assertTrue(all(offer["vendor_risk_numeric"] is None for offer in self.offers.values()))


if __name__ == "__main__":
    unittest.main()
