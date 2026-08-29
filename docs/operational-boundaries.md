# Operational boundaries

Status: **Phase 2 architecture contract**

`supplier-scorecard` remains a deterministic decision engine. Persistence, APIs, user identity and workflow orchestration are deliberately kept outside the scoring core so operational productization cannot silently change score semantics.

## Boundary principles

### 1. Decision record is the portability contract

The versioned `supplier-scorecard.decision-record` JSON envelope is the durable hand-off between the deterministic engine and any database, API, workflow system or user interface.

External systems may store, transport, index and display the record. They must not rewrite the embedded deterministic `result`.

### 2. Persistence is an adapter responsibility

A future persistence layer may use PostgreSQL, object storage, document storage or another implementation. The core package does not require a database runtime dependency.

A persistence adapter should store:

- the complete decision record;
- its schema and schema version;
- the decision payload SHA-256;
- retained artifact identities/locations where applicable;
- record creation/update metadata owned by the application layer.

The stored decision record remains the source of truth for what the engine produced at that point in time.

### 3. API layer does not become a second scoring model

A future API may expose operations such as:

- create/run a procurement evaluation;
- retrieve a decision record;
- list decisions by supplier/project/category;
- verify a decision record;
- submit an allowed human-review state transition.

The API must call the public deterministic scoring/orchestration interfaces rather than reproducing weights or policy logic in controllers, database procedures or frontend code.

### 4. Human review changes governance state, not score state

For records requiring review, application-layer users may transition the operational review state to an allowed value such as `APPROVED_EXCEPTION` or `REJECTED`.

A review action must:

1. leave the embedded v1.0 score, recommendation, ranking and policy result unchanged;
2. record reviewer identity/time/note in the application layer or review object;
3. refresh the decision-record integrity hash after the permitted review-state mutation;
4. preserve the previous record/version when audit history is required.

An exception approval is therefore a governance decision, not a recalculated supplier score.

### 5. Authentication, authorization and signatures are outside the scoring core

Identity providers, RBAC, approval authority, electronic signatures and non-repudiation belong to the hosting application/infrastructure layer.

The current SHA-256 integrity mechanism detects content changes; it is not a digital signature and does not prove reviewer identity.

### 6. Confidential operational data stays outside public fixtures

Production supplier names, quotations, commercial terms, contacts, contracts and project identifiers must not be committed to the public repository. Public examples and CI pilots use sanitized synthetic data only.

### 7. Versioning is explicit

The following versions are independent and must not be conflated:

- package/release version (for example `1.1.0`);
- deterministic scoring/result contract version (`1.0` unless intentionally changed);
- decision-record schema version (`1.0` unless intentionally changed);
- upstream tool/model/schema versions recorded in provenance.

A package release can therefore add operational capabilities without claiming that the frozen scoring model changed.

## Recommended application architecture

```text
UI / Workflow / Approval
          |
       API layer
          |
 Persistence / Audit Store
          |
 versioned decision record
          |
 supplier-scorecard pipeline
          |
 deterministic v1.0 scoring core
```

Dependencies point inward toward the deterministic contract. Database/framework concerns never become required dependencies of the scoring core.

## Phase 2 release boundary

Phase 2 is considered operationally complete when:

- decision-record generation and verification are merged;
- retained upstream provenance is complete;
- the sanitized multi-supplier pilot passes;
- the persistence/API boundary is documented;
- normal `main` CI is green;
- a separate release change deliberately bumps the package version and creates the stable tag/release.

The release step is intentionally separate from feature implementation so publishing remains an explicit governance action.
