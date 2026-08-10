## ADDED Requirements

### Requirement: Alembic lease tables for billing
Implementation SHALL add fee_catalog, bills, bill_lines with unique head after lease revision.

#### Scenario: Upgrade creates tables
- **WHEN** alembic upgrade head on empty DB
- **THEN** billing tables exist
