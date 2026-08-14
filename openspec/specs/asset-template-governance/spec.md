# asset-template-governance Specification

## Purpose
Define tenant-scoped, versioned asset templates and their bounded use by rentable units.

## Requirements

### Requirement: Versioned tenant asset templates
The system SHALL maintain tenant-owned asset templates with tenant-unique code, allow-listed category, optimistic lock and immutable published versions.

#### Scenario: Publish a valid draft
- **WHEN** an authorized administrator publishes the current valid draft using its expected lock version
- **THEN** that version becomes immutable and is available for later unit binding

#### Scenario: Stale template command
- **WHEN** two administrators mutate one template using the same lock version
- **THEN** one succeeds and the stale command receives 409

### Requirement: Bounded typed field grammar
Each template version SHALL contain at most 32 ordered fields using allow-listed scalar types and bounded keys, labels, units, numeric limits and enum options, and SHALL reject nested schemas, executable expressions, SQL and URLs.

#### Scenario: Unsafe field definition
- **WHEN** a draft contains an unknown type, nested schema, expression or URL-bearing executable field
- **THEN** validation rejects publication without changing the active version

### Requirement: Exact-version unit validation
Every new or structurally changed rentable unit SHALL reference a published same-tenant template version and its attributes SHALL contain only schema-known values of valid types and ranges.

#### Scenario: Unknown attribute key
- **WHEN** a unit mutation includes an attribute absent from the selected template version
- **THEN** the command fails atomically and no unit version is created

### Requirement: Materialized built-in categories
The system SHALL idempotently materialize templates for FACTORY, WAREHOUSE, SHOP, OFFICE, DORMITORY, PARKING and PUBLIC_SPACE without overwriting tenant customizations or inventing units.

#### Scenario: Repeated bootstrap
- **WHEN** built-in initialization runs twice for one tenant
- **THEN** template codes, published versions and checksums remain stable with no duplicates

### Requirement: Scoped template administration
Template reads and writes SHALL use separate database-derived permissions and tenant isolation, and unit permissions SHALL NOT imply template write access.

#### Scenario: Unit editor without template administration
- **WHEN** a caller has unit write but lacks asset-template write
- **THEN** published templates are usable for units but template mutation is forbidden
