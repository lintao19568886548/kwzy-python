# 瞰维智管 V2 全系统重建追踪矩阵

> 更新时间：2026-08-13 19:50（Asia/Shanghai）
> 被测代码：`8adcd77e782db47a466ba0759ac04ffaae488b1b`；报告 `acceptance_20260813_195020.json`，21/21 PASS
> 结论：**资产/租控与招商 CRM 本次定义纵切本地 PASS；V2 全产品仍为 BLOCKED。**

## 1. 状态定义

| 状态 | 含义 |
| --- | --- |
| `IMPLEMENTED` | 模型/API/UI/测试在当前定义范围内闭环 |
| `PARTIAL` | 有真实实现，但未覆盖本提示确认的完整业务范围 |
| `ADAPTER_NOT_LIVE` | 有 fail-closed/mock/sandbox 适配和测试，无真实生产联调 |
| `STUB_UNMOUNTED` | 代码目录存在静态返回/stub，且未挂主路由；不计能力 |
| `NOT_STARTED` | 无可用实现 |
| `BLOCKED_EXTERNAL` | 仅因凭据、脱敏数据、预发/生产授权等人工门禁阻塞 |

## 2. 证据基线

| 维度 | 当前证据 | 解释 |
| --- | --- | --- |
| 旧系统规模 | `docs/01-old-system-analysis`：约 482 HTTP 映射、316 Vue 文件 | 仅作业务取证，不照搬页面/代码 |
| Python API | 运行时 OpenAPI 与 YAML 严格契约 4/4 PASS；CRM V2 20 个路径方法有精确约束 | 只覆盖当前挂载模块 |
| PC | `apps/web`：13 个鉴权业务页面，另有 login/forbidden | 租控与 CRM 工作台已重建；仍没有用户要求的全产品导航和多角色工作台 |
| 员工移动端 | 不存在 `apps/employee-mobile` | `NOT_STARTED` |
| 租户小程序 | 不存在 `apps/tenant-miniprogram` | `NOT_STARTED` |
| 数据库 | PostgreSQL 16；Alembic 唯一 head `j6e24f9a1c08` | fresh upgrade + down/up 已验证 |
| 自动化 | 166 pytest、4 Vitest、32 Playwright、38 OpenSpec strict，545 文件 secrets scan | 证明当前已实现范围，不外推为全产品完成 |
| 迁移 | core fixture fast/acceptance + Identity + Asset + CRM 独立 schema dry/apply/idempotency/reconcile/rollback | 无旧生产连接，无真实脱敏快照对账 |

## 3. 产品端追踪

| 端 | 需求 | 当前实现 | 状态 | 关闭条件 |
| --- | --- | --- | --- | --- |
| PC 管理后台 | 多角色工作台、完整业务、设计系统、全状态 | Vue 3 核心表单/列表、租控矩阵/详情、招商 CRM 工作台与 32 条主链 E2E | `PARTIAL` | 全模块真实 API、角色台、完整下钻、响应式/无障碍/截图验收 |
| 员工移动端 | 待办/审批/巡检/维修/招商/财务/安防/AI | 无独立应用 | `NOT_STARTED` | 应用、鉴权、真实 API、设备能力降级、关键 E2E |
| 租户微信小程序 | 合同账单缴费、服务、访客停车、能耗、预约 | 无独立应用 | `NOT_STARTED` | 小程序原生关键链路、租户管理员权限、沙箱支付、E2E |
| 原生 App | 后续扩展 | 无 | `DEFERRED_APPROVED_BY_SCOPE` | 不阻塞当前 V2，但须保留 API/BFF 兼容 |

## 4. 业务能力矩阵

| 需求 ID | 领域/旅程 | 当前证据 | 当前缺口 | 状态 | 策略 |
| --- | --- | --- | --- | --- | --- |
| V2-PLAT-001 | 组织/RBAC/园区数据权限/审计 | access 即时吊销、refresh cookie/轮换/重放、限流/安全事件、page-access proof、用户/角色/菜单/园区授权 UI/API/E2E、audit_logs | 岗位、字段权限、完整审批流、租户生命周期、审计中心 UI、旧长尾接口 | `PARTIAL` | REDESIGN |
| V2-WB-001 | 角色工作台与自动待办 | WorkItem CRUD、bill/lease 联动、summary、PC/E2E | 角色组件配置、优先级规则、改派/复核/升级/重开全时间线、更多事件源 | `PARTIAL` | INNOVATION |
| V2-ASSET-001 | 集团→空间层级与多业态出租单元 | Park→AREA/BUILDING/FLOOR 树；同园区/类型/编码/循环/依赖保护；current-only 单元版本、乐观锁、拆并血缘、PG 并发/API/UI/E2E | 集团实体、行业模板、GIS/CAD/BIM 几何与批量导入；真实旧资产数据演练 | `PARTIAL` | REDESIGN |
| V2-RENTCTRL-001 | 租控矩阵/地图/列表/分析/下钻 | 服务端一致过滤与面积/出租率口径；矩阵/列表/筛选；Lease/Party、版本、血缘、工单详情；权限/异常/响应式 E2E | 地图视图、组合级经营分析、账单/定价/空置核验的完整下钻 | `PARTIAL` | INNOVATION |
| V2-CRM-001 | 多渠道线索与客户画像 | 规范化手机号/名称/来源去重、授权覆盖、合并血缘、来源唯一性；分配/改派/公海认领释放/超时回收；活动/业主/园区权限隔离，API/PC/PG/E2E | 真实渠道接入、企微回调/自动触达、复杂标签画像、真实旧数据迁移 | `PARTIAL` | REDESIGN |
| V2-CRM-002 | 招商过程与锁房 | NEW→CONTACTING→VISITING→QUOTING→NEGOTIATING→WON/LOST 状态机；可解释房源匹配、限时锁房/续锁/释放、并发唯一获胜、Lease 激活互斥、Lead→Party/Lease 原子转化 | 意向审批/电子签署衔接、AI 评分/推荐、真实并发容量与预发验证 | `PARTIAL` | REDESIGN |
| V2-PARTY-001 | 企业/个人统一 Party | 主档、联系人、地址、角色、园区关系、风险事件 | 企业画像、关联企业、受控证件 PII/KMS 能力 | `PARTIAL` | REDESIGN |
| V2-LEASE-001 | 多单元、多费用合同 | Lease CRUD/状态机/占用，基础 Bill 分离 | 多单元与复杂计费、模板/签章/印章/档案、履约计划 | `PARTIAL` | REDESIGN |
| V2-LEASE-002 | 续租/扩减租/调价/主体变更/退租版本链 | 只有合同状态变更 | 变更单、补充协议、不可覆盖历史、退租结算/违约/AI 审查 | `NOT_STARTED` | REDESIGN |
| V2-BILL-001 | 合同/抄表/临时费用自动出账 | Bill/line create/issue/void/discard | 计费计划、递增/免租/抽成、抄表、调账、批量导入治理 | `PARTIAL` | REDESIGN |
| V2-PAY-001 | 多渠道到账、匹配与核销 | Payment + allocation/reverse/idempotency/PG concurrency | 银行流水、支付回调、待匹配池、多账单/预收/多付/争议复核 | `PARTIAL` | REDESIGN |
| V2-COLLECT-001 | 分级催缴与审批 | CollectionCase 基础 CRUD；generic fake SMS/outbox | 自动分级、策略/话术、记录时间线、page-access proof、减免延期坏账争议审批 | `PARTIAL` | REDESIGN |
| V2-WO-001 | 租户服务与工单 | WorkOrder create/start/complete/cancel、PC/E2E | 多入口、自动派单、SLA/催办/转派/暂停/返工/重开、报价/材料/工时/评价/验收 | `PARTIAL` | REDESIGN |
| V2-SUPPLY-001 | 供应商/采购/物料/库存/外包 | 无 | 全能力 | `NOT_STARTED` | NEW |
| V2-IOT-001 | 设备台账、巡检、安防、统一 IoT | 无挂载业务模块 | 设备/适配器、告警分级去重聚合、任务/工单、恢复时间线 | `NOT_STARTED` | NEW |
| V2-INSPECT-001 | 消防/电梯/变压器每周巡检 | 无 | 周期任务、现场扫码、异常转工单、复核关闭 | `NOT_STARTED` | NEW |
| V2-DASH-001 | 经营驾驶舱与指标下钻 | Workbench 五项摘要；`analytics` 是未挂载空响应 | 指标口径、同比环比预算、多维筛选、趋势/明细/原单下钻、深色大屏 | `PARTIAL` | REDESIGN |
| V2-HR-001 | 人事/排班/考勤/绩效/资质 | 无 | 全能力 | `NOT_STARTED` | NEW |
| V2-TENANT-SVC-001 | 政策、活动、公告、企业服务、资源预约 | 无 | 全能力 | `NOT_STARTED` | NEW |
| V2-AI-001 | 问数/招商/合同/票据/工单/知识库 AI | `ai_assist` 为未挂载明确 stub | 可审计 AI 网关、证据、确认门禁、脱敏、非 AI 降级 | `STUB_UNMOUNTED` | REDESIGN |
| V2-INT-001 | 短信/通知/对象存储等适配 | fake SMS/notify、local storage、outbox；生产 fail-closed | 真实供应商、重试调度、回调验签、全契约/联调 | `ADAPTER_NOT_LIVE` | ADAPTER |
| V2-INT-002 | 银行/支付/发票/税务/签章/OCR/IoT/协作平台 | 无或未挂载占位 | 标准端口、沙箱/模拟器、契约测试、真实凭据联调 | `NOT_STARTED` | ADAPTER |

## 5. 旧 Java 能力处置总表

| 能力组 | 当前处置 | 证据/说明 |
| --- | --- | --- |
| Auth/RBAC/Park/Asset/Party/Lease/Bill/Payment | `PARTIALLY_REPLACED` | Python 已有安全会话、空间树和单元版本/拆并等核心模型，但旧系统长尾语义与真实数据迁移未全覆盖 |
| Workbench/Investment/Work orders/Collection | `PARTIALLY_REPLACED` | Investment 本次 CRM 定义范围已闭环；Workbench/工单/催缴仍只有窄主链，且旧长尾与真实数据未闭合 |
| Organization onboarding/menu/dept/region | `PARTIAL` | system admin 有部分能力，SaaS 开通与完整组织治理缺失 |
| Bill import/AI recognize/finance verify | `NOT_REPLACED` | stub/未挂载/缺工作流 |
| Access/visitor/vehicle/parking | `NOT_REPLACED` | 无实现 |
| Maintenance/inspection/equipment/IoT/metering | `NOT_REPLACED` | 无实现 |
| HRM/payroll/reimbursement | `NOT_REPLACED` | 无实现 |
| CRM/radar/wework/public acquisition | `PARTIALLY_REPLACED` | CRM 内部生命周期、公海、活动、锁房与转化已实现；radar/企微/公域获客和自动触达未替代 |
| Notices/policy/tenant service/activity/reservation | `NOT_REPLACED` | 无实现 |
| 生产外部集成 | `BLOCKED_EXTERNAL` | 缺凭据/厂商资料；不得伪造 LIVE |

任何旧能力只有在 `REPLACED`、`APPROVED_RETIRE` 或有人工依据的 `APPROVED_DEFER` 时才可关闭。目前 `KWZY_LEGACY_CAPABILITY_CLOSURE=BLOCKED`。

## 6. 数据迁移追踪

| 项 | 当前状态 | 证据 | 关闭条件 |
| --- | --- | --- | --- |
| 表级映射 | `DRAFT_CORE_ASSET_CRM` | `tools/etl/mapping/table_map.v1.yaml`、资产映射、CRM 旧接口处置与字段映射 | 覆盖全部旧表并逐项处置 |
| 字段级映射 | `DRAFT_CORE_ASSET_CRM` | core 字段映射 + 资产节点/单元/血缘 + CRM stage/source/owner/PII 映射 | 取得真实旧 schema 后闭合转换/枚举/PII/无法映射清单并签字 |
| 幂等/checkpoint/中断恢复 | `FIXTURE_PASS` | core fast/acceptance + Identity + Asset + CRM isolated-schema drill | 脱敏真实快照复演 |
| 数量/金额/面积对账 | `FIXTURE_PASS` | Asset 4 nodes/4 units/2 lineages；CRM 5 leads/4 activities/4 assignments/1 merge/1 PII quarantine，零孤儿/重复且原始 PII 未落库 | 真实合同/面积/押金/应收/实收及 CRM 分布对账 |
| 回滚 | `LOCAL_SCHEMA_AND_BACKUP_PASS` | Identity/Asset/CRM schema rollback + 52-table backup restore | 预发 Runbook 与时间窗演练 |
| 增量同步/切换 | `NOT_STARTED` | — | CDC/增量策略、停写窗口、回切决策 |

结论：`KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_FIXTURE_ONLY`。

## 7. 当前验收标识

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
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL
```
