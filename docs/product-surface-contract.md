# Product Surface Contract

Status: **Phase 3 design contract**  
Issue: #21  
Parent: #19

## Purpose

Expose Supplier Scorecard as one procurement decision workflow without duplicating or hiding deterministic scoring logic in a new application layer.

The product surface may orchestrate, persist and present decisions. It must not become a second scoring engine.

## Core resources

### ProcurementCase

Represents one RFQ / supplier-evaluation process.

Required conceptual fields:

- `case_id`
- `title`
- `category`
- `status`
- `created_at`
- `created_by`
- `profile_reference`
- `supplier_count`
- `latest_decision_record_id`

Suggested lifecycle:

`DRAFT → EVIDENCE_READY → EVALUATED → REVIEW_REQUIRED | DECISION_READY → CLOSED`

### SupplierSubmission

Represents one supplier's evidence package for a case.

Conceptual fields:

- `submission_id`
- `case_id`
- `supplier_reference`
- `quotation_reference`
- `payment_terms_reference`
- `vendor_risk_reference`
- `vendor_trend_reference` (optional)
- `technical_compliance_reference` (optional)
- `evidence_status`

The application may use internal supplier identifiers. Public/demo fixtures must use synthetic identifiers.

### EvaluationRun

Represents one deterministic execution of the procurement toolchain.

Conceptual fields:

- `run_id`
- `case_id`
- `started_at`
- `completed_at`
- `status`
- `package_version`
- `scoring_contract_version`
- `profile_snapshot_hash`
- `decision_record_id`

An EvaluationRun is immutable after completion except for hosting-layer metadata. Re-running a case creates a new run rather than rewriting historical output.

### DecisionRecord

The existing `supplier-scorecard.decision-record` envelope is the authoritative portable audit object.

The product layer may index selected fields for query/display, but the complete record must be retained unchanged except for permitted review-state transitions followed by integrity refresh.

### ReviewAction

Represents human governance outside the numeric score.

Conceptual fields:

- `review_action_id`
- `decision_record_id`
- `actor_id`
- `previous_status`
- `new_status`
- `note`
- `created_at`

Allowed review-state semantics continue to come from the decision-record contract.

## Minimum API behavior

The final transport technology is intentionally unspecified. REST-style examples below define responsibility, not framework choice.

### Create case

`POST /cases`

Creates case metadata only. Does not score suppliers.

### Add/update supplier evidence

`POST /cases/{case_id}/submissions`

Adds evidence references. Validation should distinguish missing evidence from invalid evidence.

### Run evaluation

`POST /cases/{case_id}/evaluations`

Responsibilities:

1. resolve retained evidence;
2. call the existing orchestration/scoring layer;
3. create the deterministic result;
4. create and verify the decision record;
5. persist the completed record and run metadata;
6. return the result/record reference.

The API must not independently calculate score weights, recommendation bands or policy thresholds.

### Get current case decision

`GET /cases/{case_id}/decision`

Returns the latest completed decision record plus presentation metadata.

### List evaluations

`GET /cases/{case_id}/evaluations`

Returns historical run references. Historical results are never recalculated silently.

### Verify integrity

`POST /decision-records/{id}/verify`

Runs decision-record integrity/provenance verification and returns explicit errors when verification fails.

### Submit review action

`POST /decision-records/{id}/review-actions`

May update permitted human-governance metadata only. Must not change the embedded deterministic result.

## Dashboard views

### Case overview

- case status;
- evidence readiness;
- suppliers included;
- latest evaluation status;
- current recommendation;
- review-required indicator.

### Supplier comparison

For each supplier show separately:

- quotation competitiveness;
- commercial/payment exposure;
- vendor risk;
- vendor trend signal when available;
- technical compliance when available;
- composite score;
- recommendation;
- policy status and triggers.

### Decision view

- numerical ranking;
- policy-eligible recommendation;
- explanation / trade-offs;
- REVIEW/BLOCKED reasons;
- review state;
- export/open decision record.

### Audit view

- package and scoring-contract versions;
- profile/policy hashes;
- upstream tool versions;
- retained artifact hashes;
- integrity verification status;
- review history.

## Security / deployment boundary

The product surface owns:

- authentication;
- authorization / RBAC;
- tenant isolation;
- encryption at rest/in transit;
- retention policy;
- reviewer identity;
- hosting and deployment.

The core scorecard package remains framework- and identity-provider-independent.

## Persistence rule

Persist immutable completed EvaluationRuns and complete DecisionRecords.

Do not store only the final score. A stored score without the profile, policy, provenance and evidence context is insufficient for Phase 3 auditability.

## Pilot-first implementation rule

Implement only what is required to run one real pilot end-to-end through this surface.

Before expanding the product surface, classify requests as:

- required for pilot completion;
- repeated across multiple pilots;
- enterprise/deployment requirement;
- convenience feature;
- ERP-scope expansion.

Convenience and ERP-scope features remain deferred until repeated evidence justifies them.

## Acceptance

The first implementation is acceptable when:

1. one procurement case can be created;
2. at least three supplier evidence packages can be attached;
3. one evaluation can be run through the existing deterministic core;
4. ranking/policy evidence can be inspected separately;
5. the resulting decision record can be verified;
6. a required human review can be recorded without changing the score;
7. the same retained inputs produce the same deterministic result as the CLI/Python workflow.
