# 瞰维智管 V2 独立终验与整改报告

> 日期：2026-08-14（Asia/Shanghai）
> 结论：**BLOCKED（已实现范围条件通过，全产品未完成）**
> 实现证据提交：`a9267d4c30096a7c80d66588ab06bc6838b32b0d`
> 机器报告：`evidence/independent-final-audit/acceptance-a9267d4.json`
> 报告 SHA-256：`E1D41D005DF3E8DB50C368FE58BC441A1D92AA658001EC2B3958CE58CFD2EF87`

## 1. Git、环境与运行基线

| 项 | 独立核验结果 |
| --- | --- |
| repair 分支 | `audit/full-rebuild-final-repair` |
| 实现提交 | `a9267d4c30096a7c80d66588ab06bc6838b32b0d`；114 files，14,830 insertions，2,190 deletions |
| 本地 main | `64417c61177f4e47463062fbebe48f7c54d1bc94` |
| origin/main | 2026-08-14 终验前 `git fetch origin --prune` 后为 `4be4fe0c060543178ae71783d1ce0b29fad235fe` |
| 同步关系 | main 比 origin/main ahead 2；实现提交比 origin/main ahead 3；无远端新增提交 |
| 工作树 | 精确 SHA 验收前 clean；报告和构建输出在 gitignored `infra/local-staging/out` |
| remote | `https://github.com/lintao19568886548/kwzy-python.git` |
| 禁止项 | 未 force push、未连接生产、未改历史迁移、未覆盖用户修改、未部署生产 |
| 运行版本 | Python 3.10.11；Node 22.14.0；npm 11.4.1；Docker 29.6.2；Compose 5.3.1；PostgreSQL 16.14（Docker） |
| 原生 DB 客户端 | 主机未安装 psql；所有 PostgreSQL 权威验证在 `postgres:16` 隔离容器中执行 |
| 应用入口 | API：`uvicorn app.main:app`；PC：`npm run dev` / `npm run build`；生产示例见 `infra/production` |
| 三端事实 | PC 位于 `apps/web`；员工移动端、租户小程序无应用目录和启动方式 |

环境样例为 `apps/api/.env.example`、`infra/postgres-test/.env.example`、`infra/production/production.env.example`。敏感文件名检查与 621 文件内容扫描通过；未发现被跟踪的真实密钥、Token、密码、数据库文件或 PII。样例值均为明确的非生产占位。

## 2. 整改提交内容

实现提交主要包含：

- 合同 V2：多单元/多费用、确定性费用计划、审批和签章准备门禁、不可变版本链、七类变更、续租、退租结算、WorkItem、乐观锁、幂等和失败回滚。
- 安全：附件 IDOR 修复、密码策略、JWT/会话撤销、登录和生产 fail-closed、Host/CORS/CSRF/安全头、园区/租户范围、生产 provider 门禁。
- 依赖：用 PyJWT 替换含无修复 `ecdsa` 漏洞链的 python-jose；Vitest 升到 4.1.10；Python 和 npm 已知漏洞均为 0。
- 数据：新增 `k7f35a0b2d19`、`l8a46b1c3e20`、`m9b57c2d4e31` 三个迁移，不修改历史迁移；补齐 ORM 索引、BigInteger 和时间戳 nullability 契约。
- API/PC：合同全套 API/OpenAPI、合同工作台/治理抽屉/差异展示/响应式与滚动复位，API 分页/隐私/scope 回归。
- 集成：持久化 outbox、幂等唯一约束、local/fake 与生产 fail-closed 适配器。
- 工程：真实 HTTP 性能门禁、PG ETL/备份恢复、生产 Dockerfile/Compose/Nginx、就绪探针/连接池、GitHub Actions 验收与依赖漏洞门禁。
- 证据：桌面/平板/移动窄屏截图、机器验收 JSON、性能 JSON、迁移边界和操作 Runbook。

## 3. Alembic 与 PostgreSQL 16

唯一迁移链尾部为：

```text
j6e24f9a1c08 -> k7f35a0b2d19 -> l8a46b1c3e20 -> m9b57c2d4e31 (head)
```

精确 SHA 验收执行的关键命令：

```powershell
docker compose -f infra/postgres-test/compose.yaml up -d
cd apps/api
alembic upgrade head
alembic heads
alembic downgrade -1
alembic upgrade head
python -m pytest -q --tb=line
pwsh -NoProfile -File infra/local-staging/run_full_acceptance.ps1
```

结果：

- 空库 base → head 通过，`current == heads == m9b57c2d4e31`；down one 再 up 通过。
- 迁移后 59 张表、168 个外键、38 个唯一约束、253 个索引、13 个 boolean 列。
- ORM metadata 与迁移契约测试通过；关键索引、外键、唯一性、boolean、时间戳 nullability 和序列 BigInteger 已复核。
- 合同、租控锁房、收款/核销和 outbox 幂等的 PG 并发/竞态/回滚测试通过；库存域未实现，不能声称库存并发通过。
- 禁止用 `create_all` 代替验收；完整脚本与 E2E seed 均以 Alembic 初始化。

## 4. 测试和耗时

精确实现 SHA `a9267d4` 的完整脚本从 11:33:05 到 11:38:53，总耗时 348,122 ms，24/24 步 exit 0。

| 类别 | 结果 | 脚本耗时 |
| --- | --- | --- |
| PG16 clean start | PASS | 6,940 ms |
| Alembic fresh upgrade | PASS | 2,222 ms |
| Alembic down/up | PASS | 1,597 ms |
| 后端全量（含 PG） | 241 passed，0 failed | 76,063 ms；pytest 自报 71.47 s |
| ETL fast | PASS | 15,244 ms |
| ETL acceptance | PASS | 141,502 ms |
| Identity/Asset/CRM/Contract ETL | 4/4 PASS | 1,661 ms |
| 真实 HTTP 性能 | PASS | 10,222 ms |
| 备份恢复 | PASS | 2,534 ms |
| ESLint / vue-tsc | PASS / PASS | 1,499 / 2,452 ms |
| Vitest | 3 files，6 tests passed | 1,672 ms |
| production build | 134 modules，PASS | 4,322 ms |
| Playwright | 40 passed，0 failed，0 skipped | 66,446 ms |
| OpenAPI | runtime/YAML 6 passed + YAML strict | 7,651 ms |
| OpenSpec | 49 passed，0 failed | 1,026 ms |
| secrets scan | 621 files，PASS | 368 ms |
| diff check / cleanup | PASS / PASS | 38 / 2,364 ms |

补充门禁：认证/JWT 迁移专项 29/29；Python `pip-audit --local` 0 已知漏洞（本项目自身因不在 PyPI 被跳过）；`npm audit --audit-level=high` 0 漏洞；API 和 Web 生产镜像均构建成功。

唯一测试信息项是 Starlette TestClient 上游弃用提示，不影响运行结果；真实 HTTP 与浏览器验收并未只依赖 TestClient。

## 5. 数据迁移、对账与备份恢复

合成迁移对 core、Identity、Asset、CRM 和 Contract 执行 dry-run、首次 apply、故障中断回滚、幂等重跑、分布/数量/金额/面积/孤儿/重复/PII 对账及 schema rollback。

合同合成数据结果：2 Parties、3 Contracts、3 Versions、4 Units、3 Charges、3 Schedules、2 Documents、2 Reminders、1 Quarantine；占用面积 221.50、押金 27,000、费用 8,800；重复与孤儿均为 0，报告不持久化原始 PII。

备份恢复使用 `pg_dump -Fc`，生成 950,051 bytes dump；删除并重建临时恢复库后 `pg_restore`，复核 59 张表，再删除恢复库。dump SHA-256 为 `1412F12A6AA1F071EC82BA63B3F4ECC46053828382FE342EC881FDC154D102A8`，本地证据未提交 Git。

真实旧库仍不可验：未取得经授权 schema dump/脱敏快照，无法证明真实字段/枚举/PII 映射、全量金额面积、CDC、停写、切换和回切。故结论只能是：

```text
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_SYNTHETIC_ONLY
```

## 6. HTTP 性能、可靠性和运维

真实 loopback HTTP 使用登录后的 4 个公共查询接口，1000 请求、并发 25、预热 40：

- 0 failures，错误率 0.0%，141.36 req/s。
- p50 145.961 ms，p95 280.422 ms，p99 321.082 ms，max 333.336 ms。
- 门槛 p95 ≤ 500 ms、错误率 ≤ 1%、吞吐 ≥ 20 req/s，结果 PASS。
- 性能报告 SHA-256：`A13D9450E5D11C084FAA1E1A586687EA8BF96F828E4C08947322A98FFAAA883B`。

生产契约提供显式 PG QueuePool 上限/超时/回收、`/health/ready`、非 root 镜像、只读文件系统、tmpfs、drop all capabilities 和 no-new-privileges。API 镜像用户为 `kwzy`，Web 为 UID `101`。

隔离容器栈实际启动后，数据库、API、Web 分别重启；重启前后 API 代理均按预期返回 401，最终 readiness 为 `{"status":"ready","database":"up"}`，`CONTAINER_RESTART_RECOVERY=PASS`，所有临时容器/网络/卷已清理。

这些是本机核心查询的性能与恢复证据，不是远程预发大数据容量、生产 SLO、监控告警或跨区灾备验收，因此总体运维和性能状态保持条件通过。

## 7. 安全验收

已验证范围包含认证、refresh 轮换/重放/撤销、密码策略、生产弱 JWT 拒绝、RBAC、tenant/park scope、附件 IDOR、跨租户批量访问、参数/分页限制、CSRF/Host/CORS/安全头、文件大小/归属、审计、幂等和 PG 竞态。

静态与运行扫描分类：

| 扫描项 | 人工分类 |
| --- | --- |
| TODO/FIXME/pass/NotImplementedError | runtime 的 `NotImplementedError` 仅在抽象 provider 接口；`pass` 为异常类/枚举容错，无固定成功业务实现 |
| stub/mock/placeholder/demo/fake | AI 固定 stub 未挂载，计 `MISSING`；synthetic ETL 与 local/fake provider 有环境标识，不计生产完成 |
| 静态假图表 | `analytics` 未挂载且无真实驾驶舱，计 `MISSING` |
| 未挂 router | 12 个真实 router 均挂载；`ai_assist`、`analytics` 未挂载并计缺失 |
| 前端本地 JSON/假按钮 | 未发现业务页读取本地 JSON；关键合同/租控按钮由真实 HTTP/E2E 覆盖 |
| API/OpenAPI 漂移 | 已修复，6/6 契约与 YAML strict 通过 |
| Application→ORM / Router 查 DB | 架构回归测试和人工检索未发现新增违规 |
| 默认管理员/开发免鉴权/弱 JWT | 生产/预发 fail-closed；本地测试账号只用于隔离验收 |
| 密钥/Token/DB/PII | 621 文件扫描通过；环境样例为非生产占位 |
| 历史迁移/多 head | 未修改历史迁移；新增修复迁移；唯一 head |
| 外部集成虚假完成 | 文档和运行时均区分 fake/local、fail-closed 与 live verified |

没有发现未关闭 P0；已实现范围内没有未关闭安全 P1。但 IDOR/XSS/CSRF/SSRF/开放重定向等结论只覆盖当前挂载接口，不能替代缺失业务域和远程 DAST。

## 8. 三端、角色和 UI

PC 真实浏览器验证使用 PostgreSQL、FastAPI、生产 Vite 构建和真实 HTTP；40 条 Playwright 无 skip。额外人工浏览器检查覆盖 1280px、768×1024、390×844，页面无横向溢出，合同治理抽屉、租控矩阵数据态和路由滚动复位通过；控制台 error/warn 为 0。截图位于 `evidence/independent-final-audit/`。

可验证角色切片包括系统管理员、受限用户、资产查看者、招商查看者、合同查看/提交/审批角色，以及基础财务/工单操作。决策管理层、区域/园区经理、完整招商/财务/物业岗位只能算窄功能证据；企业租户管理员与企业员工没有对应端，不能验收。

高级浅色后台和当前合同/租控响应式切片有证据；深色经营驾驶舱、全局快捷命令、右侧 AI 助手、首页组件配置、KPI 原单下钻、多园区比较、完整地图/分析切换及两端离线/重试均未完成。员工移动端和租户小程序没有启动方式或 E2E。

## 9. 旧系统与外部集成

旧 Java 证据仓静态规模为 54 Controllers、约 484 HTTP mappings、316 Vue 文件、30 SQL DDL 表。当前 Python 仓库缺少两端及 17 个组合能力，因此旧系统替代为 `BLOCKED`。

| 集成组 | 代码状态 | 真实状态 |
| --- | --- | --- |
| SMS/通知/对象存储 | local/fake + outbox + 生产 fail-closed | 未获凭据，NOT_LIVE |
| 合同签章 | port、local fake、生产 fail-closed | 未选/未验厂商，NOT_LIVE |
| 微信/邮件 | 配置门禁或局部端口 | 未联调，NOT_LIVE |
| 银行/聚合支付/税票/财务软件 | 完整适配器缺失 | MISSING |
| OCR/档案/印章/存证 | 完整业务与适配器缺失 | MISSING |
| 门禁/停车/视频/消防/能耗/IoT | 适配器和业务缺失 | MISSING |
| OA/ERP/HR/采购/协作平台 | 缺失 | MISSING |
| 云/私有模型 | AI 业务层缺失 | MISSING |

## 10. P0/P1/P2 与责任边界

| 级别 | 未关闭数 | 项目 |
| --- | --- | --- |
| P0 | 0 | 当前证据未发现 P0 |
| P1 | 6 | 员工移动端；租户小程序；17 项能力矩阵缺失的产品闭环；真实旧数据迁移；外部适配器完整性/真实联调；远程预发监控容量灾备 |
| P2 | 0 | 本轮可在当前权限内修复的 P2 已关闭；上游 TestClient 弃用提示记为 INFO |

没有任何 `APPROVED_DEFERRED` 或 `APPROVED_RETIRED`。建议责任人不是虚构姓名：

- 产品/业务负责人：决定缺失能力优先级，并对退休/延期给出书面依据。
- 数据负责人/DBA：提供经授权 schema dump、脱敏快照、对账口径和切换窗口。
- 集成负责人/安全负责人：提供沙箱协议、短期凭据、回调域名和验签要求。
- SRE/运维负责人：提供远程预发，执行监控告警、容量、重启/灾备和回切演练。
- 生产变更审批人：单独授权生产部署；当前未授权。

## 11. 最终判定

能力矩阵汇总为 2 项 `IMPLEMENTED_AND_VERIFIED`、1 项 `BLOCKED`、17 项 `MISSING`。完整细节见 `full-rebuild-traceability-matrix.md`。因为 P1 不为 0、两端缺失、真实迁移和旧系统替代未完成，repair 分支不得合并 main。

```text
KWZY_INDEPENDENT_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_BUSINESS_CLOSURE=BLOCKED
KWZY_BACKEND_REBUILD=CONDITIONAL_CORE_AND_CONTRACT_SLICE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_CORE_AND_CONTRACT_SLICE_ONLY
KWZY_EMPLOYEE_MOBILE=MISSING
KWZY_TENANT_MINIPROGRAM=MISSING
KWZY_LEGACY_REPLACEMENT=BLOCKED
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_SYNTHETIC_ONLY
KWZY_SECURITY_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PERFORMANCE_ACCEPTANCE=CONDITIONAL_LOCAL_LOOPBACK_ONLY
KWZY_OPERATIONS_READINESS=CONDITIONAL_LOCAL_ONLY
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL
```
