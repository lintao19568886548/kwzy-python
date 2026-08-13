# KWZY 全系统重建追踪矩阵

> 生成/更新：2026-08-13  
> 基线：`main` / 工作分支 `feat/full-rebuild-continue`  
> HEAD 起点：`bc174e5`（Workbench 账单闭环后）  
> 结论：**部分核心后端完成**，**非**全系统重构完成。

## 0. 真实完成度摘要

| 维度 | 估计 | 说明 |
| --- | ---: | --- |
| 后端核心主链（Auth/Park/Party/Lease/Bill/Payment） | ~85% | API+测试有，催缴案件/SMS 仍缺 |
| Identity/System/Admin | ~70% | 会话+用户/角色/菜单 API 有；组织/字典/参数/管理 UI 缺 |
| Workbench | ~70% | CRUD+账单/合同/线索挂接+summary |
| Investment leads | ~60% | v1 CRUD+转化+待办；雷达/渠道 DEFER |
| 旧 Java 全域覆盖 | ~30% | 工单/报表/审批/通知仍大量未替代 |
| 前端替换 | ~15% | 脚手架+主链列表+招商页；表单/E2E 未全 |
| 数据映射/ETL | ~10% | 骨架与 dry-run 起步，字段未闭合 |
| 预发布/生产 | 0% | NOT_EXECUTED |

**门禁现状（诚实）：**

| 标识 | 值 |
| --- | --- |
| `KWZY_PYTHON_CODE_REFACTOR` | `IN_PROGRESS` |
| `KWZY_FULL_JAVA_REPLACEMENT` | `IN_PROGRESS` |
| `KWZY_FULL_FRONTEND_REPLACEMENT` | `NOT_COMPLETE` |
| `KWZY_DATA_MIGRATION_READINESS` | `NOT_READY` |
| `KWZY_STAGING_ACCEPTANCE` | `NOT_RUN` |
| `KWZY_PRODUCTION_MIGRATION` | `NOT_EXECUTED` |
| `KWZY_PRODUCTION_DEPLOYMENT` | `NOT_EXECUTED` |
| `KWZY_FULL_REBUILD_ACCEPTANCE` | `BLOCKED` |

## 1. 运行与 Git 基线

| 项 | 值 |
| --- | --- |
| 远程 | `https://github.com/lintao19568886548/kwzy-python.git` |
| 起点 main | `bc174e5` |
| Alembic head | `d0b68c3e1a42`（唯一，revises c9a57b2d0f31） |
| Python | 3.10.11 + apps/api `.venv` |
| pytest collect | 115 tests（含 skip PG 类） |
| 最近全量 | ~100 passed / 15 skipped（Workbench 前） |
| 前端目录 | 原无；`apps/web` 本迭代脚手架 |
| 旧 Java | `D:\重构python\kwzg-Java-main`（只读证据） |
| 旧 FE | Java monorepo `playground/` Vue 体系（只读） |

## 2. 域级矩阵

| domain | docs | 旧 Java 入口 | 旧 FE | 旧表 | 新模型 | Service | API | 新 FE | 迁移 | 测试 | 状态 | 策略 | 风险 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| identity | 01/02/07 | sys user/role | system/* | users/roles | Tenant/User/Role/Menu/RefreshToken | auth/user/role/menu | /auth/* /system/* | 脚手架登录 | PARTIAL | test_identity_* | PARTIAL | REDESIGN | 组织/字典/参数未做；token_version 有 |
| park_property | 01-03 | park/unit | park/* | parks/units | Park/Building/Unit | park/unit | /parks /units | 列表页骨架 | PARTIAL | test_park_unit | PARTIAL | REDESIGN | 楼栋细节、附件 |
| party | 02 party | customer | party/* | parties* | Party* | PartyService | /parties* | 骨架 | PARTIAL | test_party_* | COMPLETE(v1) | REDESIGN | PERSON 地址拒绝；ETL 未演练 |
| lease | 02 lease | contract | contract/* | lease_* | LeaseContract* | LeaseService | /leases* | 骨架 | PARTIAL | test_lease_* | COMPLETE(v1) | REDESIGN | 押金退还/复杂条款 DEFER |
| billing | 02 bill | bill | bill/* | bills* | Bill/BillLine | BillService | /bills* | 骨架 | PARTIAL | test_bill_* | COMPLETE(v1) | REDESIGN | 滞纳金/AI 出账 DEFER |
| collection | 02 payment | payment | payment/* | payments* | Payment* | PaymentService | /payments* | 骨架 | PARTIAL | test_payment_* | COMPLETE(v1 登记) | REDESIGN | 催缴案件/SMS STUB |
| workbench | 01 dashboard | dashboard | workbench | work_items | WorkItem | WorkItem+Summary | /work-items /workbench/* | 工作台页 | N/A | test_work_item_* | PARTIAL→IN_PROGRESS | INNOVATION | 定时扫描需运维调度 |
| investment | 01 招商 | investment | investment/* | leads | Lead | LeadService | /leads* | LeadsView | PARTIAL | test_lead_api | PARTIAL(v1) | REDESIGN | 雷达/企微 DEFER |
| tenant_ops | 01 工单 | workorder | ops/* | — | — | stub | stub | 无 | MISSING | 无 | STUB | REDESIGN | 需独立 change |
| analytics | 01 看板 | dashboard | analytics | — | — | stub | 未挂 main | 无 | MISSING | 无 | STUB | REDESIGN | summary 已在 workbench |
| finance | 01 财务 | finance | finance | — | — | stub | 未挂 main | 无 | MISSING | 无 | DEFER | DEFER | 与 Bill/Payment 边界需 ADR |
| ai_assist | 01 AI | agent | tools/* | — | — | stub | 未挂 main | 无 | MISSING | 无 | STUB | INNOVATION | AI 只产草稿 |
| platform/ETL | 03 db | flyway/sql | — | 全库 | mapping | tools/etl | CLI | N/A | dry-run 骨架 | 无 | NOT_READY | RETAIN 语义 | HUMAN 字段仍可能 |
| frontend | 04-fe | playground | 全站 | — | Vue3 apps/web | — | — | scaffold | N/A | 待加 | NOT_COMPLETE | REDESIGN | 禁止照搬 vben 布局 |

## 3. 旧能力分类纪律

对每项旧能力必须进入：`RETAIN | REDESIGN | ADAPTER | DEPRECATE | DEFER`。  
当前仍有大量 **未扫完** Java 包：工单、通知、审批、导入导出、报表、短信 — 本表将随 change 追加行，**禁止**用 UNKNOWN 收尾。

## 4. 语义门禁检查清单（每域）

- [x] 鉴权 fail-closed（JWT）
- [x] 租户隔离
- [x] 园区 scope 与动作权限正交
- [x] 主链状态机（Party/Lease/Bill/Payment）
- [x] 金额 Decimal
- [x] 收款幂等 + PG 并发测试（需环境）
- [x] 审计同事务（写路径）
- [ ] 全量 PII 映射证据
- [ ] FE 调用链闭合
- [ ] ETL 对账

## 5. OpenSpec change 清单（仓库内）

| change | 类型 | 状态（工作判断） |
| --- | --- | --- |
| archive/*step1* | 历史 | 已归档 |
| implement-party/lease/bill/payment | 实现 | 代码已合 main |
| implement-identity-system-admin | 实现 | 核心 API 已合；tasks 可能未全勾 |
| complete-identity-system-admin | 设计/证据 | 证据 READY_FOR_HUMAN_REVIEW，非全完成 |
| harden-auth-payment-integrity | 加固 | 已合 |
| implement-workbench-ops | 本迭代 | 进行中 |
| repair-postgres-baseline-boolean-portability | 修复 | 独立 |

## 6. 阻塞全量验收的项（按修复顺序）

1. 前端主旅程与权限闭合  
2. 招商/工单/催缴等剩余 Java 域  
3. 字段映射 + ETL dry-run/脱敏全量演练  
4. PG16 全量非 skip 测试  
5. 预发布部署验收  
6. 生产迁移/部署（人工）
