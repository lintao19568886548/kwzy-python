# 瞰维智管 V2 自治重建状态

> 本文件是会话恢复入口；恢复工作时必须同时核对 Git，不得只信本文缓存。

| 字段 | 当前值 |
| --- | --- |
| 更新时间 | 2026-08-13 19:50（Asia/Shanghai） |
| 仓库 | `D:\重构python\kwzy-python` |
| 分支 | `main` |
| 已验证 HEAD | `8adcd77e782db47a466ba0759ac04ffaae488b1b` |
| 远程同步 | 被测时 `origin/main=d257c1b1c10cc246eb0dc006af609163826a53c8`；实现与本证据提交按任务 9.8 一并非强推送，恢复时必须再核对 Git |
| 工作树 | 精确 SHA 验收后仅回填总控证据与 OpenSpec 任务状态；被测业务代码工作树 clean |
| Alembic | 唯一 head `j6e24f9a1c08` |
| 当前阶段 | 招商 CRM V2 本次定义范围 `LOCAL_ACCEPTANCE_PASS`；进入规格同步/归档与阶段 3 合同纵切 |
| 当前 OpenSpec | `implement-investment-crm-v2` 67/67，strict PASS，待证据提交后同步归档；`complete-identity-system-admin` 的真实旧数据项保持外部门禁 |
| 生产部署/迁移 | `NOT_EXECUTED`，保持人工授权门禁 |

## 本轮已完成

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

## 最新机器证据

| 项 | 结果 |
| --- | --- |
| 精确提交报告 | `infra/local-staging/out/acceptance_20260813_195020.json`（gitignored，本机），21/21 PASS |
| 时间/提交 | 2026-08-13 19:45:07–19:50:20 +08:00；313740 ms；`8adcd77e782db47a466ba0759ac04ffaae488b1b` |
| PostgreSQL 16 | fresh base→`j6e24f9a1c08` PASS；head→-1→head PASS |
| pytest | 166 passed，1 dependency deprecation warning |
| 前端 | lint PASS；typecheck PASS；Vitest 4 passed；production build PASS |
| Playwright | 32 passed / 0 failed / 0 skipped；其中 CRM 6 条，覆盖主链、公海、管理操作、只读、409/503 恢复与平板键盘 |
| OpenAPI | 4 runtime/YAML contract tests + YAML strict PASS；CRM V2 20 个路径方法进入精确契约 |
| OpenSpec | strict 38 passed / 0 failed |
| ETL | core fast + acceptance、Identity、Asset、CRM 均 PASS；CRM 为 5/4/4/1/1 且对账、幂等、PII 隔离、rollback 全绿；真实旧数据未演练 |
| 备份恢复 | PASS，dump 883310 bytes，restore 52 tables |
| 扩展 secrets scan | PASS，545 tracked/untracked non-ignored files |
| runner SHA256 | `747C954458394D6D9F8CE4B9355DB849C3859A2199C7090386334311D3887EC3` |

## 已确认的产品级阻塞

- `apps/employee-mobile` 不存在；员工移动端未实现。
- `apps/tenant-miniprogram` 不存在；租户微信小程序未实现。
- `analytics`、`ai_assist`、`finance`、`tenant_ops` 仍是未挂载的空响应或 stub，不能计为能力。
- 资产与租控本次定义范围已闭合；集团层、GIS/CAD/BIM 地图与更深组合经营分析仍未实现。
- CRM/锁房本次定义范围已形成代码与本地验收；真实外部渠道接入、企微回调/自动触达、意向审批、AI 评分及真实旧数据迁移仍未完成，合同变更链、自动计费/对账催缴、IoT/巡检、HR/供应链、完整驾驶舱也未闭环。
- 外部短信/微信/邮件/OSS/支付/签章/发票/IoT 无真实凭据，生产联调均 `NOT_LIVE`。
- ETL 只验证合成 fixture；缺少经授权的脱敏旧库快照、字段闭合签字和新旧结果对账。
- 无登记的远程预发环境；性能基线、容灾/监控/告警和生产 Runbook 尚未完成。

## 下一恢复点

1. 提交并非强推送 CRM V2 精确验收证据，随后同步主规格并归档 `implement-investment-crm-v2`。
2. 进入阶段 3 Party/租户/合同纵切，先取证并提出多单元、多费用、变更单/补充协议版本链、审批与退租结算的 OpenSpec。
3. `complete-identity-system-admin` 保持 active：真实 schema dump 和旧密码样本为 `BLOCKED_EXTERNAL`，不得用合成 fixture 冒充或错误归档。

## 不可变安全约束

无 force push / reset --hard；无生产 DB；无真实密钥或 PII 输出；无 stub 冒充完成；生产部署与不可逆数据操作必须人工授权。
