# Design: implement-lease-contract

## 1. 目标与非目标

**目标：** 在当前租户下管理租赁合同、占用单元、条款行，并在 activate/terminate 时正确更新单元占用投影。

**非目标：** 账单签发、收款、押金退还流水、旧库同步。

## 2. 与 Party 演进的对齐

| 旧草案 | Party v1 已落地 | Lease 处理 |
| --- | --- | --- |
| Party 主档 `park_id` | 已删除；Party–Park 多对多 | **合同**带 `park_id`；创建时校验 Party 可见且园区在 scope |
| Party 模糊 `address` | 独立 `party_addresses` + PERSON 禁止 | Lease 不读 PERSON 地址 |
| Party 状态 ARCHIVED | 有 | ARCHIVED/BLACKLISTED 主体不可 activate 新合同（可建 DRAFT 时告警或拒绝 activate） |

## 3. 聚合与状态机（批准文档摘要）

**LeaseContract** 聚合根字段：contract_no、party_id、park_id、start_date、end_date、status、deposit_amount（仅字段）、remark。

子实体：LeaseContractUnit（unit_id、occupied_area、unit_rent_price）、LeaseTerm（term_type、effective_date、rate/amount…）。

状态机（`02-aggregates-and-state-machines.md`）：

```text
DRAFT ──submit──▶ PENDING_ACTIVE ──activate──▶ ACTIVE
  │                    │                        │
  │ cancel             │ reject→DRAFT           ├─▶ EXPIRING
  ▼                                             ├─▶ RENEWED
CANCELLED                                       ├─▶ TERMINATED
                                                └─▶ BREACHED
```

**activate：** 校验单元可租与占用不冲突；写占用；投影 used_area；审计。  
**terminate / breached：** 释放占用；投影 used_area；**不**实现押金退还流水。  
**renew：** v1 可采用「新合同 + 旧合同 RENEWED」；禁止改 end_date 伪装续租。

## 4. 占用与 used_area

依据 ADR-010 / 聚合文档：

- `units.used_area` 为投影 = 有效合同（ACTIVE、EXPIRING）下 `lease_contract_units.occupied_area` 之和
- 禁止业务 API 直接 PATCH used_area
- OccupancyService 在 activate / terminate / 调整占用后重算

**冲突：** 同一 unit 在有效合同上 occupied_area 之和不得超过 rentable_area（若 rentable_area 为空则仅状态校验）。

## 5. 权限（建议码，实现时 bootstrap）

| 权限 | 用途 |
| --- | --- |
| `lease:read` | 列表/详情 |
| `lease:write` | 创建/改 DRAFT、条款、占用行 |
| `lease:activate` | 提交/激活 |
| `lease:terminate` | 终止/违约终止 |

park scope：合同 `park_id` 必须在用户允许园区内；ALL 模式全园。

## 6. 持久化

- 新 Alembic revision（down_revision = Party head `c3a91b2e4f10`）
- 表：`lease_contracts`、`lease_contract_units`、`lease_terms`
- 跨方言类型；PG 部分索引如需要
- 不修改历史 migration

## 7. 风险与强制暂停边界

| 风险 | 处置 |
| --- | --- |
| 退租押金结算算法 | **本 change 不做**；字段仅存储 |
| 账期/租金递增如何出账 | **Bill change** |
| EXPIRING 的 N 天 | 实现配置项默认 **30** 天（若文档无 N，采用此默认并在 tasks 注明；产品可改配置） |
| 合同号规则 | 租户内唯一；生成策略：`LC{yyyyMMdd}{seq}` 或 UUID 短码，实现时选一并测唯一 |

若实现过程发现必须发明未批准的计费/舍入/滞纳金规则 → **HUMAN_DECISION_REQUIRED**。

## 8. 分支

- `feat/lease-contract` parent = `feat/party-master` @ 当前已推送 HEAD
