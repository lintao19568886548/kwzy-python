# 园区政策、企业服务、活动与公告验收证据

> 日期：2026-08-20（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 状态：工作树专项验收通过；精确 SHA 全量门禁待最终提交后重跑

## 当前判定

政策治理、企业服务目录与 Party-bound 服务单、园区活动容量/候补/签到、公告冻结受众与站内送达已达到本地产品范围的 `IMPLEMENTED_AND_VERIFIED`。该结论不扩展为全量重构完成。

以下边界保持真实：

- 政府政策 feed、外部服务商、支付、短信/邮件/微信、租户小程序均为 `NOT_CONNECTED`。
- 政策匹配只表示本地相关性，不构成官方资格认定；公告只证明站内信 delivery/read。
- 真实独立 notice/政策/服务/活动迁移仍为 `BLOCKED_PENDING_AUTHORIZED_NOTICE_EXPORTS_KEYMAPS_AND_SIGNED_RECONCILIATION`。
- 本轮没有重新 propose/apply 历史 `harden-step1-foundation`，也没有修改历史 migration。

## 已完成的工作树专项门禁

| 门禁 | 结果 |
| --- | --- |
| Alembic / PG16 | `e7 → d6 → e7` 通过；当前唯一 head `e7b24f0a1c09` |
| ORM drift | `all_diffs=0`, `engagement_diffs=0` |
| 后端集中回归 | domain/application/HTTP/PG16/ETL/OpenAPI/architecture：46 passed，0 failed |
| Synthetic ETL | 5 tests passed；8 阶段均 PASS，中断后 0 残留、重放 0 新增、run rollback 与 backup/delete/restore 通过 |
| 性能 | 1,000 请求、并发 25、0 错误、p95 164.911 ms、180.597 RPS；门槛 p95≤500 ms / 错误率 0% / RPS≥20 |
| 前端 | lint、typecheck、4 files / 9 Vitest、production build 通过 |
| 浏览器 | 真实 PG16 + FastAPI + production Vite engagement E2E：1 passed；覆盖 staff 与独立 tenant-principal |
| PG 备份恢复 | custom dump 1,257,743 bytes；恢复签名一致，临时恢复库已删除 |

## 业务与安全覆盖

- 四类聚合均通过 UI 建草稿、原生审批、精确版本发布；政策/活动/公告版本不可变，事件/evidence 追加保护由 PostgreSQL 验证。
- 租户用户由真实角色、Party/park relation 和 TenantServicePrincipal 派生，完成政策匹配/本地咨询、服务申请、活动报名、公告收件箱已读。
- 覆盖 unknown field、重复 query 参数、IDOR、跨 Party 幂等键、伪造 tenant Party、XSS、SSRF、不安全 URL、敏感字段和长幂等键。
- 活动最后席位并发只有一个 confirmed winner；同服务单并发预约只有一个版本赢家。
- 公告 fan-out 冻结 recipient，并验证 partial retry、唯一 delivery/read 和 `production_contacted=false`。

## Migration 证据

[engagement-etl-report.json](engagement-etl-report.json) 对 1 政策+版本、1 服务目录、1 服务单、1 活动+版本、2 报名、1 公告+版本、2 目标、2 站内 delivery 和 5 条 quarantine 完成精确对账。quarantine 原因包括未授权官方来源、外部 provider 证据缺失、Party/活动键缺失和未经证实的外部渠道。

[postgres-backup-restore.json](postgres-backup-restore.json) 记录 `pg_dump -Fc` 后临时库恢复：源/恢复均为 `alembic=e7b24f0a1c09`、20 张 engagement 表，核心行数签名完全一致；未接触生产。

## 性能与视觉证据

- [http-performance-1000x25.json](http-performance-1000x25.json)
- [engagement-staff-desktop.png](engagement-staff-desktop.png)
- [engagement-tenant-tablet.png](engagement-tenant-tablet.png)
- [engagement-mobile-offline.png](engagement-mobile-offline.png)

Desktop 显示工作人员公告发布与站内分发真值；Tablet 820px 显示 Party-bound 报名与容量；Mobile 390×844 显示公告已读和离线命令阻断，浏览器断言均无 body 横向溢出。三张截图均已在 loading 消失后生成并人工复核。

运行、worker、迁移与回滚步骤见 [park-enterprise-engagement-runbook.md](../../park-enterprise-engagement-runbook.md)。在最终精确 SHA 全量门禁、文档同步和归档前，禁止把本 README 当成全项目完成证明。
