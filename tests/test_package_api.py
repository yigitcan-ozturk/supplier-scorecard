import unittest

import supplier_scorecard


class PackageApiTests(unittest.TestCase):
    def test_package_version(self):
        self.assertEqual(supplier_scorecard.__version__, "1.1.0")
        self.assertEqual(supplier_scorecard.VERSION, "1.0")

    def test_public_scoring_api(self):
        result = supplier_scorecard.score_supplier("Supplier A", 92, 10, 12)
        self.assertEqual(result["supplier"], "Supplier A")
        self.assertEqual(result["final_decision"], "PREFERRED")
        self.assertEqual(result["version"], "1.0")

    def test_public_profile_api(self):
        profile = supplier_scorecard.get_category_profile("critical-machining")
        self.assertEqual(profile["name"], "critical-machining")
        self.assertIn("technical", profile["weights"])


if __name__ == "__main__":
    unittest.main()
