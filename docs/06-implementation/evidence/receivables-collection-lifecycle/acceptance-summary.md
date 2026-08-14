# 应收、到账、核销与催缴纵切独立验收摘要

> 验收日期：2026-08-15（Asia/Shanghai）
> 范围结论：`IMPLEMENTED_AND_VERIFIED`
> 全产品结论：`BLOCKED`
> 生产连接/部署：未执行，仍需人工授权

## 已关闭业务范围

- 当前 Lease 版本履约计划的出账 preview/apply、分组签发、来源血缘、计划同事务更新、重放和并发冲突。
- 单笔/批量到账导入、来源幂等、渠道能力真相、待处理/异常/争议单箱。
- 确定性匹配候选、规则代码和建议分配；禁止系统自动过账，由财务确认，异常/争议由经理复核。
- Payment 已分配/未分配余额、多账单分配、预收后续核销、追加式分配/冲正历史、结清联动。
- L1-L4 账龄、每账单唯一活动案件、preview/apply 催缴、hold、升级、记录、待办和结清关闭。
- waiver/extension/bad debt/dispute 调整申请、双人审批、应用及审计链。

## 数据库与迁移

唯一 Alembic head 为 `w9f57b2c4d31`：

```text
t6c24e9f1a08 -> u7d35f0a2b19 -> v8e46a1b3c20 -> w9f57b2c4d31 (head)
```

在隔离的 PostgreSQL 16 上执行并通过：

```powershell
alembic upgrade head
alembic heads
alembic current
alembic downgrade -1
alembic upgrade head
alembic check
python -m pytest -q tests/test_receivables_postgres.py tests/test_receivables_etl_postgres.py
```

全新空库从 base 升到 head、`current == heads`、w9→v8→w9、ORM/迁移契约均通过。w9 新增 16 个财务表复合租户外键；测试共核对 21 项核心 FK/unique/check/partial-index 契约，并覆盖超配、重复来源、唯一活动案件、调整和竞态。没有使用 `create_all` 代替 Alembic。

## 测试结果

| 类别 | 结果 |
| --- | --- |
| 后端全量 | 334 passed，0 failed，150.88 s；363 条既有上游弃用 warning |
| 应收 PG/领域/API/权限/并发 | 全部通过；并发到账专项额外连续 5 轮通过 |
| 前端类型 | `vue-tsc` PASS |
| ESLint | PASS |
| Vitest | 3 files / 6 tests PASS |
| Production build | 141 modules PASS |
| 浏览器 E2E | 2 passed，0 failed，24.1 s；真实 PG/FastAPI/production Vite |
| OpenAPI | runtime/YAML 契约与 YAML strict PASS |
| OpenSpec | strict 78 passed，0 failed（归档前） |
| Python 依赖 | `pip-audit --local`：0 known vulnerabilities；本地非 PyPI 包按预期跳过 |
| 前端依赖 | `npm audit --audit-level=high`：0 vulnerabilities |
| secrets | tracked + untracked 904 files PASS |
| runtime stub/architecture | 无应收固定成功/stub；Application→ORM 已清零，router 无直查数据库 |

## HTTP、可靠性与备份恢复

真实 loopback HTTP 使用登录令牌访问 8 个应收端点，1000 请求、并发 25、预热 40：失败 0，错误率 0%，p95 151.678 ms，吞吐 211.529 RPS，门槛 PASS。详见 `http-performance-20260814.json`。

API 进程停止并确认端口关闭后重新启动；重启前后 readiness 均为 ready/database up，receipts/payments/cases 行签名均为 5/5/5。详见 `service-restart-recovery-20260814.json`。

使用 `pg_dump -Fc` 生成 630,540 bytes 备份，SHA-256 为 `acc85e479b310efd8b391251657ea85769cfcfb987ff9d4f87b4acd61bd1140a`。删除/新建临时恢复库并 `pg_restore` 后，源和恢复签名均为 `alembic=w9f57b2c4d31,bills=20,receipts=5,payments=5,cases=5,adjustments=0`；随后删除恢复库。详见 `postgres-backup-restore-20260814.json`。

## 数据迁移演练

合成旧财务 fixture 的 dry-run、中断回滚、apply、幂等 reapply、对账和 schema rollback 均通过：2 bills、3 lines、2 receipts、1 payment、1 allocation、1 case、1 record、1 quarantine；重复执行新增量全为 0；来源/目标账单总额均为 1500.00；line mismatch、over-allocation、allocation mismatch、orphan、未脱敏账号、虚假外部送达均为 0。详见 `receivables-etl-report.json` 和 `docs/05-data-migration/receivables-field-mapping-v1.md`。

真实旧财务 schema/脱敏快照未提供，故真实迁移、增量同步、停写切换、回切和签字对账仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`，没有伪造为完成。

## 安全与并发整改

- 修复 ALL 园区范围 token 可导入外租户 park 的漏洞，创建到账前验证 park 的 tenant 归属。
- 用数据库复合 tenant 外键防止服务绕过后写入跨租户 finance 关系。
- 全局拒绝重复 query 参数名，返回 400 `DUPLICATE_QUERY_PARAMETER`，避免参数污染。
- 有序锁和数据库唯一约束覆盖到账来源、Idempotency-Key、多账单分配、活动催缴案件和并发写入。
- 受控字段只返回掩码/派生状态；渠道未配置时返回 `NOT_CONNECTED`，不会报告已发送、已到账或已联通。

该纵切未关闭 P0/P1/P2；全产品仍有 6 个开放 P1 类别，见 `docs/06-implementation/independent-final-audit-repair-register.md`。

## 角色、旅程和 UI

财务角色完成：出账、到账单箱、匹配解释、确认/异常、复核核销、多账单和未分配余额处理。财务经理完成：争议和调整双人审批。园区/催缴角色完成：账龄筛选、L1-L4 preview/apply、记录和案件联动。越权用户的 tenant/park/permission/字段访问被拒绝。

浏览器证据：

- `pc-desktop-payment-allocation.png`
- `pc-desktop-collection-aging.png`
- `pc-tablet-receipt-inbox.png`
- `pc-mobile-receipt-inbox.png`

人工复核无假图表、假按钮、固定成功、乱码、敏感账号原文或页面级横向溢出；表格窄屏横向滚动限制在组件内。员工移动端和租户小程序不存在，不能由 PC 响应式截图替代验收。

## 外部集成与最终边界

银行、聚合支付、税票和财务软件仍未获得合同、沙箱凭据或回调协议，运行时明确 `NOT_CONNECTED`。本轮未连接生产、未部署生产、未 force push、未触达 main。

```text
RECEIVABLES_LOCAL_PRODUCT_SCOPE=IMPLEMENTED_AND_VERIFIED
RECEIVABLES_EXTERNAL_PROVIDERS=NOT_CONNECTED
RECEIVABLES_REAL_LEGACY_MIGRATION=BLOCKED
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL
```
