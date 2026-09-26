"""Bounded acquisition of an official Find a Tender OCDS release package.

This helper is not used by CI and does not claim a successful live download.
Run locally with network access. API params verified against the publisher's docs:
https://www.find-tender.service.gov.uk/apidocumentation/1.0/GET-ocdsReleasePackages
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
MAX_BYTES = 8 * 1024 * 1024


def acquire(start, end, destination):
    # Reject malformed or unbounded collection windows before contacting the publisher.
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
        end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValueError("Date filters must use YYYY-MM-DDTHH:MM:SS") from exc
    if not start_dt < end_dt <= start_dt + timedelta(days=7):
        raise ValueError("Collection window must be positive and at most seven days")
    params = {"limit": 10, "updatedFrom": start, "updatedTo": end}
    url = ENDPOINT + "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "supplier-scorecard-research/1.0"})
    try:
        with urlopen(request, timeout=25) as response:
            if response.status != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Expected HTTP 200 JSON from official publisher")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Publisher download unavailable: {exc}") from exc
    if len(raw) > MAX_BYTES:
        raise ValueError("Download exceeds bounded sample size")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("releases"), list):
        raise ValueError("Expected OCDS release package")
    publisher = payload.get("publisher") or {}
    if not publisher.get("uri") or not payload.get("license"):
        raise ValueError("Missing source publisher URI or license; no provenance substitution")
    if not payload["releases"]:
        raise ValueError("No releases in requested period; try another bounded date range")
    Path(destination).write_bytes(raw)
    print(f"saved={destination} releases={len(payload['releases'])} source={url}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-date", required=True, help="YYYY-MM-DDTHH:MM:SS")
    p.add_argument("--to-date", required=True, help="YYYY-MM-DDTHH:MM:SS")
    p.add_argument("--output", default="raw-find-tender.json")
    a = p.parse_args()
    acquire(a.from_date, a.to_date, a.output)
