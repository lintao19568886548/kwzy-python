# 瞰维智管 V2 独立终验整改登记表

> 更新：2026-08-15（Asia/Shanghai）
> 最新精确提交验收：档案/签章/印章 `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` 的 36/36 门禁、366 后端、61 浏览器、性能、备份恢复、OpenAPI/OpenSpec 与 1,041 文件密钥扫描通过；实现和修复已正常推送。
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
| FIN-001 | P1 | 账收仅有基础登记/分配/简版案件，缺自动出账、到账单箱、可解释匹配、异常复核、多账单/预收核销和分级催缴 | 完成履约计划出账、到账/候选/财务确认/经理争议、多账单与未分配余额、L1-L4、调整双人审批及 PC 真栈；PG16、335 pytest、真实 HTTP、2 条 Playwright、合成 ETL、备份恢复通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| SEC-005 | P1 | 到账导入持有 ALL 园区范围时未验证传入园区属于当前租户；重复查询参数可造成参数污染；财务表缺数据库级复合租户外键 | 服务层验证租户园区归属；全局重复 query 参数 400 门禁；新增 w9 的 16 个复合租户外键和 IDOR/直写/参数污染回归 | CLOSED |
| ARCH-001 | P1 | 应收 Application service 直接构造 SQLAlchemy ORM，违反分层依赖边界 | ORM 构造下沉 repository factory，Application 仅传领域数据；架构扫描与全量 335 pytest 通过 | CLOSED |
| PERF-004 | P1 | 应收查询和批量预览缺真实 HTTP 性能基线；clean-SHA 前累积库复验先后暴露 DEBUG 日志放大和两个 N+1，p95 6756.641/1896.077 ms | 强制按生产契约 `DEBUG=false`；批量查询计划冲突和 Payment 分配余额并加入 SQL 查询数回归；精确 `1a11cfe` 8 端点、1000/25、0 错误，p95 352.701 ms、107.841 RPS，500 ms/20 RPS 门槛未降低 | CLOSED_LOCAL_GATE |
| WO-001 | P1 | 现有工单仅内部简版状态机，缺租户主体、规则派单、SLA、报价、成本、返工验收和评价 | 新增完整聚合、25 个受控 API 方法、PC 租户/员工工作区、PG16 并发与真实浏览器旅程；精确 `ffa72e2` 的 342 pytest、59 Playwright、合成 ETL、性能和恢复门禁通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| SEC-006 | P1 | 工单同键重放可在校验 Party/载荷前返回旧结果，伪造 JWT 权限、参数污染和复合租户引用需要独立门禁 | 先校验 Party/园区/命令语义再重放；同键异报价/验收决定返回 409；权限来自数据库；未知字段、重复参数和跨租户/园区/联系人/子资源均有 API/PG 回归 | CLOSED |
| CONC-001 | P1 | 首次新增并发验收测试证明 ACCEPTED 与 REWORK 可因预读对象缓存而双提交 | 在读取幂等记录前以 `SELECT FOR UPDATE` 锁定工单并基于锁后版本判定；PG16 并发测试证明恰好一个提交、另一个 `WORK_ORDER_VERSION_CONFLICT` | CLOSED |
| OPS-004 | P1 | Playwright 全栈启动在杀死旧端口后立即拉起，可能连接残留 4173 进程并产生伪结果 | 启动前轮询确认 API/Web 端口真正释放，再启动 PG/FastAPI/生产 Vite；聚焦与 59 条全量 E2E 均通过 | CLOSED |
| API-002 | P1 | 旧主链测试仍按“一步完成工单”调用，未执行新幂等、派单、开工和完工证据契约 | 主链改为必填 Idempotency-Key、合格处理人派单、expected_version 开工及带处理摘要/无证据原因的完工待验收；完整 342 pytest 通过 | CLOSED |
| FAC-001 | P1 | 现仓缺完整设备、周巡检、异常转工单和 IoT 告警业务纵切 | 新增 16 张设施表、唯一前向迁移 z2、32 个受控 API 方法、独立 worker、PC 真栈和合成迁移；精确 `e28678b` 的 352 pytest、60 Playwright 与 35/35 总门禁通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| SEC-007 | P1 | 巡检执行角色进入页面时被额外要求计划读取权限，形成授权正确但 UI 403；设施子资源/来源事件亦需独立隔离门禁 | 分离 `inspection:execute` 与 `inspection:read` 数据加载；设备/模板/计划/任务/绑定/告警均按租户/园区 fail closed，伪造权限、参数污染和精确重放有 API/PG 回归 | CLOSED |
| UI-002 | P1 | 告警确认后的异步刷新会清空已输入的必填解决原因，真实浏览器无法完成解决 | 仅在首次打开告警时初始化原因；刷新保留用户输入，真实 PG/FastAPI/production Vite 告警确认→解决→关闭旅程通过 | CLOSED |
| MIG-LOCAL-002 | P1 | 设施旧数据缺少可重复执行、隔离、对账和回滚演练 | 合成消防/电梯/变压器/厂务数据完成 dry/interruption/apply/reapply/reconcile/rollback；4 台设备、4 条历史、1 条隔离精确对账且不伪造计划/绑定/告警 | CLOSED_SYNTHETIC_SCOPE |
| RECORDS-001 | P1 | 现仓只有附件元数据和合同 fake 签章，缺档案保管/借阅/处置、印章保管/用印和可证明的签章真相 | 新增 16 张表、两条前向迁移、33 个受控 API 方法、PC 真栈与合成迁移；精确 `b04d738` 的 366 pytest、61 Playwright、21/21 真实 HTTP 和 36/36 总门禁通过 | CLOSED_LOCAL_PRODUCT_SCOPE |
| SEC-008 | P1 | 沙箱合同签署会伪造法律 `SIGNED`；高风险用印缺申请/最终审批/执行职责分离；执行幂等键未绑定完整命令，附件版本完整性边界不足 | 沙箱只投影非法律信封真相，live 未连接即 fail closed；高风险三角色分离，仅有审计原因的显式 override；请求指纹绑定回执，同键异载荷冲突；附件同范围和服务端 SHA-256/完整性 hold 的 API/PG 回归通过 | CLOSED |
| UI-003 | P1 | Party 企业画像在刷新完成前提示保存成功，用户紧接着提交关系时因共享 `saving` 状态静默丢弃操作 | 成功提示移到 `await load()` 后；Party 3 条与档案 1 条聚焦旅程、61 条全量 Playwright 均通过 | CLOSED |
| UI-004 | P1 | 档案页 390px 的第三个页签和六列表格字段依赖横向滚动，视觉证据不满足无截断口径 | 页签三等分；档案/信封表在窄屏重排为带字段标签的完整卡片；新增 viewport/tab/table 三重溢出断言，真实浏览器专项通过 | CLOSED |
| MIG-LOCAL-003 | P1 | 档案旧数据缺可重复执行、中断恢复、隔离、二进制/哈希对账和回滚演练 | 版本化合成元数据/二进制 fixture 完成 dry/interruption/apply/reapply/reconcile/rollback；2 分类/2 档案/2 版本/2 隔离且不伪造印章、保管、提供方或事件 | CLOSED_SYNTHETIC_SCOPE |

## 未关闭 P1

| ID | 问题 | 当前证据 | 关闭条件 | 责任人/状态 |
| --- | --- | --- | --- | --- |
| CAP-001 | 员工移动端缺失 | 无应用目录/启动方式/E2E | 建立独立端，接真实 API，完成现场任务/审批/巡检/维修等角色旅程 | 产品负责人 + 移动端负责人（待指定）；MISSING |
| CAP-002 | 租户微信小程序缺失 | 无应用目录/启动方式/E2E | 完成缴费、报修、访客、预约、租户隔离和小程序 E2E | 产品负责人 + 小程序负责人（待指定）；MISSING |
| CAP-003 | 其余组合业务闭环缺失 | 档案/签章/印章本地纵切关闭后，能力矩阵仍有 8 项为 MISSING | 按矩阵逐项实现，或取得有依据/责任人的退休或延期批准 | 产品/领域负责人（待指定）；MISSING |
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
