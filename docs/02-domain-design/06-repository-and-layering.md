# Repository 数据过滤基类 & 分层冻结（设计，非实现代码）

> 阶段 05.1 / design-patch-v1  
> **禁止在本阶段生成 SQLAlchemy 业务实现**；本文仅冻结设计契约，供阶段 06 落地。

---

## 1. 分层冻结（强制）

每个限界上下文模块目录结构：

```text
modules/<context>/
  interface/                 # 或扁平 api.py + schemas.py
    api.py                   # HTTP 路由，无业务规则
    schemas.py               # 请求/响应 DTO（Pydantic）
  application/
    service.py               # 用例编排、事务边界、权限检查调用
    commands.py              # 可选
    queries.py               # 可选
  domain/
    entities.py              # 聚合/实体/值对象（纯 Python）
    states.py                # 状态机与迁移
    events.py                # 领域事件定义
    services.py              # 领域服务（如 OccupancyService 规则）
  infrastructure/
    models.py                # ORM 表映射
    repository.py            # 仓储实现（继承 TenantParkRepository）
    adapters/                # SmsSender / Storage 等端口实现
```

### 1.1 依赖方向（单向）

```text
interface → application → domain
                ↓
         infrastructure → domain（映射）
```

| 允许 | 禁止 |
| --- | --- |
| application 调用 repository 接口 | domain import FastAPI / SQLAlchemy |
| interface 只调 application service | interface 直接 Session / 裸 SQL |
| infrastructure 实现端口 | 跨模块 import 他模块 models 写库 |
| shared/core 放横切 | 循环依赖 modules |

### 1.2 与现有骨架映射

当前 `apps/api/app/modules/*/api.py` 为 stub。阶段 06 按上表拆分或先用扁平文件但 **逻辑归属** 必须符合四层：

| 文件 | 层 |
| --- | --- |
| api.py / schemas.py | interface |
| service.py | application |
| domain.py | domain |
| models.py / repository.py | infrastructure |

---

## 2. 租户 / 园区数据过滤 — Repository 基类设计

### 2.1 设计目标

1. **默认带 `tenant_id`**，杜绝串租  
2. **写/读带 park 的资源时校验 DataScope**  
3. 业务 Repository 禁止手写「忘了 tenant」的查询  

### 2.2 伪代码契约（非可运行业务代码）

```text
<<abstract>> TenantContext
  + tenant_id: int
  + user_id: int
  + park_ids: list[int]      // LIST 模式有效园区；空且非 ALL → 无访问
  + park_scope_mode: NONE|LIST|ALL  // 全园仅 all_parks，不由 * 推导
  + permissions: list[str]
  + is_platform_admin: bool

<<abstract>> TenantParkRepositoryBase
  # 构造注入：session, tenant_context

  # ---- 租户 ----
  + current_tenant_id() -> int
  + apply_tenant(query) -> query
      # 强制 WHERE entity.tenant_id = :tenant_id

  # ---- 园区 ----
  + assert_park_in_scope(park_id) -> void
      # park_id not in scope 且非 admin → raise FORBIDDEN
  + apply_park_scope(query, park_column) -> query
      # WHERE park_column IN (:scope) ；scope 为空且非 admin → 空结果
  + filter_optional_park(query, park_column, park_id?) -> query
      # 若传入 park_id：先 assert 再等值过滤；否则 apply_park_scope

  # ---- 通用 ----
  + get_by_id_for_tenant(id) -> entity|None
      # id + tenant_id 双条件
  + add(entity) -> void
      # 写入前 entity.tenant_id = current；若有 park_id 则 assert_park_in_scope
```

### 2.3 业务仓储继承关系（示例）

```text
TenantParkRepositoryBase
  ├── ParkRepository
  ├── UnitRepository
  ├── PartyRepository
  ├── LeaseRepository
  ├── BillRepository
  ├── PaymentRepository
  ├── CollectionCaseRepository
  └── LeadRepository
```

无 `park_id` 的全局表（如部分系统字典）可仅用 `TenantRepositoryBase`（只过滤 tenant）。

### 2.4 查询规则表

| 操作 | tenant_id | park scope |
| --- | --- | --- |
| list parks | 强制 | 结果集 ∩ scope |
| list bills | 强制 | IN scope；可选 park_id 精确 |
| create bill | 强制写入 | assert park_id ∈ scope |
| get by id | id + tenant | 加载后校验 park ∈ scope |
| admin `*` | 强制 tenant（除非平台级跨租户 API，另开） | 可跨园，必须 audit |

### 2.5 Application 层配合

```text
BillService.issue(bill_id):
  bill = bill_repo.get_by_id_for_tenant(bill_id)  # 已带 tenant
  # repo 内已 park scope 校验
  domain.BillStateMachine.issue(bill)
  bill_repo.save(bill)
  outbox.append(BillIssued)
```

**Service 不得** 绕过 Repository 用 `session.execute("SELECT * FROM bills")`。

### 2.6 测试契约（阶段 06 必写）

1. Tenant A 插入账单，Tenant B get/list 不可见  
2. 用户 scope 仅 park=1，无法写 park=2  
3. 创建时自动写入 tenant_id，伪造其他 tenant_id 被覆盖或拒绝  

---

## 3. DataScope 解析（应用启动/请求级）

```text
resolve_park_scope(user_id, tenant_id):
  from role_park_scopes ∪ user_park_scopes
  if permission contains "*": return ALL_MARKER
  return distinct park_ids
```

结果放入 `TenantContext`，Repository 只读上下文，不重复查库（可请求级缓存）。

---

## 4. 与 OpenAPI / 领域对齐检查

| 设计点 | 状态 |
| --- | --- |
| snake_case API | OpenAPI v1.1 |
| envelope | `{code,message,data}` |
| Bill 无 OVERDUE 主状态 | 领域+DDL+API |
| Payment 收款登记 + allocation | 领域+DDL |
| collection_case + collection_record | 领域+DDL+API |
| LeaseTerm / Attachment | 领域+DDL 基线表 |

---

## 5. 阶段 06 落地顺序（提醒，本阶段不实现）

1. `TenantContext` + 依赖注入  
2. `TenantParkRepositoryBase`  
3. Park/Unit 仓储验证过滤器  
4. 再实现 Lease/Bill/Payment/Collection  
