## ADDED Requirements

### Requirement: Menu administration
The system SHALL support menu definition administration (list/create/update/delete or deactivate) for backend-driven navigation when the product elects to keep server menus. Menu records SHALL be tenant-aware or platform-template-aware as decided in Open Questions before apply.

#### Scenario: List menus for admin
- **WHEN** an authorized admin lists menus
- **THEN** menu tree or list data is returned without leaking secrets

### Requirement: Dynamic menu for authenticated user
The system SHALL provide a dynamic menu endpoint for the current user that returns only menus the user is allowed to see based on role-menu or equivalent bindings.

#### Scenario: User without menu binding
- **WHEN** an authenticated user has no menu grants
- **THEN** the dynamic menu response is empty or contains only public shell nodes as product-defined

### Requirement: Menu visibility is not action authorization
The system SHALL NOT treat presence of a menu node as sufficient authorization for write or sensitive APIs. Action permission codes enforced by API dependencies remain authoritative.

#### Scenario: Menu visible but API denied
- **WHEN** a user can see a menu entry but lacks the action permission for a write API
- **THEN** the write API returns 403 `PERMISSION_DENIED`
