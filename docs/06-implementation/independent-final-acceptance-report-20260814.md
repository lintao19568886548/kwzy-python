# 瞰维智管 V2 独立终验与整改报告

> 日期：2026-08-15（Asia/Shanghai，滚动更新）
> 结论：**BLOCKED（已实现范围条件通过，全产品未完成）**
> 最新精确提交闭环：档案、电子签章与印章治理；`b04d738bc75e865e1c6bfb180e93dc9b95109cf3` 的 36/36 全量门禁通过并正常推送
> 上一 clean-SHA：设施设备、周巡检与 IoT `e28678b5785b7f8bf03141bd7cffbd162932315b`（35/35，已正常推送）
> 历史 clean-SHA：租户服务/工单 `ffa72e2531396997cfe24ef1b1e42526cd4735fe`、应收 `1a11cfe08b8d2b800c7121d7462995ebb75eb75d`、Party `36805823ad2e88311b9744e9e720b282b7cc74c8`
> 本报告滚动记录自治重建；下文早期 repair 数字如与“最新闭环增量”冲突，以最新机器报告与能力矩阵为准。

## 0. 最新闭环增量

档案/签章/印章纵切已补齐为本地产品闭环：版本化档案分类/保管策略、确定性档号、附件精确版本和服务端 SHA-256、归档与完整性不一致自动 hold；法律保全、借阅/归还/过期、保管期限与依赖门禁下的处置和双人确认；印章台账、交接、丢失/停用/找回/退役、精确档案版本用印和不可变回执；无密钥签章提供方真相、信封/参与人/追加式事件、重放安全沙箱投递及 live fail-closed。旧 Java/前端/DDL 没有可证明的档案、印章或合法电子签聚合，不把旧按钮和当前 fake 状态当成真实能力。

本轮新增前向迁移 `a3d91f6a7b75`，并在其已应用后使用 `b4ea2c7d8f86` 前向硬化，没有修改历史。PostgreSQL 16 fresh base→head、唯一 `current == heads`、b4→a3→b4、metadata、复合租户/园区外键、唯一/检查/索引、档号/处置/用印并发和幂等均通过。安全审查关闭了高风险用印申请人/最终审批人/执行人未分离、执行幂等键未绑定完整命令、沙箱 Lease 伪造法律 `SIGNED` 与附件完整性边界；显式 override 必须有独立权限和审计原因。

精确提交 `b04d738` 全量脚本 36/36 步 exit 0、609,589 ms：366 pytest（188.68 s）、15 租户 worker零失败、全部合成 ETL、21/21 档案真实 HTTP、1000 请求/并发 25 性能 p95 240.541 ms、146.259 RPS、0 错误、1,595,978 bytes/146 表备份删除恢复、前端 ESLint/vue-tsc/6 Vitest/147 modules production build、61 Playwright、15 OpenAPI 契约及 YAML strict、OpenSpec strict 102/102、1,041 文件 secrets scan 和资源清理全部通过。档案/印章/签章 runtime/YAML 33 个方法精确一致；机器报告为 `evidence/records-signature-seal-governance/acceptance-clean-b04d738.json`。

全量浏览器先后真实暴露并关闭两个 P1：共享库多 DRAFT 信封让全局“发送”定位歧义，改为精确信封行；Party 企业画像在列表刷新前提前提示成功，紧接着提交关系因共享 `saving` 状态静默丢失，成功提示改到 `await load()` 后。其后视觉复核又关闭 390px 页签/六列表格依赖横向滚动的问题：页签三等分，档案/信封表改为字段完整卡片，并加入边界断言。三张人工截图覆盖桌面/平板签章真相和 390px 档案离线重试，无假数据、乱码、遮挡或横向溢出。

档案合成 ETL 对 2 分类、2 档案、2 版本和 2 隔离记录完成 dry/interruption/apply/reapply/reconcile/rollback，伪造印章、保管、提供方和事件均为 0。授权旧 schema/保管字典、脱敏元数据与二进制清单、SHA-256 manifest、主键映射、合法电子签凭据/回调证据和生产切换授权仍缺失；真实迁移保持 `BLOCKED`，供应商保持 `NOT_CONNECTED`。

下述租户服务/工单段落为历史 clean-SHA 证据，继续保留：

租户服务/工单纵切已从内部简版状态机补齐为 Party 绑定的完整本地产品闭环：数据库派生 User→Party→园区主体授权；员工代受理与租户自助受理；不可变派单规则草稿/发布/显式退役、确定性自动派单和人工改派；响应/解决 SLA；Decimal 版本报价及租户决定；追加式人工/材料/外包/其他成本和冲正；完工证据、返工/验收及一次性评价。旧 Java/前端证据只证明 `repair_order` CRUD 和 UI 流程表象，没有把无后端路由的按钮算作旧能力完成。

本轮新增前向迁移 `x0a68c3d5e42` 及后续硬化 `y1b79d4e6f53`，没有修改已应用历史。PostgreSQL 16 fresh base→head、唯一 `current == heads`、down -1→up、metadata、复合租户/园区外键、评价唯一性、并发派单和并发验收均通过。新增并发验收测试首次暴露 ACCEPTED/REWORK 可因锁前预读双提交；修复为先锁聚合后判幂等与版本，验证恰好一个成功、另一个 409。

精确提交 `ffa72e2` 全量脚本 33/33 步 exit 0、554,324 ms：342 pytest（161.50 s）、10 租户 worker 零失败、全部合成 ETL、1000 请求/并发 25 性能 p95 302.333 ms、132.87 RPS、0 错误、1,383,498 bytes/114 表备份删除恢复、前端 ESLint/vue-tsc/6 Vitest/141 modules production build、59 Playwright、13 OpenAPI 契约及 YAML strict、OpenSpec strict 86/86、942 文件 secrets scan 和资源清理全部通过。工单 runtime/YAML 25 个方法精确一致；机器报告为 `evidence/tenant-service-work-order-lifecycle/acceptance-clean-ffa72e2.json`。工单 39/39 任务及 8 份主规格同步完成，归档后 OpenSpec strict 93/93。

安全复核关闭了受理幂等键在 Party 校验前返回旧结果、报价/验收同键异命令未拒绝、伪造 JWT 权限、重复 query、未知字段和子资源 IDOR；Playwright 端口释放竞争和旧主链“一步完成工单”也已整改并回归。三张人工截图覆盖桌面报价详情、390px 租户验收评价和离线保留/重试，无横向溢出或固定抽屉拼接伪影。

工单合成 ETL 对 3 工单、6 事件、1 隔离记录完成 dry/interruption/apply/reapply/reconcile/rollback，原始 PII、孤儿事件、伪造报价/评价/外送均为 0。真实 `repair_order` schema/状态字典、脱敏快照、主键映射、附件清单和生产切换授权仍缺失，因此真实迁移保持 `BLOCKED`；员工移动端、租户小程序、设备巡检/IoT、库存及外部通知也没有被本纵切外推为完成。

下述应收段落为更早纵切 clean-SHA 证据，继续保留：

应收纵切已从基础登记补齐到本地产品闭环：当前合同版本履约计划的出账预览/应用和来源血缘；单笔/批量到账、渠道连接真相、确定性匹配候选及规则理由；禁止自动过账的财务确认、异常核对和经理争议复核；多账单分配、预收未分配余额、后续核销与追加式冲正；L1-L4 账龄、案件/记录/待办、hold、调整双人审批和结清联动。外部银行/支付仍明确 `NOT_CONNECTED`，不把模拟到账或本地文件导入写成真实联通。

本轮新增 `u7d35f0a2b19`、`v8e46a1b3c20`、`w9f57b2c4d31` 三个前向迁移且不修改已应用历史；PostgreSQL 16 空库 base→head、`current == heads`、down w9→v8→up w9、metadata 契约、21 项核心数据库约束、资金并发/重放均通过。审查中发现并关闭了三个真实 P1：ALL 园区范围绕过外租户园区、重复查询参数污染、Application 直接构造 ORM；对应加入租户园区归属校验、16 个数据库级复合租户外键、全局重复 query 参数 400 门禁和 repository factory 分层回归。

精确 SHA 全量后端为 335 passed、0 failed（151.64 s）；前端 vue-tsc、ESLint、3 文件/6 Vitest、141 modules production build 均通过；真实 PostgreSQL/FastAPI/production Vite 的应收 Playwright 为 2/2、23.0 s。真实 HTTP 8 端点、1000 请求、并发 25、0 错误，p95 352.701 ms、107.841 RPS；服务停启前后 readiness 与 receipts/payments/cases 的 5/5/5 签名一致。Python `pip-audit --local` 与 `npm audit --audit-level=high` 均为 0 已知漏洞；本地 `kwzy-api` 因非 PyPI 包由应用测试/SAST 覆盖。应收 45/45 OpenSpec 任务已完成，8 份 delta 同步主规格并归档；归档后 strict 85/85，归档暂存树 915 文件 secrets scan 0 hits。

clean-SHA 前复验没有沿用早期小数据性能：开发 `DEBUG=true` 首轮 p95 6756.641 ms，切换既定生产性能配置后仍为 1896.077 ms。根因是自动出账预览逐计划查历史冲突、Payment 分页逐笔查分配余额；改为批量查询并新增 SQL 查询数回归后，同一累积库与未降低的 500 ms 门槛通过。390px 到账列表同时从横滑表格重排为完整字段卡片，浏览器断言 table/body 均无横向溢出。

合成财务 ETL 已完成 dry-run、中断事务回滚、首次 apply、零新增幂等重跑、数量/金额/分配/孤儿/PII/外部送达对账和 schema rollback；来源/目标账单金额均为 1500.00，错配、超配、孤儿、未脱敏账号和虚假外送均为 0。`pg_dump -Fc` 备份 630,540 bytes，SHA-256 `acc85e479b310efd8b391251657ea85769cfcfb987ff9d4f87b4acd61bd1140a`，删除/重建临时恢复库后精确恢复 `w9/bills20/receipts5/payments5/cases5/adjustments0` 并清理恢复库；真实旧财务 schema/脱敏快照、供应商凭据和生产切换授权仍保持真实阻塞。

四张关键截图覆盖桌面分配抽屉、桌面账龄催缴、平板到账单箱和 390×844 手机到账单箱；手机到账列表使用字段完整卡片，E2E 同时断言 table/body 无横向溢出；人工复核无假图表、固定成功按钮、乱码或敏感账号原文。综合机器证据为 `evidence/receivables-collection-lifecycle/acceptance-clean-1a11cfe.json`。

以下 Party 企业画像段落为上一纵切 clean-SHA 证据，继续保留：

Party 企业画像精确提交 `3680582` 的完整脚本 31/31 步 exit 0、521,943 ms：PG16 fresh base→唯一 head `t6c24e9f1a08`、严格 current=heads、t6 down 到 s5 后再 up、全仓 Ruff 错误级规则、315 后端测试、8 租户 worker、全套合成 ETL、四条真实 HTTP 旅程、1,000 请求性能、备份删除/恢复、前端门禁、57 条 Playwright、11 条 OpenAPI strict、71 项当时 OpenSpec strict、856 文件 secrets scan 和资源清理均通过。实现提交 `e7d7263` 与 N+1 修复 `3680582` 已正常推送；未 force、未触达 main、未连接生产。

本纵切新增组织主体企业画像、精确完整度、关联企业图、证件指纹与同范围附件、标签来源、追加式风险及处置，并以数据库派生权限隔离受控证件/风险。三张截图人工复核无假数据、遮挡、乱码、敏感原文或移动端横向溢出；21 阶段真实 HTTP 覆盖 422、403/404 路径归属、409 乐观锁、环拒绝、幂等、完整度和目录对账。clean-SHA 性能为 p95 225.85 ms、172.617 RPS、0 错误；外部工商状态明确 `NOT_CONNECTED`。

首轮 clean-SHA 在性能步骤以 p95 535.126 ms 真实中止。根因是企业目录对每行 Party 分别查询园区和风险形成 N+1；整改为两个租户受限批量查询并增加查询数防回归后，相同门槛从空库完整复跑通过。失败报告 `acceptance-clean-e7d7263-performance-failure.json` 保留，500 ms 门槛未降低。

Party synthetic ETL 对 2 个画像、1 条关系、1 个证件、1 个标签、1 个风险和 2 条隔离记录完成 dry/interruption/apply/reapply/reconcile/rollback；没有写入原始组织标识列，个人身份材料与孤儿关系均进入隔离。真实旧 schema/脱敏快照、外部工商合同/凭据和生产切换授权继续阻塞。

Party 的 9 份 delta 已智能合并到主规格并归档为 `2026-08-14-complete-party-enterprise-profile`；归档副本为 43/43 任务，归档后 OpenSpec strict 77/77。CRM 的 `revoked` 语义冲突仍保留 active，没有借 Party 归档一并掩盖。

最新能力矩阵为 11 项 `IMPLEMENTED_AND_VERIFIED`、1 项 `BLOCKED`、8 项 `MISSING`。因此本报告仍是 `BLOCKED`；档案/签章/印章组合能力的本地 PC 产品闭环关闭，绝不外推为合法电子签 live、员工移动端、小程序、全业务、真实旧数据迁移或生产完成。

### 当前交付基线

| 项 | 当前独立核验结果 |
| --- | --- |
| 分支 / 精确 HEAD | `feat/full-rebuild-completion` / `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` |
| 实现与修复提交 | `95fa44d` 档案/签章/印章业务；`89c83b2` 信封行定位回归；`83697f9` Party 保存就绪竞态；`b04d738` 移动无截断与初版证据 |
| 远程同步 | 精确 HEAD 已正常、非 force 推送至 `origin/feat/full-rebuild-completion`；本轮未触达 main |
| 工作树保护 | 全量 Playwright 重生成的其他纵切 24 张截图属于既有用户修改，保持未暂存且不删除/不还原；本轮只提交档案证据、总控文档和 OpenSpec 收尾 |
| 运行入口 | API `uvicorn app.main:app`；PC `npm run dev` / `npm run build`；员工移动端和租户小程序无目录/启动方式 |
| 环境与敏感文件 | `.env.example` 三处均为非生产占位；1,041 个 tracked/untracked non-ignored 文件扫描 0 hits；未自动连接生产 |
| 生产授权 | `NOT_AUTHORIZED / NOT_EXECUTED`；真实 provider、不可逆迁移和生产部署继续等待独立人工授权 |

## 1. 初始 repair 基线（历史证据）

| 项 | 独立核验结果 |
| --- | --- |
| repair 分支 | `audit/full-rebuild-final-repair` |
| 实现提交 | `a9267d4c30096a7c80d66588ab06bc6838b32b0d`；114 files，14,830 insertions，2,190 deletions |
| 验收文档提交 | `be730439610fb213eefc280f851d5e86721b75a6`；已正常、非 force 推送到 `origin/audit/full-rebuild-final-repair` |
| 本地 main | `64417c61177f4e47463062fbebe48f7c54d1bc94` |
| origin/main | 2026-08-14 终验前 `git fetch origin --prune` 后为 `4be4fe0c060543178ae71783d1ce0b29fad235fe` |
| 同步关系 | main 比 origin/main ahead 2；repair 验收文档检查点比 origin/main ahead 4；无远端新增提交 |
| 工作树 | 精确 SHA 验收前 clean；报告和构建输出在 gitignored `infra/local-staging/out` |
| remote | `https://github.com/lintao19568886548/kwzy-python.git` |
| 禁止项 | 未 force push、未连接生产、未改历史迁移、未覆盖用户修改、未部署生产 |
| 运行版本 | Python 3.10.11；Node 22.14.0；npm 11.4.1；Docker 29.6.2；Compose 5.3.1；PostgreSQL 16.14（Docker） |
| 原生 DB 客户端 | 主机未安装 psql；所有 PostgreSQL 权威验证在 `postgres:16` 隔离容器中执行 |
| 应用入口 | API：`uvicorn app.main:app`；PC：`npm run dev` / `npm run build`；生产示例见 `infra/production` |
| 三端事实 | PC 位于 `apps/web`；员工移动端、租户小程序无应用目录和启动方式 |

环境样例为 `apps/api/.env.example`、`infra/postgres-test/.env.example`、`infra/production/production.env.example`。最新精确提交复验的敏感文件名检查与 1,041 文件内容扫描通过；未发现被跟踪的真实密钥、Token、密码、数据库文件或 PII。样例值均为明确的非生产占位。

## 2. 整改提交内容

实现提交主要包含：

- 合同 V2：多单元/多费用、确定性费用计划、审批和签章准备门禁、不可变版本链、七类变更、续租、退租结算、WorkItem、乐观锁、幂等和失败回滚。
- 安全：附件 IDOR 修复、密码策略、JWT/会话撤销、登录和生产 fail-closed、Host/CORS/CSRF/安全头、园区/租户范围、生产 provider 门禁。
- 依赖：用 PyJWT 替换含无修复 `ecdsa` 漏洞链的 python-jose；Vitest 升到 4.1.10；Python 和 npm 已知漏洞均为 0。
- 数据：新增 `k7f35a0b2d19`、`l8a46b1c3e20`、`m9b57c2d4e31` 三个迁移，不修改历史迁移；补齐 ORM 索引、BigInteger 和时间戳 nullability 契约。
- API/PC：合同全套 API/OpenAPI、合同工作台/治理抽屉/差异展示/响应式与滚动复位，API 分页/隐私/scope 回归。
- 集成：持久化 outbox、幂等唯一约束、local/fake 与生产 fail-closed 适配器。
- 工程：真实 HTTP 性能门禁、PG ETL/备份恢复、生产 Dockerfile/Compose/Nginx、就绪探针/连接池、GitHub Actions 验收与依赖漏洞门禁。
- 租户服务/工单：园区与租户受限报修、规则版本发布/退休、确定性自动派单与改派、报价、处理、企业联系人验收/返工/评价、WorkItem/通知 outbox、审计、乐观锁和幂等；不把 PC 移动窄屏冒充租户小程序。
- 证据：桌面/平板/移动窄屏截图、机器验收 JSON、性能 JSON、迁移边界和操作 Runbook。

## 3. Alembic 与 PostgreSQL 16

唯一迁移链尾部为：

```text
j6e24f9a1c08 -> k7f35a0b2d19 -> l8a46b1c3e20 -> m9b57c2d4e31 -> n0c68d3e5f42 -> o1d79e4f6a53 -> p2e80a5b7c64 -> q3f91b6c8d75 -> r4a02c7d9e86 -> s5b13d8e0f97 -> t6c24e9f1a08 -> u7d35f0a2b19 -> v8e46a1b3c20 -> w9f57b2c4d31 -> x0a68c3d5e42 -> y1b79d4e6f53 -> z2c80e5f6a64 -> a3d91f6a7b75 -> b4ea2c7d8f86 (head)
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

- 空库 base → head 通过，`current == heads == b4ea2c7d8f86`；b4 down 到 a3 再 up 通过，`alembic check` 无待生成迁移。
- 备份、删除测试恢复库、重建和恢复复核当前 head 与 146 张表；核心表、索引、外键、唯一性和 boolean 契约由 metadata/PG 测试覆盖。
- ORM metadata 与迁移契约测试通过；既有 Party、财务、工单、设施约束继续有效，档案新增复合租户/园区/父子引用、档号、活动 hold、借阅/处置、保管、用印回执和签章事件约束，数据库拒绝跨租户、跨园区、职责冲突和异载荷重放。
- 合同、租控锁房、收款/核销、工单验收、设施任务/告警、档案/用印和 outbox 幂等的 PG 并发/竞态/回滚测试通过；库存域未实现，不能声称库存并发通过。
- 禁止用 `create_all` 代替验收；完整脚本与 E2E seed 均以 Alembic 初始化。

## 4. 测试和耗时

当前档案精确 SHA `b04d738` 全量验收为 36/36 步、366 pytest、61 条 Playwright、3 文件/6 Vitest、147 modules production build、15 条 OpenAPI 契约及 YAML strict、OpenSpec strict 102/102、1,041 文件 secrets scan 0 hits，耗时 609,589 ms。档案 21/21 真实 HTTP、PG 并发与职责分离/幂等回归通过；归档前 41/41 任务。下表保留初始 repair 精确 SHA `a9267d4` 的历史基线，不能覆盖最新数字。

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

合成迁移对 core、Identity、Asset、CRM、Contract、组织治理、审批审计、工作台自动化、资产组合、Party 企业画像、应收闭环、租户服务/工单、设施设备和档案/签章/印章执行 dry-run、首次 apply、故障中断回滚、幂等重跑、分布/数量/金额/面积/孤儿/重复/PII/哈希对账及 schema rollback。

合同合成数据结果：2 Parties、3 Contracts、3 Versions、4 Units、3 Charges、3 Schedules、2 Documents、2 Reminders、1 Quarantine；占用面积 221.50、押金 27,000、费用 8,800；重复与孤儿均为 0，报告不持久化原始 PII。

当前档案精确 `b04d738` 全量验收使用 `pg_dump -Fc` 生成 1,595,978 bytes dump；删除并重建临时恢复库后 `pg_restore`，恢复 146 张表并再次删除恢复库。档案合成迁移为 2 分类/2 档案/2 版本/2 隔离，伪造印章、保管、提供方和事件为 0。临时 dump 按安全策略未提交 Git。

真实旧库仍不可验：未取得经授权 schema dump/脱敏快照，无法证明真实字段/枚举/PII 映射、全量金额面积、CDC、停写、切换和回切。故结论只能是：

```text
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_SYNTHETIC_ONLY
```

## 6. HTTP 性能、可靠性和运维

最新全量脚本真实 loopback HTTP 使用登录后的 12 个工作台、事件、合同、Party、资产、档案、印章和签章接口，1000 请求、并发 25、预热 40：

- 0 failures，错误率 0.0%，146.259 req/s。
- p50 162.934 ms，p95 240.541 ms，p99 321.62 ms，max 354.246 ms。
- 门槛 p95 ≤ 500 ms、错误率 ≤ 1%、吞吐 ≥ 20 req/s，结果 PASS。
- 档案专项真实 HTTP 为 21/21 阶段、926.41 ms，验证跨租户隔离、沙箱投递和外部提供方 fail-closed；全量精确提交报告保存在 `evidence/records-signature-seal-governance/acceptance-clean-b04d738.json`。

生产契约提供显式 PG QueuePool 上限/超时/回收、`/health/ready`、非 root 镜像、只读文件系统、tmpfs、drop all capabilities 和 no-new-privileges。API 镜像用户为 `kwzy`，Web 为 UID `101`。

隔离容器栈实际启动后，数据库、API、Web 分别重启；重启前后 API 代理均按预期返回 401，最终 readiness 为 `{"status":"ready","database":"up"}`，`CONTAINER_RESTART_RECOVERY=PASS`，所有临时容器/网络/卷已清理。

这些是本机核心查询的性能与恢复证据，不是远程预发大数据容量、生产 SLO、监控告警或跨区灾备验收，因此总体运维和性能状态保持条件通过。

## 7. 安全验收

已验证范围包含认证、refresh 轮换/重放/撤销、密码策略、生产弱 JWT 拒绝、RBAC、tenant/park scope、附件 IDOR、跨租户批量访问、参数/分页限制、CSRF/Host/CORS/安全头、文件大小/归属/服务端哈希、审计、幂等和 PG 竞态；档案纵切另覆盖高风险用印职责分离、命令指纹、提供方事件验签边界和 live fail-closed。

静态与运行扫描分类：

| 扫描项 | 人工分类 |
| --- | --- |
| TODO/FIXME/pass/NotImplementedError | runtime 的 `NotImplementedError` 仅在抽象 provider 接口；`pass` 为异常类/枚举容错，无固定成功业务实现 |
| stub/mock/placeholder/demo/fake | AI 固定 stub 未挂载，计 `MISSING`；synthetic ETL 与 local/fake provider 有环境标识，不计生产完成 |
| 静态假图表 | `analytics` 未挂载且无真实驾驶舱，计 `MISSING` |
| 未挂 router | 已实现业务 router 均挂载；`ai_assist`、`analytics` 未挂载并计缺失 |
| 前端本地 JSON/假按钮 | 未发现业务页读取本地 JSON；关键合同/租控按钮由真实 HTTP/E2E 覆盖 |
| API/OpenAPI 漂移 | 已修复，15/15 契约、档案/印章/签章 33 个 runtime/YAML 方法对和 YAML strict 通过 |
| Application→ORM / Router 查 DB | 应收审查发现的 Application 直接构造 ORM已下沉 repository factory；架构回归测试和人工检索未发现当前已实现纵切新增违规 |
| 默认管理员/开发免鉴权/弱 JWT | 生产/预发 fail-closed；本地测试账号只用于隔离验收 |
| 密钥/Token/DB/PII | 精确提交复验 tracked + untracked non-ignored 1,041 文件扫描通过、0 hits；既有 clean-SHA 证据继续有效；企业证件只保留指纹与掩码，应收账号只保留掩码，档案合成 fixture 无真实 PII/密钥，环境样例为非生产占位 |
| 历史迁移/多 head | 未修改历史迁移；新增修复迁移；唯一 head |
| 外部集成虚假完成 | 文档和运行时均区分 fake/local、fail-closed 与 live verified |

没有发现未关闭 P0；已实现范围内没有未关闭安全 P1。但 IDOR/XSS/CSRF/SSRF/开放重定向等结论只覆盖当前挂载接口，不能替代缺失业务域和远程 DAST。

## 8. 三端、角色和 UI

PC 真实浏览器验证使用 PostgreSQL、FastAPI、生产 Vite 构建和真实 HTTP；当前全量 61 条 Playwright 无 skip。档案截图人工复核覆盖桌面/平板签章提供方与信封真相、390px 档案离线重试；既有合同/组织/审批/工作台/资产/Party/应收/工单/设施证据继续保留。页面无假数据、乱码、遮挡或移动端横向溢出；证据位于 `evidence/records-signature-seal-governance/` 等受信目录。

可验证角色切片包括系统管理员、受限用户、资产查看者、招商查看者、合同查看/提交/审批角色、基础财务/物业工单操作和 PC 企业联系人验收。决策管理层、区域/园区经理、完整招商/财务/物业岗位只能算窄功能证据；企业租户管理员与企业员工的独立端仍不存在，不能验收。

高级浅色后台、合同/租控响应式切片、租控矩阵/几何地图/列表/空置/到期/分析、全局搜索/快捷命令入口、右侧 AI 助手入口以及用户→角色→服务器默认的首页组件配置已有真实证据；首页工作项提供受限原单深链。深色经营驾驶舱、完整会计指标口径下钻、多园区比较和两端仍未完成；资产分析仅是挂牌经营视图，不冒充驾驶舱或会计收入。员工移动端和租户小程序没有启动方式或 E2E。

## 9. 旧系统与外部集成

旧 Java 证据仓静态规模为 54 Controllers、约 484 HTTP mappings、316 Vue 文件、30 SQL DDL 表。当前 Python 仓库缺少两端且仍有 8 个组合能力为 `MISSING`、1 项迁移为 `BLOCKED`，因此旧系统替代为 `BLOCKED`。

| 集成组 | 代码状态 | 真实状态 |
| --- | --- | --- |
| SMS/通知/对象存储 | local/fake + outbox + 生产 fail-closed | 未获凭据，NOT_LIVE |
| 合同/档案签章 | 提供方注册、信封/参与人/事件、非法律 SANDBOX、生产 fail-closed | 未选/未验合法厂商，NOT_CONNECTED |
| 微信/邮件 | 配置门禁或局部端口 | 未联调，NOT_LIVE |
| 银行/聚合支付/税票/财务软件 | 完整适配器缺失 | MISSING |
| OCR/档案/印章/存证 | 本地档案/印章业务已闭环；外部 OCR/CA/时间戳/存证/硬件适配器缺失 | LOCAL_PRODUCT_ONLY / NOT_CONNECTED |
| 门禁/停车/视频/消防/能耗/IoT | 本地设施/巡检/告警业务已闭环；真实厂商适配器缺失 | LOCAL_PRODUCT_ONLY / NOT_CONNECTED |
| OA/ERP/HR/采购/协作平台 | 缺失 | MISSING |
| 云/私有模型 | AI 业务层缺失 | MISSING |

## 10. P0/P1/P2 与责任边界

| 级别 | 未关闭数 | 项目 |
| --- | --- | --- |
| P0 | 0 | 当前证据未发现 P0 |
| P1 | 6 | 员工移动端；租户小程序；8 项能力矩阵缺失的产品闭环；真实旧数据迁移；外部适配器完整性/真实联调；远程预发监控容量灾备 |
| P2 | 0 | 本轮可在当前权限内修复的 P2 已关闭；上游 TestClient 弃用提示记为 INFO |

没有任何 `APPROVED_DEFERRED` 或 `APPROVED_RETIRED`。建议责任人不是虚构姓名：

- 产品/业务负责人：决定缺失能力优先级，并对退休/延期给出书面依据。
- 数据负责人/DBA：提供经授权 schema dump、脱敏快照、对账口径和切换窗口。
- 集成负责人/安全负责人：提供沙箱协议、短期凭据、回调域名和验签要求。
- SRE/运维负责人：提供远程预发，执行监控告警、容量、重启/灾备和回切演练。
- 生产变更审批人：单独授权生产部署；当前未授权。

## 11. 最终判定

能力矩阵汇总为 11 项 `IMPLEMENTED_AND_VERIFIED`、1 项 `BLOCKED`、8 项 `MISSING`。完整细节见 `full-rebuild-traceability-matrix.md`。因为 P1 不为 0、两端缺失、真实迁移和旧系统替代未完成，完成分支不得合并 main。

```text
KWZY_INDEPENDENT_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_BUSINESS_CLOSURE=BLOCKED
KWZY_BACKEND_REBUILD=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
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
