## Context

- Fail SQL (脱敏): `UPDATE roles SET all_parks = 1 WHERE code = 'ADMIN'`
- PG: boolean ≠ integer
- SQLite historically accepts 0/1 for boolean
- Evidence of non-production: PG never successfully reached this head; local `kwzy_step1.db` is dev SQLite only

## Goals / Non-Goals

**Goals:** Portable boolean true assignment; full upgrade path on PG16 + SQLite.

**Non-Goals:** Party features; rewriting other migrations; production data migration.

## Decisions

Use SQLAlchemy core `table`/`column` update with `all_parks=True` (or `sa.true()`), not raw `= 1` or string SQL.

Keep revision id `9f17fd2e9180` and `down_revision = 8c2f4aa10b7d`.

## Risks

| 风险 | 缓解 |
| --- | --- |
| 已 stamp 该 revision 的 SQLite 库 | 不破坏；仅改 upgrade 源码，已应用库无需重跑 |
| 未来重复 fresh PG | 验证 base→head 通过 |
