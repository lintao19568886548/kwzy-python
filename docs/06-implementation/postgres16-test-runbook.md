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

## 已知基线迁移问题（PostgreSQL）

**标记：`POSTGRES_BASELINE_MIGRATION_FAILED`**

| 项 | 内容 |
| --- | --- |
| 文件 | `apps/api/alembic/versions/9f17fd2e9180_add_all_parks_scope_flags.py` |
| 错误类型 | `psycopg.errors.DatatypeMismatch` / SQLAlchemy `ProgrammingError` |
| 现象 | `UPDATE roles SET all_parks = 1` — PostgreSQL 要求 boolean 使用 `true`/`false`，整数 `1` 非法 |
| 前序 revision | `44cb70117ff4` → `8c2f4aa10b7d` 在失败前可执行；失败事务回滚后库可为空 |
| 策略 | **禁止静默改写已应用历史 migration**；须单独评审后以兼容 SQL（如 `true` 或 dialect 分支）修复 |
| 影响 | 在修复前：**不能**宣称 PG baseline upgrade 到 head 成功；**不能**解除 Party apply 的 PG 门禁 |

## 会话验证记录（脱敏）

- Docker daemon：可用时 `ServerVersion=29.6.2`  
- 容器：`kwzy_party_test_pg` / image `postgres:16` / health=healthy  
- 绑定：`127.0.0.1:55432` / DB=`kwzy_party_test` / major=16  
- Alembic heads：`9f17fd2e9180`  
- Alembic upgrade head：**失败**（见上）  
- `pytest -m pg`：连接/事务 harness 可通过（不依赖 full schema）  
- SQLite 全量：应保持通过  

