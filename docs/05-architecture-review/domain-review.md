# 领域模型架构评审（Domain Review）

> 评审角色：CTO / DDD 专家 / 智慧园区产品架构师  
> 评审对象：`docs/02-domain-design/*`  
> 对照：`docs/01-old-system-analysis/*`、`docs/03-database/*`  
> 结论摘要：**核心主链方向正确，存在若干必须在编码前闭合的设计裂缝**

---

## 1. 主链路评审

```text
Park → Building → Unit → Party → Lease → Billing/Bill → Payment/Collection
```

| 环节 | 设计结论 | 评级 |
| --- | --- | --- |
| Park | 作为数据权限与空间根边界，正确 | 通过 |
| Building | 统一厂房/宿舍楼类型，合理 | 通过 |
| Unit | 可租单元一等公民，纠正旧 floor/dorm 分裂 | 通过 |
| Party | 入驻主体独立，纠正 rental_tenant 混装 | 通过 |
| Lease | 合同独立 + 多单元占用，符合园区实操 | 通过 |
| Bill + BillLine | 费项行化 + 账期一等公民，显著优于旧宽表 | 通过 |
| Payment + Allocation | 支持分批/部分核销，纠正 receipt_time | 通过 |
| CollectionCase | 催缴过程化，优于旧「只发短信」 | 通过 |

**总评：主链在概念层已具备冻结价值，优于旧系统模型。**

---

## 2. 聚合边界是否合理

### 2.1 ParkProperty

| 聚合 | 边界判断 | 意见 |
| --- | --- | --- |
| Park | 聚合根清晰 | 通过 |
| Building | 文档写作「实体」，但可独立 CRUD | **建议明确为独立聚合根或 Park 内实体二选一** |
| Unit | 有独立状态机，业务上常独立维护 | **建议 Unit 作为独立聚合根，Park/Building 为引用 ID** |

**风险：** Building/Unit 若仅是 Park 内部实体，则跨聚合事务（合同占用改 Unit 状态）边界模糊；若都是聚合根，则需明确「只通过领域服务/应用服务改状态，禁止他模块直改」。

**冻结建议（必须写入修订案）：**

- **Park、Building、Unit 均为独立聚合根**（共享 `park_id` 引用）  
- 占用变更只允许 `OccupancyService`（应用层编排 Lease + Unit）  

### 2.2 Lease

| 聚合 | 边界判断 | 意见 |
| --- | --- | --- |
| Party | 独立主体正确 | 通过 |
| LeaseContract | 独立合同正确 | 通过 |
| LeaseContractUnit | 合同内实体正确 | 通过 |
| LeaseTerm / Attachment | 领域有、DDL 无 | **不通过（设计不一致）** |

**Party 归属园区：** 单 `park_id` 限制跨园客户（集团客户多园）。一期可接受，但必须 ADR 声明：二期改为 Party 无 park，关系表 `party_park`。

### 2.3 Billing / Collection

| 聚合 | 边界判断 | 意见 |
| --- | --- | --- |
| FeeCatalog | 字典式，可跨上下文 | 通过 |
| Bill + BillLine | 合理 | 通过 |
| Payment + Allocation | 合理 | 通过 |
| CollectionCase | 合理 | 通过 |
| Bill 与 Payment 拆上下文 | 正确（收付分离） | 通过 |

**状态机冲突风险：** `OVERDUE` 与 `PARTIALLY_PAID` 可能并存（逾期且部分收款）。当前状态机用单一 status 字段，**语义不闭合**。

**冻结建议：**

- 主状态：`DRAFT | ISSUED | PARTIALLY_PAID | PAID | VOID | DISCARDED`  
- 衍生标记：`is_overdue` 或 `overdue_since`（由 due_date + 未结清计算），不要用 OVERDUE 覆盖部分收款语义  

---

## 3. 实体关系是否合理

### 3.1 通过项

1. **合同与企业主体分离** — 通过（旧系统最大纠偏）  
2. **合同与单元多对多占用** — 通过（支持一企多单元）  
3. **账单挂 party + 可选 contract** — 通过（历史账单可无合同）  
4. **支付与账单多对多核销** — 通过（分批支付）  
5. **催缴案件挂 bill** — 通过  

### 3.2 问题项

| # | 问题 | 影响 | 级别 |
| --- | --- | --- | --- |
| D1 | 领域描述 LeaseTerm/Attachment，DDL 未落地 | 编码时漂移 | **必须改** |
| D2 | 押金仅 `deposit_amount` 字段，无押金台账/退还 | 退租结算不完整 | 一期可记技术债，须产品声明 |
| D3 | Party 仅单联系人电话 | 催缴/多联系人不足 | **建议补 contacts 表或 JSON 数组规范** |
| D4 | 合同递增条款扁平字段 vs LeaseTerm 版本 | 续租/变更协议弱 | 与 D1 一并补最小 `lease_terms` |
| D5 | 无合同/账单变更历史表 | 审计靠 audit_logs 不够业务化 | 二期可，但 audit 必须强制 |
| D6 | Lead 与 Party 无统一「客户主数据」层 | 招商-入驻仍可能双写名字 | 可接受：convert 时创建 Party |
| D7 | Unit.used_area 与占用表双写风险 | 数据不一致 | **必须规定：used_area 为投影，源在 lease_contract_units** |

---

## 4. 重点问题逐项确认

| 检查项 | 结论 | 说明 |
| --- | --- | --- |
| 合同是否独立 | **是** | `LeaseContract` 聚合根 |
| 企业主体是否独立 | **是** | `Party` / `TenantParty` |
| 账单是否支持多费用类型 | **是** | `fee_catalog` + `bill_lines.fee_code` |
| 支付是否支持分批支付 | **是** | 多 Payment + Allocation；`PARTIALLY_PAID` |
| 是否支持催缴流程 | **是（设计层）** | Case + Action + 短信二次验证；API/DDL 基本齐，通道未设计 |

**注意：** 当前「支付」语义是 **运营登记收款（Payment）**，不是租户在线收银台（PaymentGateway）。旧系统亦偏登记制。产品上必须用语区分，避免误以为已支持微信缴租闭环。

---

## 5. 是否符合智慧园区实际业务

### 5.1 符合

- 园区多空间库存管理  
- 入驻合同与租金水电出账  
- 催缴与部分回款  
- 招商线索转化  
- 多园区权限隔离思想  

### 5.2 行业常见但未建模（可分期）

| 业务 | 现状 | 建议 |
| --- | --- | --- |
| 押金/保证金流水 | 字段级 | 二期 DepositLedger |
| 物业报修工单 | 仅上下文名 | 二期 FacilityOps |
| 门禁访客 | 无 | 二期 |
| 智能表自动出账 | 事件有、表无 | 二期 Metering |
| 电子签/合同模板 | 无 | 三期 |
| 能耗碳排 | 无 | 远期 |
| 租户端门户 | API 未区分 audience | 见 API 评审 |

---

## 6. 未来扩展问题

| 扩展点 | 当前是否挡住 | 建议 |
| --- | --- | --- |
| 一合同多园区 | 挡住（单 park_id） | 明确不做或改模型 |
| 一客户多合同并行 | 支持 | — |
| 费项任意扩展 | 支持 | — |
| 在线支付入账 | 可扩 method + gateway_ref | 预留字段 |
| 多币种 | currency 字段有 | 汇率表二期 |
| 独立库大客户 | strategy 字段有 | 连接路由须补设计 |
| AI 制单 | 有 job 概念 | Draft 校验规则需规范 |

---

## 7. 领域层必须修订清单（进入编码前）

1. **ADR-001**：Park / Building / Unit 聚合根边界与占用写权限  
2. **ADR-002**：Bill 状态去掉互斥 OVERDUE，改衍生逾期  
3. **ADR-003**：Party 单园限制与二期扩展  
4. **补齐领域-DDL 对齐**：`lease_terms`（可简化）、附件策略（表或对象存储 key）  
5. **不变量写入测试清单**：`used_area` 投影、核销金额约束、园区 scope  

---

## 8. 领域评审结论

| 维度 | 分数（10） |
| --- | --- |
| 主链正确性 | 9 |
| 聚合边界清晰度 | 6 |
| 与旧系统纠偏价值 | 9 |
| 与 DDL/API 一致性 | 5 |
| 行业完备性（一期） | 7 |
| **领域综合** | **7.2 / 10** |

**结论：主链可冻结；边界与一致性问题必须先出修订案，不可直接进入无约束编码。**
