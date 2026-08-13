# 最终能力状态（代码级 · 证据表 · 封板）

> 更新：2026-08-13  
> `TESTED_CODE_SHA`：`23fa781e089018c9740c22e0aeb6a6d6e7ff8bbd`  
> 验收脚本 SHA256：`79B4F447DD3B574380A961FE6864B567F9BCEAA18240D979AB231742BA35A839`  
> 规则：无代码/接口/UI/测试证据不得标 IMPLEMENTED / ADAPTER_COMPLETE。禁止连接真实生产库。

| 能力 | docs 来源 | 旧 Java 证据 | 新后端 | 新 API | 新前端路由 | 迁移/表 | 权限码 | 自动测试 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Identity 会话 | identity | 登录/会话 | modules/identity | /auth/* | /login | tenants/users | session | pytest + e2e auth | IMPLEMENTED |
| 用户/角色/权限 | identity admin | 系统管理 | user/role admin | /system/users\|roles | /system | users/roles/permissions | identity.user.* role.* | e2e system-admin | IMPLEMENTED |
| 组织/字典/参数 | config admin | 参数字典 | config_admin | /system/org\|dict\|params | /system tabs | org_units/dicts/params | identity.org/dict/param.* | e2e 掩码 | IMPLEMENTED |
| 园区/单元 | park_property | 园区 | park/unit | /parks /units | /parks | parks/buildings/units | park:* unit:* | pytest + e2e | IMPLEMENTED |
| Party+联系人 | party | 主体 | party service | /parties /contacts | /parties | parties/contacts | party:* | e2e party | IMPLEMENTED |
| Lease 生命周期 | lease | 合同 | lease service | /leases/* | /leases | lease_contracts | lease:* | e2e lease + main-chain | IMPLEMENTED |
| Bill/Payment | billing/collection | 账单收款 | bill/payment | /bills /payments | /bills /payments | bills/payments | bill:* payment:* | e2e billing-payment | IMPLEMENTED |
| Workbench/WorkItem | workbench | 待办 | work_item | /workbench /work-items | /workbench /todos | work_items | work_item:* | e2e workbench | IMPLEMENTED |
| Investment Leads | investment | 招商 | lead service | /leads/* | /leads | leads | lead:* | e2e investment-leads | IMPLEMENTED |
| Work Orders | facility_ops | 工单 | work_order | /work-orders/* | /work-orders | work_orders | work_order:* | e2e work-orders | IMPLEMENTED |
| Collection Cases | collection | 催缴 | collection | /collection/cases | /collection | collection_cases | collection:* | e2e collection | IMPLEMENTED |
| Approvals | workflow | 审批 | approval | /approvals/* | /approvals | approvals | approval:* | pytest approval | ADAPTER_COMPLETE |
| Attachments local | attachments | 附件 | attachment repo | /attachments | — | attachments | attachment:* | pytest attachments | ADAPTER_COMPLETE |
| SMS/Notify/WeChat Fake | integrations | 通知 | Fake + outbox | /integrations/* | — | integration_outbox | — | pytest + outbox GET | ADAPTER_COMPLETE |
| OSS S3 生产 stub | integrations | OSS | S3 fail-closed | config | — | — | — | unit fail-closed | ADAPTER_COMPLETE |
| 跨租户隔离 | security | multi-tenant | tenant_id | all | /forbidden | tenants | * | e2e cross-tenant | IMPLEMENTED |
| ETL fixture→PG16 | ETL tools | n/a | tools/etl | n/a | n/a | etl_fixture | n/a | drill fast+acceptance | READY_FOR_STAGING_DATA |
| 浏览器完整主链 | FE | SPA | FastAPI | REST | apps/web | PG16 e2e | RBAC UI | Playwright 24/24 no-skip | IMPLEMENTED |
| 支付网关/企微/OCR 真联调 | external | 凭据 | Fake only | — | — | — | — | not live | LIVE_VERIFICATION_PENDING |
| Radar 爬虫 | disposition | Java | — | — | — | — | — | deprecated | DEPRECATED_WITH_EVIDENCE |

## 本地全栈验收（封板复跑）

- 命令：`pwsh -NoProfile -File .\infra\local-staging\run_full_acceptance.ps1`
- 被测提交：`23fa781e089018c9740c22e0aeb6a6d6e7ff8bbd`
- 结果：退出码 **0**；pytest 136；Playwright 24/0/0；ETL 双档 PASS；备份恢复 PASS；OpenAPI PASS；OpenSpec 28/0；密钥扫描 PASS；清理 PASS。

## 门禁

```text
KWZY_PYTHON_CODE_REFACTOR=COMPLETE
KWZY_FULL_JAVA_REPLACEMENT=COMPLETE_PENDING_LIVE_EXTERNAL_VERIFICATION
KWZY_FULL_FRONTEND_REPLACEMENT=COMPLETE
KWZY_DATA_MIGRATION_READINESS=READY_FOR_STAGING_DATA
KWZY_LOCAL_STAGING_EQUIVALENT=PASS
KWZY_CODE_REBUILD_ACCEPTANCE=PASS
LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED
KWZY_REMOTE_STAGING_ACCEPTANCE=NOT_RUN
KWZY_PRODUCTION_MIGRATION=NOT_EXECUTED
KWZY_PRODUCTION_DEPLOYMENT=NOT_EXECUTED
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED_EXTERNAL_ACCEPTANCE
```

## 历史状态

过程中曾出现 `IN_PROGRESS` / `NOT_COMPLETE` / `PENDING_FULL_RUNNER` / 部分 E2E skip / 仅 health 本地预发等标记，均属迭代中间态，已被干净 main 复合验收取代。
