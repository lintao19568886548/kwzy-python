# Phase 06 Step1 完成报告

> 范围：**Identity + Park + Unit** 仅  
> 未实现：Party / Lease / Bill / Payment  
> 未修改：`kwzg-Java-main`  
> 未写入：旧系统数据库  

---

## 1. 完成清单

| 任务 | 状态 |
| --- | --- |
| SQLAlchemy 2.0 Models（Mapped / relationship / tenant_id / 软删） | ✅ |
| Alembic 初始化 + 首次 migration | ✅ |
| 数据库创建成功（SQLite `kwzy_step1.db`） | ✅ |
| Repository 基类 tenant/park 过滤 | ✅ |
| Park / Unit Service | ✅ |
| REST `/parks` `/units` CRUD | ✅ |
| RBAC 登录授权（Role/Permission/UserRole/园区范围） | ✅ |
| 统一错误 envelope + request_id + JSON 日志 | ✅ |
| Park/Unit 同事务审计 | ✅ |
| pytest | ✅ **23 passed** |

---

## 2. 分层落位

```text
app/
  infrastructure/database/
    base.py                          # Base + mixins
    session.py                       # engine/session
    repository_base.py               # TenantParkRepositoryBase
    models/
      identity.py                    # Tenant, User, Role, UserParkScope
      park_property.py               # Park, Building, Unit
  modules/identity/
    application/bootstrap.py         # 默认租户种子
    interface/api.py                 # /auth/login, /auth/me
  modules/park_property/
    domain/states.py                 # 状态机
    application/park_service.py
    application/unit_service.py
    infrastructure/*_repository.py
    interface/api.py + schemas.py
```

---

## 3. 数据库

### 3.1 Migration

- `alembic/versions/44cb70117ff4_step1_identity_park_unit.py`（以实际文件名为准）
- `alembic/versions/8c2f4aa10b7d_step1_foundation_hardening.py`
- 命令：

```bash
cd apps/api
set PYTHONPATH=.
set DATABASE_URL=sqlite+pysqlite:///./kwzy_step1.db
alembic upgrade head
```

### 3.2 表清单（step1）

`tenants`, `users`, `roles`, `permissions`, `role_permissions`, `user_roles`,
`user_park_scopes`, `role_park_scopes`, `parks`, `buildings`, `units`, `audit_logs`,
`alembic_version`

### 3.3 安全说明

- 默认 **SQLite 本地库**，**不连接** 旧 Java MySQL  
- 生产请使用**新建空库**的 MySQL URL，禁止指向 `magic` 旧库  

---

## 4. API（prefix `/api/v1`）

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/parks` | 列表 |
| POST | `/parks` | 创建 |
| GET | `/parks/{park_id}` | 详情 |
| PATCH | `/parks/{park_id}` | 修改 |
| DELETE | `/parks/{park_id}` | 软删 |
| GET | `/units` | 列表（可 `park_id`） |
| POST | `/units` | 创建（绑定 park；无 building 时自动主楼） |
| GET | `/units/{unit_id}` | 详情 |
| PATCH | `/units/{unit_id}` | 修改 |
| PATCH | `/units/{unit_id}/status` | 状态迁移 |
| DELETE | `/units/{unit_id}` | 软删 |
| POST | `/auth/login` | 租户感知登录；可选 tenant_code（本地 admin/admin123 种子） |
| GET | `/auth/me` | 当前上下文 |

响应 envelope：`{ code, message, data }`

---

## 5. 业务规则（已实现）

**Park**

- 创建 / 修改 / 查询 / 软删  
- 强制 `tenant_id`  

**Unit**

- 必须绑定 `park_id`  
- 可选 `building_id`；缺省自动创建园区下「主楼」  
- 状态迁移：`domain/states.py` 白名单  
- `used_area` 不接受业务随意主数据改写（投影字段，step1 忽略客户端写入）  

**Repository**

- 所有查询带 `tenant_id`  
- park 数据范围：仅 `permissions` 含 `*` 或 `is_platform_admin` 视为全园；
  否则只允许 `park_ids` 内园区，空 `park_ids` 表示无园区权限  
- 动作权限：Park/Unit 读写分别校验 `park:*` / `unit:*` 权限码  
- 关键写操作：JSON 业务日志 + `audit_logs` 同事务记录  

---

## 6. 测试结果

```text
23 passed
```

覆盖：

1. 数据库连接  
2. 创建 Park  
3. 创建 Unit  
4. Park–Building–Unit 关系  
5. 状态迁移  
6. HTTP API 端到端  
7. 租户感知登录与数据库 RBAC claims  
8. 权限拒绝与 production 无 Token 401  
9. 422/500 统一错误 envelope 与 request_id  
10. 非法状态、软删除、事务审计和结构化日志  

```bash
cd apps/api
set PYTHONPATH=.
pytest -q
```

---

## 7. 本地启动

```bash
cd apps/api
set PYTHONPATH=.
set DATABASE_URL=sqlite+pysqlite:///./kwzy_step1.db
uvicorn app.main:app --reload --port 8000
```

- Swagger: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

---

## 8. 明确未做（等待指令）

- ❌ Party  
- ❌ Lease  
- ❌ Bill  
- ❌ Payment  
- ❌ Collection  
- ❌ refresh token / logout / SMS / page-access（仍属后续 Identity 能力）  
- ❌ Building 独立 CRUD 与 used_area 占用投影服务  

Lease/Billing/Collection 等目录中的 `api.py` 当前仍为未挂载 stub。

---

## 9. 出口

```text
【PHASE06-STEP1 COMPLETE】

Identity + Park + Unit 基础模块已验证。
等待下一步指令（再开 Party / Lease 等）。
```


---

## 后记（2026-08-07）close-step1-acceptance-gaps

在不动 Party/Lease/Bill/Payment 前提下关闭验收缺口：DB head、无密钥 bootstrap、权限/园区正交、DDD Entity+Mapper、日志 module、OpenAPI 校验与 Git runbook。  
授权语义变更原因：纠正 `*` 误授全园；ADR-005 与 07 测试规范同步修订。详见验收报告后记。
