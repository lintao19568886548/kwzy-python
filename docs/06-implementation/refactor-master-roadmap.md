# KWZY Python 重构总路线图（Master Roadmap）

> 状态文件：由 Workspace Agent 维护。以本文件 + `refactor-agent-state.md` 为跨会话真相源。  
> 更新：2026-08-10  
> 范围：`kwzy-python`（禁止混入 `D:\宜租网\parkwise-main`）

---

## 1. 能力模块与依赖顺序

| 序 | 能力 | 依赖 | OpenSpec change | 状态 | 验收条件（摘要） | 风险 / 延期 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | Step1 基础：Identity + Park + Unit | — | archive: harden-step1 / close-step1-gaps；repair-postgres-baseline-boolean-portability | **完成** | 权限、scope、日志、审计、PG harness | Boolean 可移植已修 |
| 1 | Party 主数据 | Step1 | `implement-party-master`（+ 归档 `design-party-domain`） | **完成并推送** `feat/party-master`@`d7e1300`（**未合 main**） | P0=0 P1=0；PERSON 地址全拒绝；ORG 地址 OK；迁移/PG/SQLite/OpenAPI/全量测试 | PERSON 地址 KMS/加密 → 独立后续 change；Lease 未实现 |
| 2 | Lease | Party + Park/Unit | `implement-lease-contract` | **实现完成**（分支 `feat/lease-contract`，head `d4b02c3f5a21`） | 合同生命周期+占用+投影；74 tests | 押金退还/出账计费属后续 |
| 3 | Bill | Lease | 待建 | **未开始** | 同上 | 舍入/税费/滞纳金须批准 |
| 4 | Payment（收款登记） | Bill | 待建 | **未开始** | 核销/退款须批准 | 非在线支付订单 |
| 5 | 文档/接口/迁移/安全收口 | 各能力 | 按能力分 change | 进行中 | OpenAPI 同步、唯一 head、无敏感文件 | — |
| 6 | 最终人工验收 | 全部必做项 | — | **未开始** | 见 agent 指令「重构完成定义」 | 合并 main / 部署需人工 |

**依赖原则：** Party → Lease → Bill → Payment（stacked feature branch）。未获准合并 main 前不部署生产。

---

## 2. 分支策略（Stacked）

| 阶段 | 分支 | Parent | 说明 |
| --- | --- | --- | --- |
| Party | `feat/party-master` | `main` @ design archive | 当前 |
| Lease | 待定 `feat/lease-*` | 已验收 Party HEAD | 验收通过后创建 |
| Bill | 待定 | 已验收 Lease HEAD | — |
| Payment | 待定 | 已验收 Bill HEAD | — |

禁止 force push；禁止自动合并 main。

---

## 3. 已批准延期 / P2 登记

| ID | 项 | 原因 | 后续 |
| --- | --- | --- | --- |
| D-PII-KMS | PERSON 地址 KMS/字段加密/专用 PII 权限 | v1 全拒绝安全边界已落地 | 独立 change |
| D-LEASE-STUB | 既有 Lease/Bill/Payment 路由 stub | 本阶段未实现 | 各能力 change |
| D-APP-ORM | Application 持有 ORM 实例（不 import models） | 与 Park 一致；架构 import 门禁通过 | 可选重构 |

---

## 4. 生产方言

- 权威：PostgreSQL 16  
- 本地/单测：SQLite  
- 测试容器：`infra/postgres-test`，仅 `127.0.0.1`，用后停止  

---

## 5. 修订记录

| 日期 | 说明 |
| --- | --- |
| 2026-08-10 | 初建；Party 第三次验收通过；commit `d7e1300` 已推送 origin |
