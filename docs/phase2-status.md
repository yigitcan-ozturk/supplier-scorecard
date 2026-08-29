# Phase 2 status

This branch integrates the frozen v1.0 scoring core with the scoped operational Phase 2 work.

## Included

- payment-term review safety from `main`;
- decision-record contract;
- SHA-256 artifact provenance;
- deterministic decision payload integrity;
- initial human-review state;
- installed pipeline CLI `--decision-record` output;
- tests for record integrity and CLI artifact capture.

## Remaining before merge

- run CI on the integrated branch;
- execute the sanitized three-supplier engineering procurement pilot from issue #9;
- update public README/release notes after the pilot proves the flow;
- close issue #7 only after the integrated acceptance criteria pass.

The v1.0 weights, score bands, category semantics and policy gates remain unchanged.
