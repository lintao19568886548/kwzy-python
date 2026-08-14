# Work Order Acceptance and Rating Specification

## Purpose

Define Party-bound acceptance, preserved rework evidence and immutable service ratings.

## Requirements

### Requirement: Completion and tenant acceptance are separate
Technician completion SHALL move to `WAITING_ACCEPTANCE`; only a Party-bound principal or authorized reasoned proxy SHALL produce `ACCEPTED` or `REWORK` acceptance evidence.

#### Scenario: Technician self-accepts
- **WHEN** the current assignee lacks tenant acceptance authority and calls acceptance
- **THEN** the request is denied and the WorkOrder remains waiting

### Requirement: Rework preserves all prior evidence
A rework decision SHALL require a bounded reason, append an acceptance attempt and reopen the same WorkOrder to the appropriate in-progress state. Quotes, actual entries, prior completion and SLA events SHALL not be deleted.

#### Scenario: Tenant rejects first completion
- **WHEN** the bound tenant requests rework
- **THEN** attempt one remains queryable and the original field task is reopened for the current assignee

### Requirement: Acceptance closes tasks and aggregate atomically
Acceptance SHALL record actor Party/principal, time, comment and current version, move the WorkOrder to `COMPLETED`, close outstanding service tasks and emit one completion event in the same transaction.

#### Scenario: Concurrent accept and rework
- **WHEN** accept and rework target the same aggregate version concurrently
- **THEN** exactly one decision commits and the other receives 409

### Requirement: Rating is bounded, Party-scoped and immutable
After acceptance, the bound Party MAY submit one 1–5 rating with bounded tags/comment and an idempotency key. Rating before completion, duplicate different rating or cross-Party rating SHALL be rejected.

#### Scenario: Retry same rating
- **WHEN** the tenant retries the identical rating with the same key
- **THEN** the original rating is returned and no duplicate exists
