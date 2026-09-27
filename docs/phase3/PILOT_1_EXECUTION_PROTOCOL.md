# Phase 3 — Pilot 1 execution protocol (warehouse conveyor)

Status: execution-ready template; **not** a claim that a real pilot has been run.

## Data boundary
Keep original RFQs, supplier identities, quotations, contacts, payment details and decision records in an access-controlled private workspace. Do not commit them, their hashes when linkable, or identifiable excerpts to this public repository. Publish only synthetic examples or reviewed aggregate findings.

## Inputs to gather privately
- Procurement case ID, category, requirement revision and evaluation date.
- At least two independently received supplier quotations, each with currency, quotation date, validity, line items, quantity, scope, exclusions, delivery basis and lead time.
- Payment terms and any ambiguous commercial conditions.
- Available vendor-risk evidence with observation dates; missing evidence must remain missing, never fabricated.
- Technical requirement matrix: dimensions, throughput/handling constraints, deviations, clarifications and supporting evidence where available.
- Manual baseline: analyst preparation minutes, review minutes, touchpoints and unresolved questions.

## Execution checklist
1. Inventory source documents in private storage and record access/provenance.
2. Confirm comparable scope and quantities; flag missing/incomparable data before normalization.
3. Run currency-normalizer and retain source and FX provenance.
4. Run rfqdiff; inspect supplier mapping, criteria and quote-comparison explanations.
5. Run payment-terms-parser; if review is required or numeric exposure cannot be justified, preserve the fail-closed state.
6. Run vendor-risk-engine with dated evidence; do not infer history from one observation.
7. Include technical-compliance evidence only when supported; otherwise record unresolved human review.
8. Run supplier-scorecard-pipeline with the stable v1.1.0 release and an explicit category profile; retain the decision record and artifacts privately.
9. Independently verify decision-record integrity, source-to-supplier mapping and score/policy separation.
10. Have a human reviewer record the decision and rationale outside the scoring contract.
11. Compare elapsed effort and review findings with the manual baseline.

## Acceptance evidence
- All required inputs inventoried and gaps explicit.
- Repeat run on identical retained inputs produces an identical deterministic scoring result.
- Any policy hold is preserved even when the held supplier has the highest numeric score.
- Every material decision claim can be traced to private source evidence.
- Human reviewer records agreement/disagreement and reason.
- Preparation time and decision lead time are measured, not estimated retrospectively.

## Private result worksheet fields
Case ID; date; number of quotes; input completeness; category profile; tool versions; manual preparation minutes; assisted preparation minutes; manual decision lead time; assisted decision lead time; REVIEW/BLOCKED findings; useful findings confirmed by reviewer; false positives; false negatives; unresolved evidence; replay pass/fail; reviewer outcome; product gaps.

## Publication gate
Only release sanitized aggregate findings after checking that supplier, buyer, price and project details cannot be reconstructed. One pilot cannot justify changing frozen scoring weights or thresholds. Repeat the process for the generator and technical-forging cases before assessing Phase 3 exit criteria.
