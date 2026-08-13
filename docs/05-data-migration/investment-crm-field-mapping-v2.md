# 招商 CRM V2 字段映射与迁移门禁

> 状态：`DRAFT_FROM_REPOSITORY_EVIDENCE`
> 范围：传统 `investment`、CRM lead 表族、radar external lead → V2 Lead/Activity/Assignment/Merge
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
- 非法面积、非法电话、未知枚举和缺主键映射的隔离数。
- 首次 apply 与幂等 re-apply 新增数；rollback 后 isolated schema 不存在。

合成演练通过后的唯一允许状态为 `CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`。真实预发导入必须另有只读脱敏快照授权、映射签字、PII 处理方案、备份/回滚和切换窗口。
