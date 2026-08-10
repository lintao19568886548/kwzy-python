# KWZY Python Workspace Agent 状态

> 会话重启后**必须先读本文件 + refactor-master-roadmap.md**。

---

## 当前执行点

| 字段 | 值 |
| --- | --- |
| 更新时间 | 2026-08-10 |
| 当前分支 | `feat/lease-contract` |
| HEAD | （见 git；基于 Party 推送后最新） |
| parent branch | `feat/party-master` |
| parent commits | `d7e1300`（Party 实现）、`c181e7f`（状态文档） |
| 当前 OpenSpec change | `implement-lease-contract`（proposal/design/specs/tasks 已建） |
| 当前任务 | 0.2 strict validate 后按 tasks 从领域开始 APPLY |
| 是否允许继续 | **是**；禁止 merge main |

---

## Party 已交付（锁定）

| 项 | 值 |
| --- | --- |
| 分支 | `feat/party-master` |
| 实现 commit | `d7e1300` |
| 状态文档 commit | `c181e7f` |
| 远程 | 已推送 origin |
| 第三次验收 | P0=0 P1=0；67 tests；PG/SQLite/OpenAPI/openspec 通过 |
| main | **未合并** |

---

## Lease 边界（已写入 design）

**做：** 合同生命周期、占用、terms、used_area 投影、tenant/park、审计  

**不做：** Bill/Payment、押金退还流水、旧 rental 适配、自动 EXPIRING 调度产品化  

**暂停触发：** 实现中若需发明未批准计费/舍入/滞纳金/退款算法 → HUMAN_DECISION_REQUIRED  

---

## 下一条动作

1. `openspec validate implement-lease-contract --strict`  
2. tasks 1.x Domain 实体与规则 + 单测  
3. 2.x 迁移与仓储  
4. 3.x Service/Router  
5. 测试与推送 `feat/lease-contract`  

---

## Stacked 分支记录

| 分支 | parent | parent commit | change | push |
| --- | --- | --- | --- | --- |
| feat/party-master | main | 0a2e75d 一带 | implement-party-master | d7e1300 + c181e7f |
| feat/lease-contract | feat/party-master | c181e7f | implement-lease-contract | 进行中 |
