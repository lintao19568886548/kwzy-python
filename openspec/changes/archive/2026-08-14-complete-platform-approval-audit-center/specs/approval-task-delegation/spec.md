## ADDED Requirements

### Requirement: Stable same-tenant task candidates
The system SHALL materialize a stable same-tenant user candidate snapshot for each opened step from its user and active-role assignees, and SHALL expose actionable tasks only to the assigned user or an effective delegate.

#### Scenario: Later role change does not rewrite open candidates
- **WHEN** role membership changes after a step opens
- **THEN** the existing task candidate set remains unchanged and a future step resolves candidates when it opens

#### Scenario: Empty resolved candidate set fails closed
- **WHEN** a step opens but its user/role rules resolve to no active same-tenant users
- **THEN** the transition rolls back with an unassigned-step conflict and no false pending task is shown

### Requirement: Effective-dated delegation
An authorized user SHALL create, revoke and list effective-dated delegations to another active same-tenant user, optionally limited by business type; self-delegation, cycles, invalid time ranges and overlapping duplicates SHALL be rejected.

#### Scenario: Delegate decides on behalf of grantor
- **WHEN** a valid delegate decides a task assigned to the grantor during the effective period
- **THEN** the decision records both acting user and original assignee and applies normal separation-of-duties checks

#### Scenario: Expired delegation denied
- **WHEN** a delegate acts after the delegation end time
- **THEN** the system returns forbidden and persists no decision event or success audit

### Requirement: SLA and escalation
Every opened task SHALL have a due time derived from the published step SLA; an idempotent sweep SHALL mark overdue tasks, raise priority and create an escalation event/work-item update without changing approval outcome.

#### Scenario: Overdue sweep is idempotent
- **WHEN** the sweep processes the same overdue task multiple times
- **THEN** only one overdue event exists and its work item remains one open, urgent projection

#### Scenario: Terminal task is not escalated
- **WHEN** a task is already approved, rejected, skipped or cancelled
- **THEN** the sweep leaves it unchanged
