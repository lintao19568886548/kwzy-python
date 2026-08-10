## ADDED Requirements

### Requirement: Payment tables migration
Implementation SHALL create payments and payment_allocations with a unique Alembic head.

#### Scenario: Upgrade
- **WHEN** alembic upgrade head
- **THEN** payment tables exist
