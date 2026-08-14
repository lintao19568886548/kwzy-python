# kwzy-api

瞰维智管 V2 Python 模块化单体 API。当前代码不是全业务完成声明；已验证范围和仍缺失范围以独立验收报告及能力矩阵为准。

## 当前运行结构

`app/main.py` 挂载 Identity、Park Property、Party、Lease、Billing、Collection、Workbench、Investment、Facility Ops、Integrations、Workflow 和 Attachments 共 12 个路由。`ai_assist` 与 `analytics` 仍未形成可验收业务能力，也未挂载为完成接口。

模块按 `api.py`（接口）、`service.py`/`application`（应用）、`domain.py`（领域）和 `models.py`/`repository.py`（基础设施）分层。领域层不得依赖 FastAPI 或 SQLAlchemy；业务查询必须包含 `tenant_id`，园区操作还须执行权限和数据范围检查。

## 本地启动

```bash
cd apps/api
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,pg]"
Copy-Item .env.example .env

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

默认开发配置可使用 SQLite；预发布和生产环境会拒绝 SQLite，必须显式提供 PostgreSQL URL。不要把开发数据库用于迁移验收，也不要用 `create_all` 代替 Alembic。

- OpenAPI UI: `http://127.0.0.1:8000/docs`
- 存活探针: `http://127.0.0.1:8000/health`
- 就绪探针: `http://127.0.0.1:8000/health/ready`

## 数据库和测试

PostgreSQL 16 验收至少执行：

```bash
alembic upgrade head
alembic current
alembic heads
alembic downgrade -1
alembic upgrade head
python -m pytest -q
```

完整的隔离数据库、ETL、性能、备份恢复、前端和浏览器验收入口位于 `infra/local-staging/run_full_acceptance.ps1`。生产容器契约和人工操作步骤位于 `infra/production/` 与 `docs/05-deployment/production-operations-runbook.md`。

## 安全约定

- API 响应 envelope 为 `{ "code", "message", "data" }`。
- 登录 JWT 的权限和园区范围来自服务端 RBAC 数据；生产环境禁止匿名开发范围、默认 JWT 密钥、通配 CORS 和 SQLite。
- 新密码执行长度、复杂度、账号片段与常见弱口令检查。
- Payment 表示收款登记，不等于在线支付订单；`Bill.status` 不使用 `OVERDUE`，逾期通过派生字段表达。
- 生产签章、支付和消息等外部适配器在缺少真实凭据与验证证据时必须 fail closed，不能标记为已上线。

设计、OpenAPI 与独立验收证据见仓库 `docs/`、`openspec/` 和 `docs/06-implementation/evidence/`。
