# 核心库表说明（DDL v1 + v1.1）

> 基线：`01-core-ddl-v1.sql`（已含 05.1 对 bills/tenants/units 的就地修订）  
> 补丁：`01-core-ddl-v1.1-patch.sql`（新表与增量）  
> 状态：阶段 05.1 设计修订后

---

## 1. 设计原则

1. **所有业务表带 `tenant_id`**（权限字典 permissions 可全局）  
2. **金额 `DECIMAL(14,2)`**，单价可用更高精度  
3. **状态用字符串枚举**，应用层约束 + 文档状态机  
4. **逻辑删除**仅空间资产使用 `is_deleted`；财务单据倾向状态作废  
5. **时间 `DATETIME(3)`**，业务日用 `DATE`（业务时区 Asia/Shanghai，存储建议 UTC 由 ADR-T04）  
6. 一期 **有选择地加 FK**  
7. **账单 status 禁止 OVERDUE**；逾期用 `is_overdue` 计算 + 可选 `overdue_since`  
8. **独立库连接禁止明文 DSN**，只用 `dedicated_secret_ref`  

---

## 2. 账单状态与逾期（P0-1）

| 字段 | 取值 |
| --- | --- |
| `status` | DRAFT \| ISSUED \| PARTIALLY_PAID \| PAID \| VOID \| DISCARDED |
| `overdue_since` | 首次逾期日，可空 |
| `is_overdue` | **不强制落库**；`status∈{ISSUED,PARTIALLY_PAID} AND due_date<today AND total>paid` |

查询「逾期未结」：

```sql
WHERE tenant_id = ?
  AND status IN ('ISSUED', 'PARTIALLY_PAID')
  AND due_date IS NOT NULL
  AND due_date < CURDATE()
  AND total_amount > paid_amount
```

---

## 3. 相对旧库的纠偏对照

| 旧表 | 新表 | 变化 |
| --- | --- | --- |
| `customer` + 独立库 | `tenants` + tenant_id | 默认共享库；密钥引用 |
| `park` | `parks` | 基本一致 |
| `factory` | `buildings` | 统一楼栋类型 |
| `factory_floor` / dormitory | `units` | 统一可租单元；used_area 投影 |
| `rental_tenant` | `parties` + `lease_contracts` + `lease_contract_units` + `lease_terms` | 主体/合同/占用/条款 |
| `amount_bill` | `bills` | 账期一等公民；无 OVERDUE 状态 |
| 宽表费项 + ele/water | `bill_lines` + `fee_catalog` | 行模型 |
| `receipt_time` | `payments` + `payment_allocations` | **收款登记**与核销 |
| 催缴短信一次性 | `collection_cases` + `collection_records` + `page_access_proofs` | 案件+跟进记录闭环 |
| `finance` | `ledger_entries` | 带来源引用 |
| `investment` | `leads` + `lead_activities` | 清晰漏斗状态 |
| 无 | `outbox_events` / `audit_logs` / `attachments` | 事件、审计、附件 |

`audit_logs` 包含 `request_id` 与 `client_ip`，Park/Unit 关键写操作与业务事务同提交；
审计 detail 仅保存非敏感摘要。

### 3.1 运行真相：Alembic（Step1）

| 项 | 说明 |
| --- | --- |
| 权威来源 | `apps/api/alembic/versions/*` + ORM models；**不以设计 DDL 静默改库** |
| Step1 head | `9f17fd2e9180`（`all_parks` 列；前序 `8c2f4aa10b7d` 含 RBAC/audit） |
| `roles.all_parks` / `users.all_parks` | Boolean，默认 false；ADMIN 种子/迁移回填 true |
| `permissions` | 全局权限码字典；`*` 仅动作超级权限 |
| 园区范围表 | `user_park_scopes` / `role_park_scopes`（租户过滤并集） |

设计 SQL（`01-core-ddl-v1*.sql`）与 live migration 有差距时，**以 Alembic 为准**并回写文档。

**明确不上 v1 主链的表：**  
雷达爬虫全套、企微 CRM、HRM、门禁、完整报销、在线支付订单表。

---

## 4. v1.1 新增表职责

| 表 | 职责 |
| --- | --- |
| `lease_terms` | 递增/免租等条款行（**已入基线 DDL**） |
| `attachments` | 通用附件元数据 + storage_key（**已入基线 DDL**） |
| `collection_records` | 催缴跟进记录（原 collection_actions 已更名） |
| `party_contacts` | 多联系人 |
| `ai_job_items` | AI 识别明细 Draft |
| `number_sequences` | 业务编号 |
| `idempotency_keys` | 写幂等 |
| `page_access_proofs` | 高敏二次验证 |
| `inbox_consume_log` | 事件消费幂等 |
| `menus` / `role_menus` | 可选动态菜单 |

---

## 5. 关键索引意图

| 索引 | 支撑查询 |
| --- | --- |
| `bills(tenant, party, period_*)` | 防重、历史账单 |
| `bills(tenant, park, status)` | 未收列表 |
| `bills(tenant, status, due_date)` | 逾期扫描 |
| `lease_contracts(tenant, end_date)` | 到期提醒 |
| `units(tenant, park, status)` | 空置库存 |
| `outbox(status, id)` | 派发扫描 |

---

## 6. 编号生成

| 实体 | 格式示例 |
| --- | --- |
| contract_no | `LC{yyyy}{seq}` |
| bill_no | `BILL{yyyyMM}{seq}` |
| payment_no | `PAY{yyyyMM}{seq}` |
| entry_no | `LE{yyyyMM}{seq}` |

使用 `number_sequences` 表保证并发。

---

## 7. 初始化步骤

```bash
mysql -uroot -p -e "CREATE DATABASE IF NOT EXISTS kwzy DEFAULT CHARSET utf8mb4;"
mysql -uroot -p kwzy < docs/03-database/01-core-ddl-v1.sql
mysql -uroot -p kwzy < docs/03-database/01-core-ddl-v1.1-patch.sql
```

注意：patch 中部分 `ADD COLUMN` 在已合并基线的库上可能重复，按环境跳过错误即可。  
阶段 06 起以 **Alembic** 为唯一演进手段，本 SQL 为基线快照。

---

## 8. used_area 投影

- 源：`lease_contract_units` JOIN 有效状态合同  
- 写：仅 `OccupancyService`  
- API：禁止客户端直接改 used_area 作为业务真源  
