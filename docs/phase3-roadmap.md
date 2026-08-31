# Phase 3 — Pilot → Product

Status: **active**  
Parent issue: #19

## Objective

Turn the technically complete `supplier-scorecard v1.1.0` into a commercially credible procurement product through real-world pilot evidence, a minimal unified product surface and a repeatable paid-pilot proposition.

## Core guardrail

The deterministic scoring/result contract remains version `1.0`.

Phase 3 does not change weights, recommendation bands, category semantics or policy gates unless repeated pilot evidence identifies a concrete decision-quality failure that cannot be solved at the workflow/data-quality layer.

## Workstreams

### A. Real procurement pilots — #20

Run 3–5 confidential engineering procurement cases.

For each case, record privately:

- category and buying context;
- supplier count;
- quotation/payment/vendor/technical evidence availability;
- baseline manual process and effort;
- scorecard result and policy outcome;
- human review outcome;
- final operational decision;
- data gaps and false-positive/false-negative observations.

Public repository output is limited to sanitized aggregate findings.

### B. Product surface — #21

Expose the full decision flow as one procurement system:

`RFQ → normalization → quotation → payment → vendor risk → technical compliance → ranking/policy → decision record → human review`

The minimum surface should include:

- one procurement-case/RFQ workflow;
- supplier evidence ingestion;
- ranking and policy state;
- evidence drill-down;
- review queue;
- decision explanation;
- provenance/integrity panel;
- exportable decision record.

The API/application layer must call the deterministic core rather than duplicating scoring logic.

### C. Commercial package — #22

Develop an evidence-backed paid-pilot proposition for engineering procurement teams.

Before final pricing, validate:

- RFQ volume;
- suppliers per RFQ;
- analyst hours per evaluation;
- sourcing criticality/value;
- audit/review burden;
- deployment preference;
- buyer perception of value from speed, auditability and risk detection.

## Phase 3 metrics

### Operational efficiency

- baseline manual preparation time;
- assisted preparation time;
- baseline decision lead time;
- assisted decision lead time;
- spreadsheet/manual touch points avoided.

### Decision quality

- REVIEW/BLOCKED findings surfaced;
- data-quality problems surfaced;
- findings judged useful by human reviewer;
- missed-risk observations;
- unnecessary-review observations.

### Auditability

- decision record generated for each case;
- retained evidence integrity verification;
- reproducibility from retained inputs;
- explicit human-review state when required.

### Commercial evidence

- qualified buyer conversations;
- pilot willingness;
- willingness-to-pay evidence;
- deployment/security objections;
- recurring integration requirements.

## Exit criteria

Phase 3 is complete when:

1. at least 3 real confidential pilot cases are completed;
2. a measurable operational-efficiency or decision-quality benefit is demonstrated;
3. one end-to-end pilot can be completed through the unified product surface;
4. a sanitized demo mirrors the real workflow;
5. a bounded paid-pilot proposition exists;
6. market feedback supports a specific commercial model or provides clear no-go evidence;
7. any proposed v1.2 engineering scope is tied to repeated evidence rather than speculative features.

## Non-goals

- ERP replacement;
- automated contract award;
- opaque ML supplier ranking;
- public storage of real supplier/customer/project data;
- feature expansion without pilot evidence.

## Product principle

Supplier Scorecard should sell **explainable procurement decision infrastructure**: independent evidence, explicit policy, human governance and reproducible decisions.
