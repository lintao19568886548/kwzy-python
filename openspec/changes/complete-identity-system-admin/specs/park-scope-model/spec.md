## ADDED Requirements

### Requirement: Park scope administration surfaces
The system SHALL provide authenticated administration operations to assign and revoke user and/or role park scopes, including explicit all-parks flags, subject to tenant isolation and action permissions. These operations SHALL update the same underlying grant tables used by login-time authorization resolution.

#### Scenario: Admin assigns parks to role
- **WHEN** an authorized admin assigns parks {10,20} to a role in the same tenant
- **THEN** users with that active role include 10 and 20 in resolved LIST scope after re-login or re-resolution per token policy

#### Scenario: Admin clears all-parks
- **WHEN** an authorized admin removes all-parks from a principal that has no remaining listed parks
- **THEN** subsequent authorization resolution is not ALL
