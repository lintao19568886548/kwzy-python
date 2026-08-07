# 聚合设计与状态机

> 配套：`01-domain-overview.md`  
> 聚焦核心域：ParkProperty / Lease / Billing / Collection

---

## 1. ParkProperty（园区与空间）

### 1.1 聚合

#### Park（园区）聚合根

| 属性 | 说明 |
| --- | --- |
| id | 主键 |
| tenant_id | SaaS 租户 |
| name / address / area | 基础信息 |
| contact / manager | 运营联系 |
| status | ACTIVE / INACTIVE |
| version | 乐观锁 |

**不变量：**

- 同一 tenant 下园区名唯一（可配置）
- INACTIVE 后不可新建合同占用其单元

#### Building（楼栋）实体

- 归属 park_id
- type: FACTORY / DORMITORY / MIXED / OTHER
- name, address, built_at, description

#### Unit（可租单元）实体 — 关键纠偏点

统一旧 `factory_floor` 与宿舍房间：

| 属性 | 说明 |
| --- | --- |
| building_id / park_id | 归属 |
| name / code | 如 3F-A |
| rentable_area / used_area | 面积；**used_area 为投影字段** |
| base_rent_price | 挂牌租金参考 |
| status | 见状态机 |
| attributes JSON | 层高、承重、消防等级、电梯等扩展 |

**投影规则（P0 冻结，ADR-010）：**

- `used_area` **不是**手工主数据，源数据为有效合同占用 `lease_contract_units.occupied_area` 之和  
- 有效合同状态：`ACTIVE`、`EXPIRING`（及产品定义的在租集合）  
- 合同 activate / terminate / 调整占用后，由 `OccupancyService` 回写投影  
- 允许运维「校正工单」触发重算，禁止业务 API 直接 PATCH used_area 绕过合同  

**聚合根边界（P0 冻结，ADR-001）：**  
Park、Building、Unit **均为独立聚合根**（通过 ID 引用）；跨聚合占用变更只允许应用层编排。

### 1.2 Unit 状态机

```text
                  ┌──────────┐
                  │  DRAFT   │  录入中
                  └────┬─────┘
                       │ publish
                       ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│MAINTENANCE│◀──▶│ VACANT   │───▶│ RESERVED │
└──────────┘    └────┬─────┘    └────┬─────┘
                     │ activate lease      │
                     ▼                     │
                ┌──────────┐               │
                │ OCCUPIED │◀──────────────┘
                └────┬─────┘
                     │ terminate / release
                     ▼
                ┌──────────┐
                │ VACANT   │
                └──────────┘
                     │
                     ▼
                ┌──────────┐
                │RETIRED   │ 永久停用
                └──────────┘
```

**规则：**

- OCCUPIED 必须存在有效 Lease occupancy
- used_area 由占用服务计算/回写，禁止纯手工与合同脱节（允许校正工单）

---

## 2. Lease（租赁）

### 2.1 聚合

#### TenantParty（入驻方）聚合根

| 属性 | 说明 |
| --- | --- |
| name | 企业/个人名称 |
| contact_phone | 主联系电话（催缴默认） |
| contact_name | 联系人 |
| id_number / credit_code | 证件（可选）
| park_id | 主归属园（一期单园；跨园见 ADR-003） |
| status | ACTIVE / BLACKLIST / ARCHIVED |

**联系人：** 主电话保留在 Party；扩展联系人见 `party_contacts`（DDL v1.1）。

#### LeaseContract（合同）聚合根

| 属性 | 说明 |
| --- | --- |
| contract_no | 业务编号（租户内唯一） |
| party_id | 入驻方 |
| park_id | 园区 |
| start_date / end_date | 租期 |
| status | 见状态机 |
| deposit_amount | 押金金额（台账二期；一期仅字段） |
| remark | 备注 |

子实体：

- **LeaseContractUnit**：合同占用哪些 unit + 面积 + 单元租金  
- **LeaseTerm**（v1.1 落表）：条款行，`term_type` = INCREASE / RENT_FREE / OTHER，替代扁平 increase_* 为主数据  
  - 为兼容迁移，合同头可保留 `increase_date` / `increase_rate` 作为「主递增条款缓存」，以 terms 为准  
- **附件**：不建业务子表强绑定；统一走 `attachments` 通用表（`resource_type=LEASE_CONTRACT`）

### 2.2 合同状态机

```text
DRAFT ──submit──▶ PENDING_ACTIVE ──activate──▶ ACTIVE
  │                    │                        │
  │ cancel             │ reject                 ├─▶ EXPIRING（到期前 N 天系统标记）
  ▼                    ▼                        │
CANCELLED           DRAFT                       ├─▶ RENEWED（新合同承接，旧合同归档）
                                                ├─▶ TERMINATED（正常退租）
                                                └─▶ BREACHED（违约终止）
```

**规则：**

- activate 时：校验单元可租、写 occupancy、发 `LeaseActivated`
- terminate：释放单元、发 `LeaseTerminated`、触发退租结算用例（押金）
- 续租：新建合同 + 旧合同 RENEWED，保留历史不可覆盖改 end_date 糊弄（允许修正但记审计）

### 2.3 领域服务

- `OccupancyService`：计算单元占用、冲突检测
- `ContractNoGenerator`：合同号生成
- `LeaseReminderService`：到期提醒（读模型/任务）

---

## 3. Billing（计费账单）

### 3.1 聚合

#### FeeCatalog（费项字典）— 可独立或共享内核

- code: RENT / WATER / ELECTRIC / MANAGEMENT / SERVICE / TAX / OTHER
- name, unit, taxable, sort

#### Bill（账单）聚合根

| 属性 | 说明 |
| --- | --- |
| bill_no | 业务编号 |
| park_id / party_id / contract_id | 关联 |
| period_start / period_end | 账期（关键，纠偏旧 create_time 约定） |
| title / project_name | 展示名 |
| currency | CNY |
| status | **收付主状态**（见下，**不含 OVERDUE**） |
| total_amount | 行合计缓存 |
| paid_amount | 已核销金额缓存 |
| due_date | 应付日 |
| overdue_since | 首次进入逾期的日期；结清后清空（可空） |
| source | MANUAL / IMPORT / AI / METER |
| source_ref | 外部任务 id |

**衍生属性（可不落库或冗余缓存）：**

| 属性 | 计算规则 |
| --- | --- |
| `open_amount` | `total_amount - paid_amount` |
| `is_overdue` | `status ∈ {ISSUED, PARTIALLY_PAID}` 且 `due_date < today` 且 `open_amount > 0` |

子实体 **BillLine**：

| 属性 | 说明 |
| --- | --- |
| fee_code | 费项 |
| description | 如「3F 电表-A」 |
| quantity / unit_price / amount | 计量 |
| meter_reading_from/to | 可选 |
| multiplier | 倍率 |
| meta JSON | 扩展 |

#### BillDraft（草稿）— 导入/AI 用

- 未入账前独立存储或 status=DRAFT 的 Bill
- 确认后 ISSUED

### 3.2 账单状态机（P0 修订 · ADR-002）

**主状态（互斥，写入 `bills.status`）：**

```text
DRAFT ──issue──▶ ISSUED ──▶ PARTIALLY_PAID ──▶ PAID
  │                │
  │                └── void ──▶ VOID
  │                     （约束：paid_amount=0；已收款须先冲正 Payment）
  └── discard ──▶ DISCARDED
```

| 主状态 | 含义 |
| --- | --- |
| DRAFT | 草稿，可改行项目 |
| ISSUED | 已签发，未收到任何有效核销 |
| PARTIALLY_PAID | 已有部分核销，仍有 open_amount |
| PAID | 已结清（open_amount=0） |
| VOID | 作废（未收款） |
| DISCARDED | 草稿废弃 |

**禁止：** 使用 `OVERDUE` 作为 `status` 枚举值（会与 PARTIALLY_PAID 互斥冲突）。

**逾期（正交维度）：**

```text
is_overdue = f(status, due_date, open_amount, today)
```

- 逾期任务 / 催缴建案：扫描 `is_overdue=true` 的账单，**不修改 status 为 OVERDUE**  
- 可选回写 `overdue_since`：首次判定逾期时写入，结清或作废时清空  
- 列表筛「逾期未结」：`is_overdue=true` 或等价 SQL 条件  

**规则：**

- issue 后锁定费项结构（更正走红冲/调整单二期，一期可限角色改）
- paid_amount 仅能由 Collection 核销回写；回写后重算 status：  
  - open=total → ISSUED  
  - 0<open<total → PARTIALLY_PAID  
  - open=0 → PAID  
- total_amount = sum(lines.amount)
- 同一 party + period 防重（应用层 duplicate-check）

### 3.3 出账用例

1. **人工出账**：选合同 → 继承上期表计模板 → 录行 → 保存草稿 → 签发  
2. **导入出账**：ImportJob → 多 Draft → 校验 → 批量 issue  
3. **AI 出账**：RecognizeJob → Draft → 人工确认 issue  
4. **表计出账**：订阅读数事件 → 生成水电行草稿  

---

## 4. Collection（收款与催缴）

### 4.1 聚合

#### Payment（收款登记）聚合根

> **产品语义冻结（ADR-008 / P0-8）：**  
> Payment = **运营侧收款登记与核销凭证**，不是租户在线收银台订单。  
> 微信/支付宝等作为 `method` 枚举可记「线下已收渠道」；  
> **在线支付网关、支付回调、租户自助缴租 = 二期**，不在 v1 主链范围。

| 属性 | 说明 |
| --- | --- |
| payment_no | 编号 |
| park_id / party_id | 关联 |
| amount | 实收金额 |
| method | CASH / TRANSFER / WECHAT / ALIPAY / OTHER |
| paid_at | 收款时间 |
| status | CONFIRMED / REVERSED |
| operator_id | 操作人（登记人） |
| remark | 备注 |

子实体 **PaymentAllocation（分摊核销）**：

| 字段 | 规则 |
| --- | --- |
| bill_id | 目标账单 |
| amount | 本次核销金额 |
| 约束1 | sum(allocations) ≤ payment.amount |
| 约束2 | 对单账单：累计核销 ≤ bill.total_amount |
| 效果 | 回写 bill.paid_amount，并重算 bill.status（ISSUED/PARTIALLY_PAID/PAID） |

**部分收款：** 一笔 Payment 可只核销账单的一部分；同一账单可对应多笔 PaymentAllocation（多笔收款登记）。

#### CollectionCase（催缴案件）聚合根

| 属性 | 说明 |
| --- | --- |
| bill_id / party_id / park_id | 关联 |
| status | OPEN / IN_PROGRESS / PROMISED / CLOSED / WRITTEN_OFF |
| level | L1 短信 / L2 电话 / L3 上门 |
| assignee_id | 跟进人 |
| next_action_at | 下次行动时间 |
| open_amount_snapshot | 建案时欠款快照（可选） |

#### CollectionRecord（催缴记录）— 子实体，表名 `collection_records`

> 原称 CollectionAction；**冻结名为 CollectionRecord / collection_records**。

| 属性 | 说明 |
| --- | --- |
| case_id | 所属案件 |
| record_type | SMS / CALL / VISIT / NOTE / SYSTEM |
| content | 内容/话术/纪要 |
| result | 结果摘要（接通/承诺/拒接等） |
| channel_ref | 短信供应商回执等（可空） |
| created_by / created_at | 操作者与时间 |

**闭环规则：**

1. 账单 `is_overdue=true` → 可自动或手工 **创建 CollectionCase**  
2. 跟进过程写入 **CollectionRecord**（电话/上门/短信/备注）  
3. **短信发送** 必须带 `page_access_proof`，成功后写一条 `record_type=SMS`  
4. 全额结清（bill.status=PAID）→ Case → CLOSED  
5. 承诺还款 → PROMISED；逾期未履约 → 回 IN_PROGRESS 并升 level  

#### RentVerifyTask（可选一期简化）

- 与 Payment 关联的复核任务：PENDING / CONFIRMED / ABNORMAL

### 4.2 收款流程状态（账单侧视角）

```text
ISSUED 或 PARTIALLY_PAID（均可 is_overdue=true|false）
    │ 收款登记 Payment + payment_allocations
    ▼
PARTIALLY_PAID ──全额核销──▶ PAID
    │
    └── 若仍 is_overdue ──▶ CollectionCase 继续跟进（不改 status 为 OVERDUE）
```

### 4.3 催缴案件状态机

```text
OPEN ──assign──▶ IN_PROGRESS ──promise──▶ PROMISED ──paid──▶ CLOSED
                     │                        │
                     ├─ escalate level        └── break promise ──▶ IN_PROGRESS
                     └─ write_off ──▶ WRITTEN_OFF
                     │
                     └── 每一步可追加 CollectionRecord
```

---

## 5. IdentityAccess（简）

### 5.1 聚合

- **User**：登录身份，隶属 tenant
- **Role**：权限码集合 + 默认菜单
- **Permission**：code 字符串
- **UserParkScope / RoleParkScope**：数据范围
- **Session/RefreshToken**：会话

### 5.2 登录状态

无复杂状态机；账号 `status`: ACTIVE / DISABLED。

---

## 6. Investment（简）

### Lead 状态机

```text
NEW → CONTACTING → VISITING → NEGOTIATING → WON → （convert 到 Lease DRAFT）
                              └──────────▶ LOST
```

WON 时发 `LeadConverted`，**不在本上下文写合同最终数据**，由 Lease 应用服务接收创建。

---

## 7. 不变量清单（实现必测）

1. 任何 BillLine.amount 变更后 Bill.total_amount 一致  
2. PaymentAllocation 之和不超过 Payment.amount  
3. 账单已核销合计不超过 total_amount  
4. Unit OCCUPIED 当且仅当存在 ACTIVE/EXPIRING 占用  
5. 跨园写操作必须在用户 data scope 内  
6. AI/Import 不可跳过 issue 权限直接 PAID  
7. 催缴短信发送必须通过二次验证凭证  
8. `bills.status` 永不为 `OVERDUE`；逾期只通过 `is_overdue` 表达  
9. `units.used_area` 等于有效占用之和（投影一致）  
10. 所有业务查询默认带 `tenant_id` 条件  

---

## 8. 一期可裁剪

| 项 | 一期 | 二期 |
| --- | --- | --- |
| 合同多单元 | 支持 1 单元 | 多单元组合 |
| 红冲调整单 | 管理员改草稿/作废 | 完整调整单 |
| 催缴案件 | 有 Case + 短信 Action | 全渠道策略引擎 |
| 押金管理 | 字段级 | 押金台账与退还流 |
| 独立 Verify | 可选合并进 Payment.confirm | 独立审批流 |
