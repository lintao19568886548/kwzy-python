# approval-audit-data-migration Specification

## Purpose
TBD - created by archiving change complete-platform-approval-audit-center. Update Purpose after archive.
## Requirements
### Requirement: Legacy approval and audit disposition
The project SHALL publish source-to-target disposition for scattered reimbursement, leave, outreach-template and other approval states plus legacy operation logs, identifying migrated, recomputed, quarantined and unsupported fields without claiming unavailable data.

#### Scenario: Unsupported implicit status documented
- **WHEN** a legacy module has only an integer status and no durable approver history
- **THEN** the mapping marks missing history as unavailable rather than synthesizing decisions

### Requirement: Schema-versioned synthetic drill
The project SHALL provide a loopback/test-database-only synthetic fixture and runner covering definition versions, steps, instances, tasks, delegations, approval events and new audit-chain records through dry-run, apply, idempotent reapply, reconciliation and rollback.

#### Scenario: Idempotent reapply
- **WHEN** the same synthetic fixture is applied twice
- **THEN** the second run inserts no duplicate definition/version/instance/task/delegation/event or audit-chain row

#### Scenario: Rollback removes fixture scope only
- **WHEN** rollback executes after reconciliation
- **THEN** all fixture-owned rows are removed while unrelated platform rows and authorization grants remain unchanged

### Requirement: Real migration remains blocked without evidence
Real legacy migration SHALL remain `BLOCKED` until an authorized schema dump, desensitized samples and owner-approved field mapping exist; synthetic success MUST NOT be labeled production reconciliation or cutover readiness.

#### Scenario: Missing old schema
- **WHEN** the authorized legacy schema and samples are unavailable
- **THEN** reports state the blocker and omit pass claims for real approval history, audit completeness and cutover
