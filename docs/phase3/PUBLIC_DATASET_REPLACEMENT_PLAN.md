# Phase 3 — Public dataset replacement selection (2026-09-26)

Purpose: supplement unavailable/expired historical uploads with independently sourced public procurement records. Public notices are **not** substitutes for confidential, original multi-supplier RFQ quotations. Do not claim real multi-bid pilot completion from award notices.

## Selected sources

1. **Primary: UK Contracts Finder OCDS (2026)** — https://data.open-contracting.org/en/publication/128 ; original publisher API https://www.contractsfinder.service.gov.uk/apidocumentation/ . Open Government Licence v3.0 as listed by registry. Select a small set of completed procurement processes with a documented notice URL, OCID, buyer, category, publication date, award amount/currency and named awardee when available. Preserve raw records and provenance privately or in a dedicated appropriately licensed dataset location; do not blindly commit large dumps.
2. **Secondary: UK Find a Tender OCDS (2026)** — https://data.open-contracting.org/en/publication/41 ; publisher guidance https://www.gov.uk/government/publications/open-contracting . Select a disjoint or deliberately matched sample; preserve exact OCID and notice/release IDs. Flag missing supplier IDs and inconsistent date fields.
3. **Exploratory: UK OpenTender** — https://data.open-contracting.org/en/publication/92 . Use only if bid-level fields are actually present and the exact release has a verifiable original notice and reuse terms. Do not infer losing bid prices from awards.

## Inclusion gates
- Exact source record URL, publication date, publisher, licensing and immutable/raw capture available.
- Real published record with procurement category, buyer, tender or award and GBP value when present.
- No personal contact details in public fixture outputs; minimize fields.
- Separate known values from unknown fields; preserve missingness and original currency.
- Do not equate awarded contract amount with individual submitted quotation price.

## Target sample (not yet collected)
- Contracts Finder: 10 verified notices, including 3 engineering/equipment procurements if discoverable.
- Find a Tender: 5 independently verified notices, including 2 comparable categories if discoverable.
- OpenTender: 3 exploratory records **only** when actual bid fields are verified; otherwise record unsupported and do not fill.

## Reproducible extraction outputs
- source_manifest.jsonl: source URL, retrieval timestamp, license, record ID/OCID, publication date, record hash, inclusion reason.
- sanitized_public_records.jsonl: category, published amount/currency, dates and documented supplier identifier only when legally and operationally appropriate.
- coverage_report.json: counts and field coverage for quotation price, award amount, payment terms, technical compliance, delivery, vendor-risk evidence and competing bids. Every unsupported field is null/unknown, not zero.

## Validation tracks
A. **Public record ingestion/provenance:** parse and normalize the actual public records; check hashes, currency fields, date handling and missingness. No claim of multi-bid scoring validation.
B. **Synthetic multi-offer scoring:** run separately against independently invented offers in samples/phase3/synthetic-incomparable-offers.json and exercise missing delivery, dimensional review and ambiguous payment gating.
C. **Private real RFQ pilot:** original multiple supplier quotes, human-review outcomes and measured time baseline required. Public notices cannot satisfy this gate.

## Completion gates
Mark public dataset selection complete only after actual records are downloaded, provenance captured and extraction tests pass. Mark Phase 3 real pilot complete only after the private end-to-end evaluation and reviewer signoff; documentation and green fixture CI are insufficient.
