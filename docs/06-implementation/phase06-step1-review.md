# Phase06-Step1 基础代码审查报告

> 审查日期：2026-08-07  
> 范围：Identity + Park + Unit（**不含** Party/Lease/Bill/Payment）  
> 原则：只评基础架构；发现的问题仅修架构，不扩业务  

> 2026-08-07 后续补充：`harden-step1-foundation` 已完成 RBAC、统一错误、
> request_id/JSON 日志、事务审计与删除缺陷修复；当前全量测试为 **23 passed**。

---

## 0. 结论摘要

| 项 | 结论 |
| --- | --- |
| 总体评价 | **有条件通过（Conditional Pass）** |
| 是否可进入下一步（Party） | **可以**，在本轮架构修复之后 |
| 审查后修复 | 已完成（见 §8） |
| 测试 | **12 passed**（含隔离用例） |

```text
【STEP1 ARCHITECTURE REVIEW: CONDITIONAL PASS → FIXED】
核心仓库与分层可用；P0 安全语义问题已修复。
不要继续 Party 直至产品指令；本审查已结束。
```

---

## 1. SQLAlchemy 2.0 模型规范

### 1.1 检查结果：**通过（良好）**

| 检查点 | 状态 | 说明 |
| --- | --- | --- |
| DeclarativeBase | ✅ | `Base` 统一元数据 |
| `Mapped[]` + `mapped_column` | ✅ | 全模型使用 |
| 类型注解 | ✅ | 完整 |
| `relationship` | ✅ | Tenant↔User/Park，Park↔Building↔Unit |
| `created_at` / `updated_at` | ✅ | `TimestampMixin` |
| `tenant_id` | ✅ | 业务表具备；FK → tenants |
| 软删除 | ✅ | Park/Building/Unit `is_deleted` |
| PK 跨库 | ✅ | BigInteger + SQLite Integer variant |
| UniqueConstraint | ✅ | username/tenant、unit code/building |

### 1.2 后续扩展支持（Party/Lease/Bill/Payment）

| 能力 | 是否就绪 | 说明 |
| --- | --- | --- |
| 共用 Base/Mixin | ✅ | 新模型可直接继承 |
| tenant_id 列约定 | ✅ | FK_TYPE + index |
| park_id 列约定 | ✅ | Unit 已示范；Party/Bill 同构 |
| Alembic 链路 | ✅ | env 已挂 metadata |
| 关系图扩展点 | ✅ | Park 为空间根；后续 Party/Lease 挂 park_id |

**建议（不阻塞）：**  
后续模型统一使用 `TenantMixin` **或** 显式 `tenant_id = mapped_column(FK_TYPE, ForeignKey("tenants.id"))`（当前因 relationship 需要 FK，显式写法更清晰，保持一致即可）。

### 1.3 小问题（非阻塞）

| ID | 问题 | 级别 |
| --- | --- | --- |
| M1 | Application 直接构造 ORM 实体 | 中（务实单体可接受） |
| M2 | Identity 无 SoftDelete（User） | 低（可二期） |
| M3 | `updated_at` 依赖 onupdate，部分 DB 需应用层保证 | 低 |

---

## 2. Repository 是否支持后续模块

### 2.1 检查结果：**通过（修复后更稳）**

`TenantParkRepositoryBase` 已提供：

- `tenant_id` 强制过滤（`_base_select`）
- `apply_park_scope` / `assert_park_in_scope`
- `get_by_id` / `list` / `count` / `add` / `save` / `soft_delete`
- `add` **强制覆盖** `entity.tenant_id = ctx.tenant_id`（防伪造）

后续模块继承方式：

```text
PartyRepository(park_field="park_id")
LeaseRepository(park_field="park_id")
BillRepository(park_field="park_id")
PaymentRepository(park_field="park_id")
```

Park 自身使用 `park_field="id"` 做 scope（列表按 park.id 过滤）——设计可理解。

### 2.2 审查中发现并已修复

| ID | 问题 | 修复 |
| --- | --- | --- |
| R1 | `add()` 在 `park_field="id"` 时可能对 Park 误做 park 校验语义混乱 | `park_field != "id"` 才做 park 字段校验 |
| R2 | `save()` 未校验 park scope | 已对非 id 的 park 字段补 `assert_park_in_scope` |

### 2.3 后续注意（文档级）

- Bill/Payment 批量写入必须走同一 base，禁止 Session 裸 query。  
- `find_by_*` 类方法必须基于 `_base_select()`（Unit 已遵守）。  

---

## 3. tenant_id 隔离

### 3.1 设计意图：**正确**

- 上下文：`TenantContext.tenant_id`  
- 仓储：所有 select 带 `tenant_id == ctx.tenant_id`  
- 写入：强制 stamp tenant_id  

### 3.2 审查中发现并已修复

| ID | 问题 | 级别 | 修复 |
| --- | --- | --- | --- |
| T1 | JWT 缺 `tenant_id` 时变为 0 仍可能进系统 | **高** | deps 拒绝 `tenant_id <= 0` |
| T2 | 登录按 username 全局查，多租户同名冲突 | **中** | 多候选返回 `AUTH_TENANT_AMBIGUOUS` |
| T3 | 无跨租户隔离自动化测试 | **高（质量）** | 新增 `test_isolation.py` |

### 3.3 验证

- `test_tenant_isolation_park_list`：租户 A 不可见租户 B 的 Park  
- `test_tenant_id_spoof_on_create_is_overwritten`：创建结果 tenant_id 强制为上下文  

**结论：修复后 tenant 隔离正确，可支撑后续 Party/Lease/Bill。**

---

## 4. park_id 数据权限

### 4.1 原实现缺陷（P0，已修）

```python
# 错误语义（已删除）
has_all_park_access = ... or not self.park_ids
```

空 `park_ids` 被当成「全部园区」→ **权限放大**，后续 Bill/Payment 会直接串园。

### 4.2 修复后语义

| 条件 | 权限 |
| --- | --- |
| `permissions` 含 `*` 或 `is_platform_admin` | 全园 |
| 否则 `park_ids` 非空 | 仅列表内园区 |
| 否则 `park_ids` 空 | **无园区**（拒绝） |

Dev 无 Token：仍发 `permissions=["*"]`（仅 local/test）。  
Production：无 Token → 401。

### 4.3 验证

- `test_empty_park_ids_is_not_all_access`  
- `test_park_scope_blocks_other_park`  
- `test_unit_scope_and_tenant`（读/写越权）  

**结论：修复后 park 数据权限正确。**

---

## 5. 分层严格性

### 5.1 目标结构

```text
interface → application → domain
                ↓
         infrastructure
```

### 5.2 实际对照

| 层 | 现状 | 评价 |
| --- | --- | --- |
| interface | `interface/api.py` + schemas | ✅ 薄 |
| application | ParkService / UnitService | ✅ 有用例 |
| domain | `states.py` 状态规则 | ✅ 有，但偏薄 |
| infrastructure | models / repositories / session | ✅ |

### 5.3 违规/债务

| ID | 问题 | 级别 | 处理 |
| --- | --- | --- | --- |
| L1 | Application **直接依赖 ORM Model**（构造 Park/Unit） | 中 | **本步不重构实体**；后续可引入 domain entity + mapper。记录为可接受务实债务。 |
| L2 | Application 内 `session.commit()` | 低 | 单体常见；可后期 UoW |
| L3 | Identity login 在 interface 直访问 Session+Model | 中 | 可下沉 Application；step1 可接受 |
| L4 | 旧 stub 模块仍在目录（billing 等 api 未挂 main） | 低 | main 仅注册 identity+park；无运行风险 |

**结论：分层方向正确，未达到教科书级纯 domain；对 Step1 可接受，扩展 Party 前保持同一纪律即可。**

---

## 6. API 响应格式

### 6.1 检查结果：**通过**

成功：

```json
{ "code": "OK", "message": "...", "data": ... }
```

业务错误（`AppError`）：

```json
{ "code": "PARK_NOT_FOUND", "message": "...", "data": null }
```

| 检查点 | 状态 |
| --- | --- |
| `ok()` 统一 envelope | ✅ |
| AppError handler 同 shape | ✅ |
| snake_case 路径参数 | ✅ |
| HTTP 状态码 + body.code | ✅ |

### 6.2 小建议（非阻塞）

- 校验错误（FastAPI 422）尚未统一成 envelope — 可后续加 exception handler。  
- 分页结构已在 data 内：`total/page/page_size/items` — 与设计一致。  

---

## 7. 测试覆盖

### 7.1 审查前

| 覆盖 | 状态 |
| --- | --- |
| DB 连接 | ✅ |
| 建 Park/Unit | ✅ |
| 关系 | ✅ |
| API 流程 | ✅ |
| **租户隔离** | ❌ |
| **园区 scope** | ❌ |
| 状态机非法迁移 | 弱 |

### 7.2 审查后

| 文件 | 内容 |
| --- | --- |
| `tests/test_park_unit.py` | 功能与 API |
| `tests/test_isolation.py` | 租户隔离 + park scope + 语义断言 |
| `tests/test_health.py` | 健康检查 |

```text
12 passed
```

### 7.3 仍可增强（不阻塞下一步）

- 非法 unit 状态迁移 400  
- 软删除后 list 不可见  
- production 无 Token → 401  
- 登录多租户歧义  

---

## 8. 本轮已修复清单（仅基础架构）

| 修复项 | 文件 |
| --- | --- |
| `has_all_park_access` 去掉「空 park_ids=全权限」 | `shared/tenant_context.py` |
| JWT 强制有效 `tenant_id` | `shared/deps.py` |
| Repository add/save park 校验边界 | `repository_base.py` |
| 登录多租户用户名歧义 | `identity/interface/api.py` |
| 隔离与 scope 测试 | `tests/test_isolation.py` |

**未做：** 新增 Party/Lease/Bill/Payment 任何业务。

---

## 9. 分项评分（修复后）

| 维度 | 分数（10） |
| --- | --- |
| SQLAlchemy 规范 | 8.5 |
| Repository 可扩展性 | 8.5 |
| tenant 隔离 | 9.0 |
| park 权限 | 9.0 |
| 分层严格性 | 7.0 |
| API 响应统一 | 8.5 |
| 测试覆盖 | 8.0 |
| **综合** | **8.3 / 10** |

---

## 10. 对后续 Party 的前置条件

进入 Party 前建议遵守：

1. `Party` 模型：`tenant_id` + `park_id` + SoftDelete + timestamps  
2. `PartyRepository(TenantParkRepositoryBase)`，`park_field="park_id"`  
3. Service 只通过 Repository 访问；创建时 stamp tenant  
4. 测试至少复制：跨租户不可见 + 跨园 403/404  
5. 不使用 `park_ids=[]` 表示超管；超管必须 `permissions=["*"]`  

---

## 11. 最终裁定

| 项 | 内容 |
| --- | --- |
| 裁定 | **通过（修复后）** |
| 阻塞项 | 无 |
| 技术债 | Application 依赖 ORM（可接受） |
| 禁止 | 在未指令前开发 Party |

```text
【PHASE06-STEP1 REVIEW COMPLETE】

基础架构可支撑后续 Party / Lease / Bill / Payment。
等待下一步指令。
```
