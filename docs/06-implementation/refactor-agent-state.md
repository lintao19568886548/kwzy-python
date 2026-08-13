# 瞰维智管 V2 自治重建状态

> 本文件是会话恢复入口；恢复工作时必须同时核对 Git，不得只信本文缓存。

| 字段 | 当前值 |
| --- | --- |
| 更新时间 | 2026-08-13 17:00（Asia/Shanghai） |
| 仓库 | `D:\重构python\kwzy-python` |
| 分支 | `main` |
| 已验证 HEAD | `d9c0b0b1a35a3a25dd205d765ef2e7f36e5c74e6` |
| 远程同步 | `HEAD == origin/main`（写本文前已核对） |
| 工作树 | Identity/System/Admin 纵切候选变更尚待提交 |
| Alembic | 候选唯一 head `h4c02d7e9a86` |
| 当前阶段 | Identity/System/Admin 核心纵切收口；V2 全量仍持续推进 |
| 当前 OpenSpec | `complete-identity-system-admin`；本地可做项接近闭合，真实旧数据项保持外部门禁 |
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

## 最新机器证据

| 项 | 结果 |
| --- | --- |
| 稳定基线报告 | `infra/local-staging/out/acceptance_20260813_160036.json`（gitignored，本机），18/18 PASS |
| Identity 候选报告 | `infra/local-staging/out/acceptance_20260813_165323.json`；功能门禁全绿，仅文档行尾检查失败，待清理后整套复跑 |
| PostgreSQL 16 | fresh base→`h4c02d7e9a86` PASS；head→-1→head PASS |
| pytest | 143 passed，1 dependency deprecation warning |
| 前端 | lint PASS；typecheck PASS；Vitest 4 passed；production build PASS |
| Playwright | 25 passed / 0 failed / 0 skipped；含 cookie/session 和完整 System Admin 管理链 |
| OpenAPI | 3 contract tests + YAML strict PASS；运行时 87 paths / 122 operations |
| OpenSpec | strict 32 passed / 0 failed |
| ETL | core fast + acceptance PASS；Identity 独立 6 表/关系 dry/apply/idempotency/reconcile/rollback PASS；真实旧数据未演练 |
| 备份恢复 | PASS，dump 838139 bytes，restore 47 tables |
| secrets scan | PASS，483 tracked files |

## 已确认的产品级阻塞

- `apps/employee-mobile` 不存在；员工移动端未实现。
- `apps/tenant-miniprogram` 不存在；租户微信小程序未实现。
- `analytics`、`ai_assist`、`finance`、`tenant_ops` 仍是未挂载的空响应或 stub，不能计为能力。
- 资产版本链、完整 CRM/锁房、合同变更链、自动计费/对账催缴、IoT/巡检、HR/供应链、完整驾驶舱均未闭环。
- 外部短信/微信/邮件/OSS/支付/签章/发票/IoT 无真实凭据，生产联调均 `NOT_LIVE`。
- ETL 只验证合成 fixture；缺少经授权的脱敏旧库快照、字段闭合签字和新旧结果对账。
- 无登记的远程预发环境；性能基线、容灾/监控/告警和生产 Runbook 尚未完成。

## 下一恢复点

1. 清理总控 Markdown 行尾并在 clean PostgreSQL 16 上复跑含 Identity ETL 的全量门禁。
2. 提交、推送 Identity/System/Admin 非生产检查点；把报告与精确 commit 回填四份总控文档。
3. `complete-identity-system-admin` 的真实 schema dump 和旧密码样本保持 `BLOCKED_EXTERNAL`，不得用合成 fixture 冒充。
4. 建立并实施下一条资产与租控纵切；继续沿主路线图推进三端和全业务闭环。

## 不可变安全约束

无 force push / reset --hard；无生产 DB；无真实密钥或 PII 输出；无 stub 冒充完成；生产部署与不可逆数据操作必须人工授权。
