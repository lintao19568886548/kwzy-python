# 数据库设计架构评审（Database Review）

> 评审对象：`docs/03-database/01-core-ddl-v1.sql` + `02-schema-notes.md`  
> 对照：领域设计、旧系统多库模型

---

## 1. 总体评价

DDL v1 覆盖 **主链交易表**，相对旧 `magic.sql` 的宽表/混装模型是结构性进步。  
但作为「架构冻结」基线，仍存在：**领域承诺未落表、权限导航缺失、历史/通知不足、财务偏流水账**。

**数据库综合评分：70 / 100**

---

## 2. 关键能力检查

### 2.1 是否支持多租户

| 项 | 结论 |
| --- | --- |
| `tenants` 表 | 有 |
| 业务表 `tenant_id` | 基本齐全 |
| 默认 SHARED 策略 | 有 `db_strategy` / `dedicated_dsn` |
| 行级强制隔离 | **仅靠应用层**，无 DB RLS / 强制视图 |
| 独立库路由 | 字段预留，**无连接路由规范表/配置设计** |

**结论：支持「逻辑多租户」；生产级隔离依赖应用过滤器，必须在技术架构强制 Middleware。**  
**风险：漏写 tenant_id 条件即串租。**

**必须补充（设计层）：**

- 全局约定：所有查询默认带 `tenant_id = :current`  
- 禁止裸 SQL 无租户条件（代码评审门禁）  
- `dedicated_dsn` 不建议明文进表，改密钥引用 ID  

### 2.2 是否支持多园区

| 项 | 结论 |
| --- | --- |
| `parks` | 有 |
| 业务表 `park_id` | 主链表基本有 |
| 用户跨园 | `user_park_scopes` + `role_park_scopes` |

**结论：支持。**  
**缺口：** `role_park_scopes.park_id` / `user_park_scopes.park_id` **无 FK 到 parks**（可接受性能考量，但要文档说明）。

### 2.3 是否支持权限隔离

| 能力 | DDL | 评价 |
| --- | --- | --- |
| RBAC | users/roles/permissions/* | 基础具备 |
| 园区数据范围 | user/role_park_scopes | 具备 |
| 动态菜单 | **无 menu 表** | **相对旧系统倒退** |
| 部门组织 | **无 dept** | 旧有，一期可砍但需声明 |
| 权限码字典 | permissions 全局 | OK |
| 刷新令牌 | refresh_tokens | OK |

**结论：功能权限 + 园区范围「能做」；管理端菜单与旧系统对齐能力缺失。**

**必须决定：**

- A）一期静态前端路由 + 权限码控制按钮（可接受）  
- B）补 `menus` / `role_menus`（更贴近旧系统与运营可配）  

架构建议：**至少预留 menus 表结构进 v1.1**，否则运营改菜单只能发版。

### 2.4 是否支持财务扩展

| 能力 | 现状 | 评价 |
| --- | --- | --- |
| 流水 | `ledger_entries` | 最简运营流水 |
| 核销 | payment_allocations | 好 |
| 科目体系 | 无 | 非会计系统，OK |
| 应收账龄快照 | 无 | 分析弱 |
| 退款/冲正 | payment REVERSED | 字段级，无冲正分录规范 |
| 押金专户 | 无 | 弱 |
| 与 bill 强关联 | ref_type/ref_id | 弱关联可扩展 |

**结论：支持「运营财务扩展起步」；不支持完整财务中台。一期 OK，须产品边界写死。**

### 2.5 是否支持 AI 分析

| 能力 | 现状 | 评价 |
| --- | --- | --- |
| AI 任务 | `ai_jobs` | 有骨架 |
| 导入任务 | `bill_import_jobs` | 过简（旧系统十数张表） |
| 识别结果明细 | **无 ai_job_items** | **不利于人工复核 UI** |
| 特征/指标仓 | 无 | 分析靠实时查交易表 |
| 审计 prompt/模型版本 | result_meta JSON | 可塞，缺规范 |
| RAG 知识库 | 无 | 二期 |

**结论：支持 AI 任务落库的最小闭环；不支持完整 AI 数据飞轮。**  
**建议 v1.1：** `ai_job_items`（draft_json, confidence, commit_bill_id, status）。

---

## 3. 字段设计检查

### 3.1 优点

- 金额 `DECIMAL(14,2)`，单价更高精度  
- 状态字符串 + 注释枚举  
- 账期 `period_start/end` 明确  
- JSON 扩展位（attributes/meta）避免过早宽表  
- 软删仅限空间资产  

### 3.2 问题

| # | 问题 | 级别 |
| --- | --- | --- |
| S1 | `users.password_hash` NOT NULL — 短信-only 用户难落地 | 中 |
| S2 | `parties.contact_phone` NOT NULL 单字段 — 多联系人弱 | 中 |
| S3 | `bills.status` 含 OVERDUE — 与部分收款语义冲突 | **高** |
| S4 | `lease_contracts` 无 `version` / 无变更历史 | 中 |
| S5 | `dedicated_dsn` 明文风险 | **高（安全）** |
| S6 | `fee_catalog` UNIQUE(tenant_id, code) 在 MySQL 中 NULL tenant 多行行为需验证 | 中 |
| S7 | 多表缺 `created_by`/`updated_by` | 中 |
| S8 | 无 `deleted_at` 统一策略（仅 is_deleted） | 低 |
| S9 | 编号无 sequence 表 | 中（并发号段） |

---

## 4. 表关系检查

### 4.1 关系正确性

```text
tenants 1—* parks 1—* buildings 1—* units
parks 1—* parties 1—* lease_contracts *—* units (lease_contract_units)
parties 1—* bills 1—* bill_lines
parties 1—* payments 1—* payment_allocations *—1 bills
bills 1—* collection_cases 1—* collection_actions
```

主链 FK 基本合理。

### 4.2 关系缺陷

| # | 问题 | 建议 |
| --- | --- | --- |
| R1 | 领域 LeaseTerm/Attachment 无表 | 补表或明确「附件只存 OSS + audit」 |
| R2 | scope 表无 FK parks | 文档化 or 加 FK |
| R3 | `ledger_entries` 无 FK 到 payment | 靠 ref 可接受 |
| R4 | `leads.converted_*` 无 FK | 建议加 |
| R5 | `bills.contract_id` 无 FK | 建议加（可空） |
| R6 | 无 outbox 消费日志表 | 建议 `inbox_consume_log` 防重 |

---

## 5. 索引设计检查

### 5.1 已有合理索引

- bills(tenant, party, period)  
- bills(tenant, park, status)  
- lease end_date  
- units park+status  
- outbox status  

### 5.2 建议补齐

| 索引 | 原因 |
| --- | --- |
| `payments(tenant_id, paid_at)` | 收款日报 |
| `payment_allocations(bill_id)` | 已有；确认覆盖 |  
| `collection_cases(tenant_id, park_id, status)` | 催缴工作台 |
| `leads(tenant_id, contact_phone)` | 去重 |
| `audit_logs(tenant_id, user_id, created_at)` | 追责 |
| `users(tenant_id, status)` | 用户管理 |

**唯一约束建议：**

- 可选：`bills(tenant_id, party_id, period_start, period_end, status!=VOID)` 防重 — MySQL 部分唯一索引有限，可用应用层 + 条件唯一表  

---

## 6. 状态字段检查

| 表 | 评价 |
| --- | --- |
| parks/units/leases/bills/payments/cases/leads | 有 status，方向对 |
| bills OVERDUE | **需修订（见领域评审）** |
| 缺 status 变更时间 | 建议 `status_changed_at` 或历史表 |
| 缺枚举表 | 可用 CHECK（MySQL 8.0.16+）或应用层 |

---

## 7. 历史记录设计检查

| 类型 | 现状 | 评价 |
| --- | --- | --- |
| 审计日志 | `audit_logs` | 有，字段尚可 |
| 合同版本史 | 无 | 退租/纠纷弱 |
| 账单调整史 | 无（VOID 替代） | 一期可 |
| 核销撤销史 | REVERSED | 需规定是否生成负向 allocation |
| Outbox | 有 | 好 |
| 操作者 | 部分 created_by | 不完整 |

**结论：审计有底，业务历史偏弱。一期强制 audit_logs 写入规范可过关。**

---

## 8. 与旧库迁移可行性

| 点 | 评价 |
| --- | --- |
| 主数据映射路径 | 清晰（schema-notes） |
| 合同-单元占用 | **旧数据常缺失 → 迁移灰数据** |
| 账期解析 | **高风险** |
| 一客户一库 → 共享库 | 需 ETL 合并 tenant_id |
| 收款从 receipt_time 生成 | 可脚本化全额核销 |

必须单独《数据迁移风险报告》，不阻塞架构冻结但阻塞上线。

---

## 9. 数据库必须修订清单

### P0（编码前必须改 DDL 或出豁免 ADR）

1. **Bill 状态模型修订**（去掉互斥 OVERDUE 或加 is_overdue）  
2. **领域-DDL 对齐**：lease_terms 最小集 **或** 文档删除 LeaseTerm 承诺  
3. **附件策略**：`attachments` 通用表 **或** OSS key 规范  
4. **dedicated_dsn 安全处理**  
5. **AI job items 最小表**（若一期做 AI 制单）  

### P1（强烈建议 v1.1）

6. menus / role_menus（若管理端可配菜单）  
7. number_sequences  
8. party_contacts  
9. inbox_consume_log  
10. bills.contract_id FK  

### P2（二期）

11. 押金台账、表计档案、通知表、指标快照表  

---

## 10. 数据库评审结论

| 维度 | 分数 |
| --- | --- |
| 多租户 | 7/10 |
| 多园区 | 9/10 |
| 权限隔离 | 6/10 |
| 主链范式 | 8/10 |
| 财务扩展 | 6/10 |
| AI 扩展 | 5/10 |
| 一致性/安全 | 6/10 |
| **综合** | **70/100** |

**结论：可作为主链开发基线候选；P0 项关闭前不建议「无保留意见冻结」。**
