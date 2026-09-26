"""Network-free tests for bounded Find a Tender acquisition.

No live publisher download is claimed. The transport is mocked so CI remains deterministic.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.phase3_download_find_tender import acquire, MAX_BYTES


class FakeResponse:
    def __init__(self, body, content_type="application/json", status=200):
        self._stream = io.BytesIO(body)
        self.headers = {"Content-Type": content_type}
        self.status = status

    def read(self, size):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class FindTenderDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "raw.json"

    def _acquire(self):
        return acquire("2026-01-01T00:00:00", "2026-01-02T00:00:00", self.target)

    @patch("scripts.phase3_download_find_tender.urlopen")
    def test_valid_bounded_release_is_saved(self, mock_urlopen):
        payload = {"publisher": {"uri": "https://example.org/test"},
                   "license": "https://example.org/license",
                   "releases": [{"ocid": "ocds-test-1", "id": "release-1", "date": "2026-01-01"}]}
        mock_urlopen.return_value = FakeResponse(json.dumps(payload).encode())
        self._acquire()
        self.assertEqual(json.loads(self.target.read_text()), payload)
        request = mock_urlopen.call_args.args[0]
        self.assertIn("limit=10", request.full_url)

    @patch("scripts.phase3_download_find_tender.urlopen")
    def test_html_response_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b"<html>blocked</html>", "text/html")
        with self.assertRaises(ValueError):
            self._acquire()
        self.assertFalse(self.target.exists())

    @patch("scripts.phase3_download_find_tender.urlopen")
    def test_missing_provenance_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b'{"releases":[{"id":"test"}]}')
        with self.assertRaises(ValueError):
            self._acquire()
        self.assertFalse(self.target.exists())

    @patch("scripts.phase3_download_find_tender.urlopen")
    def test_oversized_response_is_rejected(self, mock_urlopen):
        mock_urlopen.return_value = FakeResponse(b"x" * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            self._acquire()
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
