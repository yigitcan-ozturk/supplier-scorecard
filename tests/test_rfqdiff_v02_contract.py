import unittest

import main as scorecard


class RfqdiffV02ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "tool": "rfqdiff",
            "version": "0.2",
            "currency": "EUR",
            "recommended_supplier": "Crest Manufacturing",
            "suppliers": [
                {
                    "name": "Crest Manufacturing",
                    "currency": "EUR",
                    "price": 124800,
                    "lead_time_weeks": 5,
                    "payment_days": 60,
                    "score": 93.5,
                    "score_breakdown": {
                        "price": 43.5,
                        "lead_time": 30.0,
                        "payment_terms": 20.0,
                    },
                    "rfqdiff_source": {
                        "file": "industrial-rfq.csv",
                        "format": "csv",
                        "sha256": "c0627382a79415ec0daf90335d28d9a1b906366aae60e90b5c463d5f02982ed8",
                        "row": 4,
                    },
                },
                {
                    "name": "Alpha Components",
                    "currency": "EUR",
                    "price": 118400,
                    "lead_time_weeks": 6,
                    "payment_days": 30,
                    "score": 80.8,
                    "score_breakdown": {
                        "price": 45.8,
                        "lead_time": 25.0,
                        "payment_terms": 10.0,
                    },
                    "rfqdiff_source": {
                        "file": "industrial-rfq.csv",
                        "format": "csv",
                        "sha256": "c0627382a79415ec0daf90335d28d9a1b906366aae60e90b5c463d5f02982ed8",
                        "row": 2,
                    },
                },
            ],
            "decision_summary": {
                "recommended_supplier": {
                    "name": "Crest Manufacturing",
                    "score": 93.5,
                },
                "runner_up": {"name": "Alpha Components", "score": 80.8},
                "score_margin": 12.7,
            },
            "decision_explanation": {
                "winner": "Crest Manufacturing",
                "runner_up": "Alpha Components",
                "score_margin": 12.7,
                "winner_score_breakdown": {
                    "price": 43.5,
                    "lead_time": 30.0,
                    "payment_terms": 20.0,
                },
                "criterion_leaders": {
                    "price": "Delta Engineering",
                    "lead_time": "Crest Manufacturing",
                    "payment_terms": "Crest Manufacturing",
                },
            },
            "weights": {
                "price": 0.5,
                "lead_time": 0.3,
                "payment_terms": 0.2,
            },
        }

    def test_extract_rfq_score_accepts_v02_additive_payload(self) -> None:
        self.assertEqual(
            scorecard.extract_rfq_score(self.payload, "Crest Manufacturing"),
            93.5,
        )
        self.assertEqual(
            scorecard.extract_rfq_score(self.payload, "alpha components"),
            80.8,
        )

    def test_additive_v02_fields_do_not_change_score_consumption(self) -> None:
        supplier = self.payload["suppliers"][0]
        supplier["future_additive_metadata"] = {"trace": "safe-to-ignore"}
        self.payload["future_top_level_metadata"] = {"contract": "additive"}

        self.assertEqual(
            scorecard.extract_rfq_score(self.payload, "Crest Manufacturing"),
            93.5,
        )

    def test_contract_still_rejects_missing_supplier_list(self) -> None:
        with self.assertRaisesRegex(ValueError, "'suppliers' list"):
            scorecard.extract_rfq_score({"tool": "rfqdiff", "version": "0.2"}, "Supplier A")


if __name__ == "__main__":
    unittest.main()
