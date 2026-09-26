# Phase 3 — verified public OCDS acquisition runbook

Official UK publication guidance: https://www.gov.uk/government/publications/open-contracting
Official Find a Tender OCDS release-package endpoint: https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages
Official Contracts Finder API documentation: https://www.contractsfinder.service.gov.uk/apidocumentation/
OCDS standard explanation (release vs record): https://standard.open-contracting.org/latest/en/primer/releases_and_records/

## Status / boundaries
- Official sources and endpoint documentation identified. **No real records have yet been ingested or independently verified in this repository.**
- Previous CI success validates synthetic tests and the offline extractor, **not live API accessibility**.
- Public award values are not submitted bids. A procurement award notice cannot substitute for original competing supplier offers in the private pilot.

## Acquisition procedure
1. Open the official Find a Tender API help from the UK government guidance; confirm the live API's currently supported query parameters and pagination before requesting a bounded date range. Do not assume an undocumented `limit` parameter.
2. Download one *small* release package in its original JSON representation. Keep its complete metadata, including publisher URI and license. If the endpoint response omits required provenance, stop and log that limitation rather than synthesizing a publisher or license.
3. Check that the JSON contains a release package (`releases`) and that the source, OCIDs, release IDs and publication dates are actually present.
4. In a private/local working directory, run:
   `python scripts/phase3_extract_ocds.py raw.json source_manifest.jsonl public_records.jsonl`
5. Review manifest and sanitized award output. Only publish a small subset after source/license and privacy checks; retain the raw source file and SHA-256 manifest in the reproducibility archive.
6. Capture total releases, award rows, award-value coverage, currency coverage, absent competing bids and absent payment/technical/delivery data in the coverage report.
7. Run `python -m unittest discover -s tests -v` and retain the GitHub Actions run URL with the commit SHA.

## Stop conditions
- Source returns HTML, authentication challenge, error or unexpectedly large file.
- License/publisher missing, unverifiable original notice, or incomplete release IDs.
- Extraction would convert award values into quotation prices or infer unobserved commercial terms.

## Independent acceptance
Public-data ingestion is verified only after at least one *real* source release package is downloaded, parsed, hashed, reviewed and its source URL and retrieval date are recorded. Synthetic fixture CI alone does not satisfy this gate.
