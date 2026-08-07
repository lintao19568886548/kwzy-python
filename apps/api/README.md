# kwzy-api

AI 智慧园区平台 — Python 模块化单体 API 骨架。

## 结构

```text
app/
  core/           # 配置、DB、安全、异常
  shared/         # 响应体、依赖注入（tenant/scope）
  modules/        # 限界上下文（见 ADR-006 分层）
    identity/
    tenant_ops/
    park_property/
    lease/
    billing/
    collection/
    finance/
    investment/
    ai_assist/
    analytics/
  main.py
```

### 模块内分层（阶段 06 强制，ADR-006）

```text
modules/<ctx>/
  api.py           # interface — 路由
  schemas.py       # interface — Pydantic DTO
  service.py       # application
  domain.py        # domain 规则/状态机（可薄）
  models.py        # infrastructure ORM
  repository.py    # infrastructure 仓储（默认带 tenant_id）
```

**禁止：** domain 依赖 FastAPI/SQLAlchemy；跨模块直接写他模块表。  
**强制：** 查询带 `tenant_id`；园区写操作校验 DataScope（ADR-004/005）。

### 响应与账单约定（05.1）

- 响应 envelope：`{ "code", "message", "data" }`
- Bill.status **禁止 OVERDUE**；使用 `is_overdue` 衍生字段
- Payment = **收款登记**，非在线支付订单

## 快速启动

```bash
cd apps/api
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -e ".[dev]"
copy .env.example .env

uvicorn app.main:app --reload --port 8000
```

打开：

- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## 数据库

基线 DDL：

```text
docs/03-database/01-core-ddl-v1.sql
```

```bash
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS kwzy DEFAULT CHARSET utf8mb4;"
mysql -uroot -p kwzy < ../../docs/03-database/01-core-ddl-v1.sql
```

当前接口多为 **stub**，可先不连库跑通路由。

> 运行时 `main.py` 仅挂载 Identity 与 ParkProperty；Lease/Billing/Collection 等
> `api.py` 仍是未挂载 stub，不代表业务已经实现。

### Step1 身份与安全

- `/auth/login` 支持可选 `tenant_code`，多租户同名用户必须指定租户。
- JWT 的 `permissions` 与 `park_ids` 来自 RBAC/园区范围表，不再由登录硬编码。
- Park/Unit API 同时执行动作权限码与 tenant/park 数据范围检查。
- local/test 可无 Token 使用显式开发超级范围；production 必须携带有效 JWT。
- production 禁止默认 JWT secret 与通配 CORS。

## 测试

```bash
pytest -q
```

当前 Step1 基础加固基线：`23 passed`。

## 设计文档

- `docs/02-domain-design/` 领域设计
- `docs/03-database/` 库表
- `docs/04-api/openapi-v1-core.yaml` OpenAPI 主链
