## ADDED Requirements

### Requirement: Document legacy identity endpoints
The system SHALL maintain a documented mapping from legacy Java Identity/System/Admin endpoints (canonical `/api/...` paths) to new `/api/v1/...` endpoints or explicit NON_SUPPORT status. Mapping evidence MUST reference controller file and line numbers from static analysis.

#### Scenario: Legacy login mapping
- **WHEN** consumers consult the compatibility matrix for `POST /api/auth/login`
- **THEN** they find a mapping to `POST /api/v1/auth/login` with contract status COMPATIBLE_REDESIGN or better after apply verification

### Requirement: No silent EXACT_MATCH claims
The system MUST NOT claim EXACT_MATCH for a legacy endpoint unless request and response schemas, status codes, auth requirements, and side effects are verified. Family-level redesign MUST be labeled COMPATIBLE_REDESIGN, SCHEMA_MISMATCH, or MISSING.

#### Scenario: Admin user list without Python API
- **WHEN** legacy `GET /api/user/list` has no Python implementation
- **THEN** its status is MISSING, not COMPLETE

### Requirement: Deprecation window is human-approved
Any dual-running compatibility shim or path alias SHALL require an approved deprecation window and MUST NOT be invented at apply time without product decision.

#### Scenario: Alias requires decision
- **WHEN** a path alias such as dual `/auth` and `/api/v1/auth` is proposed
- **THEN** tasks remain blocked until deprecation and versioning are approved
