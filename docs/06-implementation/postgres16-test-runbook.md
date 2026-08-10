# PostgreSQL 16 本地测试 Runbook

> 用途：Party apply 前 / 集成测
> 生产方言权威：PostgreSQL 16
> SQLite 仅快速单测，**不能**替代本环境约束验证

## 前置

- Docker Desktop 已安装且 daemon 运行
- 端口默认 `55432`（被占用则改 `POSTGRES_PORT`）

## 启动

```bash
cd D:\重构python\kwzy-python
# 生成本地 .env（勿提交）
# 设置随机 POSTGRES_PASSWORD 后：
docker compose -f infra/postgres-test/compose.yaml --env-file infra/postgres-test/.env up -d
docker compose -f infra/postgres-test/compose.yaml ps
```

## 连接串（环境变量）

```text
TEST_DATABASE_URL=postgresql+psycopg://kwzy_party_test:<password>@127.0.0.1:55432/kwzy_party_test
```

- 仅 `127.0.0.1`
- 库名 `kwzy_party_test`
- **禁止**打印密码到日志/聊天

## Alembic（apps/api）

```bash
cd apps/api
# PowerShell 示例：设置进程环境后
# $env:DATABASE_URL = $env:TEST_DATABASE_URL
# 清除 settings 缓存后：
.venv\Scripts\python.exe -m alembic heads
.venv\Scripts\python.exe -m alembic upgrade head
```

## 测试

```bash
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pytest -q -m pg
```

## 停止

```bash
docker compose -f infra/postgres-test/compose.yaml down
# 仅当确认 volume 名为 kwzy_party_test_pgdata 时可：
# docker compose -f infra/postgres-test/compose.yaml down -v
```

## 安全

- 不连接生产 / 旧 Java 库
- `.env` 被 gitignore
- Compose 无真实密码

## 基线迁移布尔兼容（已修复）

**原标记：`POSTGRES_BASELINE_MIGRATION_FAILED` → 已 RESOLVED（repair change）**

| 项 | 内容 |
| --- | --- |
| 文件 | `apps/api/alembic/versions/9f17fd2e9180_add_all_parks_scope_flags.py` |
| 原错误 | `UPDATE roles SET all_parks = 1` → PG `DatatypeMismatch`（boolean≠integer） |
| 修复 | SQLAlchemy `roles.update().values(all_parks=True)`（跨方言布尔） |
| revision | ID 与 `down_revision` **保持不变** |
| 验证 | PG16 fresh upgrade head；downgrade -1 → upgrade head；临时 SQLite base→head |

OpenSpec：`repair-postgres-baseline-boolean-portability`

## 会话验证记录（脱敏）

- Docker：`ServerVersion=29.6.2`；容器 `kwzy_party_test_pg` healthy
- 绑定：`127.0.0.1:55432` / DB=`kwzy_party_test` / major=16
- Alembic heads/current：`9f17fd2e9180`
- Alembic PG upgrade head：**成功**
- Alembic PG downgrade/upgrade 往返：**成功**
- 临时 SQLite upgrade head：**成功**
- `pytest -m pg`：4 passed
- SQLite 全量：35 passed

