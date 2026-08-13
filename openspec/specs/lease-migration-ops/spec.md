# lease-migration-ops Specification

## Purpose
定义租赁合同基础表的 Alembic 迁移、唯一迁移头以及 PostgreSQL 16 升降级验证规则。该规格确保合同、合同单元和条款表可以从空库可靠建立，也可以单步回退而不破坏 Party 数据。

## Requirements

### Requirement: New Alembic revision for lease tables
Implementation SHALL add a single new Alembic revision creating lease_contracts, lease_contract_units, and lease_terms with down_revision equal to the Party head at apply time, keeping a unique head.

#### Scenario: Upgrade on PostgreSQL 16
- **WHEN** alembic upgrade head runs on empty PostgreSQL 16
- **THEN** lease tables exist and alembic current equals heads

#### Scenario: Downgrade removes lease tables
- **WHEN** alembic downgrade -1 runs after lease revision
- **THEN** lease tables are dropped without breaking Party tables
