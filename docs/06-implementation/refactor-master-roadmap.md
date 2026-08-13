# 瞰维智管 V2 全量重建主路线图

> 更新时间：2026-08-13 20:09（Asia/Shanghai）
> 当前已验证基线：`main@8adcd77e782db47a466ba0759ac04ffaae488b1b`
> 总体状态：**IN_PROGRESS — 资产/租控与招商 CRM 定义纵切本地 PASS，不等于 V2 全产品完成**

## 1. 权威顺序与恢复协议

需求冲突按以下顺序裁决：真实业务与已确认产品需求 → `docs/` 证据 → 旧 Java/前端/schema/运行行为 → OpenSpec/OpenAPI/测试/当前代码 → 有记录的行业最佳实践决策。

每次上下文压缩、会话恢复或分支切换后，必须先读取本文件、`refactor-agent-state.md`、`full-rebuild-traceability-matrix.md`、`refactor-final-acceptance.md`，再核对 `git status --short --branch` 与 `git rev-parse HEAD`。禁止用旧封板摘要代替当前代码取证。

## 2. 当前真实基线

- 已有：FastAPI 模块化单体、PostgreSQL 16/Alembic、Vue 3 PC 管理端、核心身份/Party/合同/账单/收款/待办/简版工单与催缴案件，资产空间树/单元版本与租控工作台，以及招商 CRM 去重合并、公海、活动、漏斗、匹配锁房和原子转化工作台。
- 已验证 `8adcd77`：21/21 门禁，PG16 fresh upgrade/down-up、166 pytest、4 Vitest、32 Playwright、OpenAPI 4/4 + YAML strict、OpenSpec 38/38、core/Identity/Asset/CRM 合成 ETL、52 表恢复、545 文件 secrets scan 均通过。
- 未拥有：员工移动端、租户微信小程序、集团层与 GIS/CAD/BIM 地图、CRM 真实外部获客/企微自动触达/意向审批/AI 评分、合同变更链、自动计费/到账匹配、设备巡检/IoT、完整经营驾驶舱、HR/供应链、真实 AI 业务能力和生产外部联调。
- 迁移现状：资产与 CRM 合成数据已证明首次导入、幂等重放、分布/数量/面积/血缘/PII 隔离对账和回滚；仍未获得旧生产库授权，也未完成脱敏真实快照演练。

## 3. 纵切路线

| 阶段 | 交付边界 | 当前状态 | 退出门禁 |
| --- | --- | --- | --- |
| 0 | 全仓审计、证据矩阵、设计系统、平台底座 | **IN_PROGRESS** | 四份总控文档一致；历史 PASS 限定范围；新缺口进入 OpenSpec |
| 1 | 资产与租控 | **LOCAL_ACCEPTANCE_PASS** | 本次 OpenSpec 范围已闭合；集团/GIS/CAD/BIM、真实旧数据和更深经营分析继续由后续纵切关闭 |
| 2 | 招商 CRM | **LOCAL_ACCEPTANCE_PASS** | 本次 OpenSpec 的去重合并、分配/公海、活动状态机、漏斗、匹配锁房并发与原子转化已闭合；真实渠道/审批/AI/旧数据继续由后续纵切关闭 |
| 3 | Party、租户与合同 | **PARTIAL** | 多单元、多费用规则、变更单/补充协议版本链、审批/退租结算 |
| 4 | 账单、收款、核销与催缴 | **PARTIAL** | 自动出账、银行/支付流水、待匹配池、多账单核销、分级催缴与复核 |
| 5 | 租户服务、工单与供应链 | **PARTIAL** | 多入口、派单/SLA/验收/返工、报价、材料工时、供应商库存 |
| 6 | 设备、巡检、安防与 IoT | **NOT_STARTED** | 设备台账、每周巡检、告警聚合升级、厂商适配器与模拟器 |
| 7 | 驾驶舱与多角色工作台 | **PARTIAL** | 统一指标口径、角色工作台、待办优先级/升级/复核、逐级下钻 |
| 8 | 员工移动端与租户小程序 | **NOT_STARTED** | 两端真实 API、权限、关键旅程、响应式/离线/错误状态 E2E |
| 9 | AI 与外部集成 | **STUB_OR_ADAPTER_ONLY** | AI 可审计/可降级；无凭据适配器明确 `NOT_LIVE`；契约测试 |
| 10 | 旧系统替代、迁移、全链路验收 | **BLOCKED_BY_PRIOR_PHASES** | 能力处置闭合、脱敏数据演练、性能安全运维证据、P0/P1=0 |

## 4. 当前执行队列

1. 资产代码、精确 SHA 验收证据已非强推送；`implement-asset-rent-control-v2` 已同步主规格并归档为 `2026-08-13-implement-asset-rent-control-v2`。
2. 招商 CRM 实现提交 `8adcd77` 已在 clean SHA 上 21/21 验收；8 份 delta 已同步主规格并归档为 `2026-08-13-implement-investment-crm-v2`。
3. `complete-identity-system-admin` 保持 active，等待人工提供经授权的只读旧 schema dump 与密码哈希样本；这不阻塞后续非生产研发，但阻止 Identity 迁移 readiness 变为 READY。
4. 阶段 3 已完成基础 Lease 规格同步归档与 `implement-contract-lifecycle-v2` 规划（4/4 工件、3/102 任务、strict PASS）；当前进入 schema/version、费用计划、审批文档、变更占用、退租结算和查询 API 实施。
5. CRM 归档及合同规划检查点暂留本地；向 GitHub 继续非强推送需用户明确确认该仓库的数据外发授权。
6. 之后依次执行阶段 4–10；每个纵切必须同时交付模型、迁移、服务、API、适用终端 UI、测试、OpenAPI、迁移映射和运行手册。

## 5. 每个纵切的固定循环

证据取证 → 更新矩阵 → OpenSpec/设计 → strict validate → domain/application/infrastructure/interface → Alembic → 真实 UI → unit/repository/API/contract/E2E → SQLite/PG16 → 权限/跨租户/并发/幂等/异常 → 截图与响应式 → stub/TODO/未挂载扫描 → 文档/映射/runbook → P0/P1 清零 → 安全提交并推送。

## 6. 永久门禁

- 不连接或修改旧 Java 生产库；不执行生产部署/生产迁移；不做不可逆数据操作。
- 不 force push，不覆盖用户未提交修改，不删除历史迁移。
- 生产凭据缺失时只能交付 fail-closed adapter、sandbox/mock 和契约测试，并标记 `NOT_LIVE`。
- 只有三端、全业务闭环、旧能力处置、真实脱敏迁移演练、安全/性能/E2E/运维证据全部成立时，才允许 `KWZY_FULL_REBUILD_ACCEPTANCE=PASS`。
