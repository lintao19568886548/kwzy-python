# 旧招商/CRM/Radar 能力处置（CRM V2）

> 依据：仓库旧系统分析与 `_api-raw.tsv`；未连接旧生产环境
> 结论：传统招商核心流程由 V2 REDESIGN；外部雷达/企微/自动触达仅保留边界，均非 LIVE

## 1. 传统招商登记

| 旧能力/路径 | V2 处置 | 目标证据 | 当前状态 |
| --- | --- | --- | --- |
| `GET /api/investment/list` | REDESIGN | `/api/v1/leads` shared scoped filters + board | `PLANNED` |
| `GET /api/investment/{id}` | REDESIGN | Lead detail + timeline/assignment/merge/locks | `PLANNED` |
| create/update/delete investment | REDESIGN | create + versioned patch；不物理删除历史 | `PLANNED` |
| `follow-feedback` | REDESIGN | append-only `/leads/{id}/activities` | `PLANNED` |
| `convert-to-tenant` | REDESIGN | 单事务 Lead→Party→可选 Lease DRAFT | `PLANNED` |
| `agent-stats` | REDESIGN | scoped funnel owner/source breakdown | `PLANNED` |
| `crm/backfill` | RETIRE_ONLINE_MUTATION | offline isolated ETL + reconciliation report | `PLANNED` |
| traditional investment images | DEFER_TO_ATTACHMENTS | 关联 Attachment/evidence，需真实字段映射 | `BLOCKED_SCHEMA` |

## 2. CRM 销售过程

| 旧能力 | V2 处置 | 说明 |
| --- | --- | --- |
| 双 Lead/Customer 主档 | CONSOLIDATE | 单一 Lead；重复候选、带理由覆盖、merge lineage；WON 后关联 Party |
| 分配负责人/公海 | REDESIGN | owner/public scope、assign/claim/release/recycle、append-only 事件和 PG claim race |
| 跟进/拜访/SOP | REDESIGN | activity timeline + next follow + WorkItem；SOP 模板/自动化另行提案 |
| 看房/报价/谈判 | REDESIGN_CORE | VISIT/QUOTE/NEGOTIATION 活动与阶段；复杂报价审批不在本 change |
| 房源匹配 | REDESIGN_NON_AI | current VACANT Unit 的面积/用途/价格规则分和理由 |
| 限时锁房 | NEW_GOVERNED | ACTIVE 条件唯一、过期/释放/Lease 消费、Unit RESERVED 投影 |
| 漏斗/渠道/销售统计 | REDESIGN | shared filter 下阶段/来源/owner/时效一致口径 |

## 3. Radar 与外部渠道

| 旧能力/路径族 | V2 处置 | 门禁 |
| --- | --- | --- |
| crawler source/task、代理池、公开商机 URL 解析 | DEFERRED | 无运行必要性确认、供应商/目标站合规和运维预算；禁止复刻爬虫 |
| signal event / external lead convert | ADAPTER_BOUNDARY_ONLY | 仅 `source_type/source_ref` 幂等入口与合成 fixture；无真实拉取 |
| enterprise profile/tag/evidence | DEFERRED | 需企业数据来源、合法性、保存期限和 PII 规则 |
| score rule / AI lead score | DEFERRED_NON_AI_FALLBACK | 本 change 仅确定性房源匹配，不称 AI |
| outreach template/task、外呼/短信/企微 | ADAPTER_NOT_LIVE | 缺凭据/回调/模板审批/联系同意；生产 fail-closed |
| contact restriction import/release | BLOCKED_COMPLIANCE | 在合规模型与审批确定前不得自动触达 |
| radar analytics | PARTIAL_REDESIGN | 核心 CRM 漏斗本地实现；采集/触达效果指标等待真实来源 |

## 4. 关闭规则

旧能力只有满足下列之一才能关闭：

- `REPLACED`：模型/API/适用 UI/权限/迁移/测试与真实业务语义均有证据；
- `APPROVED_RETIRE`：有业务与合规负责人签字；
- `APPROVED_DEFER`：范围、风险和后续触发条件已记录。

当前仅基础 Lead CRUD 已落地；本表的 `PLANNED` 项须等待 `implement-investment-crm-v2` 实现和精确 SHA 验收。Radar/企微/触达不得因 CRM 本地 PASS 被标记为已替代或 LIVE。
