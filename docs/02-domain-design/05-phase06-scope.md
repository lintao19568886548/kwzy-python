# 阶段 06 范围一页纸（In / Out of Scope）

> 阶段 05.1 冻结  
> 仅在 P0 设计修订验收后进入编码

---

## In Scope（允许开发）

| 序号 | 模块 | 交付 |
| --- | --- | --- |
| 1 | 基础设施 | Alembic、ORM 基类、`tenant_id` 强制、DataScope、审计钩子、幂等键 |
| 2 | Identity | 登录/刷新/登出、me、codes、page-access、用户种子 |
| 3 | ParkProperty | Park / Building / Unit CRUD + 状态；used_area 投影服务 |
| 4 | Lease | Party CRUD、contacts、Lease + terms、占用、activate/terminate |
| 5 | Billing | FeeCatalog、Bill/Lines、issue/void、duplicate-check、`is_overdue` |
| 6 | Collection | **收款登记** Payment + Allocation；账单 status 回写 |
| 7 | Finance（薄） | 收款确认 → ledger_entries |
| 8 | Collection SMS | preview + send（Mock SmsSender + page_access_proof） |
| 9 | 测试 | 租户隔离、核销不变量、占用冲突、逾期计算 |

---

## Out of Scope（禁止进入 06）

- 招商雷达 / 企微 CRM / 在线支付收银台  
- Excel 账单导入完整治理流水线（可后置）  
- 门禁 / 运维工单 / HRM / 报销  
- 微服务拆分、完整会计科目  
- 动态菜单运营后台（表已预留，UI/API 可后置）  
- 租户端小程序门户 BFF  

---

## 产品用语

| 正确 | 错误 |
| --- | --- |
| 收款登记 Payment | 「已经支持微信支付闭环」 |
| is_overdue 逾期未结 | status=OVERDUE |
| used_area 投影 | 手工主数据面积占用 |

---

## 依赖 ADR

见 `04-adr-pack.md`：ADR-001～011、ADR-T01～T07。
