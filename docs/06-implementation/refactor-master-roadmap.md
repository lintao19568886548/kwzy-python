# KWZY 全系统重构主路线图

> 更新：2026-08-13 — 续跑总指令  
> 当前：**部分核心后端**；禁止将 pytest 通过等同全系统完成。

## 主线

```text
仓库基线审计
→ 全量追踪矩阵（full-rebuild-traceability-matrix.md）
→ Phase A Workbench 闭环（账单已挂 + 合同到期 + summary）
→ Phase B Identity/System/Admin 补全（组织/字典/参数/UI）
→ Phase C 主链复核与缺陷修复
→ Phase D 旧 Java 剩余域（招商/工单/通知/报表…）逐 change
→ Phase E 创新前端 apps/web
→ Phase F 数据映射与 ETL
→ Phase G 工程质量收口
→ 最终验收包（生产迁移/部署仍 NOT_EXECUTED）
```

## 状态板

| 阶段 | 状态 |
| --- | --- |
| Phase06 Party/Lease/Bill/Payment | COMPLETE（scoped v1，main） |
| V2.3.2 Identity 证据 | READY_FOR_HUMAN_REVIEW（artifacts，非实现完成） |
| Identity 实现 | PARTIAL（会话+用户角色菜单 API） |
| Workbench | IN_PROGRESS（CRUD+账单/合同+summary） |
| 前端替换 | NOT_COMPLETE（脚手架起步） |
| 数据迁移工具 | NOT_READY（骨架起步） |
| 预发布验收 | NOT_RUN |
| 生产部署 | NOT_EXECUTED |

## 创新原则

- 保留业务能力与不变量，不照搬 Java 实现
- 配置化规则、自动待办、工作台优先
- AI 仅建议，不绕过权限/财务
- OpenSpec 是变更工具，不是唯一需求来源
- 每域：docs + 旧代码证据 → change → 测试 → 矩阵更新 → 推送

## 依赖顺序（执行）

1. Workbench 闭环（低侵入挂接领域事件）
2. 主链安全/并发复核
3. Identity 管理缺口
4. 招商 leads 真实现（替代 stub）
5. 前端主链页面
6. ETL 映射与 dry-run
7. 工单/运营/通知等长尾域

## 门禁

只有矩阵无 UNKNOWN、FE 闭合、ETL READY、测试全绿，才可声明  
`KWZY_FULL_REBUILD_ACCEPTANCE=PASS`。
