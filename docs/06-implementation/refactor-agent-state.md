# 瞰维智管 V2 自治重建状态

> 本文件是会话恢复入口；恢复工作时必须同时核对 Git，不得只信本文缓存。

| 字段 | 当前值 |
| --- | --- |
| 更新时间 | 2026-08-15（Asia/Shanghai） |
| 仓库 | `D:\重构python\kwzy-python` |
| 分支 | `feat/full-rebuild-completion`（从 repair `37d7cf7da768eef8d7bcc743635117b8f34c7bbb` 创建） |
| 已验证 HEAD | `b04d738bc75e865e1c6bfb180e93dc9b95109cf3`：档案/签章/印章 36/36 精确提交全验收，366 后端、61 浏览器、前端四门禁、OpenAPI/OpenSpec、1000/25 性能、备份恢复和合成迁移通过 |
| 远程同步 | 实现、修复与初版证据至 `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` 已正常推送到 `origin/feat/full-rebuild-completion`；未 force、未触达 main |
| 工作树 | 本轮档案证据、总控文档和 OpenSpec 收尾待提交；24 张其他纵切被全量 Playwright 重生成的视觉证据保持未暂存，不得删除、还原或混入本轮提交 |
| Alembic | 唯一 head `b4ea2c7d8f86`；PG16 fresh head、`current == heads`、`b4→a3→b4`、146 表备份删除恢复通过；既有已应用 `a3d91f6a7b75` 未修改，硬化使用前向 `b4` |
| 当前阶段 | 独立验收为 11 implemented / 1 blocked / 8 missing；组合能力 1–10、13 已关闭本地产品范围，完整项目仍 `CONDITIONAL/BLOCKED` |
| 当前 OpenSpec | 档案/签章/印章 41/41，11 份 delta 待本轮证据提交后同步归档；精确实现 strict 102/102。CRM `revoked` 语义冲突仍保持 active |
| 生产部署/迁移 | `NOT_EXECUTED`，保持人工授权门禁 |

## 本轮已完成

- [x] 独立取证蓝图、旧 Java/前端/DDL 与现有附件/合同文档，确认旧证据没有可证明的档案、印章或合法电子签聚合，未把旧按钮和 fake `SIGNED` 当业务事实。
- [x] 新增 `a3d91f6a7b75` 与前向硬化 `b4ea2c7d8f86`，完成 16 张档案/保全/借阅/处置/印章/签章表、复合租户/园区外键和唯一/检查/索引约束；已应用 a3 未被修改。
- [x] 完成版本化分类与保管、确定性档号、附件版本/服务端哈希/完整性 hold、法律保全、借阅、处置双人确认，以及印章台账/保管/状态历史/精确版本用印。
- [x] 完成无密钥提供方真相、信封/参与人/事件、授权重放安全沙箱投递和 live fail-closed；Lease 沙箱不再伪造法律 `SIGNED`。
- [x] 关闭高风险用印申请/最终审批/执行职责分离、执行命令指纹幂等、档案 E2E 多目标定位、Party 保存成功就绪竞态和 390px 页签/表格截断五类 P1，并加入 API/PG/浏览器防回归。
- [x] 重建 PC 档案/签章/印章工作区，覆盖桌面、平板、390px、权限/冲突/离线/重试；三张截图逐张人工复核。
- [x] 精确 `b04d738` 全门禁 36/36：PG16 fresh/down-up/唯一 head，366 pytest，61 Playwright，前端 lint/typecheck/6 Vitest/build，15 OpenAPI+YAML strict，102 OpenSpec，21/21 真实 HTTP，1000/25 p95 240.541 ms/146.259 RPS/0 错误，1,595,978 bytes/146 表备份恢复，1,041 文件 secrets scan；合成 ETL 为 2 分类/2 档案/2 版本/2 隔离且无伪造印章、提供方或事件。

- [x] 独立取证旧消防/电梯/变压器/厂务设备 CRUD 和现仓缺口，明确物理删除、自由字符串、匿名默认租户及“界面有 IoT 不等于真实接入”的风险边界。
- [x] 新增 `z2c80e5f6a64` 单一前向迁移与 16 张设施表，完成受控设备台账/历史/退役依赖保护、不可变模板版本、周计划和确定性任务。
- [x] 完成类型化巡检提交、异常证据、漏检升级、稳定 WorkItem/WorkOrder，以及提供方真相、无密钥引用、绑定历史、严格授权事件摄入、告警关联/分级/处置/升级。
- [x] 重建 PC 设施运营工作区，覆盖桌面巡检异常转工单、IoT 告警来源/关联/工单和 390px 离线保留/重试；三张截图逐张人工复核。
- [x] 真实浏览器发现并修复执行角色被错误要求 `inspection:read`、ACK 刷新清空必填解决原因两项 P1；API/PG 同时覆盖租户/园区/子资源 IDOR、参数污染、事件精确重放和并发冲突。
- [x] 精确 `e28678b` 全门禁 35/35：PG16 fresh/down-up/唯一 head，352 pytest，60 Playwright，前端 lint/typecheck/6 Vitest/build，14 OpenAPI+YAML strict，94 OpenSpec，1000/25 p95 320.076 ms/135.6 RPS/0 错误，1,495,479 bytes/130 表备份恢复，982 文件 secrets scan；设施合成 ETL 为 4 设备/4 历史/1 隔离且无伪造 IoT 交付。

- [x] 独立取证旧 `repair_order`、MaintenanceController/Repository 和旧前端流程，确认旧后端仅 CRUD、没有可证明的派单/报价/验收通知实现，未把旧 UI 按钮当成后端事实。
- [x] 新增 `x0a68c3d5e42` 与前向硬化 `y1b79d4e6f53`，完成 WorkOrder 聚合、Party 服务主体、规则/事件/报价/成本/验收/评价模型及复合租户/园区外键。
- [x] 完成员工代受理与租户自助受理、不可变派单规则草稿/发布/显式退役、确定性自动派单、人工改派、SLA 幂等升级、版本报价/决定、追加式成本/冲正、完工证据、返工/验收与一次评价。
- [x] 修复跨 Party 幂等键预查、同键异报价/验收命令、伪造 JWT 权限、重复 query、未知字段和子资源 IDOR；新增 PG 并发验收后发现并修复 ACCEPTED/REWORK 双提交锁顺序缺陷。
- [x] 重建 PC 工单/租户服务工作区，覆盖员工与租户角色、桌面报价抽屉、390px 验收评价、离线保留/重试和无横向溢出；三张截图人工复核通过。
- [x] 合成 `repair_order` ETL 完成 dry/interruption/apply/reapply/reconcile/rollback，3 工单/6 事件/1 隔离精确对账，原始 PII、伪造报价/评价/外送均为 0；真实旧库保持外部阻塞。
- [x] 精确 `ffa72e2` 全门禁 33/33：PG16 fresh/down-up/唯一 head，342 pytest，59 Playwright，前端 lint/typecheck/6 Vitest/build，13 OpenAPI+YAML strict，86 OpenSpec，1000/25 p95 302.333 ms/132.87 RPS/0 错误，1,383,498 bytes/114 表备份恢复，942 文件 secrets scan。

- [x] 独立取证旧账单/流水/核销/催缴与当前基础实现，发布财务字段映射、外部渠道真相和真实旧数据阻塞边界。
- [x] 完成履约计划出账、到账单箱、确定性匹配候选、财务确认/异常、经理争议、多账单/预收后续核销、追加式冲正、L1-L4 催缴和调整双人审批。
- [x] 新增 `u7d35f0a2b19`、`v8e46a1b3c20`、`w9f57b2c4d31` 前向迁移；w9 的 16 个复合租户外键、21 项数据库约束和资金竞态回归通过。
- [x] 关闭外租户园区导入、重复查询参数污染和 Application 直接构造 ORM 三项 P1；加入服务/数据库/中间件/架构防回归。
- [x] 完成应收 PC 出账、到账、分配和催缴工作区；真实 PG/FastAPI/production Vite 的 2 条 Playwright 及桌面/平板/390×844 四张截图通过。
- [x] 精确 `1a11cfe` 全量 335 pytest、前端 lint/typecheck/6 Vitest/141 modules build、2 条真实浏览器和 OpenAPI 通过；OpenSpec/secrets/依赖门禁在证据归档前后复核。
- [x] 精确 SHA 真实 HTTP 1000/25 为 p95 352.701 ms、107.841 RPS、0 错误；API 重启前后 5/5/5 签名一致；PG dump/删除恢复签名精确一致。
- [x] clean-SHA 前保留 p95 6756.641（DEBUG 日志放大）和 1896.077 ms（计划冲突/Payment 余额 N+1）失败链；强制 `DEBUG=false`、批量查询和 SQL 查询数回归后在累积库通过，500 ms 门槛未降低。
- [x] 将 390px 到账表格重排为字段完整的卡片列表，E2E 同时断言 table/body 无横向溢出；金额、掩码账号、渠道、状态和复核操作不再截断。
- [x] 应收 synthetic ETL dry/interruption/apply/reapply/reconcile/rollback 通过；金额 1500.00 精确对账，真实旧 schema/脱敏快照仍保持 BLOCKED。
- [x] 应收 45/45 OpenSpec 任务完成，8 份 delta 同步主规格并归档；归档后 strict 85/85、归档暂存树 915 文件 secrets scan 0 hits，综合机器证据为 `evidence/receivables-collection-lifecycle/acceptance-clean-1a11cfe.json`。

- [x] 独立取证旧 rental tenant、Radar 企业画像和当前 Party 边界，发布字段映射与旧接口替代/保留/阻塞处置；个人身份材料、真实工商提供商和旧数据不被伪造为完成。
- [x] 新增 `t6c24e9f1a08` 单一前向迁移、纯领域企业规则、租户安全仓储、严格 API/OpenAPI 与数据库派生的受控证件/风险权限。
- [x] 完成组织企业画像与精确完整度、关联企业规范化/无环历史、证件原文 SHA-256 指纹化、来源标签、追加式风险/处置和目录筛选。
- [x] 将 Party PC 重建为真实目录与响应式详情抽屉；桌面执行画像/关系/标签/风险/证件真操作及 409 保留，平板证明字段权限不取数，手机证明离线/重试且无横向溢出。
- [x] 完成 21 阶段真实 HTTP、PG 画像/关系/标签/风险并发、跨园区/租户附件与子资源 IDOR、伪造 JWT 权限和证件原文不落响应/审计/数据库的回归。
- [x] 完成 Party synthetic ETL dry/interruption/apply/reapply/reconcile/rollback；个人身份与孤儿关系隔离，真实 schema/脱敏快照继续 BLOCKED。
- [x] 精确 `3680582` clean-SHA 总门禁 31/31：PG16/Alembic、315 后端、8 租户 worker、全套 ETL、真实 HTTP、1000 请求性能、备份恢复、前端、57 浏览器、11 OpenAPI、71 当时 OpenSpec、856 文件 secrets 全通过。
- [x] 保留首轮 clean-SHA p95 535.126 ms 失败链，定位目录 N+1；批量化园区/风险查询并加查询数回归后，同一 1000/25 门槛 p95 225.85 ms、172.617 RPS、0 错误。

- [x] 独立复核旧 factory/floor/dormitory/rental manage 证据，明确统一可租单元替代与设施、商业 GIS/CAD/BIM、真实数据阻塞边界。
- [x] 完成七类租户业态模板、受限字段语法、草稿/发布/新草稿/停用、不可变版本及数据库派生独立权限。
- [x] 单元创建/结构版本/拆分/合并保留精确模板版本，空间 Point/Polygon/CRS 以乐观锁更新且不伪造外部底图。
- [x] 完成矩阵、真实几何示意地图、列表、空置、到期和经营分析；挂牌潜力明确标注为非会计收入。
- [x] 完成 `q3f91b6c8d75` 功能迁移及后续 `r4a02c7d9e86` 租户复合外键修复迁移、PG 并发/数据库越权拒绝、OpenAPI、22 阶段真实 HTTP、52 浏览器与三张人工复核截图。
- [x] 提交前硬化关闭跨租户模板引用、模板/业态错配、空白草稿名、自交/退化多边形、维修/锁定单元误计空置；286 后端测试与全仓 Ruff 错误级规则通过。
- [x] 完成资产组合 synthetic ETL 的 dry/interruption/apply/reapply/reconcile/rollback；真实旧 schema/脱敏样本仍保持 BLOCKED。
- [x] 修复验收脚本的 PostgreSQL `.env` 读取、Alembic unique current head 硬断言、失败子命令输出保留及 UTF-8 运维日志。

- [x] 独立取证旧 workspace/outbox/consume-log/站内通知/调度任务和当前 Python 缺口，发布替代/保留/阻塞处置与切换 Runbook。
- [x] 新增业务事件/消费者、规则/不可变版本/执行、通知、调度定义/运行、工作台布局/组件 ORM，以及唯一前向迁移 `p2e80a5b7c64`。
- [x] 完成事务事件发布、PG `SKIP LOCKED` claim、有限退避、DEAD/代次 replay、受限规则动作、通知隔离、持久调度恢复和独立多租户 worker。
- [x] 完成 WorkItem 深链/乐观锁/来源所有权/升级改派，以及用户→角色→服务器默认布局和数据库派生权限不放大。
- [x] 重建 PC 实时工作台、消息中心和自动化控制面，覆盖规则草稿/发布/退役、调度、事件/死信、执行记录、个人/角色布局。
- [x] 工作树总门禁 28/28：PG16/Alembic、277 后端、真实 HTTP、1000 请求性能、备份恢复、前端、50 浏览器、OpenAPI/OpenSpec/secrets 全通过。
- [x] 浏览器控制技能独立检查管理员桌面与手机布局：无 body 横向溢出、无 console warning/error；三张 Playwright 截图已固化。
- [x] 性能整改保留失败链：先发现 p95 946.484 ms 与脚本退出码覆盖，再由硬化脚本真实阻断 p95 729.289 ms；查询合并和 `DEBUG=false` 后同门槛 p95 242.193 ms。

- [x] 独立取证旧报销、请假、触达模板、菜单待办和 `api_log`，明确平台替代与领域/真实迁移边界。
- [x] 新增定义/不可变版本/节点/审批人/申请扩展/任务/委托/事件/租户审计链头 ORM 与唯一前向 Alembic revision。
- [x] 完成 ANY/阈值 ALL、多步、退回/驳回/撤回/重提、自审批特批、幂等/乐观锁、有效期委托、SLA 升级和 WorkItem 投影。
- [x] 完成递归脱敏、链头锁、确定性 SHA-256、独立校验、租户/园区查询和公式安全受权 CSV 导出。
- [x] 重建 PC 审批审计中心五区；真实浏览器覆盖委托决定、409 保持、403 伪造权限、平板只读、移动 503/重试和截图人工复核。
- [x] 完成 13 阶段独立真实 HTTP 旅程及合成 ETL dry/interruption/apply/reapply/reconcile/rollback。
- [x] 真实 HTTP 在降升级后发现 `APPROVAL_TASK` 孤儿投影撞唯一键；修复新迁移的投影清理后，同一路径通过。

- [x] 从 repair 精确 SHA `37d7cf7` 建立 `feat/full-rebuild-completion`，并保留 local main、origin/main、repair 三条 safety ref。
- [x] 独立复核 repair 验收报告、20 项能力、22 条旅程与旧 Java/PC/SQL 原始证据，不把历史 PASS 当作全量完成。
- [x] 读取 `complete-identity-system-admin` 全部上下文，确认 51/53；授权 schema dump 与密码样本是事实外部阻塞。
- [x] 创建 `complete-platform-organization-governance` 的 proposal、design、6 份 specs 和 27 项任务，strict PASS 并进入 apply。
- [x] 记录旧 organization/region/dept/park/role/position/字段策略证据和处置，未把组织开通或真实迁移误计为完成。
- [x] 完成集团/区域生命周期、园区有效期归属历史、岗位任职和服务端字段投影；任职不隐式授予 RBAC 或园区范围。
- [x] 完成 PC 组织治理工作区及桌面/平板/移动端加载、只读、403、409、503/重试和无横向溢出验收，三张截图已留存。
- [x] 完成 PostgreSQL 16 约束/并发与组织治理合成 ETL 的 dry/apply/幂等/对账/回滚，真实旧 schema/脱敏样本仍保持外部门禁。
- [x] 正常提交并推送 `8bb8770 feat: complete platform organization governance`，未 force；在该 clean SHA 上再次运行 25 项总验收，25/25 exit 0。
- [x] 将组织治理六份 delta 智能合并到主规格并归档；归档后 OpenSpec strict 53/53 PASS。

- [x] 读取用户全量 V2 目标和四份既有总控文档。
- [x] 核对 Git：发现旧验收绑定 `23fa781`，当前代码已推进到 `d9c0b0b`。
- [x] 读取 `implement-workbench-ops` 的 proposal/spec/design/tasks，确认 6/9 中两项其实是 non-goals。
- [x] 读取旧系统分析、领域设计、工程规范并盘点当前 API/UI/迁移/测试入口。
- [x] 发现并修复验收脚本会误杀无关 8000 端口的安全问题。
- [x] 将宽松的“允许 422/404/403”外部适配 E2E 改为真实 fake SMS 200 + outbox 断言。
- [x] 提交并推送 `d9c0b0b test: harden local acceptance boundaries`。
- [x] 在干净 `d9c0b0b` 复跑本地全量验收，18/18 步骤 exit 0。
- [x] 同步并归档 `implement-workbench-ops`、`implement-party-master`，主规格 strict 校验通过。
- [x] 加固 access/refresh 会话、登录限流、安全事件、HttpOnly refresh cookie、页面二次验证和生产短信 fail-closed。
- [x] 完成用户/角色/菜单/园区授权的事务审计、跨租户校验、会话吊销和 PC 管理体验。
- [x] 发布 74 条旧 Identity 接口处置表与字段映射，禁止把未替代长尾接口记为完成。
- [x] 完成合成 Identity 用户/角色/菜单/授权关系的 dry-run、首次 apply、幂等复跑、对账与 rollback 演练。
- [x] 提交并推送 `0c8d5c5 feat: harden identity and system administration`。
- [x] 在 clean `0c8d5c5` 上复跑包含 Identity ETL 的 19 项全量门禁，19/19 exit 0。
- [x] 完成 Park→AREA/BUILDING/FLOOR 空间树及同园区、父子类型、同级编码、循环和依赖保护。
- [x] 完成出租单元 current-only 版本链、乐观锁、结构版本、拆分/合并、血缘与 Lease 占用并发串行化。
- [x] 完成租控摘要、矩阵/列表、详情下钻及 PC 空间/单元管理工作台，并完成真实浏览器视觉检查。
- [x] 完成资产字段映射、旧接口处置和独立 schema 合成 ETL 的 dry/apply/idempotency/reconcile/rollback。
- [x] 提交 `b25eb07 feat: implement asset rent control v2`，并在该 clean SHA 上复跑 20 项全量门禁，20/20 exit 0。
- [x] 将资产代码与 `6d104f4` 验收证据非强推送到 `origin/main`。
- [x] 同步 21 条资产/租控增量要求到主规格并归档 `2026-08-13-implement-asset-rent-control-v2`；归档后 OpenSpec strict 37/37 PASS。
- [x] 同步并归档已落地的基础 `implement-investment-leads` 规格，消除与 CRM V2 的增量冲突。
- [x] 完成 CRM V2 proposal/design、8 份 delta specs 和 67 项任务；change strict PASS。
- [x] 发布旧 investment/CRM/radar 能力处置与字段/枚举/PII 映射，外部雷达/企微/触达继续 NOT_LIVE/BLOCKED。
- [x] 完成 CRM V2 线索规范化去重/授权覆盖/合并、丰富状态机、活动时间线、分配/改派/公海认领释放/超时回收、权限隔离与审计。
- [x] 完成可解释房源匹配、限时锁房/续锁/释放、并发唯一获胜、Lease 激活互斥及 Lead→Party/Lease 原子幂等转化与失败回滚。
- [x] 重建 PC 招商工作台并完成桌面/平板、键盘焦点、只读/403/409/503 恢复、管理分配/合并等 6 条 CRM E2E；修复共享平板导航和系统管理异步成功提示竞态。
- [x] 完成独立 PostgreSQL CRM 合成 ETL：dry/apply/idempotent/reconcile/rollback，5 leads/4 activities/4 assignments/1 merge/1 PII quarantine，原始 PII 未落库。
- [x] 提交 `8adcd77 feat: implement investment crm v2`，并在该 clean SHA 上完成 21 项全量门禁，21/21 exit 0。
- [x] 将 CRM 8 份 delta 同步主规格并归档 `2026-08-13-implement-investment-crm-v2`；归档后 OpenSpec strict 44/44 PASS。
- [x] 将已落地基础合同 5 份 delta 同步主规格并归档 `2026-08-13-implement-lease-contract`，消除合同 V2 增量基线缺口。
- [x] 完成 `implement-contract-lifecycle-v2` proposal/design、10 份 delta specs 和 102 项任务；change strict 与全量 OpenSpec 49/49 PASS。

## 最新机器证据（档案/签章/印章精确 SHA）

版本化报告 `docs/06-implementation/evidence/records-signature-seal-governance/acceptance-clean-b04d738.json` 精确对应 `b04d738bc75e865e1c6bfb180e93dc9b95109cf3`：36/36 步、609,589 ms、0 failed；PG16 唯一 head `b4ea2c7d8f86`、366 pytest、61 Playwright、33 个 runtime/YAML 方法、前端四门禁、21/21 真实 HTTP、1000/25 p95 240.541 ms/146.259 RPS/0 错误、档案合成 ETL、1,595,978 bytes/146 表备份恢复、102 OpenSpec 和 1,041 文件 secrets scan 通过。

## 历史机器证据（设施设备/巡检/IoT 精确 SHA）

版本化报告 `docs/06-implementation/evidence/facility-device-inspection-iot/acceptance-clean-e28678b.json` 精确对应 `e28678b5785b7f8bf03141bd7cffbd162932315b`：35/35 步、584,594 ms、0 failed；PG16 唯一 head `z2c80e5f6a64`、352 pytest、60 Playwright、32 个设施 runtime/YAML 方法、前端四门禁、HTTP 1000/25 p95 320.076 ms/135.6 RPS/0 错误、设施合成 ETL、1,495,479 bytes/130 表备份恢复、94 OpenSpec 和 982 文件 secrets scan 通过。

## 历史机器证据（租户服务/工单精确 SHA）

版本化报告 `docs/06-implementation/evidence/tenant-service-work-order-lifecycle/acceptance-clean-ffa72e2.json` 精确对应 `ffa72e2531396997cfe24ef1b1e42526cd4735fe`：33/33 步、554,324 ms、0 failed；PG16 唯一 head `y1b79d4e6f53`、342 pytest、59 Playwright、25 个工单 runtime/YAML 方法、前端四门禁、HTTP 1000/25 p95 302.333 ms/132.87 RPS/0 错误、合成工单 ETL、1,383,498 bytes/114 表备份恢复、86 OpenSpec 和 942 文件 secrets scan 通过；8 份主规格同步并归档后 strict 93/93。

## 历史机器证据（应收闭环 clean SHA）

证据目录 `docs/06-implementation/evidence/receivables-collection-lifecycle/`：精确 `1a11cfe08b8d2b800c7121d7462995ebb75eb75d` 的 335 pytest、2 条应收 Playwright、前端四门禁、HTTP 1000/25 p95 352.701 ms、107.841 RPS、0 错误；PG16 唯一 head `w9f57b2c4d31`；合成 ETL、API 重启和 630,540 bytes 备份删除恢复通过。

## 历史机器证据（Party 企业画像 clean SHA）

版本化报告 `docs/06-implementation/evidence/party-enterprise-profile/acceptance-clean-3680582.json`：精确对应 `36805823ad2e88311b9744e9e720b282b7cc74c8`，31/31 步 exit 0，521,943 ms；PG16 fresh/down-up 与唯一 head `t6c24e9f1a08`、315 pytest、8 租户 worker、全套合成 ETL、Party 21 阶段真实 HTTP 626.54 ms、1,000 请求性能（p95 225.85 ms、172.617 RPS、0 错误）、备份恢复 1,265,613 bytes/100 表、前端 lint/typecheck/6 Vitest/build、57 Playwright、OpenAPI 11/11+strict、OpenSpec 71/71、856 文件 secrets scan 和资源清理均通过。报告 SHA-256 为 `FB03AA7BFC9F9D6024D657D3B39C7220536EAAFCDFAD994BE54199BA97BA963E`。

## 历史机器证据（招商 CRM clean SHA）

版本化报告 `docs/06-implementation/evidence/investment-crm-completion/acceptance-clean-4f870af.json`：报告精确对应 `4f870af20c7c3b574b0f9cc8498e3c2dfb14e5fe`，30/30 步、0 failed，484,424 ms；PG16 fresh/down-up 与唯一 head `s5b13d8e0f97`、298 pytest、全部合成 ETL、真实 HTTP、1,000 请求性能（p95 239.342 ms、159.254 RPS、0 错误）、备份恢复 1,213,678 bytes/94 表、前端 lint/typecheck/6 Vitest/build、54 Playwright、OpenAPI strict、OpenSpec 70/70、817 文件 secrets scan 和资源清理均通过。

招商 change 任务 5.5 仍未关闭：delta spec 的审批状态只有 `PENDING/APPROVED/REJECTED/RETURNED/WITHDRAWN`，没有 `REVOKED`。现有回归已经覆盖园区授权撤销、审批撤回、拒绝、退回、过期、异线索和并发，但不会未经业务架构决策扩展共享审批状态机。

## 历史机器证据（工作台/自动化 clean SHA）

版本化报告 `docs/06-implementation/evidence/platform-workbench-automation/acceptance-clean-fedc98e.json`：报告内 HEAD 精确为 `fedc98efb7a33f39240216fbb861b57f6142649b`，28/28 步 exit 0，485,199 ms；PG16 唯一 head `p2e80a5b7c64`，277 pytest，5 租户 worker 零失败，全部合成 ETL 通过，工作台真实 HTTP 通过，性能 1,000 请求/并发 25/p95 250.49 ms/146.018 RPS/0 错误，备份恢复 1,115,283 bytes/82 表，前端 lint/typecheck/6 Vitest/build、50 Playwright、OpenAPI 9/9+strict、OpenSpec 61/61、741 文件 secrets scan 和清理均通过。

## 历史机器证据（组织治理与审批/审计 clean SHA）

审批/审计 clean-SHA `13243b4` 证据：后端完整 264 passed；PG16 fresh/down-up 与唯一 head 通过；前端 lint/typecheck/Vitest 6/build 通过；Playwright 聚焦 3/3、全量 46/46；独立 HTTP 13 阶段 799.63 ms；性能 1,000 请求、p95 306.849 ms、0 错误；ETL 9 表对账、零重复/PII/伪造决定且 rollback 通过；备份恢复 72 表；OpenAPI 8/8、OpenSpec 54/54、secrets 695 文件；26/26 clean-SHA 总门禁通过。

| 项 | 结果 |
| --- | --- |
| 精确提交报告 | `infra/local-staging/out/acceptance_20260814_130159.json`（gitignored，本机），25/25 PASS；追踪副本 `acceptance-clean-8bb8770.json` |
| 时间/提交 | 2026-08-14 12:55:24–13:01:59 +08:00；395014 ms；`8bb87707251de1e4c22cf4009928c71d84958b8a` |
| PostgreSQL 16 | fresh base→`n0c68d3e5f42` PASS；head→-1→head PASS；唯一 head |
| pytest | 253 passed，1 dependency deprecation warning |
| 前端 | lint PASS；typecheck PASS；Vitest 6 passed；production build PASS |
| Playwright | 43 passed / 0 failed / 0 skipped；组织治理 3 条覆盖桌面真实旅程、平板只读与移动 503/重试 |
| OpenAPI | 7 runtime/YAML contract tests + YAML strict PASS |
| OpenSpec | strict 50 passed / 0 failed |
| ETL | core fast + acceptance、Identity、Asset、CRM、Contract、Organization Governance 均 PASS；组织治理 1/2/3/2/2/2 对账、幂等、无授权行/原始 PII、rollback 全绿；真实旧数据未演练 |
| 性能 | 1000 请求、并发 25、p95 302.694 ms、128.8 RPS、0% 错误，门槛 PASS |
| 备份恢复 | PASS，dump 985813 bytes，restore 65 tables |
| 扩展 secrets scan | PASS，654 tracked/untracked non-ignored files |

## 已确认的产品级阻塞

- `apps/employee-mobile` 不存在；员工移动端未实现。
- `apps/tenant-miniprogram` 不存在；租户微信小程序未实现。
- `analytics`、`ai_assist`、旧 `tenant_ops` 仍是未挂载的空响应或 stub，不能计为驾驶舱、AI 或旧模块完成；租户服务已由受控 `facility_ops` 纵切闭合，但员工移动端、租户小程序和外部通知/对象存储仍未完成。
- 资产模板与组合租控本地产品范围已闭合；集团/区域/园区归属治理已闭合；商业 GIS/CAD/BIM 和真实旧坐标迁移未获合同/数据，保持 NOT_CONNECTED/BLOCKED_EXTERNAL。
- CRM/锁房、合同 V2、Party 企业画像、应收、工单、设施/巡检/IoT 及档案/签章/印章本地产品范围已形成代码和机器证据；外部工商/银行/支付/IoT/合法电子签提供商、真实外部渠道、企微回调/自动触达、AI 评分、HR/供应链、完整驾驶舱和真实旧数据迁移仍未完成。
- 外部短信/微信/邮件/OSS/支付/签章/发票/IoT 无真实凭据，生产联调均 `NOT_LIVE`。
- ETL 只验证合成 fixture；缺少经授权的脱敏旧库快照、字段闭合签字和新旧结果对账。
- 无登记的远程预发环境；性能基线、容灾/监控/告警和生产 Runbook 尚未完成。

## 下一恢复点

1. 提交档案/签章/印章证据与总控文档，正常推送后同步 11 份主规格并归档。
2. 从能力矩阵第 14 项 HR、排班、考勤、绩效和资质进入下一纵切，继续关闭剩余 8 个 `MISSING`。
3. `complete-identity-system-admin` 保持 active：真实 schema dump 和旧密码样本为 `BLOCKED_EXTERNAL`，不得用合成 fixture 冒充或错误归档；生产部署仍须单独人工授权。

## 不可变安全约束

无 force push / reset --hard；无生产 DB；无真实密钥或 PII 输出；无 stub 冒充完成；生产部署与不可逆数据操作必须人工授权。
