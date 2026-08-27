# Decision Record Contract

Status: **Phase 2 proposal**  
Target: **scoped v1.1 follow-on**  
Parent issue: #6  
Implementation issue: #7

## Purpose

`supplier-scorecard` v1.0 remains the authoritative deterministic scoring core. The decision-record layer adds operational provenance, integrity and human-review metadata around the existing result without changing score calculation, recommendation bands, category weights or policy-gate semantics.

The record is intended to answer four audit questions:

1. What decision did the scorecard produce?
2. Which normalized inputs, profile and policy produced it?
3. Which exact retained artifacts and tool versions contributed to it?
4. Was the decision subject to human review after deterministic scoring?

## Invariants

- The embedded `result` is a normal v1.0 single-supplier or portfolio result.
- Adding or removing the wrapper must not change the v1.0 result.
- `REVIEW` and `BLOCKED` are never converted into contractual acceptance by the wrapper.
- Human-review metadata is operational state, not an additional hidden score.
- Confidential supplier/project data must not be committed to public fixtures.

## Envelope

```json
{
  "schema": "supplier-scorecard.decision-record",
  "schema_version": "1.0",
  "result": {},
  "provenance": {
    "scorecard": {
      "tool": "supplier-scorecard",
      "version": "1.0"
    },
    "profile": {
      "snapshot": {},
      "sha256": "..."
    },
    "policy": {
      "snapshot": {},
      "sha256": "..."
    },
    "artifacts": []
  },
  "review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "reviewed_at": null,
    "note": null
  },
  "integrity": {
    "algorithm": "sha256",
    "canonicalization": "json-sort-keys-compact-v1",
    "payload_sha256": "..."
  }
}
```

## Artifact provenance

Each retained artifact entry should use the following shape:

```json
{
  "role": "rfqdiff-output",
  "path": "pipeline-output/rfq.json",
  "tool": "rfqdiff",
  "version": "1.0",
  "sha256": "...",
  "retained": true
}
```

Rules:

- `sha256` is calculated from the exact file bytes when the artifact exists and is retained.
- A temporary/non-retained artifact is represented explicitly with `retained: false` and `sha256: null` rather than pretending provenance exists.
- Paths are operational references only; the hash is the integrity identity.
- Upstream tool/version metadata is recorded when present but must not be fabricated when absent.

## Profile and policy provenance

The resolved profile and final policy rules used by the scorecard are stored as snapshots. Their hashes are calculated from canonical JSON so a later profile-file edit cannot silently rewrite the historical decision context.

Canonical JSON for hashes uses UTF-8 encoded `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.

## Human review

`review.required` is derived from the deterministic outcome:

- `PASS` / auto-eligible result: `required = false`, initial `status = NOT_REQUIRED`.
- `REVIEW`: `required = true`, initial `status = PENDING`.
- `BLOCKED`: `required = true`, initial `status = PENDING`.

Allowed operational review states:

- `NOT_REQUIRED`
- `PENDING`
- `APPROVED_EXCEPTION`
- `REJECTED`

An `APPROVED_EXCEPTION` does not alter the embedded score or policy result. It records a human governance decision outside the scoring core.

## Integrity payload

`integrity.payload_sha256` is calculated over the complete record **excluding the `integrity` object itself**. This avoids recursive hashing while making changes to the result, provenance or review state detectable.

The wrapper hash is not a digital signature and does not prove who approved a decision. Signature/identity infrastructure is explicitly outside this first contract and may be added later as a separate scope.

## Compatibility

- v1.0 CLI/Python callers remain valid.
- Existing v1.0 result JSON remains valid and unchanged.
- Decision-record output should be opt-in in the first implementation.
- Single-supplier and portfolio modes use the same envelope, differing only in the embedded `result` shape.

## Acceptance gate for implementation

- Existing v1.0 tests continue to pass unchanged.
- New tests prove deterministic canonical hashing.
- New tests prove an artifact-byte change changes the artifact hash.
- New tests prove wrapper creation does not mutate the embedded result.
- New tests cover `NOT_REQUIRED` and `PENDING` review initialization.
- Documentation clearly states that provenance and review state do not modify scoring semantics.
