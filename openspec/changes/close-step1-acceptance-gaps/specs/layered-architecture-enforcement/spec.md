## ADDED Requirements

### Requirement: Domain has no SQLAlchemy dependency
Domain layer modules under business contexts SHALL NOT import SQLAlchemy or define ORM-mapped classes.

#### Scenario: Domain package is free of sqlalchemy imports
- **WHEN** architecture dependency checks scan `modules/*/domain`
- **THEN** no module in those packages imports `sqlalchemy`

### Requirement: Application does not construct ORM models
Application services SHALL NOT instantiate infrastructure ORM model classes for persistence writes.

#### Scenario: Park and Unit application create paths use domain or repository APIs
- **WHEN** Park or Unit create/update application code is inspected or tested for layering
- **THEN** it does not call ORM model constructors for `Park`/`Unit`/`Building` outside infrastructure mappers/repositories

### Requirement: Repository boundary maps domain objects
Infrastructure repositories SHALL accept and/or return domain entities or application DTOs at their public boundary, converting to ORM models only inside infrastructure.

#### Scenario: Mapper converts both directions
- **WHEN** a Park is loaded or saved through the repository
- **THEN** conversion between domain representation and ORM occurs in infrastructure mapping code

### Requirement: Regression guard for layer violations
The test suite or static check SHALL fail when application modules import `app.infrastructure.database.models` except for an explicit allowlist (if any must remain temporary and documented).

#### Scenario: Forbidden import fails check
- **WHEN** a non-allowlisted application module imports ORM models
- **THEN** the architecture dependency test or check fails

### Requirement: No new business modules in this change
This capability's implementation SHALL NOT introduce Party, Lease, Bill, or Payment business modules or APIs.

#### Scenario: Scope limited to Identity and ParkProperty layering
- **WHEN** the change is applied
- **THEN** no new Party/Lease/Bill/Payment feature modules are added as part of the layering fix
