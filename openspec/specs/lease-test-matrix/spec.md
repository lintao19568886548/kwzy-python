# lease-test-matrix Specification

## Purpose
定义租赁合同基础能力的领域、应用、接口、仓储、权限、范围隔离、占用、审计和数据库自动化测试矩阵。该规格确保 SQLite 快速反馈与 PostgreSQL 16 权威行为都得到覆盖并可以重复验证。

## Requirements

### Requirement: Automated test matrix
Implementation SHALL provide domain, application/API, repository, permission, tenant isolation, park scope, occupancy conflict, used_area projection, audit, SQLite, and PostgreSQL 16 tests for lease.

#### Scenario: PostgreSQL marker tests
- **WHEN** pytest -m pg runs with TEST_DATABASE_URL
- **THEN** lease-related PG cases pass including migration head checks if applicable
