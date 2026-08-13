# KWZY 全系统重建追踪矩阵（封板）

> 更新：2026-08-13  
> 被测代码：`TESTED_CODE_SHA=23fa781e089018c9740c22e0aeb6a6d6e7ff8bbd`  
> 验收脚本 SHA256：`79B4F447DD3B574380A961FE6864B567F9BCEAA18240D979AB231742BA35A839`  
> 结论：**代码级全栈本地验收 PASS**；外部联调与生产 **未执行**。

## 0. 真实完成度摘要（当前）

| 维度 | 估计 | 说明 |
| --- | ---: | --- |
| 后端核心主链 | ~95% | Auth/Park/Party/Lease/Bill/Payment + 测试 + 浏览器主链 |
| Identity/System/Admin | ~95% | 会话、用户/角色、组织/字典/参数、管理 UI + e2e |
| Workbench | ~95% | CRUD、事件待办、summary、浏览器闭环 |
| Investment leads | ~90% | CRUD/跟进/转化/权限 + e2e（雷达等外部 DEFER） |
| Work Orders / Collection | ~90% | API+UI+e2e；真实短信/企微 NOT_VERIFIED |
| 旧 Java 代码级替代 | ~90% | 主业务域已替代；真实外部适配待凭据 |
| 前端替换 | ~95% | production FE + Playwright 24 条真实主链 |
| 数据映射/ETL | ~85% | 双档演练、幂等、checkpoint、对账；无旧生产库连接 |
| 预发布/生产 | 0% | 远程/生产 NOT_RUN / NOT_EXECUTED |

**门禁（当前）：**

| 标识 | 值 |
| --- | --- |
| `KWZY_PYTHON_CODE_REFACTOR` | `COMPLETE` |
| `KWZY_FULL_JAVA_REPLACEMENT` | `COMPLETE_PENDING_LIVE_EXTERNAL_VERIFICATION` |
| `KWZY_FULL_FRONTEND_REPLACEMENT` | `COMPLETE` |
| `KWZY_DATA_MIGRATION_READINESS` | `READY_FOR_STAGING_DATA` |
| `KWZY_LOCAL_STAGING_EQUIVALENT` | `PASS` |
| `KWZY_CODE_REBUILD_ACCEPTANCE` | `PASS` |
| `LIVE_EXTERNAL_INTEGRATION` | `NOT_VERIFIED` |
| `KWZY_REMOTE_STAGING_ACCEPTANCE` | `NOT_RUN` |
| `KWZY_PRODUCTION_MIGRATION` | `NOT_EXECUTED` |
| `KWZY_PRODUCTION_DEPLOYMENT` | `NOT_EXECUTED` |
| `KWZY_FULL_REBUILD_ACCEPTANCE` | `BLOCKED_EXTERNAL_ACCEPTANCE` |

## 1. 运行与 Git 基线（封板）

| 项 | 值 |
| --- | --- |
| 远程 | `https://github.com/lintao19568886548/kwzy-python.git` |
| 被测 main | `23fa781e089018c9740c22e0aeb6a6d6e7ff8bbd` |
| Alembic head | `g3b91f6d4c75`（唯一） |
| pytest（PG16 URL） | 136 passed |
| Playwright | 24 passed / 0 failed / 0 skipped |
| OpenSpec strict | 28 passed / 0 failed |
| 前端 | `apps/web` production build + 全业务表单 |
| 验收一键 | `infra/local-staging/run_full_acceptance.ps1` |

## 2. 域级矩阵（当前）

| domain | 新 API | 新 FE | 测试 | 状态 | 策略 |
| --- | --- | --- | --- | --- | --- |
| identity | /auth /system users roles | Login + System | pytest + e2e | IMPLEMENTED | REDESIGN |
| park_property | /parks /units | ParksView | pytest + e2e seed | IMPLEMENTED | REDESIGN |
| party | /parties* | PartiesView | pytest + e2e | IMPLEMENTED | REDESIGN |
| lease | /leases* | LeasesView | pytest + e2e | IMPLEMENTED | REDESIGN |
| billing | /bills* | BillsView | pytest + e2e | IMPLEMENTED | REDESIGN |
| collection payment | /payments* | PaymentsView | pytest + e2e | IMPLEMENTED | REDESIGN |
| collection cases | /collection/cases* | CollectionCasesView | pytest + e2e | IMPLEMENTED | REDESIGN |
| workbench | /work-items /workbench | Workbench/Todos | pytest + e2e | IMPLEMENTED | INNOVATION |
| investment | /leads* | LeadsView | pytest + e2e | IMPLEMENTED | REDESIGN |
| facility_ops | /work-orders* | WorkOrdersView | pytest + e2e | IMPLEMENTED | REDESIGN |
| workflow | /approvals* | ApprovalsView | pytest | ADAPTER_COMPLETE | REDESIGN |
| attachments | /attachments* | — | pytest | ADAPTER_COMPLETE | ADAPTER |
| integrations | /integrations/* Fake | — | pytest + outbox | ADAPTER_COMPLETE | ADAPTER |
| platform/ETL | CLI tools/etl | N/A | drill fast/acceptance | READY_FOR_STAGING_DATA | RETAIN 语义 |
| frontend | REST 消费 | apps/web 全路由 | Playwright 24 | COMPLETE | REDESIGN |
| live external | 生产 Provider | — | 无真实凭据 | NOT_VERIFIED | ADAPTER |

## 3. 语义门禁清单

- [x] 鉴权 fail-closed（JWT）
- [x] 租户隔离
- [x] 园区 scope 与动作权限正交
- [x] 主链状态机（Party/Lease/Bill/Payment）
- [x] 浏览器 RBAC 与跨租户拒绝
- [x] 本地全栈一键验收 exit 0
- [ ] 真实外部联调
- [ ] 远程预发布
- [ ] 生产迁移与部署

## 4. 历史状态（过程）

早期矩阵曾写：Workbench 部分、前端脚手架 ~15%、招商/工单 stub、ETL 10%、门禁 `IN_PROGRESS`/`NOT_COMPLETE`/`PENDING_FULL_RUNNER`、本地仅 `/health` 等。  
以上为迭代过程记录，**非当前结论**。当前以 `TESTED_CODE_SHA` 与 `run_full_acceptance.ps1` 复跑为准。
