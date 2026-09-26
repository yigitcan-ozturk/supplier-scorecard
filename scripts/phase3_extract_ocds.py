"""Offline, fail-closed OCDS release extraction for Phase 3 public-data research.

Usage: python scripts/phase3_extract_ocds.py raw.json source_manifest.jsonl public_records.jsonl
Raw JSON must be obtained separately from the publisher. This script never fetches URLs.
Award values are NOT supplier quotation prices. No score or pilot success is inferred.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def releases_from(payload):
    if isinstance(payload, dict) and isinstance(payload.get("releases"), list):
        return payload["releases"]
    if isinstance(payload, dict) and isinstance(payload.get("records"), list):
        return [r for record in payload["records"] for r in record.get("releases", [])]
    if isinstance(payload, dict) and payload.get("ocid") and payload.get("id"):
        return [payload]
    raise ValueError("Expected OCDS release, release package or record package")


def extract(raw_path, manifest_path, records_path):
    raw = Path(raw_path).read_bytes()
    payload = json.loads(raw)
    publisher = payload.get("publisher", {}) if isinstance(payload, dict) else {}
    source = publisher.get("uri")
    license_url = payload.get("license") if isinstance(payload, dict) else None
    if not source or not license_url:
        raise ValueError("Publisher URI and license must be present in package metadata; do not invent provenance")
    releases = releases_from(payload)
    if not releases:
        raise ValueError("No releases found")
    manifest, records = [], []
    for release in releases:
        ocid, rid, date = release.get("ocid"), release.get("id"), release.get("date")
        if not all((ocid, rid, date)):
            raise ValueError("Missing OCID, release ID or release date")
        canonical = json.dumps(release, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        manifest.append({"ocid": ocid, "release_id": rid, "publication_date": date,
                         "publisher_uri": source, "license": license_url,
                         "raw_package_sha256": hashlib.sha256(raw).hexdigest(),
                         "release_sha256": hashlib.sha256(canonical).hexdigest(),
                         "extracted_at_utc": datetime.now(timezone.utc).isoformat()})
        awards = release.get("awards") or []
        for award in awards:
            value = award.get("value") or {}
            records.append({"ocid": ocid, "release_id": rid, "award_id": award.get("id"),
                            "publication_date": date, "award_amount": value.get("amount"),
                            "award_currency": value.get("currency"),
                            "submitted_bid_price": None, "payment_terms": None,
                            "delivery_cost": None, "technical_compliance": None,
                            "supplier_risk": None})
    for target, rows in [(manifest_path, manifest), (records_path, records)]:
        Path(target).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    print(f"validated_releases={len(manifest)} published_awards={len(records)}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: phase3_extract_ocds.py raw.json manifest.jsonl records.jsonl")
    extract(*sys.argv[1:])
