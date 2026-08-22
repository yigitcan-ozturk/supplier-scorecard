import tomllib
import unittest
from pathlib import Path

import supplier_scorecard


class PackagingContractTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self):
        metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["version"], supplier_scorecard.__version__)

    def test_public_api_exposes_stable_engine(self):
        result = supplier_scorecard.score_supplier("Supplier A", 90, 10, 20)
        self.assertEqual(result["version"], "1.0")
        self.assertEqual(result["supplier"], "Supplier A")


if __name__ == "__main__":
    unittest.main()
