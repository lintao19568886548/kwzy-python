# 瞰维智管 V2 独立终验整改登记表

> 更新：2026-08-14（Asia/Shanghai）
> 最新 clean-SHA 验收：Party 企业画像精确提交 `36805823ad2e88311b9744e9e720b282b7cc74c8` 31/31 门禁通过，已正常推送。
> 原则：关键词命中必须人工分类；`CLOSED` 仅表示对应缺陷已修复并回归，不外推为全产品完成。

## 已关闭问题

| ID | 级别 | 问题 | 整改与回归 | 状态 |
| --- | --- | --- | --- | --- |
| SEC-001 | P0 | 附件读取存在跨租户/归属绕过风险 | repository/service/router 强制 tenant、owner、业务归属；IDOR 回归 | CLOSED |
| SEC-002 | P0 | 生产环境可能沿用开发身份/弱配置 | production/staging 禁止匿名、bootstrap、默认/短 JWT、通配 CORS/Host 和 SQLite | CLOSED |
| SEC-003 | P1 | 密码、refresh/replay/撤销和用户停用边界不足 | 密码策略、refresh 轮换、重放检测、token version、即时撤销；认证专项 29/29 | CLOSED |
| SEC-004 | P1 | 缺统一安全头/Host/CSRF 边界 | 中间件与回归测试；真实浏览器无 console error/warn | CLOSED |
| DEP-001 | P1 | python-jose→ecdsa 无修复漏洞；Vitest/Vite 漏洞 | 改用 PyJWT；Vitest 4.1.10；pip-audit 与 npm audit 均 0 | CLOSED |
| DB-001 | P1 | ORM metadata 与迁移索引、序列类型和时间戳契约漂移 | 新增 `m9b57c2d4e31`，不改历史；fresh/down-up、metadata 契约通过 | CLOSED |
| DB-002 | P1 | outbox 重放缺数据库唯一幂等约束 | 新增 `l8a46b1c3e20` 和 PG 并发测试 | CLOSED |
| CONTRACT-001 | P1 | 合同仅基础状态机，缺多单元/多费用/变更版本/退租 | 合同 V2 全纵切、OpenAPI、PC、PG 并发/失败注入、ETL；精确 SHA 全验收通过 | CLOSED |
| API-001 | P1 | OpenAPI 漂移、分页/隐私/scope 证据不足 | YAML/runtime 对齐；6/6 strict；14 项专项回归 | CLOSED |
| UI-001 | P1 | 合同治理/响应式/路由滚动和差异展示缺陷 | PC 工作台、抽屉、snapshot diff、scroll reset；40 E2E 和人工截图 | CLOSED |
| PERF-001 | P1 | 无真实 HTTP 性能门禁 | loopback 登录后 1000 请求；p95 280.422 ms、141.36 RPS、0 错误 | CLOSED_LOCAL_GATE |
| OPS-001 | P1 | 无生产容器、readiness/pool/CI/Runbook | 非 root/只读/cap-drop 容器、PG pool/readiness、CI、Runbook、栈启动和重启恢复 | CLOSED_LOCAL_GATE |
| MIG-LOCAL-001 | P1 | 合同迁移缺幂等/中断/对账/回滚 | 合成 PG16 dry/apply/interruption/idempotent/reconcile/rollback + 备份恢复 | CLOSED_SYNTHETIC_SCOPE |
| WB-001 | P1 | 统一工作台仅固定摘要，缺事件/规则/通知/调度/多角色布局和可恢复投递 | 完成事务事件、受限版本化规则、收件人隔离通知、持久调度/worker、来源待办、用户/角色布局、PC 控制面；277 pytest、真实 HTTP、50 E2E 和 PG 并发通过 | CLOSED |
| PERF-002 | P1 | 首轮工作台性能 p95 946.484 ms，事件列表 N+1、布局重复/串行查询且本地性能栈开启 SQL DEBUG | 合并消费者、摘要、待办、通知、健康和布局查询；按生产契约 DEBUG=false；clean-SHA 同一 1000/25 门槛 p95 250.49 ms、146.018 RPS、0 错误 | CLOSED_LOCAL_GATE |
| OPS-003 | P1 | 全量脚本可被后续命令覆盖性能进程退出码并误记 PASS | 每步重置退出码并在 Docker/Alembic/性能/HTTP/备份恢复/OpenAPI 后立即 `Assert-NativeSuccess`；p95 729.289 ms 的中间轮次已真实中止为 FAIL，最终 28/28 PASS | CLOSED |
| ASSET-001 | P1 | 业态仍为自由字符串，缺模板版本、地图/空置/到期/分析与完整响应式状态 | 七类版本化模板、精确单元版本绑定、真实空间几何、多视图 PC、PG/HTTP/52 E2E/ETL 全通过；外部 GIS/CAD/BIM 明确 NOT_CONNECTED | CLOSED_LOCAL_PRODUCT_SCOPE |
| ACC-001 | P1 | 全量脚本未真正拒绝多 Alembic head/current 漂移，且失败时丢失子命令输出、中文日志乱码 | 唯一 head/current 硬断言覆盖 fresh 与 down/up；保留失败输出并强制 UTF-8；三轮真实执行验证 | CLOSED |
| ASSET-002 | P1 | 提交前审查发现数据库可写入跨租户模板引用、显式模板可跨业态、几何可退化/自交且不可用单元误计挂牌潜力 | 不修改已应用 q3，新增 r4 复合租户外键；增加领域/API/PG 回归并修正空置口径；286 pytest、fresh/down-up 和 30/30 总门禁通过 | CLOSED |
| PARTY-001 | P1 | Party 仅有基础主档，缺企业画像、关联企业、受控证件、来源标签、风险闭环及真实 PC 操作 | 新增 t6 前向迁移、纯领域规则、租户/园区/字段权限、指纹化证件、并发约束、真实 HTTP/PG/PC/ETL；clean-SHA 315 pytest、57 E2E 和 31/31 总门禁通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| PERF-003 | P1 | Party 首轮 clean-SHA 企业目录逐行查询园区/风险形成 N+1，聚合 p95 535.126 ms 超过 500 ms 门槛 | 改为两个租户受限批量查询并增加查询数防回归；相同 1000/25 clean-SHA 门禁 p95 225.85 ms、172.617 RPS、0 错误 | CLOSED_LOCAL_GATE |
| FIN-001 | P1 | 账收仅有基础登记/分配/简版案件，缺自动出账、到账单箱、可解释匹配、异常复核、多账单/预收核销和分级催缴 | 完成履约计划出账、到账/候选/财务确认/经理争议、多账单与未分配余额、L1-L4、调整双人审批及 PC 真栈；PG16、334 pytest、真实 HTTP、2 条 Playwright、合成 ETL、备份恢复通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| SEC-005 | P1 | 到账导入持有 ALL 园区范围时未验证传入园区属于当前租户；重复查询参数可造成参数污染；财务表缺数据库级复合租户外键 | 服务层验证租户园区归属；全局重复 query 参数 400 门禁；新增 w9 的 16 个复合租户外键和 IDOR/直写/参数污染回归 | CLOSED |
| ARCH-001 | P1 | 应收 Application service 直接构造 SQLAlchemy ORM，违反分层依赖边界 | ORM 构造下沉 repository factory，Application 仅传领域数据；架构扫描与全量 334 pytest 通过 | CLOSED |
| PERF-004 | P1 | 应收查询和批量预览缺真实 HTTP 性能基线 | 8 个端点、1000 请求、并发 25、0 错误，p95 151.678 ms、211.529 RPS；阈值 500 ms/20 RPS | CLOSED_LOCAL_GATE |

## 未关闭 P1

| ID | 问题 | 当前证据 | 关闭条件 | 责任人/状态 |
| --- | --- | --- | --- | --- |
| CAP-001 | 员工移动端缺失 | 无应用目录/启动方式/E2E | 建立独立端，接真实 API，完成现场任务/审批/巡检/维修等角色旅程 | 产品负责人 + 移动端负责人（待指定）；MISSING |
| CAP-002 | 租户微信小程序缺失 | 无应用目录/启动方式/E2E | 完成缴费、报修、访客、预约、租户隔离和小程序 E2E | 产品负责人 + 小程序负责人（待指定）；MISSING |
| CAP-003 | 其余组合业务闭环缺失 | 应收闭环关闭后，能力矩阵仍有 11 项为 MISSING | 按矩阵逐项实现，或取得有依据/责任人的退休或延期批准 | 产品/领域负责人（待指定）；MISSING |
| MIG-001 | 真实旧数据迁移和切换无法验收 | 仅合成数据；无旧 schema/脱敏快照 | 授权数据、全量/增量/中断/回滚/金额面积数量对账和签字 | 数据负责人/DBA（待指定）；BLOCKED_EXTERNAL_EVIDENCE |
| INT-001 | 外部适配器不完整且未 live verify | 局部 fake/local/fail-closed；多数平台缺失 | 实现缺失端口，提供沙箱凭据/协议，完成验签、重试、死信、补偿和降级 | 集成/安全负责人（待指定）；MISSING_AND_BLOCKED_EXTERNAL |
| OPS-002 | 远程预发/生产容量、监控告警和灾备未验收 | 本地容器/性能/恢复通过 | 获批预发执行大数据容量、慢 SQL、连接池、告警、备份恢复/RTO-RPO/回切；生产另审批 | SRE/生产审批人（待指定）；BLOCKED_EXTERNAL_EVIDENCE |

## 分级汇总

```text
OPEN_P0=0
OPEN_P1=6
OPEN_P2=0
INFO=1  # Starlette TestClient 上游弃用提示；真实 HTTP/E2E 不受影响
```

未关闭项没有被改写为延期，也没有通过删除需求关闭。因为 `OPEN_P1 != 0`，禁止合并 main、禁止输出全量 PASS。
