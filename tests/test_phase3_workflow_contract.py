"""Guardrails for the manually triggered Phase 3 public-data workflow.

Static checks complement (but do not replace) a real GitHub workflow_dispatch run.
"""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/phase3-public-ocds.yml"


class Phase3WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_and_read_only_repository_permissions(self):
        self.assertIn("workflow_dispatch:", self.source)
        self.assertNotIn("pull_request:", self.source)
        self.assertNotIn("schedule:", self.source)
        self.assertIn("contents: read", self.source)

    def test_evidence_chain_is_present_and_short_lived(self):
        for required in (
            "phase3_download_find_tender.py",
            "phase3_extract_ocds.py",
            "phase3_coverage_report.py",
            "retention-days: 7",
            "if-no-files-found: error",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)


if __name__ == "__main__":
    unittest.main()
