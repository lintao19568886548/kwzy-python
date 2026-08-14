# field-access-policy Specification

## Purpose
Define fail-closed, server-enforced access policies for allow-listed protected fields.

## Requirements

### Requirement: Role-based protected field policies
The system SHALL let authorized administrators configure `VISIBLE`, `MASKED`, or `HIDDEN` access for allow-listed protected resource fields on same-tenant roles only.

#### Scenario: Configure user phone masking
- **WHEN** an administrator assigns `MASKED` for `USER.phone` to a same-tenant role
- **THEN** users holding that role receive a deterministic masked phone value from user list responses

#### Scenario: Unknown resource field rejected
- **WHEN** an administrator submits a resource or field not present in the server allow-list
- **THEN** the system rejects the policy and stores no arbitrary field rule

### Requirement: Fail-closed multi-role resolution
The system SHALL resolve field policies from current database role assignments, SHALL use `HIDDEN` over `MASKED` over `VISIBLE` when multiple roles apply, and SHALL default protected fields without a policy to `MASKED`.

#### Scenario: Hidden overrides visible
- **WHEN** a user has one role granting `VISIBLE` and another role granting `HIDDEN` for the same protected field
- **THEN** the response omits that field

#### Scenario: Star action permission does not bypass
- **WHEN** a user has the `*` action permission but no explicit visible field policy
- **THEN** the protected field remains masked

### Requirement: Server-side projection and safe audit
The system SHALL execute field projection before serializing the API response and SHALL audit policy changes without storing protected field values.

#### Scenario: Client claim ignored
- **WHEN** a client sends a fabricated field mode or role identifier
- **THEN** the server uses only database role assignments and policy rows for the request tenant

#### Scenario: Policy update audit contains no PII
- **WHEN** a field policy is created or changed
- **THEN** the audit entry records identifiers and modes but no protected resource value
