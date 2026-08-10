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
