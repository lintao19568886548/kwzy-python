## ADDED Requirements

### Requirement: Schema-only identity field mapping
The system SHALL maintain field-level mapping for Identity/System tables discovered from static SQL/source (for example `user`, `role`, menu/permission relation tables, park scope relations). Mapping rows MUST include old evidence file and numeric line when available. Unmapped columns SHALL remain `HUMAN_MAPPING_REQUIRED`.

#### Scenario: Password column mapping is partial
- **WHEN** old password storage algorithm differs from new `password_hash`
- **THEN** mapping status is PARTIAL_TRANSFORM or HUMAN_MAPPING_REQUIRED and cutover is blocked until hash strategy is approved

### Requirement: No production database connections for migration design
Migration design and evidence collection MUST NOT connect to old Java production databases. Only schema-only dumps, static SQL, and non-production test databases are allowed.

#### Scenario: Missing tenant schema dump
- **WHEN** tenant schema dump is unavailable
- **THEN** data migration readiness remains BLOCKED and tasks must not claim ETL ready

### Requirement: PostgreSQL is the authority for migration validation
When migration jobs are later implemented, PostgreSQL 16 SHALL be the authoritative validation target. SQLite MAY be used for unit tests but MUST NOT alone certify migration completeness.

#### Scenario: PG required for migration acceptance
- **WHEN** identity data migration acceptance is requested
- **THEN** PostgreSQL validation evidence is required
