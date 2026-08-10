## Why

Fresh PostgreSQL 16 baseline `alembic upgrade head` fails at revision `9f17fd2e9180` because `UPDATE roles SET all_parks = 1` uses an integer where PostgreSQL expects boolean. This blocks Party implement apply gates. The revision is local/test baseline only (never successfully applied on production PostgreSQL).

## What Changes

- Minimal portable fix of the boolean assignment in `9f17fd2e9180` (same revision id / down_revision).
- Regression verification on disposable PG 16 + temporary SQLite.
- Docs note of the failure and resolution.

## Capabilities

### New Capabilities

- `postgres-baseline-boolean-portability`: Boolean literals in baseline migrations must be dialect-portable.

### Modified Capabilities

- （无业务 capability 语义变更）

## Impact

| 面 | 说明 |
| --- | --- |
| Migration | 仅一行 UPDATE 表达式；语义仍为 ADMIN.all_parks=true |
| SQLite | 必须仍可 base→head |
| Party | 不实现；仅解除 PG baseline 阻塞 |
