## ADDED Requirements

### Requirement: Payment APIs
Payment APIs SHALL expose POST/GET /payments and reverse under /api/v1 with tenant isolation and park scope.

#### Scenario: Write requires payment:write
- **WHEN** user without payment:write creates payment
- **THEN** 403
