# position-assignment-governance Specification

## Purpose
Define tenant-scoped position masters and effective-dated user assignments without implicit authorization grants.

## Requirements

### Requirement: Tenant-scoped position master
The system SHALL maintain position masters with tenant-local unique codes, optional same-tenant organization-unit ownership, status, sort order, and descriptive responsibilities.

#### Scenario: Create position in department
- **WHEN** an authorized administrator creates a position under a same-tenant organization unit
- **THEN** the system persists and returns the position with its department reference

#### Scenario: Foreign department hidden
- **WHEN** a position command references an organization unit from another tenant
- **THEN** the system returns not found and persists nothing

### Requirement: Effective-dated user assignments
The system SHALL assign same-tenant users to positions with start/end dates, optional park context, primary-position flag, and immutable historical records after ending.

#### Scenario: End assignment preserves history
- **WHEN** an administrator ends a current assignment
- **THEN** the record remains queryable with its end time and is no longer current

#### Scenario: Accessible park required
- **WHEN** an assignment command references a park outside the administrator's explicit park scope
- **THEN** the system rejects the command without revealing or modifying the park

### Requirement: Assignment uniqueness and authorization separation
The system MUST prevent duplicate current user-position-park assignments and more than one current primary assignment per user, and MUST NOT derive roles, permissions, or park scope from a position assignment.

#### Scenario: Duplicate primary rejected
- **WHEN** two current primary assignments are submitted for the same user
- **THEN** at most one commits and the other returns a conflict

#### Scenario: Position does not grant access
- **WHEN** a user receives a position scoped to a park but has no role or direct park grant
- **THEN** the user's resolved action permissions and park scope remain unchanged
