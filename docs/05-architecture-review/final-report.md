# 架构冻结评审 — 最终报告

> 项目：`kwzy-python`（AI 智慧园区）  
> 评审日：以仓库文档版本为准  
> 角色：CTO / 企业架构师 / DDD / 智慧园区产品架构  
> 范围：设计冻结评审（无业务编码）

---

## 0. 执行摘要

| 项 | 结论 |
| --- | --- |
| 旧系统主链是否被正确重建 | **是**（且模型优于旧系统） |
| 是否可宣称「全业务完整迁移设计」 | **否**（大量支撑域刻意二期） |
| 领域主链是否可开发 | **是（有条件）** |
| DDL / OpenAPI / 分层是否无保留意见冻结 | **否** |
| **最终裁定** | **条件通过（Conditional Approval）** |

### 裁定语句

```text
【ARCHITECTURE CONDITIONALLY APPROVED】

允许进入「阶段 06：SQLAlchemy + Alembic + 核心 CRUD」的范围仅限：
  Identity(基础) + ParkProperty + Party/Lease + Billing + Collection(收款)

前提：完成本报告第 3 节「必须修改问题」的设计修订（改文档/DDL/OpenAPI/ADR），
再开始持久化编码。

未完成 P0 设计修订前，禁止大规模 CRUD 开发。
```

**不是无条件的 `【ARCHITECTURE APPROVED】`。**  
原因：领域-DDL-API 三线不一致、账单状态语义、租户安全过滤器与分层规范尚未闭合——带着裂缝编码会形成第三代技术债。

---

## 1. 当前架构评分（100 分）

| 分项 | 权重 | 得分 | 加权 |
| --- | --- | --- | --- |
| 业务覆盖与分期策略 | 15% | 72 | 10.8 |
| 领域模型（主链） | 25% | 72 | 18.0 |
| 数据库设计 | 20% | 70 | 14.0 |
| API 设计 | 15% | 73 | 11.0 |
| 技术架构与演进 | 15% | 68 | 10.2 |
| 一致性（域/库/API/代码骨架） | 10% | 55 | 5.5 |
| **总分** | 100% | — | **69.5 ≈ 70 / 100** |

### 分数解读

| 区间 | 含义 |
| --- | --- |
| 85+ | 可无保留意见冻结 |
| 70–84 | 条件通过，补 P0 后开发 |
| 60–69 | 主链方向对，但不可开干 |
| <60 | 推倒重来 |

**70 分 = 条件通过线。** 主链思想达标；工程一致性拖后腿。

---

## 2. 第一部分：业务完整性检查（缺失业务列表）

> 说明：「当前设计对应」含领域文档 / DDL / OpenAPI 三者综合；任一缺失则视为未完整设计。

### 2.1 用户权限

**业务名称：** 用户权限与访问控制  

**旧系统对应：** 中心/租户用户、角色、菜单、权限码、role_park/user_park、二次验证、部门  

**当前设计对应：** users/roles/permissions/scopes + JWT；领域 IdentityAccess  

**是否需要补充：** **是（一期必要子集）**  

**建议方案：**  

- 一期：登录 + RBAC + 园区 scope + 权限码（可无动态菜单，前端静态路由）  
- 必须：page-access 高敏二次验证（催缴）  
- v1.1：menus/role_menus、部门、改密/登出 OpenAPI 化  

---

### 2.2 园区管理

**业务名称：** 园区管理  

**旧系统对应：** park CRUD、园区列表、看板统计  

**当前设计对应：** parks 表 + Park API  

**是否需要补充：** 小（统计 API）  

**建议方案：** 主 CRUD 进入 06；dashboard 统计可二期读模型  

---

### 2.3 空间管理

**业务名称：** 空间/房源管理  

**旧系统对应：** factory、factory_floor、dormitory、租赁 manage  

**当前设计对应：** buildings + units + 状态机  

**是否需要补充：** 小  

**建议方案：** 一期落地；宿舍用 building_type 区分；附件/图片存储端口  

---

### 2.4 企业管理（入驻企业）

**业务名称：** 入驻企业管理  

**旧系统对应：** rental_tenant 客户部分  

**当前设计对应：** parties  

**是否需要补充：** **是（联系人、详情 API）**  

**建议方案：** Party 完整 CRUD；contacts 扩展；禁止再与合同混表  

---

### 2.5 企业管理（SaaS 租户/组织开通）

**业务名称：** SaaS 组织开通与邀请  

**旧系统对应：** organization、provisioning、invitation、VIP  

**当前设计对应：** tenants 表极简；TenantOps 上下文有名无实  

**是否需要补充：** **二期**（单租户部署可先种子数据）  

**建议方案：** 一期用 SQL 种子 tenants+admin；二期再做开通状态机  

---

### 2.6 招商

**业务名称：** 招商线索  

**旧系统对应：** investment 登记 + 雷达巨型模块 + CRM  

**当前设计对应：** leads + activities + convert；雷达明确二期  

**是否需要补充：** 一期补跟进 API；雷达 **不进 06**  

**建议方案：** 登记+转化主路径进 06 后半；雷达独立上下文与 worker  

---

### 2.7 合同

**业务名称：** 租赁合同  

**旧系统对应：** rental_tenant 合同字段 + 到期提醒  

**当前设计对应：** lease_contracts + units 占用 + 状态机  

**是否需要补充：** **是（terms/附件/续租用例）**  

**建议方案：** 激活/终止进 06；terms 最小表或扁平字段 ADR 二选一闭合  

---

### 2.8 账单

**业务名称：** 出账与账单管理  

**旧系统对应：** amount_bill、ele/water、导入、AI 识别  

**当前设计对应：** bills/bill_lines/fee_catalog；AI/import job 骨架  

**是否需要补充：** 一期人工出账必须；导入流水线二期；AI 可并行但独立  

**建议方案：** 06 先 MANUAL 出账+issue+void+duplicate-check；AI commit 走 Draft  

---

### 2.9 支付

**业务名称：** 收款/支付  

**旧系统对应：** receipt 登记为主；微信/支付宝偏会员  

**当前设计对应：** payments + allocations（运营登记收款）  

**是否需要补充：** **用语与产品边界必须澄清**；在线支付网关二期  

**建议方案：** 06 做登记收款+部分核销+冲正规则；不承诺租户在线缴租  

---

### 2.10 财务

**业务名称：** 财务台账  

**旧系统对应：** finance 流水、利润表、收款核验  

**当前设计对应：** ledger_entries 极简  

**是否需要补充：** 一期可「收款自动写流水」；核验/利润表二期  

**建议方案：** PaymentConfirmed → LedgerEntry；不做会计科目  

---

### 2.11 消息

**业务名称：** 通知/短信/站内信/Outbox  

**旧系统对应：** 短信、in_app_notification、Rabbit/Kafka、outbox  

**当前设计对应：** outbox_events 表；催缴短信 API 有；站内信无表  

**是否需要补充：** **是（短信端口+验证码 Redis）**；站内信二期  

**建议方案：** 抽象 SmsSender；验证码进 Redis；outbox 先同库事务  

---

### 2.12 数据分析

**业务名称：** 经营分析与工作台  

**旧系统对应：** dashboard/analytics 多接口  

**当前设计对应：** Analytics 上下文名 + stub；无指标表  

**是否需要补充：** 一期最小 workbench 聚合查询即可  

**建议方案：** 06 末尾提供 3～5 个只读统计；禁止复杂实时 join 膨胀  

---

### 2.13 其它旧系统有、新设计明确后置

| 业务名称 | 旧系统 | 当前设计 | 是否补充 | 建议 |
| --- | --- | --- | --- | --- |
| 门禁访客车辆 | access | 上下文名 | 二期 | 独立 Access |
| 运维工单巡检 | maintenance | FacilityOps | 二期 | WorkOrder 统一 |
| HRM 考勤薪酬 | hrm+salary | HRM | 二期 | 严禁回挂 Lease |
| 智能表计 | hezhong/ymsino | Metering | 二期 | 读数事件入账 |
| 报销 | reimbursement | 无 | 二期 | 审批流 |
| 企微 CRM | crm | CRMChannel | 二期 | — |
| 招商雷达 | investment/radar | AcquisitionRadar | 二期 | 独立 worker |
| Agent 工作台 | agent | AIAssist 部分 | 二期 | 主链稳定后 |
| 组织开通 MQ 丛林 | messaging 海量类 | 简化 outbox | 不复制 | 状态机+outbox |

---

## 3. 必须修改的问题（P0）

完成前 **不得** 宣称 Architecture Fully Approved，**不得** 无约束进入大规模 CRUD。

| ID | 问题 | 归属 | 修改动作 |
| --- | --- | --- | --- |
| P0-1 | Bill `OVERDUE` 与 `PARTIALLY_PAID` 语义互斥 | 领域+DDL+API | 主状态去掉 OVERDUE，增加 `is_overdue` 或计算字段 |
| P0-2 | 领域 LeaseTerm/Attachment 与 DDL 不一致 | 领域+DDL | 补最小表 **或** 从领域文档删除承诺并 ADR |
| P0-3 | OpenAPI 与实现 envelope/命名不一致 | API | 统一 snake_case + `{code,message,data}` + ErrorResponse |
| P0-4 | Party API 不完整 | API | 补 GET/PATCH（DELETE 或停用） |
| P0-5 | 多租户/园区过滤无强制架构规范 | 技术 | ADR：Repository 基类强制 tenant_id；DataScope 中间件 |
| P0-6 | 分层未冻结 | 技术 | 冻结模块内 domain/application/infrastructure/interface 模板 |
| P0-7 | 高敏催缴二次验证仅有故事无设计闭环 | 业务+API | 补 page-access 凭证 API 与校验点 |
| P0-8 | 「支付」产品语义易误解 | 产品 | 文档统一称「收款登记 Payment」，在线支付单列二期 |
| P0-9 | `dedicated_dsn` 安全 | DDL | 移出明文连接串，改密钥引用 |
| P0-10 | Unit.used_area 与占用双写 | 领域 | 规定 used_area 为投影，源数据为 lease_contract_units |

---

## 4. 推荐修改方案（设计修订包 v1.1，仍不写业务代码）

建议单独提交设计修订（预计文档工作 0.5–1 天）：

1. `docs/02-domain-design/04-adr-pack.md` — ADR-001～006 + T01～T06  
2. 更新 `02-aggregates` 账单状态与 Unit 投影规则  
3. 更新 `01-core-ddl-v1.sql` 或 `01-core-ddl-v1.1-patch.sql`  
4. 更新 `openapi-v1-core.yaml` 契约一致性  
5. 更新 `apps/api/README.md` 分层与模块模板说明（无业务逻辑）  

修订包验收清单：

- [ ] 域/库/API 三处账单状态一致  
- [ ] 无「文档有表无」的悬挂概念  
- [ ] 租户隔离与 scope 有可测试的架构描述  
- [ ] 一期范围边界一页纸（In Scope / Out of Scope）  

---

## 5. 可以继续开发的部分（修订 P0 后）

### 5.1 阶段 06 允许范围（In Scope）

| 顺序 | 模块 | 交付 |
| --- | --- | --- |
| 1 | 基础设施 | Alembic、ORM 基类、tenant/scope、审计钩子 |
| 2 | Identity | 用户种子、登录、me、权限码 |
| 3 | ParkProperty | Park/Building/Unit CRUD + 状态 |
| 4 | Lease | Party + Lease + 占用 + activate/terminate |
| 5 | Billing | FeeCatalog、Bill/Lines、issue/void、duplicate-check |
| 6 | Collection | Payment + Allocation、账单 paid 回写 |
| 7 | Finance | 收款自动 ledger（薄） |
| 8 | Collection SMS | mock SmsSender + preview（真实通道可开关） |
| 9 | 测试 | 租户隔离、核销不变量、占用冲突 |

### 5.2 明确不在 06（Out of Scope）

- 招商雷达 / 企微 CRM  
- 账单 Excel 复杂导入治理全套  
- 门禁 / 运维 / HRM / 报销  
- 在线微信缴租  
- 微服务拆分  
- 完整会计总账  

---

## 6. 下一阶段开发计划

### 阶段 05.1 — 设计修订（必须先做）

- 关闭全部 P0  
- 输出 In/Out Scope 一页纸  
- 架构师复检勾选  

### 阶段 06 — 持久化与主链 CRUD

1. Alembic 初始化（从修订后 DDL 生成）  
2. 通用：BaseModel（tenant_id, timestamps）、UnitOfWork  
3. 按 5.1 顺序实现  
4. 契约测试对齐 OpenAPI  
5. 本地 docker-compose：MySQL + Redis  

### 阶段 07 — 催缴与工作台增强  

### 阶段 08 — AI 制单（Draft 管道）  

### 阶段 09 — 迁移旧数据 PoC（单园区）  

### 阶段 10 — 支撑域按优先级  

---

## 7. 分项评审索引

| 文档 | 焦点 | 分项分 |
| --- | --- | --- |
| [domain-review.md](./domain-review.md) | 聚合与主链 | 7.2/10 |
| [database-review.md](./database-review.md) | DDL | 70/100 |
| [api-review.md](./api-review.md) | OpenAPI | 73/100 |
| [technical-review.md](./technical-review.md) | 分层与基础设施 | 68/100 |

---

## 8. 最终签字意见（架构委员会视角）

**同意：**

- 以 DDD 重切园区主链，而非 Java 直译  
- Party / Lease / BillLine / PaymentAllocation 纠偏  
- 模块化单体分期，雷达/AI worker 后置  
- 一期共享库 tenant_id  

**不同意（当前版本）：**

- 在三线不一致情况下直接全面 CRUD  
- 将「收款登记」默认为「在线支付完成」  
- 复制旧系统 messaging 开关丛林  
- 无租户过滤基类的裸仓库实现  

---

## 9. 裁定输出

```text
【ARCHITECTURE CONDITIONALLY APPROVED】  （评审时）

总分：70 / 100
状态：条件通过 → 阶段 05.1 P0 设计修订已闭合
下一动作：进入阶段 06（SQLAlchemy + Alembic + 核心 CRUD）
范围：docs/02-domain-design/05-phase06-scope.md
验收清单：docs/05-architecture-review/p0-revision-checklist.md

【P0 DESIGN REVISION COMPLETE】

完整无条件【ARCHITECTURE APPROVED】仍不扩大为「全业务冻结」；
仅批准主链范围内的实现开工。
```

---

## 10. 给业务方的一句话

> 新架构把「能赚钱的主链」设计对了，也比旧系统更干净；  
> 但设计图纸自己还有接缝没焊死——**先焊缝，再开工**，否则 AI 智慧园区会先变成「聪明的技术债园区」。
