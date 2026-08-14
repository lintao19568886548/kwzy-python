# 平台统一工作台与自动化纵切验收证据

> 工作树验收日期：2026-08-14（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`；本文件先记录工作树闭环，clean-SHA 提交与复验结果在提交后补录。
> 判定：统一工作台和自动待办组合能力已在本地真实栈闭环；全项目仍为 `CONDITIONAL/BLOCKED`，员工移动端、租户小程序、其余业务域、真实旧数据和生产均未完成或未获授权。

## 交付范围

- 事务内业务事件、消费者状态机、租户/园区安全的并发 claim、有限退避、死信和受控代次 replay；
- 受限条件/动作语法、草稿和不可变发布版本、幂等执行证据，不允许动态代码、SQL 或 URL；
- 收件人/园区隔离的站内通知、未读数、读取/归档和有界原子批量读取；
- allow-list 调度定义、持久运行、心跳、超时恢复、并发策略、手工运行/重试和独立 worker；
- WorkItem 深链、乐观锁、来源所有权、升级/改派和事件追踪；
- 用户 → 角色 → 服务器默认布局、组件权限不放大、个人/角色配置与冲突反馈；
- PC 实时工作台、消息中心和自动化控制面，包含规则、调度、事件、执行记录、死信及角色默认首页管理；
- OpenAPI、PG16、真实 HTTP、Playwright、多角色/响应式/离线/403/409、性能、合成 ETL 和运维契约。

## 工作树完整闸门

机器报告：`acceptance-worktree-20260814.json`，28/28 步 exit 0，16:30:32–16:38:24 +08:00，总耗时 472,584 ms。

| 类别 | 结果 |
| --- | --- |
| Alembic / PG16 | 唯一 head `p2e80a5b7c64`；fresh base→head、`downgrade -1 → upgrade head`、ORM/约束/并发专项通过 |
| 后端 | 完整 `277 passed, 1 warning`；pytest 自报 106.65 秒；独立 worker 扫描 5 租户、0 失败 |
| 真实 HTTP | 审批/审计与工作台自动化两条独立旅程均 PASS；工作台旅程覆盖规则版本、事件幂等派发、通知、调度、角色/个人布局、409、三次重试→DEAD→代次 replay |
| 性能 | 1,000 请求、并发 25、预热 40、0 错误、p95 242.193 ms、145.478 RPS；原门槛 p95≤500 ms / 错误率≤1% / RPS≥20，PASS |
| 备份恢复 | `pg_dump -Fc` 1,115,006 bytes；删除/创建恢复库、`pg_restore`、82 表复核和恢复库清理均 PASS |
| 前端 | ESLint PASS；Vue typecheck PASS；Vitest 3 files / 6 tests PASS；production build PASS |
| 浏览器 | 完整真栈 Playwright `50 passed`；工作台专项覆盖实时通知/布局、多角色、桌面/平板/手机、403、409、offline/retry 和管理动作 |
| OpenAPI / OpenSpec | runtime/YAML `9 passed` + YAML strict；OpenSpec strict `61 passed` |
| 安全 | 733 文件 secrets scan PASS；数据库派生权限、tenant/park/recipient IDOR、参数污染、批量边界、深链 allow-list 和错误脱敏回归通过 |
| 清理 | API/Web 进程、测试恢复库、PostgreSQL 容器/网络/卷均已清理；未连接生产 |

## 性能整改循环

首次工作树全验收暴露聚合 p95 946.484 ms，且脚本被后续命令覆盖 `$LASTEXITCODE` 后错误记录性能步骤为 exit 0。整改先让每个关键原生命令立即断言退出码；下一轮因此在 p95 729.289 ms 时真实中止并输出 FAIL。随后消除事件消费者 N+1、工作台摘要重复查询、待办/通知双查询、自动化健康四次标量查询和布局双查询，并将性能栈按生产契约设置为 `DEBUG=false`，不降低阈值。最终同一闸门为 p95 242.193 ms、0 错误。失败证据未删除，也未通过删端点、降并发或放宽阈值结束整改。

## 视觉证据

- `pc-desktop-workbench.png`：桌面只读工作台、实时 KPI、空待办和消息；
- `pc-tablet-workbench.png`：平板布局与局部响应式重排；
- `pc-mobile-workbench.png`：手机纵向卡片、导航和空状态。

浏览器控制技能另以管理员在 1440×900 检查自动化控制面，并以 390×844 检查移动首页；两者 `document.scrollWidth == clientWidth`，控制台 warning/error 为 0。页面展示的规则、调度、事件、角色布局和空状态均来自本地 PostgreSQL/真实 API，不读取本地业务 JSON。

## 合成迁移与外部边界

`workbench-automation-etl-worktree.json` 证明 dry-run、中断回滚、首次 apply、零新增幂等重跑、逐表对账、零伪造成功、零启用调度、零原始 PII、授权身份不变和 schema rollback。真实旧 outbox/通知/任务/布局仍缺经授权 schema 与脱敏快照，因此只允许：

```text
WORKBENCH_AUTOMATION_MIGRATION=CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA
REAL_LEGACY_MIGRATION=BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE
```

## 组合能力结论

20 项矩阵中的“统一工作台和自动待办”可升级为 `IMPLEMENTED_AND_VERIFIED`。这不等于完整经营驾驶舱、员工移动端、租户小程序、全旧系统替代或生产就绪；这些项目保持各自的 `MISSING`/`BLOCKED` 状态。
