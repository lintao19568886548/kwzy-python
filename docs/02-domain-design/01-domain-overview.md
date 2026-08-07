# AI 智慧园区平台 — 领域设计总览

> 版本：v1.0  
> 依据：`docs/01-old-system-analysis/*`  
> 产品代号：`kwzy-python`  
> 原则：领域重建，禁止 Java 直译

---

## 1. 产品愿景

面向产业园区/厂房租赁运营商的 **AI 原生智慧园区运营平台**：

- 管空间（园区、楼栋、可租单元）
- 管合同（入驻企业、条款、到期续退）
- 管现金流（账单、收款、催缴、台账）
- 管增长（招商线索、渠道、雷达获客）
- 管现场（通行、巡检工单、表计）
- 用 AI 降本增效（制单识别、催缴策略、客服、线索评分）

---

## 2. 统一语言（Ubiquitous Language）

| 术语 | 含义 | 旧系统对应（勿再混用） |
| --- | --- | --- |
| **租户（SaaS Tenant）** | 购买/使用本平台的运营组织 | `customer` / 租户库 |
| **入驻方（Tenant Party）** | 园区内承租企业或个人 | `rental_tenant` 的客户部分 |
| **租赁合同（Lease Contract）** | 法律与计费约定 | `rental_tenant` 的合同部分 |
| **可租单元（Unit）** | 可出租的最小空间单元 | `factory_floor` / 宿舍房间抽象 |
| **楼栋（Building）** | 厂房/宿舍楼 | `factory` / `dormitory` |
| **园区（Park）** | 运营空间与数据权限边界 | `park` |
| **账单（Bill）** | 一期应收凭证 | `amount_bill` |
| **费项行（Bill Line）** | 账单明细（租/水/电/管理…） | 头表宽字段 + ele/water |
| **收款登记（Payment）** | 运营登记的一笔实收（**非**在线支付订单） | `receipt_time` 隐含 |
| **核销（Allocation）** | 收款分摊到账单 | 缺失 |
| **逾期（is_overdue）** | 账单衍生属性，**不是** status 枚举 | 无显式模型 |
| **催缴案件（Collection Case）** | 逾期跟进过程 | 仅短信发送 |
| **线索（Lead）** | 潜在入驻意向 | `investment` / radar lead |
| **数据范围（Data Scope）** | 用户可访问的园区集合 | `role_park` + `user_park` |

---

## 3. 限界上下文一览

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ IdentityAccess│────▶│  TenantOps   │────▶│ ParkProperty │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                     ┌──────────────┐             │
                     │ Investment   │──convert──▶│
                     │ + CRMChannel │             │
                     └──────────────┘             ▼
                                          ┌──────────────┐
                                          │    Lease     │
                                          └──────┬───────┘
                                                 │
                     ┌──────────────┐            ▼
                     │   Metering   │──readings─▶│  Billing   │
                     └──────────────┘            └──────┬───────┘
                                                        │
                                                        ▼
                                                 ┌──────────────┐
                                                 │  Collection  │──▶ FinanceLedger
                                                 └──────────────┘
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ FacilityOps  │  │     HRM      │  │  AccessCtrl  │  │  Analytics   │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
                          ▲
                          │ tools / drafts only
                   ┌──────────────┐
                   │   AIAssist   │
                   └──────────────┘
```

### 3.1 上下文职责表

| 上下文 | 职责 | 不负责 |
| --- | --- | --- |
| IdentityAccess | 登录、用户、角色、权限码、会话 | 园区业务规则 |
| TenantOps | SaaS 组织开通、邀请、订阅 | 入驻合同 |
| ParkProperty | 园区/楼栋/单元库存与状态 | 合同条款、账单 |
| Lease | 入驻方、合同、占用、续退租 | 出账计算细节可委派 |
| Billing | 出账、费项、草稿、作废 | 收现金、发短信 |
| Collection | 收款、核销、催缴案件 | 改合同 |
| FinanceLedger | 台账分录、对账 | UI 经营看板口径可另建 |
| Investment | 线索跟进、转化 | 爬虫采集实现 |
| AcquisitionRadar | 公域采集、评分信号（可独立部署） | 直接改合同 |
| Metering | 表计档案与读数 | 生成正式账单（输出读数事件） |
| FacilityOps | 资产、巡检、工单 | 财务 |
| HRM | 员工考勤薪酬 | 租赁合同 |
| AccessControl | 访客车辆门禁 | 合同 |
| AIAssist | 识别/对话/建议 | 交易最终提交须经应用服务 |
| Analytics | 只读指标 | 写业务状态 |

---

## 4. 核心域 / 支撑域 / 通用域

| 类型 | 上下文 |
| --- | --- |
| **核心域** | Lease、Billing、Collection、ParkProperty |
| **支撑域** | Investment、Metering、FacilityOps、FinanceLedger、Analytics |
| **通用域** | IdentityAccess、TenantOps、Notification、AIAssist |

一期必须打通：**ParkProperty → Lease → Billing → Collection**。

---

## 5. 多租户与数据权限（横切）

### 5.1 租户隔离

- 每个请求解析 `tenant_id`（JWT claim）
- 默认 **共享库 + tenant_id 行级隔离**
- 旗舰客户可配置独立库连接（路由层），**表结构必须一致**

### 5.2 园区数据范围

- 用户有效园区 = 角色授权 ∪ 用户直接授权（可配置取交集策略，默认并集）
- 所有带 `park_id` 的读/写必须校验 scope
- 超级管理员可跨园（**显式** `roles.all_parks` / `users.all_parks` → `park_scope_mode=ALL`，须审计）
- 动作权限 `*` **不**授予全园；空 `park_ids` 且非 ALL → 无园区数据访问

### 5.3 审计

- 关键写操作写 `audit_logs`：谁、何时、何租户、何资源、前后快照摘要

---

## 6. 领域事件（跨上下文协作）

| 事件 | 发布方 | 订阅方 | 用途 |
| --- | --- | --- | --- |
| `LeadConverted` | Investment | Lease | 创建入驻方与合同草稿 |
| `LeaseActivated` | Lease | ParkProperty, Billing | 占用单元、可计费 |
| `LeaseTerminated` | Lease | ParkProperty | 释放单元 |
| `BillIssued` | Billing | Collection, Analytics | 进入应收 |
| `BillOverdue` | Billing/Job | Collection | 建催缴案件 |
| `PaymentReceived` | Collection | Billing, FinanceLedger | 更新账单状态、入账 |
| `MeterReadingCaptured` | Metering | Billing | 生成水电行草稿 |
| `TenantProvisioned` | TenantOps | Identity, Notification | 初始化管理员 |

事件投递：先 **Outbox 表**，再异步派发（Redis Stream / RabbitMQ）。

---

## 7. 应用层用例（主链）

| 用例 | 主上下文 | 说明 |
| --- | --- | --- |
| 登录 | IdentityAccess | 密码/短信，发 JWT |
| 创建园区 | ParkProperty | 建园 + 授权 |
| 维护单元 | ParkProperty | 楼栋/单元 CRUD、空置状态 |
| 新签合同 | Lease | 入驻方 + 合同 + 占用 |
| 出账 | Billing | 人工/导入/AI 草稿确认 |
| 确认收款 | Collection | 登记支付并核销 |
| 催缴 | Collection | 预览 + 二次验证 + 发送 |
| 线索转化 | Investment→Lease | 一键转合同草稿 |
| AI 识别制单 | AIAssist→Billing | 只产草稿 |

---

## 8. 模块与代码目录映射（Python）

```text
apps/api/app/modules/
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
```

每个模块建议内部：

```text
api.py          # 路由
schemas.py      # Pydantic DTO
models.py       # SQLAlchemy
service.py      # 应用服务
domain.py       # 实体/值对象/状态机（可先薄）
repository.py   # 持久化
events.py       # 领域事件定义
```

---

## 9. 与旧系统关系

| 旧概念 | 新处理 |
| --- | --- |
| `rental_tenant` | 拆成 Party + LeaseContract |
| `amount_bill` 宽表 | Bill + BillLine |
| `receipt_time` | Payment + 状态机 |
| salary 在 rental | 迁 HRM（二期） |
| investment + radar 同 Controller | 分模块；radar 可独立 worker |
| Map 响应 | 强类型 Schema + OpenAPI |

---

## 10. 文档索引

| 文档 | 内容 |
| --- | --- |
| `01-domain-overview.md` | 本文 |
| `02-aggregates-and-state-machines.md` | 聚合与状态机 |
| `03-context-map.md` | 上下文映射与集成 |
| `../03-database/` | DDL |
| `../04-api/` | OpenAPI |

---

## 11. 决策记录（ADR 摘要）

完整正文见：`docs/02-domain-design/04-adr-pack.md`（阶段 05.1）。

1. **默认共享库多租户**，兼容独立库路由（密钥引用，不明文 DSN）。  
2. **合同与入驻方分离**。  
3. **账单行模型**，费项字典化。  
4. **收款与账单分离**，支持部分核销；Payment=收款登记。  
5. **账单主状态不含 OVERDUE**，逾期为正交衍生属性。  
6. **AI 不直接提交交易**，只产 Draft。  
7. **一期模块化单体**，导入/雷达后续拆 worker。  
8. **Park/Building/Unit 独立聚合根**；`used_area` 为占用投影。
