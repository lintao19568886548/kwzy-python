## ADDED Requirements

### Requirement: Party module four-layer layout
Implementation SHALL place Party code under app/modules/party with domain, application, infrastructure, and interface layers. Domain SHALL NOT import FastAPI or SQLAlchemy. Application SHALL NOT construct ORM models. Router SHALL NOT use Session or concrete repositories directly.

#### Scenario: Layering static check covers party
- **WHEN** architecture tests run after Party implementation
- **THEN** party application modules do not import ORM models except documented allowlists

### Requirement: Feature branch gate before apply
Before applying this change, implementers SHALL ensure main is clean and synced with origin/main, create and use branch feat/party-master for all Party implementation work, forbid direct Party development on main, and forbid force push. This preflight planning stage SHALL NOT create the branch.

#### Scenario: Implementation only on feat/party-master
- **WHEN** Party code is developed
- **THEN** it lands on feat/party-master and not main

### Requirement: PostgreSQL gate before complete or merge
This change SHALL NOT be marked Complete or merged to main while PostgreSQL 16 integration environment is unavailable or failing. SQLite success alone SHALL NOT authorize production dialect correctness.

#### Scenario: Block complete without PG
- **WHEN** PostgreSQL integration tests cannot run
- **THEN** implement-party-master must not be treated as Complete

### Requirement: Deliver approved capabilities without out-of-scope modules
Implementation SHALL implement approved Party master capabilities including addresses via party_addresses and SHALL NOT implement Lease, Bill, Payment, legacy rental adapter, identity-number storage, or old-data ETL.

#### Scenario: No lease module
- **WHEN** this change is applied
- **THEN** no Lease business module is introduced

### Requirement: Permission codes seeded
Bootstrap or migration seed SHALL include party:read, party:write, party:manage_unscoped, party:risk_read, and party:risk_manage.

#### Scenario: Permission dictionary contains party codes
- **WHEN** local/test bootstrap completes
- **THEN** the five party permission codes exist

### Requirement: Structured logging on writes
Successful Party write operations SHALL log with request_id, tenant_id, user_id, module=party, action, and resource_id without dumping full address lines or unmasked phones.

#### Scenario: Create logs success
- **WHEN** a party is created successfully
- **THEN** a structured success log includes module party and resource_id

### Requirement: Completion report
Implementation SHALL produce a completion report under docs/06-implementation documenting tables, APIs, permissions, tests, OpenAPI sync, and residual risks.

#### Scenario: Report exists after delivery
- **WHEN** implementation tasks complete
- **THEN** the completion report path is present
