## Context

现有 Investment 纵切已经有租户/园区安全的 Lead、append-only Activity、AssignmentEvent、公海领取/释放/回收、解释性房源匹配、PG 条件唯一锁和 Party/Lease 转化，PC `/leads` 也已使用真实 API。独立复核确认缺口不是重写这些能力，而是补上规则驱动归属、第一类带看、审批中心约束的意向快照和可安全接入的外部渠道。

旧 Java 的传统 `investment`、CRM/Radar、external lead、public opportunity 和 outreach 表族证明“线索来源很多且主数据分裂”，但未提供可直接照搬的自动分配与意向审批权威规则。V2 因此以当前 Lead 为唯一招商主档，外部记录只作为可审计接收事实，不恢复爬虫、企微或外呼供应商的未验证实现。

## Goals / Non-Goals

**Goals:**

- 以版本化、可发布、可预览的园区规则自动选择真实有效且有园区授权的招商人员，并在并发请求下保持确定性。
- 将带看预约与完成事实从自由文本 Activity 中提升为可查询、可冲突检测的业务对象，同时把完成事实追加回时间线。
- 将意向房源、面积、期限、价格及有效期冻结成不可变版本，通过现有版本化 Approval Definition/Request/Task 执行审批。
- 仅在已批准且仍有效的意向覆盖目标单元时允许新建或续期排他锁；转化继续受自身有效锁约束。
- 提供默认禁用、签名验证、时间窗、幂等、隔离和安全重放的通用渠道入口；不保存明文密钥，不连接未授权外部网络。
- PC、OpenAPI、PG16、真实 HTTP、Playwright、性能、ETL、备份恢复与报告形成同一纵切证据。

**Non-Goals:**

- 不恢复旧系统的公开网页爬虫、代理池、企微/短信/外呼厂商实现，也不声称任何真实渠道已联调。
- 不允许渠道请求指定内部 owner、权限、审批结论、锁或合同；这些只能由服务器规则与人工动作产生。
- 不在本纵切实现企业画像、营销评分、触达模板或 AI 推荐；它们属于后续客户画像/AI/外部适配器能力。
- 不修改已应用的 `j6e24f9a1c08` 或其他历史迁移，只在当前唯一 head 后新增迁移。

## Decisions

1. **自动分配采用已发布不可变版本与数据库串行化。** `LeadAssignmentRule` 保存园区/触发器和当前版本；`LeadAssignmentRuleVersion` 冻结策略；`LeadAssignmentMember` 冻结成员、容量、权重/顺序。执行时锁定当前版本行，过滤停用用户和无园区授权成员，按 `active_open_count / capacity`、最近分配时间、稳定顺序和 user id 选择。没有候选时进入公海并记录 `AUTO_ASSIGN_FALLBACK`。相比随机或内存轮询，这一方案可复现、可对账且适合多进程。

2. **人工覆盖与自动归属共用 AssignmentEvent。** 自动执行写 `AUTO_ASSIGN`，预览不写业务数据，人工改派仍写 `ASSIGN/REASSIGN`。Lead 的 owner/pool/lock_version 与事件、待办、审计在同一事务提交，避免双主数据。

3. **带看是独立聚合并回写不可变活动事实。** `LeadViewing` 使用 `SCHEDULED→CONFIRMED→COMPLETED`，并允许从开放状态转 `CANCELLED/NO_SHOW`；`LeadViewingUnit` 冻结 unit id 与当时版本。创建/改期以乐观锁和同一负责人时间窗冲突检查保护；只有完成动作追加一条 `VISIT` Activity 并按规则从 CONTACTING 推进到 VISITING。

4. **意向业务快照与通用审批实例分离。** `LeadIntentApplication` 持有生命周期和当前版本，`LeadIntentVersion` 保存不可变报价/期限/单元快照，`LeadIntentUnit` 保存单元及面积。提交时调用 `ApprovalService.create`，biz type 固定 `LEAD_INTENT`、biz id 固定意向 id、snapshot 不含电话等 PII。读取和门禁以 `ApprovalRequest.status` 为权威并同步本地投影。相比在招商域复制审批引擎，可复用 ANY/ALL、委托、SLA、待办和审计。

5. **批准意向是锁房的先决条件。** acquire/renew 请求必须携带同 Lead 的 approved intent id，且版本未过有效期并包含同一 current Unit/期望面积；锁记录保存 intent application/version id 以供历史对账。释放和到期不要求审批，避免无法清理库存。

6. **外部渠道以公开随机标识 + HMAC 接收，不以 JWT 或租户 id 取信。** `LeadChannel` 保存不可枚举 public id、启用状态、默认园区、允许来源和 `secret_env_key`，实际密钥只从环境读取。签名基串为版本、时间戳、事件 id 与原始 body 摘要；固定时间比较、最大时钟偏差、请求体/字段上限与 `(channel_id, external_event_id)` 唯一约束阻断伪造和重放。失败记录只保存摘要、原因和脱敏预览。

7. **渠道落地分两阶段。** 签名通过后先持久化 Inbox；规范化校验成功才以 `source_type=CHANNEL:<code>` 和稳定 source_ref 创建/复用 Lead，再按规则自动分配。业务失败进入 `QUARANTINED`，只有渠道管理员可修正映射后重放；重复事件返回同一结果，不重复建 Lead。

8. **权限全部来自当前数据库授权。** 新增 `lead.assignment_rule.read/write/run`、`lead.viewing.read/write`、`lead.intent.read/write/submit`、`lead.channel.read/write/replay`。伪造 header/body 权限、owner、审批状态或 park 均无效。

## Risks / Trade-offs

- **[审批结果与意向投影短暂不同步]** → 详情和关键命令在同一事务读取 ApprovalRequest 并刷新投影；批量 sweep 仅作修复，门禁不信缓存状态。
- **[自动分配热点行]** → 规则版本行只在短事务内 `FOR UPDATE`，候选统计有明确园区/owner/status 索引；并发测试证明不重复分配且不会丢事件。
- **[渠道密钥轮换]** → 配置允许当前/上一 secret env key 的有限重叠窗口并记录命中 key id，不记录密钥；没有可用密钥时 fail closed。
- **[外部载荷含 PII/恶意内容]** → 严格 allow-list 映射、长度/类型限制、日志脱敏、原始 body 不落审计；未知字段隔离而非猜测。
- **[意向通过后房源状态变化]** → 锁房时重新锁 Unit 并验证 current/vacant/无锁，批准不是库存保证；失败返回 409 且不改变意向事实。
- **[范围扩大影响本轮时长]** → 复用现有 Lead、Approval、WorkItem、Audit 和 PC 页面，不实现雷达评分/爬虫/营销供应商。

## Migration Plan

1. 在 `r4a02c7d9e86` 后新增一个前向 Alembic revision，创建规则/版本/成员、带看/单元、意向/版本/单元、渠道/接收箱表，并为 LeadUnitLock 增加意向外键。
2. fresh PG16 upgrade、`current == heads`、downgrade -1/upgrade，比较 ORM metadata 与索引/约束；不修改历史 revision。
3. 对既有 Lead 不自动补写虚构规则、带看或意向。默认无发布规则时沿用当前创建归属或公海行为，渠道默认不存在且关闭。
4. 合成迁移只验证可授权样例的规则、带看、意向和渠道接收事实；真实旧 schema/脱敏样本到位后另行全量/增量/中断/回切演练。
5. 回滚应用版本前先停止渠道接收与自动分配 worker，再 downgrade 新 revision；真实生产迁移与部署仍需人工批准。

## Open Questions

- 各园区的正式分配容量、工作时间和排除名单尚无业务签字；实现提供可配置规则，不填充生产默认。
- 意向审批的正式步骤、金额阈值与审批人尚无生产配置；验收使用隔离租户中显式创建的版本化定义。
- 未取得真实渠道协议、回调 IP、签名格式和沙箱凭据；本纵切只证明通用 HMAC 合约与 fail-closed 行为。
