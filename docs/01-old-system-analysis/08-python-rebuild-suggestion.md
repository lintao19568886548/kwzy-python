# 08 Python 新版重构建议

> 目标产品：**AI 智慧园区平台**（`kwzy-python`）  
> 原则：**业务逆向驱动领域重建**，禁止 Java 代码直译  
> 输入：本目录 01–07 分析文档

---

## 0. 总体设计原则

1. **领域优先**：先定限界上下文与聚合，再选框架。  
2. **主链打穿**：园区 → 房源 → 合同 → 账单 → 收款 → 分析。  
3. **AI 原生**：AI 作为能力层，不进核心交易事务。  
4. **多端统一 API**：PC / 小程序 / App 共用契约，BFF 可选。  
5. **渐进迁移**：数据可迁、功能可灰度，不要求 Big Bang。  
6. **继承基因**：多租户 + 园区数据权限必须保留。  

---

## 1. DDD 领域拆分

### 1.1 建议限界上下文（Bounded Context）

| 上下文 | 中文 | 核心聚合 | 旧系统来源 |
| --- | --- | --- | --- |
| **IdentityAccess** | 身份与权限 | User, Role, Permission, Session | auth/system/permission |
| **TenantOps** | 租户运营（SaaS） | Tenant, Organization, Invitation, Provisioning | organization/customer |
| **ParkProperty** | 园区与空间资产 | Park, Building, Unit, FacilityAsset | park/factory/dormitory |
| **Lease** | 租赁合同 | TenantParty, LeaseContract, ContractTerm, Occupancy | rental_tenant |
| **Billing** | 计费账单 | Bill, BillLine, MeterReading, BillDraft | amount_bill/ele/water |
| **Collection** | 收款催缴 | Payment, Receipt, CollectionCase, SmsNotice | receipt/sms/rent_verify |
| **FinanceLedger** | 财务台账 | LedgerEntry, Reconciliation | finance |
| **Investment** | 招商 CRM | Lead, Activity, Opportunity | investment 传统 |
| **AcquisitionRadar** | 获客雷达 | CrawlJob, Signal, ScoreCard | investment/radar |
| **CRMChannel** | 渠道获客 | Channel, Scan, OwnerBinding | crm |
| **AccessControl** | 通行 | VisitorPass, VehiclePermit, DoorDevice | access |
| **FacilityOps** | 设施运维 | Asset, Inspection, WorkOrder | maintenance |
| **HRM** | 人事薪酬 | Employee, Attendance, Leave, Payroll | hrm + salary |
| **Metering** | 计量 | Meter, Reading, VendorAdapter | smartmeter/hezhong/ymsino |
| **Notification** | 通知 | InAppMessage, OutboxEvent | messaging/notices |
| **AIAssist** | AI 能力 | ChatSession, RecognizeJob, AgentTask | llm/agent/ai-bill |
| **Analytics** | 分析 | MetricSnapshot, DashboardQuery | dashboard |

### 1.2 上下文映射（关键）

```text
Investment --LeadConverted--> Lease
Lease --OccupancyChanged--> ParkProperty
Lease --BillableParty--> Billing
Metering --Readings--> Billing
Billing --BillIssued--> Collection
Collection --Paid--> FinanceLedger
Collection --Overdue--> CollectionCase
ParkProperty --Scope--> 几乎所有查询
IdentityAccess --Authz--> 所有写操作
AIAssist --BillDraft--> Billing（防腐层）
AcquisitionRadar --QualifiedLead--> Investment
```

### 1.3 聚合设计要点（相对旧模型纠偏）

| 旧模型 | 新模型 |
| --- | --- |
| `rental_tenant` 混合 | `TenantParty` + `LeaseContract` + `ContractVersion` |
| `amount_bill` 宽表费项 | `Bill` + `BillLine(fee_type, amount, qty, price)` |
| `receipt_time` 表示已收 | `Payment` + `PaymentAllocation` + 账单状态机 |
| `role_park`+`user_park` 双通道 | 统一 `DataScope(park_ids)` 策略 |
| 客户三套 | 统一 `Party`（组织/个人）+ 角色关系 |
| 巡检多表 | `WorkOrder` + `AssetType` 扩展 |

### 1.4 应用架构（Python）

推荐形态（可分阶段）：

```text
阶段1：模块化单体（Modular Monolith）
  FastAPI + 清晰 package 边界 + 异步任务队列

阶段2：按负载拆分服务
  - core-api（交易主链）
  - import-worker（账单导入/AI 识别）
  - radar-worker（爬虫与评分）
  - analytics-api（只读）
```

建议技术选型方向（非强制锁定版本）：

| 层 | 建议 |
| --- | --- |
| API | FastAPI / Starlette |
| 领域/应用 | 自研清晰 Service + Domain 模块（不必上重型框架） |
| ORM | SQLAlchemy 2.0 + Alembic |
| 校验 | Pydantic v2 |
| 任务 | Celery / Arq / RQ + Redis |
| 缓存 | Redis |
| 消息 | 先 Redis Stream/Rabbit，Outbox 表保留 |
| 权限 | Casbin 或自研 Policy + JWT |
| 观测 | OpenTelemetry + 结构化日志 |

---

## 2. 数据库重新设计方向

### 2.1 多租户策略

| 方案 | 适用 | 建议 |
| --- | --- | --- |
| 一租户一库（旧） | 强隔离、大客户 | **可选保留给旗舰客户** |
| 一库 + `tenant_id` 行级 | 中小客户、低运维 | **默认新方案** |
| Schema per tenant | 折中 | 可选 |

**推荐：混合**  
- 默认共享库 + `tenant_id` + RLS/强制过滤器  
- 大客户可迁独立库（连接路由继承旧思想，但模型统一）

### 2.2 核心表草案（逻辑）

```text
tenants
users, roles, permissions, user_roles, role_permissions
user_park_scopes

parks
buildings (原 factory)
units (原 factory_floor / dormitory 统一)
unit_media

parties (客户/企业主体)
lease_contracts
lease_contract_units (多房源)
lease_terms (递增、免租期等)
lease_status_history

fee_catalog (费项字典)
bills
bill_lines
meter_accounts
meter_readings

payments
payment_allocations
collection_cases
collection_records

ledger_entries

leads
lead_activities
lead_sources

work_orders
assets
inspections

employees, attendances, leave_requests, payroll_runs, payroll_items

outbox_events
audit_logs
```

### 2.3 账单状态机（示例）

```text
DRAFT → ISSUED → PARTIALLY_PAID → PAID
                 ↘ VOID
（逾期 is_overdue 为正交衍生属性，禁止 status=OVERDUE；见 05.1 ADR-002）
                 ↘ WRITTEN_OFF
```

### 2.4 合同状态机（示例）

```text
DRAFT → ACTIVE → EXPIRING → RENEWED
                  ↘ TERMINATED
                  ↘ BREACHED
```

### 2.5 迁移策略

1. 先迁 **主链主数据**（租户、园区、房源、合同、账单、收款）  
2. 财务流水对账后迁  
3. 招商/雷达分期  
4. 建立 **对账报表**：旧 amount_bill.total vs 新 bill 汇总  
5. 双写窗口可选，但应用层要有 anti-corruption  

---

## 3. API 设计方向

### 3.1 统一规范

- 前缀：`/api/v1`  
- 资源名复数名词：`/parks`、`/leases`、`/bills`  
- 动作：`POST /bills/{id}/issue`、`POST /bills/{id}/collect`  
- 错误：稳定 `error.code` + 可读 message  
- 分页：`page/page_size` + `total`  
- 幂等：写接口支持 `Idempotency-Key`  
- 文档：OpenAPI 自动生成，前端 orval/openapi-generator  

### 3.2 鉴权与范围

```text
Authorization: Bearer <access_token>
X-Tenant-Id: <tenant>          # 或从 token 解析
X-Park-Id: <current_park>      # 可选当前园区上下文
```

数据权限：服务层强制 `park_id IN scopes`，禁止只靠前端隐藏。

### 3.3 模块 API 蓝图（示例）

| 模块 | 资源示例 |
| --- | --- |
| Auth | `/auth/login` `/auth/refresh` `/auth/sms/*` |
| Parks | `/parks` `/parks/{id}/units` |
| Leases | `/leases` `/leases/{id}/renew` `/leases/{id}/terminate` |
| Bills | `/bills` `/bills/{id}/lines` `/bills/import/jobs` |
| Payments | `/payments` `/collection-cases` |
| Leads | `/leads` `/leads/{id}/convert` |
| WorkOrders | `/work-orders` |
| AI | `/ai/bill-recognize/jobs` `/ai/chat` |

### 3.4 兼容策略

- 不对旧前端承诺永久兼容  
- 若需过渡，单独 `/api/legacy/*` 防腐层，限期下线  

---

## 4. AI 能力融合方向

### 4.1 定位

AI = **副驾（Copilot）+ 自动化管道**，不是账本。

### 4.2 优先场景（ROI 排序）

| 场景 | 说明 | 旧系统基础 |
| --- | --- | --- |
| P0 账单识别入账 | Excel/通知单 → BillDraft → 人工确认 | ai-recognize/import |
| P0 催缴话术与名单 | 账龄分层 + 短信/企微文案 | collection-sms |
| P1 智能客服 | 园区制度/缴费 FAQ + RAG | smart-service |
| P1 招商线索评分 | 企业画像+需求匹配房源 | radar score |
| P1 合同风险摘要 | 到期/递增/空置预警 | contract reminder |
| P2 巡检影像识别 | 消防器材是否在位 | maintenance 图片 |
| P2 Agent 工作台 | 运营指令编排 | agent |

### 4.3 AI 架构

```text
[客户端] → API Gateway → AI Assist Service
                              │
                              ├─ Prompt/Tool Registry
                              ├─ LLM Provider (百炼/自建/SpaceXAI等)
                              ├─ RAG (园区知识库)
                              └─ 输出仅 BillDraft/建议，入账走 Billing 应用服务
```

规则：

1. AI 输出必须 **结构化 schema 校验**  
2. 低置信度强制人工  
3. 全链路 audit：模型、提示词版本、输入哈希、操作者  
4. 禁止 AI 直接写支付/删合同  

### 4.4 数据飞轮

- 导入纠正 → 模板/别名学习（旧 bill_import 已有治理思想，应保留）  
- 催缴成功率 → 策略优化  
- 线索转化 → 评分特征迭代  

---

## 5. PC / 微信小程序 / APP 三端设计建议

### 5.1 角色与端

| 角色 | 主端 | 核心任务 |
| --- | --- | --- |
| 园区管理员/财务 | PC | 合同、账单、财务、权限 |
| 管家/招商 | App / 小程序 | 跟进、巡检、催缴、访客 |
| 租户企业联系人 | 小程序 | 账单查询、缴费、报修、访客预约 |
| 访客 | 小程序/H5 | 登记 |
| 员工 | App | 打卡请假 |

### 5.2 三端架构

```text
                 ┌── PC Web (Vue3/React 管理台)
 API/BFF ────────┼── App (Flutter/UniApp/Capacitor 二选一)
                 └── 微信小程序 (原生或 uni-app)
```

建议：

- **管理端 PC**：继续中后台信息密度（表格、批量、导入）  
- **App**：任务制首页（待办、催缴、巡检、打卡）  
- **小程序**：租户自助 + 获客转化 + 分享  

### 5.3 能力矩阵

| 能力 | PC | App | 小程序 |
| --- | --- | --- | --- |
| 账单制单/导入 | ✅ | 部分 | ❌ |
| 收款确认 | ✅ | ✅ | ❌ |
| 租户缴费 | ❌ | 可选 | ✅ |
| 招商跟进 | ✅ | ✅ | 轻 |
| 打卡 | ❌ | ✅ | 可选 |
| 报修 | ✅ | ✅ | ✅ 租户 |
| 雷达运营 | ✅ | 轻 | ❌ |
| AI 识别 | ✅ | ✅ | ❌ |

### 5.4 旧三端问题纠正

- 停止「每个页面复制 mobile-list」；采用 **响应式 + 少数原生页**  
- 小程序不要只做 WebView 壳，关键路径（登录、账单、报修）原生化  
- 统一设计系统与权限码，避免三端菜单不一致  

---

## 6. 分阶段实施路线图

### 阶段 A：地基（4–6 周量级，示意）

- Identity + Tenant + ParkProperty  
- 基础权限与园区 scope  
- OpenAPI 与多端登录  

### 阶段 B：租赁主链

- Lease + Billing + Collection 最小闭环  
- 人工制单 + 收款 + 简单催缴  
- 数据从旧库迁移 PoC  

### 阶段 C：增强

- 导入管道 + AI 识别  
- 财务台账与核验  
- 工作台指标  

### 阶段 D：增长

- Investment + CRM  
- 雷达 worker 独立  
- 租户小程序缴费/报修  

### 阶段 E：智慧化

- 表计自动出账  
- Agent 运营编排  
- 分析仓与预测  

---

## 7. 工程与治理建议

1. **包结构按上下文**，禁止巨型 controller 文件  
2. **全部迁移用 Alembic**，禁止运行期改表探测成常态  
3. **契约测试**：OpenAPI 与集成测试守护主链  
4. **审计日志**一等公民  
5. **配置**：12-factor，密钥进密钥管理，不进仓库  
6. **灰度**：按租户开关新模块，而不是数百个内部 dry-run 类  
7. **文档**：ADRs 记录关键决策（多租户模型、账单模型等）  

---

## 8. 明确不做什么

1. 不把 Java messaging 的 PlanService 丛林搬到 Python  
2. 不保留 `Map` 式无 schema API  
3. 不把工资继续放在租赁模块  
4. 不让爬虫进程与交易 API 强绑定同生命周期  
5. 不为兼容而永久保留双路径 `/park` vs `/system/park`  

---

## 9. 成功标准（重建是否达标）

| 维度 | 标准 |
| --- | --- |
| 业务 | 合同-账单-收款闭环可独立运营一个园区 |
| 数据 | 新旧账单金额对账差异可解释 |
| 架构 | 核心上下文可独立测试，AI/导入可独立扩缩容 |
| 体验 | PC 管理效率不降，App 待办驱动，小程序租户可自助 |
| AI | 识别入账节省 ≥50% 月度制单时间（可度量） |
| 安全 | 园区数据权限零越权（自动化用例） |

---

## 10. 与文档目录的衔接

| 文档 | 用途 |
| --- | --- |
| 01 结构 | 摸清旧仓库与部署 |
| 02 后端业务 | 领域拆分输入 |
| 03 数据库 | 迁移与 ER 重建输入 |
| 04 前端页面 | 三端信息架构输入 |
| 05 API | 新 OpenAPI 对照清单 |
| 06 流程 | 状态机与用例 |
| 07 问题 | 还债优先级 |
| **08 本文** | **Python AI 智慧园区设计方向** |

---

## 11. 结语

旧系统证明了市场需求与功能广度；  
新系统要用 Python 生态更快集成 AI 与数据能力，但必须以 **清晰的园区领域模型** 为底盘。  

**下一阶段建议工作（分析之后）：**

1. 输出《AI 智慧园区领域设计说明书》（聚合/状态机/上下文图）  
2. 输出《核心库表 v1 DDL》  
3. 输出《OpenAPI v1 主链草稿》  
4. 在 `kwzy-python` 落地模块化单体骨架  

---

*本阶段仅分析，未修改旧系统任何文件，未编写业务 Python 实现代码。*
