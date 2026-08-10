## ADDED Requirements

### Requirement: Bill APIs under /api/v1
Bill list/get/create/update/issue/void/discard SHALL use unified envelope, tenant isolation, and park scope.

#### Scenario: Cross-tenant hidden
- **WHEN** tenant A requests tenant B bill id
- **THEN** API returns 404
