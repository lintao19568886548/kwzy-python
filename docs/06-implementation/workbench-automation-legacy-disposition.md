# 工作台、消息与定时任务旧系统处置

> 结论日期：2026-08-14。本文只裁决当前纵切；未经授权的旧数据库和外部 XXL-Job/Kafka/RabbitMQ 环境仍是事实阻塞。

## 原始证据

| 证据 | 独立观察 | 裁决 |
| --- | --- | --- |
| `dashboard/workspace/WorkspaceController.java`、`WorkspaceRepository.java` | `/dashboard/workspace/list` 实际查询 `api_log`，按角色树过滤访问日志，并非可配置业务工作台 | `RETIRED_BY_REDESIGN`：访问证据归审计中心，不迁成首页布局 |
| `DashboardOverviewController.java` | `/dashboard/workbench-todos` 为多模块即时拼装的只读汇总 | `REPLACED`：改为来源拥有的 WorkItem 投影、事件规则和可下钻组件 |
| `db/manual/001-event-outbox.sql` | MySQL `event_outbox/event_consume_log` 有事件、幂等、状态和重试字段 | `TRANSFORM`：迁至租户/园区范围的 `business_events/event_consumer_logs`；未知事件隔离，不伪造成功 |
| `db/manual/002-in-app-notification.sql` | 通知绑定中心用户和 customer/db 名，且依赖手工 DDL | `TRANSFORM`：先完成 tenant/user 映射，再迁入收件人隔离的 `in_app_notifications`；无法映射的接收人隔离 |
| `messaging/*PlanService.java` | 大量类明确标注 plan、dry-run、未来集成或安全门未开启 | `NOT_IMPLEMENTED_EVIDENCE`：不作为旧系统已投产能力，也不计入迁移成功 |
| `BusinessOutboxPublisher.java`、`OutboxDispatcher.java`、`EventConsumeLogRepository.java` | 存在部分真实发布、投递和消费日志路径 | `REPLACED`：事务内数据库 Outbox、`SKIP LOCKED`、有界重试、DEAD 与代际重放 |
| `BackendMigrationJobHandlers.java`、`XxlJobConfig.java` | XXL-Job handler 覆盖组织开通、退款、短信、爬虫等异构任务 | `SELECTIVE_TRANSFORM`：仅映射本系统注册的三个安全 handler，迁入后默认停用；其余隔离并回到对应业务纵切 |
| 旧 PC 工作台/工单待办页面 | 待办散落在业务页面和查询参数，首页组件不可持久配置 | `REPLACED`：用户→角色→服务端默认布局、消息中心、规则/任务控制面和真实下钻 |

## 字段与状态映射

| 旧字段/状态 | 新字段/状态 | 规则 |
| --- | --- | --- |
| `customer_id` / 租户库 | `tenant_id` | 必须由签字确认的租户映射表转换，不按字符串猜测 |
| `event_id` | `source_event_id` 迁移证据 + 新主键 | 源 ID 保留在迁移映射；运行时使用新 bigint 主键 |
| `aggregate_type/id` | `source_type/source_id` | 仅注册类型进入主表 |
| `pending/retry/failed/success/sent/dead` | `PENDING/RETRY/RETRY/SUCCEEDED/SUCCEEDED/DEAD` | `SUCCEEDED` 只能来自持久源成功证据；缺失不得推断 |
| `consumer_group` | `WORKBENCH_AUTOMATION` | 旧 consumer 仅在事件可映射时进入；原值留迁移证据 |
| `recipient_center_user_id` | `recipient_user_id` | 先经 tenant+user 映射；未知接收人隔离 |
| `unread/read/archived` | `UNREAD/READ/ARCHIVED` | 首次已读时间可证明时才保留 |
| XXL handler | 注册 `handler_key` | 只接受 `OUTBOX_DISPATCH`、`LEASE_TODO_SYNC`、`APPROVAL_OVERDUE_SWEEP`；全部默认 `enabled=false` |
| `api_log` 工作台访问记录 | `audit_logs`（另行保留） | 禁止迁为 WorkItem、通知或布局 |

## 未迁移与阻塞

- 旧工作台即时拼装结果不落库迁移；上线前从合同、审批、账单、线索和工单原始状态重建来源投影。
- 组织开通、退款、短信、爬虫、账单导入等 XXL handler 属于其他业务或外部集成，不塞进通用调度器。
- Kafka/RabbitMQ/XXL-Job 的真实积压、消费位点和管理端配置未获得授权，当前不能宣称已完成生产切换。
- 旧通知正文可能含 PII；真实抽取必须先脱敏并通过拒绝规则，原文不得写入验收报告或日志。

合成演练入口：`tools/etl/run_workbench_automation_etl_drill.py`。它验证 dry-run、事务中断回滚、首次 apply、幂等复跑、对账、隔离和 fixture rollback；它不连接生产，也不替代真实旧数据演练。
