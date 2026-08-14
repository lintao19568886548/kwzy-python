# 招商 CRM V2 字段映射与迁移门禁

> 状态：`CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`；真实数据仍 `BLOCKED_PENDING_SCHEMA_AND_SAMPLE_EXPORT`
> 范围：传统 `investment`、CRM lead 表族、radar external lead → V2 Lead/Activity/Assignment/Merge/Viewing/Intent/ChannelInbox
> 禁止：连接旧生产库、导出真实 PII、根据字段名猜枚举、把合成演练标记为真实 readiness

## 1. 证据与可信度

| 来源 | 可确认事实 | 可信度/限制 |
| --- | --- | --- |
| `docs/01-old-system-analysis/02-backend-business-analysis.md` | 传统 investment、CRM lead、radar 表族及跟进/拜访/分配/匹配职责 | 仓库静态取证；非真实 schema |
| `03-database-analysis.md` | investment→tenant、external lead/signal→lead、property match 等关系 | 表族级；字段/约束未知 |
| `05-api-analysis.md`、`_api-raw.tsv` | CRUD、follow-feedback、convert、stats、radar 路径 | 路由级；请求/响应枚举未验证 |
| 当前 Python `leads` | name/phone/contact/agent/intent/status/owner/Party/Lease | 可直接迁移并由 Alembic backfill |

真实旧 schema dump、字段注释、枚举样本、用户/园区/租户主键映射和脱敏记录均未取得，因此真实 readiness 保持 `BLOCKED_PENDING_SCHEMA_AND_SAMPLE_EXPORT`。

## 2. 目标事实

| 目标 | 主键/幂等键 | 职责 |
| --- | --- | --- |
| `leads` | V2 id；`tenant_id + source_type + source_ref` 条件唯一 | 当前主档、阶段、负责人/公海、SLA、合并目标和版本 |
| `lead_activities` | source activity ref 或目标 id | append-only 跟进、拜访、报价、谈判和阶段事实 |
| `lead_assignment_events` | source assignment ref 或目标 id | ASSIGN/REASSIGN/CLAIM/RELEASE/RECYCLE 历史 |
| `lead_merge_links` | source lead + target lead | 重复合并血缘，不删除来源历史 |
| `lead_unit_locks` | target id；ACTIVE unit 条件唯一 | V2 运行期锁房；旧 property match 不直接生成有效锁 |
| `lead_assignment_rules/versions/members` | V2 配置 id/version | 只迁经业务签字的规则与成员容量；旧 owner 历史不反推生产规则 |
| `lead_viewings/viewing_units` | source appointment ref 或目标 id | 只接收明确时间窗、状态与 Unit 映射；自由备注仍为 Activity |
| `lead_intent_applications/versions/units` | source intent ref/version | 冻结可证明的单元/面积/期限/报价；审批结果须单独映射 |
| `lead_channels/channel_inbox_events` | channel public id + external event id | 渠道配置默认禁用；只迁来源事实/摘要，不迁密钥和未知原始载荷 |

## 3. 表/字段映射

| 旧来源候选 | 目标 | 转换 | 状态 |
| --- | --- | --- | --- |
| `investment.id` | `leads.source_ref` | 字符串化；`source_type=LEGACY_INVESTMENT` | `CONDITIONAL` |
| old tenant/park foreign key | `tenant_id/park_id` | 必须经签字主键映射，禁止名称模糊匹配 | `BLOCKED_MAPPING` |
| tenant/customer/company name | `leads.name/normalized_name` | trim + Unicode/case/空白规范化；保留原名 | `CONDITIONAL` |
| phone/mobile/tel | `contact_phone/normalized_phone` | trim；合法长度；报告只输出掩码/计数 | `CONDITIONAL_PII` |
| contact/person | `contact_name` | trim；空串→NULL | `CONDITIONAL_PII` |
| agent/channel | `agent_name/source_type` | 原中介名保留；渠道 code 待字典确认 | `BLOCKED_ENUM` |
| intent grade/level | `intent_level` | A/B/C/HIGH/MEDIUM/LOW 映射需样本闭合 | `BLOCKED_ENUM` |
| intended area | `intent_area` | Decimal(12,2)，负数隔离 | `CONDITIONAL` |
| progress/status | `leads.status` | 目标 NEW/CONTACTING/VISITING/QUOTING/NEGOTIATING/WON/LOST/CANCELLED；未知值隔离 | `BLOCKED_ENUM` |
| follow feedback/history | `lead_activities` | 每条 append-only NOTE/CALL/VISIT；禁止拼接覆盖 remark | `BLOCKED_SCHEMA` |
| owner/sales id | `owner_user_id` + assignment event | 必须经旧用户→V2 user 映射；无映射进入 PUBLIC | `BLOCKED_MAPPING` |
| converted tenant/customer | `party_id` | 只关联经 Party 对账确认的映射，不重复创建 | `BLOCKED_MAPPING` |
| converted contract | `lease_id` | 只关联已迁移 Lease；不存在则保持 NULL 并报告 | `BLOCKED_MAPPING` |
| loss reason | `lost_reason` + terminal activity | 保留原文，超长截断需报告 | `CONDITIONAL` |
| CRM `investment_lead` external key | `source_type/source_ref` | `LEGACY_CRM` + 原主键 | `BLOCKED_SCHEMA` |
| radar `external_lead` key | `source_type/source_ref` | `LEGACY_RADAR` + 原主键；不触发外部抓取 | `BLOCKED_SCHEMA` |
| signal/evidence/profile/tag | 后续 evidence/profile capability | 本 change 不猜测合并到 remark | `DEFERRED` |
| `property_match_result` | 无直接导入 | 仅作历史证据；V2 用当前 Unit 重新计算匹配 | `RECOMPUTE` |
| old score/rule result | 无权威目标 | 不当作 AI/规则事实；可在未来保存历史快照 | `DEFERRED` |
| old reservation/lock | `lead_unit_locks` | 不直接生成 ACTIVE；须结合当前 Unit/Lease 和有效期人工规则 | `BLOCKED_BUSINESS_RULE` |
| legacy visit/schedule rows | `lead_viewings` 或 `lead_activities` | 只有明确预约时间、状态、owner、park 和 Unit 才建 Viewing；否则只迁历史 Activity | `BLOCKED_SCHEMA` |
| legacy intention/quotation | `lead_intent_*` | 必须有 Unit、面积、期限、价格和审批来源；缺审批人/结果不得伪造 APPROVED | `BLOCKED_SCHEMA_AND_APPROVAL` |
| legacy auto assignment rule | `lead_assignment_rule_*` | 必须有园区、触发器、成员、容量/顺序和生效版本签字；不能从历史 owner 反推 | `BLOCKED_BUSINESS_RULE` |
| external lead receive fact | `lead_channel_inbox_events` | 稳定 event id/source ref、摘要和结果可迁；明文 secret/raw PII 不迁 | `BLOCKED_SCHEMA_AND_PROVIDER` |

## 4. 阶段兼容

| 当前 Python/旧候选值 | V2 目标 | 说明 |
| --- | --- | --- |
| NEW | NEW | 直接保留 |
| FOLLOWING | CONTACTING | Alembic 确定性 backfill；API 输入兼容一期 |
| CONTACTING/VISITING/QUOTING/NEGOTIATING | 同名 | 需真实样本证明旧值存在 |
| WON/converted | WON | 必须与 Party/Lease 对账，不凭字符串单独判定 |
| LOST | LOST | lost_reason 必须保留或报告缺失 |
| CANCELLED | CANCELLED | 直接保留 |
| duplicate/merged | MERGED | 只有明确保留者映射时才生成 merge link |
| 其他 | 隔离 | 报告值与数量，等待业务签字 |

## 5. 合成演练最小对账

- 来源/目标 Lead 总数及 traditional/CRM/radar-like 来源分布。
- 各阶段、公海/私有、负责人映射成功/失败分布。
- Activity、Assignment、Merge 数量；来源外部键重复数。
- Lead→Park/User/Merged target 孤儿数。
- Rule/version/member 数、有效版本唯一性、成员园区授权与容量分布。
- Viewing/status/unit link 数；自由备注误建 Viewing 数必须为 0。
- Intent/version/unit/Approval link 数；无审批证据却标 APPROVED 数必须为 0。
- Channel/inbox/source ref 数、重复 external event id 与 raw secret/PII 持久化数必须为 0。
- 非法面积、非法电话、未知枚举和缺主键映射的隔离数。
- 模拟批次中断必须事务回滚为零行，随后恢复 apply；幂等 re-apply 新增数为 0；rollback 后 isolated schema 不存在。

2026-08-14 本地 PG16 合成演练已覆盖 17 类目标对象和上述四类隔离原因，5/5 测试通过；报告不含原始 PII/secret。该结论不改变真实旧数据授权门禁。

合成演练通过后的唯一允许状态为 `CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`。真实预发导入必须另有只读脱敏快照授权、映射签字、PII 处理方案、备份/回滚和切换窗口。

## 6. V2 规则与签名口径

- 自动分配排序：`open_lead_count / capacity` 升序 → `last_assigned_at`（NULL 最先）→ `member_order` → `user_id`；执行锁定发布版本，预览不写入。
- 带看窗口：`end_at > start_at`，最大 24 小时，1–20 个同园区 current Unit；同 owner 的 SCHEDULED/CONFIRMED 时间窗不得重叠。
- 意向快照：1–20 个 Unit，requested area 大于 0 且不超过 current rentable area，起止日期有序，valid_until 有界；审批 snapshot 排除电话和原始联系人 PII。
- 渠道签名基串：`v1\n<unix_timestamp>\n<external_event_id>\n<sha256(raw_body)>`，使用 HMAC-SHA256 和恒定时间比较；默认允许偏差 300 秒，请求体与字段上限由服务端固定。
