## ADDED Requirements

### Requirement: Dynamic menus for current user
The system SHALL return menus granted via the user's roles for navigation.

#### Scenario: My menus
- **WHEN** an authenticated user requests route menus
- **THEN** only menus linked to their active roles (or all menus for `*` action admins as configured) are returned ordered by sort
