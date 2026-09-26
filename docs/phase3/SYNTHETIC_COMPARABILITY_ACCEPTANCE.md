# Phase 3 — public synthetic acceptance scenario: incomparable offers

This is a **synthetic contract-test specification**, not a real procurement result. All values and supplier names in future fixtures must be invented independently of private offers.

## Scenario
Four synthetic suppliers respond to one engineered procurement requirement. Inputs deliberately include: (A) complete offer with delivery included; (B) lower unit price but delivery cost unknown; (C) alternative dimensions requiring engineering approval; (D) ambiguous payment terms requiring human review.

## Required assertions
- Missing delivery cost must not be silently normalized to zero or treated as fully comparable landed cost.
- Dimensional deviation must remain visible as technical review, never be erased by price ranking.
- Ambiguous payment terms without a defensible numeric risk must fail closed.
- Numerical rank and policy eligibility must remain separate outputs.
- No invented vendor-risk history or technical-compliance score is permitted when evidence is absent.
- Decision record preserves resolved profile/policy and provenance for all retained artifacts.
- Repeated execution with identical retained inputs produces identical deterministic scoring outputs.

## Evidence needed before calling this implemented
- A fully synthetic machine-readable fixture and its expected outcomes.
- Tests covering each assertion above, run in CI.
- No regression to the frozen v1.0 scoring contract.

Status: specification only; tests are not yet implemented by this document.
