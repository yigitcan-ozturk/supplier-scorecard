"""Offline integration test: bounded acquisition -> OCDS extraction -> coverage report.

Entirely invented publisher payload. This is NOT evidence of real public-data ingestion.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.phase3_download_find_tender import acquire
from scripts.phase3_extract_ocds import extract
from scripts.phase3_coverage_report import report


class _Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, data):
        self.data = data

    def read(self, size):
        return self.data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Phase3OfflinePipelineTests(unittest.TestCase):
    @patch("scripts.phase3_download_find_tender.urlopen")
    def test_download_extract_and_coverage_without_invented_bids(self, mock_urlopen):
        synthetic_package = {
            "publisher": {"uri": "https://example.org/synthetic-ocds"},
            "license": "https://example.org/synthetic-license",
            "releases": [{"ocid": "ocds-synthetic-1", "id": "r-1", "date": "2026-01-01T00:00:00Z",
                          "awards": [{"id": "a-1", "value": {"amount": 12500, "currency": "GBP"}}]}]
        }
        mock_urlopen.return_value = _Response(json.dumps(synthetic_package).encode())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw, manifest, records, coverage = [root / name for name in
                                                ("raw.json", "manifest.jsonl", "records.jsonl", "coverage.json")]
            acquire("2026-01-01T00:00:00", "2026-01-02T00:00:00", raw)
            extract(raw, manifest, records)
            report(records, coverage)
            result = json.loads(coverage.read_text())
            self.assertEqual(result["total_award_rows"], 1)
            self.assertEqual(result["observed_fields"]["award_amount"], 1)
            self.assertEqual(result["observed_fields"]["submitted_bid_price"], 0)
            self.assertEqual(result["missing_fields"]["payment_terms"], 1)
            self.assertFalse(result["real_private_multi_bid_pilot_validated"])
            self.assertEqual(len(json.loads(manifest.read_text().splitlines()[0])["raw_package_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
