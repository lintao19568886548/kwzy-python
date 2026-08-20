# 园区政策、企业服务、活动与公告运行手册

## 能力边界

本纵切只运行园区本地 engagement 真值。政府政策源、外部服务商、外部通知渠道、支付和小程序均未连接；任何运维输出都不得把本地相关性写成官方资格，不得把站内投递写成短信、邮件或政府系统送达。

真实旧数据迁移状态固定为 `BLOCKED_PENDING_AUTHORIZED_NOTICE_EXPORTS_KEYMAPS_AND_SIGNED_RECONCILIATION`，直到取得独立 notice/政策/服务/活动 schema 导出、行数水位、脱敏快照、park/Party/user/attachment 键映射、来源权属、容差和负责人签字。`magic.sql`、旧代码或 `kwzy_step1.db` 不能替代这些输入。

## 部署前门禁

1. PostgreSQL 必须为 16.x，`alembic current` 与唯一 `heads` 均为 `e7b24f0a1c09`。
2. 从空库升级和现有 `d6a13e9f0b98 → e7b24f0a1c09 → d6a13e9f0b98 → e7b24f0a1c09` 必须通过；禁止修改历史 migration。
3. ORM metadata drift、engagement 单元/HTTP/PG 并发/ETL、OpenAPI 与 OpenSpec strict 必须为零失败。
4. PC lint、typecheck、Vitest、production build 和真实 Playwright 三档视口必须通过。
5. 备份恢复、性能和 secrets/dependency gate 必须在同一验收 SHA 重跑。

## Worker 与定时任务

- 公告 fan-out 只处理已冻结的站内目标，建议每批 200 条；失败记录保留 `attempt_count/last_error`，重试不得产生重复 recipient/channel delivery。
- 公告 schedule sweep 发布已到时且审批通过的精确版本，并把过期公告转为 `EXPIRED`；撤回后未处理 delivery 必须失败留证。
- 政策 expiry sweep 只按持久化有效窗处理，追加事件与审计；不得修改既有版本正文。
- 服务 SLA sweep 只追加升级事件/状态，不联系外部服务商；WorkOrder handoff 必须走现有受控关联。
- 每次 worker 运行记录 tenant、批次大小、处理/跳过/失败数量和 request/run id。当前 local staging 证据必须保持 `production_contacted=false`。

## Synthetic importer

```powershell
$env:TEST_DATABASE_URL = '<loopback PostgreSQL test URL>'
apps\api\.venv\Scripts\python.exe tools\etl\run_engagement_etl_drill.py `
  --out docs\06-implementation\evidence\park-enterprise-policy-service-engagement\engagement-etl-report.json
```

Importer 只接受声明为 synthetic、无真实客户数据、无权威旧 schema/export 的 fixture，并拒绝非 loopback 或 production-like 数据库名。它执行 dry-run、事务中断回滚、checkpoint/resume、首次 apply、零新增 replay、版本/有效窗/服务单/容量/报名/受众/送达/已读/隔离对账、run-scoped rollback 和逻辑 backup/delete/restore。

隔离记录只保存来源引用、原因和不可逆指纹。禁止猜测 Party/park、伪造原生审批、把政府来源声明为已授权、把外部服务商标记为已连接或把外部 delivery 标为成功。

## 回滚与恢复

- 数据导入回滚按 `run_id` 删除；先核对 run manifest，禁止无条件清空 engagement 表。
- schema 回滚只用于上线前/无新业务写入的演练。出现业务写入后使用前向修复 revision 或导出/补偿，不回改历史 migration。
- 上线前使用 `pg_dump -Fc`，恢复到明确命名的临时数据库，比对 Alembic、20 张 engagement 表和各核心聚合签名；验证后删除临时库与临时 dump。
- 生产 RPO/RTO、停写、切换、删除和回切需独立授权；本地演练不能替代生产演练。

## 告警与排障

- HTTP 409：刷新聚合与 `lock_version`，核对幂等键载荷指纹，不盲重放不同命令。
- HTTP 403/404：核对数据库角色、park scope、TenantServicePrincipal 和 Party relation；禁止依赖客户端 claims 放宽。
- 活动容量冲突：以 PostgreSQL 锁后的 registration/capacity 为准，检查候补顺序，禁止手工增加 confirmed count。
- 公告送达不一致：比较 frozen target、delivery 和 in-app notification；外部渠道始终为 `NOT_CONNECTED`。
- 恢复前保留 request_id、审计、BusinessEvent 和 append-only evidence，不删除用于定位的历史。
