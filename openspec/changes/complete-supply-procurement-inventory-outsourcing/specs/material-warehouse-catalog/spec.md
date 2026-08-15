# Material and Warehouse Catalogue

## ADDED Requirements

### Requirement: Tenant material catalogue
The system SHALL maintain tenant-unique material codes, units, categories, active state, reorder threshold, and auditable changes.

#### Scenario: Reject duplicate material code
- **WHEN** an operator creates the same normalized material code twice in one tenant
- **THEN** the second request is rejected without creating a duplicate

### Requirement: Park-scoped warehouses
The system SHALL bind each warehouse to one tenant and park and SHALL enforce caller park scope on every read and mutation.

#### Scenario: Query warehouse outside scope
- **WHEN** a park-scoped user requests another park warehouse
- **THEN** the system returns not found

### Requirement: Governed catalogue query
The system SHALL provide bounded paging, normalized filtering, active-state filtering, and deterministic ordering for materials and warehouses.

#### Scenario: Reject unbounded page size
- **WHEN** a caller requests a page larger than the configured maximum
- **THEN** validation rejects the request before database execution
