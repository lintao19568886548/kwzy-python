## ADDED Requirements

### Requirement: Leave uses native approval truth
Submission SHALL create one native approval and status SHALL reconcile from it, never from a caller-supplied approval flag.

#### Scenario: Forged approval
- **WHEN** a caller attempts direct APPROVED state
- **THEN** the command is rejected

### Requirement: Approved leave affects roster and attendance
Approved leave SHALL block conflicting roster assignments and trigger deterministic summary regeneration; cancellation SHALL preserve prior evidence.

#### Scenario: Full-day leave conflict
- **WHEN** a shift is assigned on approved full-day leave
- **THEN** the system returns 409
