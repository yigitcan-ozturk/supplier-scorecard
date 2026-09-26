# Phase 3 release gate — evidence-based status

This checklist is a release gate, not a claim of completed real-world validation. The v1.0 scoring baseline stays frozen.

| Gate | Current evidence | Status |
| --- | --- | --- |
| Synthetic fixture and fail-closed unit tests | PR #26, CI #139 (Python 3.11/3.12/3.13) | PASS |
| Synthetic download to extraction to coverage integration | Offline mocked transport test in PR #26 | PASS (synthetic only) |
| Manual-only public acquisition workflow | Phase 3 workflow and static workflow tests | IMPLEMENTED; not live-run verified |
| Official real OCDS package acquired | No successful publisher download established | BLOCKED |
| Real public data provenance and coverage | Requires downloaded package, manifest and coverage artifact | NOT VERIFIED |
| Four-supplier private pilot | Protocol and sanitized report template only; complete actual comparison unverified | NOT VERIFIED |
| Product/commercial acceptance | Requires pilot findings, user review and release decision | NOT VERIFIED |

## Next execution sequence

1. Review PR #26; keep Draft until workflow and release criteria are accepted. Existing stable release is unchanged.
2. After an approved merge, manually run Phase 3 Public OCDS Acquisition with a bounded date range. Successful unit tests do not prove publisher reachability.
3. Inspect publisher response, license, raw SHA-256, release manifest, award coverage and artifacts. Never reclassify published award amounts as competing supplier quotations.
4. If publisher access fails, record the HTTP error and obtain an official release package by a permitted alternate official distribution method; never fabricate or silently replace the source.
5. Execute the real RFQ pilot privately, resolve missing delivery, payment and technical fields, and publish only a reviewed sanitized report.
6. Make a separate release decision once both public-data and private-pilot evidence have been reviewed.

Privacy: Never commit customer names, supplier quotations, original attachments, addresses or commercially sensitive RFQ details to the public repository.
