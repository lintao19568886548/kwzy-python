# 瞰维智管 V2 自治重建状态

> 本文件是会话恢复入口；恢复工作时必须同时核对 Git，不得只信本文缓存。

| 字段 | 当前值 |
| --- | --- |
| 更新时间 | 2026-08-14（Asia/Shanghai） |
| 仓库 | `D:\重构python\kwzy-python` |
| 分支 | `feat/full-rebuild-completion`（从 repair `37d7cf7da768eef8d7bcc743635117b8f34c7bbb` 创建） |
| 已验证 HEAD | 资产组合精确实现提交 `44ae618aa4b0a83bbb89eff2b040475bbfcb0479` 完成 30/30 clean-SHA 总门禁 |
| 远程同步 | `feat/full-rebuild-completion` 与远端同步到 `44ae618`；实现提交已正常推送；本轮未 force、未触达 main |
| 工作树 | 仅 clean-SHA 证据、滚动报告与 OpenSpec 同步/归档待提交；8 张既有审批/组织截图因二进制归属保护保持未暂存，未删除、未还原、未提交 |
| Alembic | 唯一 head `r4a02c7d9e86`；PG16 fresh q3→r4 与 `r4→q3→r4` 通过，已应用 q3 未修改 |
| 当前阶段 | 独立验收为 5 implemented / 1 blocked / 14 missing；组合能力 1、2、3、6、7 已关闭，完整项目仍 `CONDITIONAL/BLOCKED` |
| 当前 OpenSpec | `2026-08-14-complete-asset-portfolio-views` 已同步主规格并归档；Identity 真实旧数据任务继续外部门禁 |
| 生产部署/迁移 | `NOT_EXECUTED`，保持人工授权门禁 |

## 本轮已完成

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

## 最新机器证据（工作台/自动化 clean SHA）

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
- `analytics`、`ai_assist`、`finance`、`tenant_ops` 仍是未挂载的空响应或 stub，不能计为驾驶舱、AI、完整财务或租户服务；已实现的工作台自动化不外推这些能力。
- 资产模板与组合租控本地产品范围已闭合；集团/区域/园区归属治理已闭合；商业 GIS/CAD/BIM 和真实旧坐标迁移未获合同/数据，保持 NOT_CONNECTED/BLOCKED_EXTERNAL。
- CRM/锁房与合同 V2 定义范围已形成代码与本地验收；真实外部渠道、企微回调/自动触达、意向审批、AI 评分、自动计费/对账催缴、IoT/巡检、HR/供应链、完整驾驶舱和真实旧数据迁移仍未完成。
- 外部短信/微信/邮件/OSS/支付/签章/发票/IoT 无真实凭据，生产联调均 `NOT_LIVE`。
- ETL 只验证合成 fixture；缺少经授权的脱敏旧库快照、字段闭合签字和新旧结果对账。
- 无登记的远程预发环境；性能基线、容灾/监控/告警和生产 Runbook 尚未完成。

## 下一恢复点

1. 正常提交并推送资产模板/组合租控 clean-SHA 证据、主规格同步和 OpenSpec 归档。
2. 继续关闭能力矩阵剩余 14 个 `MISSING`，优先选择下一个能形成完整真实旅程的业务纵切。
3. `complete-identity-system-admin` 保持 active：真实 schema dump 和旧密码样本为 `BLOCKED_EXTERNAL`，不得用合成 fixture 冒充或错误归档；生产部署仍须单独人工授权。

## 不可变安全约束

无 force push / reset --hard；无生产 DB；无真实密钥或 PII 输出；无 stub 冒充完成；生产部署与不可逆数据操作必须人工授权。
