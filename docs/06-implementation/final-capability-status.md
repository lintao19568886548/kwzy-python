# 当前能力状态（代码级 · 范围化证据表）

> 更新：2026-08-13 18:05（Asia/Shanghai）
> `TESTED_CODE_SHA`：`b25eb079655d8d3417fc7a40d3b8741f36ea0698`
> 验收脚本 SHA256：`6B192E6DBA9ACABC6220694CB0C7AE36A511A0719D1072CB956D676CF72A7C88`
> 规则：无模型/API/UI/测试证据不得标记本地实现；本地实现、适配器和生产联调必须分开。禁止连接真实生产库。

| 能力 | docs 来源 | 旧 Java 证据 | 新后端 | 新 API | 新前端路由 | 迁移/表 | 权限码 | 自动测试 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Identity 会话 | identity | 登录/会话 | modules/identity | /auth/* | /login | tenants/users/security_events | session | pytest + e2e auth | IMPLEMENTED_LOCAL_SCOPE |
| 用户/角色/权限/组织配置 | identity/config admin | 系统管理 | admin services | /system/* | /system | users/roles/permissions/org/dicts/params | identity.* | e2e system-admin | PARTIAL_LEGACY_LONG_TAIL |
| 空间层级/出租单元 | park_property | 园区/楼栋/单元 | spatial/unit/version/lineage | /parks /spaces /units | /rent-control | parks/buildings/units/unit_lineages | park:* unit:* | pytest + PG race + e2e | IMPLEMENTED_LOCAL_SCOPE |
| 租控工作台 | park_property | 租控 | rent_control | /rent-control/* | /rent-control | query projection | park:read/unit:* | pytest + e2e desktop/tablet | IMPLEMENTED_LOCAL_SCOPE |
| Party+联系人 | party | 主体 | party service | /parties /contacts | /parties | parties/contacts | party:* | e2e party | PARTIAL |
| Lease 生命周期 | lease | 合同 | lease service | /leases/* | /leases | lease_contracts | lease:* | e2e lease + main-chain | PARTIAL |
| Bill/Payment | billing/collection | 账单收款 | bill/payment | /bills /payments | /bills /payments | bills/payments | bill:* payment:* | e2e billing-payment | PARTIAL |
| Workbench/WorkItem | workbench | 待办 | work_item | /workbench /work-items | /workbench /todos | work_items | work_item:* | e2e workbench | PARTIAL |
| Investment Leads | investment | 招商 | lead service | /leads/* | /leads | leads | lead:* | e2e investment-leads | PARTIAL |
| Work Orders/Collection | facility_ops/collection | 工单/催缴 | work_order/case | /work-orders /collection/cases | /work-orders /collection | work_orders/collection_cases | work_order:* collection:* | e2e | PARTIAL |
| Approvals/Attachments | workflow/attachments | 审批/附件 | minimal services | /approvals /attachments | /approvals | approvals/attachments | approval:* attachment:* | pytest | MINIMAL_LOCAL_SCOPE |
| SMS/Notify/Object storage | integrations | 通知/存储 | fake/local + fail-closed | /integrations/* | — | integration_outbox | — | pytest + outbox | ADAPTER_NOT_LIVE |
| 跨租户/园区隔离 | security | multi-tenant | tenant/park scope | mounted APIs | /forbidden | tenant_id/park grants | * | pytest + e2e cross-tenant | IMPLEMENTED_CURRENT_SCOPE |
| Asset ETL fixture→PG16 | ETL tools | 旧资产待取证 | isolated synthetic drill | n/a | n/a | etl_asset_fixture | n/a | dry/apply/idempotent/reconcile/rollback | CONDITIONAL_SYNTHETIC_READY |
| PC 浏览器主链 | FE | SPA | FastAPI | REST | apps/web | PG16 e2e | RBAC UI | Playwright 28/28 no-skip | PARTIAL_PRODUCT_SCOPE |
| 员工移动端/租户小程序 | product scope | 多端 | — | — | 应用不存在 | — | — | — | NOT_STARTED |
| 支付网关/企微/OCR 真联调 | external | 凭据 | Fake only | — | — | — | — | not live | LIVE_VERIFICATION_PENDING |
| Radar 爬虫 | disposition | Java | — | — | — | — | — | deprecated | DEPRECATED_WITH_EVIDENCE |

## 本地全栈验收（当前已实现范围）

- 命令：`pwsh -NoProfile -File .\infra\local-staging\run_full_acceptance.ps1`
- 被测提交：`b25eb079655d8d3417fc7a40d3b8741f36ea0698`
- 机器报告：`infra/local-staging/out/acceptance_20260813_180435.json`（gitignored，本机）
- 结果：20/20 exit 0；pytest 151；Vitest 4；Playwright 28/0/0；core/Identity/Asset ETL PASS；48 表备份恢复 PASS；OpenAPI PASS；OpenSpec 33/0；518 文件密钥扫描 PASS；清理 PASS。

## 门禁

```text
KWZY_PRODUCT_BLUEPRINT=IN_PROGRESS
KWZY_BACKEND_REBUILD=CONDITIONAL_CORE_SLICE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_CORE_SLICE_ONLY
KWZY_EMPLOYEE_MOBILE=BLOCKED_NOT_IMPLEMENTED
KWZY_TENANT_MINIPROGRAM=BLOCKED_NOT_IMPLEMENTED
KWZY_LEGACY_CAPABILITY_CLOSURE=BLOCKED
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_FIXTURE_ONLY
KWZY_SECURITY_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PERFORMANCE_ACCEPTANCE=BLOCKED_NOT_RUN
KWZY_E2E_ACCEPTANCE=CONDITIONAL_CORE_SLICE_ONLY
KWZY_OPERATIONS_READINESS=BLOCKED
LIVE_EXTERNAL_INTEGRATION=NOT_VERIFIED
KWZY_REMOTE_STAGING_ACCEPTANCE=NOT_RUN
KWZY_PRODUCTION_MIGRATION=NOT_EXECUTED
KWZY_PRODUCTION_DEPLOYMENT=NOT_EXECUTED
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
```

## 历史状态

旧版本曾把代码样板、适配器和完整产品替代混写为 COMPLETE；该表述已撤销。当前 PASS 只绑定上述精确 SHA 的已实现范围，不能外推为旧 Java 全替代、三端全量、真实数据迁移、外部平台联调或生产就绪。
