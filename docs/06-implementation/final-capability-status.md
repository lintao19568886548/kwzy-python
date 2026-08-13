# 最终能力状态（代码级 · 证据表）

> 更新：2026-08-13 · 分支 `feat/browser-e2e-full-stack`  
> 规则：无代码/接口/UI/测试证据不得标 `IMPLEMENTED` / `ADAPTER_COMPLETE`。  
> 禁止连接真实生产库。

| 能力 | docs 来源 | 旧 Java 证据 | 新后端 | 新 API | 新前端路由 | 迁移/表 | 权限码 | 自动测试 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Identity 会话 | identity docs | 登录/会话 | `modules/identity` | `/auth/*` | `/login` | tenants/users/roles | * / session | pytest identity + e2e auth | IMPLEMENTED |
| 用户/角色/权限 | identity admin | 系统管理 | user/role admin | `/system/users|roles` | `/system` | users/roles/permissions | identity.user.* role.* | e2e system-admin | IMPLEMENTED |
| 组织/字典/参数 | config admin | 参数字典 | config_admin | `/system/org|dict|params` | `/system` tabs | org_units/dicts/params | identity.org/dict/param.* | e2e system-admin 掩码 | IMPLEMENTED |
| 园区/单元 | park_property | 园区 | park/unit services | `/parks` `/units` | `/parks` | parks/buildings/units | park:* unit:* | pytest + e2e seed | IMPLEMENTED |
| Party+联系人 | party | 主体 | party service | `/parties` `/contacts` | `/parties` | parties/contacts | party:* | e2e party | IMPLEMENTED |
| Lease 生命周期 | lease | 合同 | lease service | `/leases/*` | `/leases` | lease_contracts | lease:* | e2e lease + main-chain | IMPLEMENTED |
| Bill/Payment | billing/collection | 账单收款 | bill/payment | `/bills` `/payments` | `/bills` `/payments` | bills/payments | bill:* payment:* | e2e billing-payment | IMPLEMENTED |
| Workbench/WorkItem | workbench | 待办 | work_item service | `/workbench` `/work-items` | `/workbench` `/todos` | work_items | work_item:* | e2e workbench | IMPLEMENTED |
| Investment Leads | investment | 招商 | lead service | `/leads/*` | `/leads` | leads | lead:* | e2e investment-leads | IMPLEMENTED |
| Work Orders | facility_ops | 工单 | work_order service | `/work-orders/*` | `/work-orders` | work_orders | work_order:* | e2e work-orders | IMPLEMENTED |
| Collection Cases | collection | 催缴 | collection service | `/collection/cases` | `/collection` | collection_cases | collection:* | e2e collection | IMPLEMENTED |
| Approvals | workflow | 审批 | approval service | `/approvals/*` | `/approvals` | approvals | approval:* | pytest approval | ADAPTER_COMPLETE |
| Attachments local | attachments | 附件 | attachment repo | `/attachments` | — | attachments | attachment:* | pytest attachments | ADAPTER_COMPLETE |
| SMS/Notify/WeChat Fake | integrations | 通知 | Fake providers + outbox | `/integrations/*` | — | integration_outbox | identity.param.write | pytest providers + e2e outbox GET | ADAPTER_COMPLETE |
| OSS S3 生产 | integrations | OSS | S3 stub fail-closed | config | — | — | — | unit fail-closed | ADAPTER_COMPLETE |
| 跨租户隔离 | security | multi-tenant | tenant_id scope | all | forbidden | tenants | * | e2e cross-tenant-security | IMPLEMENTED |
| ETL fixture→PG16 | ETL tools | n/a | tools/etl | n/a | n/a | etl_fixture schema | n/a | drill fast+acceptance PASS | READY_FOR_STAGING_DATA |
| 浏览器完整主链 | FE | SPA | FastAPI | REST | apps/web routes | PG16 e2e | RBAC UI | Playwright 24/24 no-skip | IMPLEMENTED |
| 支付网关/企微/OCR 真联调 | external | 凭据 | Fake only | — | — | — | — | not live | LIVE_VERIFICATION_PENDING |
| Radar 爬虫 | disposition | Java | — | — | — | — | — | deprecated | DEPRECATED_WITH_EVIDENCE |

## 浏览器 E2E 证据

- 命令：`apps/web` → `npx playwright test`
- globalSetup：Docker PG16 → Alembic head → `scripts/e2e_seed.py` → uvicorn `:8010` → `npm run build` + vite preview `:4173`
- 禁止 API 不可用时 skip：`helpers.requireApiHealthy` 抛错
- 结果（本批）：**24 passed**（auth/party/lease/billing/workbench/leads/work-orders/system-admin/cross-tenant/main-chain/smoke）
- 一键：`scripts/run_browser_e2e.ps1`

## ETL 证据

| 档位 | master | txn | 结果 |
| --- | --- | --- | --- |
| fast | 1247 | 10105 | `ETL_DRILL=PASS` |
| acceptance | 12322 | 101005 | `ETL_DRILL=PASS` |

- 工具：`tools/etl/generate_large_fixture.py --profile fast|acceptance`
- 演练：`tools/etl/run_etl_drill.py`（生成/ dry-run / PG apply / 幂等 / checkpoint 续跑）
- 报告目录：`tools/etl/out/drill_*`

## 门禁（诚实）

```
KWZY_FULL_FRONTEND_REPLACEMENT=COMPLETE
KWZY_DATA_MIGRATION_READINESS=READY_FOR_STAGING_DATA
KWZY_CODE_REBUILD_ACCEPTANCE=PASS_PENDING_FULL_LOCAL_SCRIPT
KWZY_LOCAL_STAGING_EQUIVALENT=PENDING_FULL_RUNNER
LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED
KWZY_REMOTE_STAGING_ACCEPTANCE=NOT_RUN
KWZY_PRODUCTION_MIGRATION=NOT_EXECUTED
KWZY_PRODUCTION_DEPLOYMENT=NOT_EXECUTED
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED_EXTERNAL_ACCEPTANCE
```

说明：浏览器全栈 E2E 与 ETL 规模演练已通过；`infra/local-staging/run_full_acceptance.ps1` 已升级为含 Playwright+双档 ETL，完整一键跑需在干净环境复验后才能标 `KWZY_LOCAL_STAGING_EQUIVALENT=PASS`。
