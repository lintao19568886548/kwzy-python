## MODIFIED Requirements

### Requirement: Occupancy conflict detection on activate
Before initial activation, approved change application or exit closure, the system MUST lock the Lease root and all affected current Units in ascending id order, reconcile CRM unit locks and active Lease occupancy, and reject any cross-tenant, cross-park, retired, over-capacity or foreign-lock conflict.

#### Scenario: Initial activation consumes own CRM lock
- **WHEN** a PENDING_ACTIVE contract is linked to its source Lead active lock and all capacity rules pass
- **THEN** activation consumes that lock, writes version 1 and projects the Unit occupied in one transaction

#### Scenario: Concurrent expansion conflict
- **WHEN** two approved changes concurrently add overlapping capacity on the same current Unit
- **THEN** PostgreSQL commits exactly one valid projection and the other returns `UNIT_OCCUPANCY_CONFLICT` 409 without partial version or schedule writes

#### Scenario: Foreign CRM lock blocks transfer
- **WHEN** a unit-transfer change targets a Unit actively locked by another Lead
- **THEN** apply fails and the original/new Unit occupancy, change status and contract version remain unchanged

### Requirement: used_area projection
`units.used_area` MUST equal the sum of current occupied_area for contracts in ACTIVE, EXPIRING or EXIT_PENDING status. Initial activation and applied expansion, reduction, transfer, early-exit close, termination or breach MUST recompute all affected Units inside the same transaction; clients MUST NOT write used_area directly.

#### Scenario: Reduction updates only approved delta
- **WHEN** an approved reduction applies from the current base version
- **THEN** the new contract version contains the reduced unit set and every affected Unit used_area is recomputed from effective current occupancy

#### Scenario: Exit pending keeps occupancy
- **WHEN** an exit settlement is submitted or approved but not closed
- **THEN** the contract remains in the occupying set and its Units stay OCCUPIED or RESERVED according to aggregate occupancy

#### Scenario: Exit close releases atomically
- **WHEN** an approved, financially cleared settlement closes
- **THEN** the terminal version, TERMINATED status, Unit release, todo closure and audit commit together or all roll back
