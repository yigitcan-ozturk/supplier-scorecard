"""Unit tests for offline OCDS extraction without external downloads."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.phase3_extract_ocds import extract


class OcdsExtractionTests(unittest.TestCase):
    def test_extract_preserves_unknowns_and_provenance(self):
        payload = {"publisher": {"uri": "https://example.org/fictional-publisher"},
                   "license": "https://example.org/fictional-license",
                   "releases": [{"ocid": "ocds-test-123", "id": "release-1",
                                 "date": "2026-01-02T00:00:00Z",
                                 "awards": [{"id": "award-1", "value": {"amount": 1234, "currency": "GBP"}}]}]}
        with tempfile.TemporaryDirectory() as tmp:
            raw, manifest, records = [Path(tmp) / name for name in ("raw.json", "manifest.jsonl", "records.jsonl")]
            raw.write_text(json.dumps(payload), encoding="utf-8")
            extract(raw, manifest, records)
            m = json.loads(manifest.read_text().splitlines()[0])
            r = json.loads(records.read_text().splitlines()[0])
            self.assertEqual(len(m["release_sha256"]), 64)
            self.assertEqual(m["ocid"], "ocds-test-123")
            self.assertEqual(r["award_amount"], 1234)
            self.assertIsNone(r["submitted_bid_price"])
            self.assertIsNone(r["payment_terms"])

    def test_missing_publisher_and_license_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            raw.write_text(json.dumps({"releases": [{"ocid": "test", "id": "x", "date": "2026-01-01"}]}))
            with self.assertRaises(ValueError):
                extract(raw, Path(tmp) / "manifest", Path(tmp) / "records")


if __name__ == "__main__":
    unittest.main()
