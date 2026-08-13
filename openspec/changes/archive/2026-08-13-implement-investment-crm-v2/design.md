## Context

当前 `leads` 只有联系人、意向、负责人、粗状态和转化外键；更新 remark 会覆盖历史，列表只做租户/园区过滤，重复线索可静默创建，负责人/园区由用户手填 ID。转化调用会内部提交的 PartyService 和 LeaseService，因此 Party 已落库而后续合同或 Lead 更新失败时无法整体回滚。资产纵切已提供 current-only Unit、乐观锁、拆并血缘和 Lease 激活的 PostgreSQL 行锁，可作为房源匹配与锁房的可靠基础。

旧系统同时存在传统 `investment`、CRM lead 表族和 radar 外部线索，包含跟进、拜访、SOP、分配、房源匹配、评分和分析，但也存在双主档、巨型 Controller 和外部采集运维耦合。本设计先关闭人工/导入线索的核心 CRM，不连接旧生产库，不引入真实外部渠道。

## Goals / Non-Goals

**Goals:**

- 建立单一 Lead 聚合的重复治理、销售阶段、负责人/公海和不可覆盖的过程时间线。
- 在租户/园区/负责人权限下提供可解释房源匹配和 PostgreSQL 并发安全的限时锁房。
- 将 Lead→Party→可选 Lease DRAFT、锁房关联、待办和审计组成单事务。
- 提供口径一致的漏斗、公海与逾期指标，以及无需手填内部 ID 的 PC 招商工作台。
- 以兼容迁移、合成 ETL、OpenAPI、SQLite/PG/浏览器测试证明当前范围。

**Non-Goals:**

- 真实 radar 爬虫/代理池、企微/短信/外呼、公开商机抓取、AI 评分或自动推荐。
- 生产数据库、真实旧数据、生产部署、真实凭据和不可逆切换。
- 合同审批/签章、复杂报价审批、合同变更链和最终计费；这些由后续纵切承担。
- 员工移动端和租户小程序；本 change 只交付 PC 与可复用 API。

## Decisions

### 1. Lead 保持单一聚合，并把 status 作为销售阶段唯一事实

`leads.status` 统一为 `NEW/CONTACTING/VISITING/QUOTING/NEGOTIATING/WON/LOST/CANCELLED/MERGED`。迁移把 `FOLLOWING` backfill 为 `CONTACTING`；接口在一个兼容期接受 `FOLLOWING` 输入但规范化后只返回新枚举。新增规范化名称/电话、来源、pool 状态、分配/活动时间、下一跟进、回收期限、合并目标和 `lock_version`。

没有数据库电话唯一约束：现实中同一电话可能代理多个企业。重复由确定性候选、409 门禁和带理由覆盖治理；来源外部键则使用 tenant/source/source_ref 条件唯一约束保证导入幂等。

### 2. 活动、分配和合并采用 append-only 事实表

新增 `lead_activities`、`lead_assignment_events`、`lead_merge_links`。Lead 保存当前投影供列表与漏斗查询，历史事实不被更新/删除。阶段推进由活动命令完成，并同时维护 `last_activity_at/next_follow_up_at` 和 LEAD_FOLLOW 待办。合并只把来源标记 `MERGED` 并链接保留者，不物理搬移或删除历史。

### 3. 权限同时约束能力、园区和所有权

- `lead:read`：看本人私有线索和公海摘要；公海未领取时电话脱敏。
- `lead:write`：维护本人线索并写活动。
- `lead:claim`：领取公海线索。
- `lead:manage`：园区范围内看全量、分配、释放、回收和合并。
- `lead:lock`：匹配与锁房；仍需满足本人线索或 `lead:manage`。
- `lead:convert`：转化，并继续组合 `party:write`/`lease:write`。

所有仓储首先应用 tenant + authorized park scope，再应用 owner/pool scope；按 ID 访问不得通过 403/404 差异泄露外部租户数据。

### 4. 领取、分配、合并和锁房都使用版本与行锁

Lead 写命令要求 `expected_version`。PostgreSQL 对 Lead/Unit 使用 `SELECT ... FOR UPDATE`；SQLite 依赖同事务版本比较以支持快速测试。公海领取在锁内验证 owner 为空，只有一个请求成功。

`lead_unit_locks` 保存 `ACTIVE/RELEASED/EXPIRED/CONSUMED`、到期时间、Lead/Unit/Lease 关系和版本。数据库用 `ACTIVE` 条件唯一索引保证同一 current Unit 只有一个活动锁；取得 Unit 行锁后先惰性过期旧锁，再创建新锁。有效锁把 Unit 投影为 `RESERVED`；释放/过期在没有有效 Lease 时恢复 `VACANT`。

### 5. 匹配是确定性规则，不伪装为 AI

候选只取同园区、current、`VACANT` 且无有效锁的 Unit。面积满足度、用途匹配和租金预算分别计分，返回总分及逐项 reason，稳定按 score、面积差、unit id 排序。缺少字段只降低可计算维度，不捏造画像或外部数据。

### 6. 转化改为可组合的单事务

PartyService.create_party 与 LeaseService.create_contract 增加默认 `commit=True` 的兼容参数；CRM 转化用 `commit=False`，同一 session 内创建 Party、可选 Lease DRAFT、关联活动锁、更新 Lead、关闭待办和写审计，最后一次 commit。任一步失败统一 rollback，不留下孤立 Party/Lease。Lease 激活在 Unit 行锁内只允许无锁或属于该 Lease 的有效锁，并把该锁标为 `CONSUMED`。

### 7. 读模型共享同一过滤器和时间口径

列表、看板、漏斗和导出候选共享 park/owner/pool/status/source/keyword/created range 过滤器。漏斗按当前阶段计数，并单独返回新增、转化、丢失、公海、逾期跟进和平均首跟进时长；所有比例明确零分母返回 0。时间统一存 UTC，API 输出 ISO 8601。

### 8. PC 使用一页工作台承载渐进式操作

`/leads` 使用授权园区选择、指标卡、阶段看板/列表、公海切换和详情抽屉。详情中显示时间线、分配历史、重复候选、房源匹配和锁房；负责人来自真实用户 API。写控件按权限隐藏/禁用，但服务器仍是最终授权边界。桌面与平板必须支持键盘、可见焦点、加载/空/错误/403/409/成功状态。

## Risks / Trade-offs

- [惰性过期依赖访问触发] → 所有锁房查询/获取/Lease 激活先 sweep；未来调度器只做提前清理，不改变正确性。
- [状态枚举变更影响旧客户端] → `FOLLOWING` 输入兼容一阶段、迁移 backfill、OpenAPI 标注 deprecated mapping，并更新所有当前调用方。
- [负责人范围收紧改变旧列表可见性] → 管理员 bootstrap 增加 `lead:manage`；普通账号只看本人/公海是预期安全收紧，并补权限 E2E。
- [跨服务去内部 commit 改动风险] → 参数默认保持现有行为，新增失败注入与回滚测试覆盖组合路径。
- [Unit RESERVED 与 Lease 激活竞态] → 两条路径统一锁 current Unit，Lease 只消费属于自身的有效锁；PG 并发测试覆盖一胜一败和回滚。
- [真实旧数据字段未知] → 先交付字段映射和 isolated synthetic drill，状态保持 `BLOCKED_PENDING_SCHEMA_AND_SAMPLE_EXPORT`。

## Migration Plan

1. 新增 CRM 表和 Lead 字段，约束先可空；确定性回填 normalized 字段、stage、pool、时间和 lock_version。
2. 建立 tenant/park/owner/source/时间索引、来源条件唯一索引和 ACTIVE unit lock 条件唯一索引，再收紧可非空字段。
3. fresh base→head 和 head→-1→head；对存量基础 Lead 运行兼容 API 测试。
4. isolated schema 执行 old investment/radar-like 合成 dry/apply/idempotency/reconcile/rollback，真实数据不接入。
5. 发布 API/UI 后，通过开关保留 `FOLLOWING` 输入映射一个版本；观察完毕后另行提案移除兼容。
6. 回滚只撤销本迁移和 isolated fixture；生产切换必须另有人工批准的备份、停写和回切 Runbook。

## Open Questions

- 公海自动回收默认 7 天、锁房默认 48 小时且最大 7 天先作为代码/系统参数默认值；真实运营 SLA 待业务负责人提供后可配置调整，不阻塞本地实现。
- 真实 radar/企微来源 code、联系人合规名单和触达审批规则等待供应商与法务输入，本 change 只保留 `source_type/source_ref` 和 fail-closed 边界。
