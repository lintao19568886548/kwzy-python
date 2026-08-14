# 旧招商/CRM/Radar 能力处置（CRM V2）

> 依据：仓库旧系统分析与 `_api-raw.tsv`；未连接旧生产环境
> 结论：传统招商核心流程由 V2 REDESIGN；外部雷达/企微/自动触达仅保留边界，均非 LIVE

## 1. 传统招商登记

| 旧能力/路径 | V2 处置 | 目标证据 | 当前状态 |
| --- | --- | --- | --- |
| `GET /api/investment/list` | REDESIGN | `/api/v1/leads` shared scoped filters + board | `IMPLEMENTED_LOCAL` |
| `GET /api/investment/{id}` | REDESIGN | Lead detail + timeline/assignment/merge/locks | `IMPLEMENTED_LOCAL` |
| create/update/delete investment | REDESIGN | create + versioned patch；不物理删除历史 | `IMPLEMENTED_LOCAL` |
| `follow-feedback` | REDESIGN | append-only `/leads/{id}/activities` | `IMPLEMENTED_LOCAL` |
| `convert-to-tenant` | REDESIGN | 单事务 Lead→Party→可选 Lease DRAFT | `IMPLEMENTED_LOCAL` |
| `agent-stats` | REDESIGN | scoped funnel owner/source breakdown | `IMPLEMENTED_LOCAL` |
| `crm/backfill` | RETIRE_ONLINE_MUTATION | offline isolated ETL + reconciliation report | `IMPLEMENTED_LOCAL_SYNTHETIC` |
| traditional investment images | DEFER_TO_ATTACHMENTS | 关联 Attachment/evidence，需真实字段映射 | `BLOCKED_SCHEMA` |

## 2. CRM 销售过程

| 旧能力 | V2 处置 | 说明 |
| --- | --- | --- |
| 双 Lead/Customer 主档 | CONSOLIDATE | 单一 Lead；重复候选、带理由覆盖、merge lineage；WON 后关联 Party |
| 分配负责人/公海 | REDESIGN | 人工与版本化自动规则、容量、创建/渠道/回收触发、公海回退均完成本地真栈验证 |
| 跟进/拜访/SOP | REDESIGN | Activity + next follow + WorkItem 与第一类带看预约/改期/完成/取消/爽约已验证；SOP 模板另行治理 |
| 看房/报价/谈判 | REDESIGN_CORE | Viewing、不可变 Intent 版本和权威 Approval 门禁已闭环；旧自由备注不伪造成 Viewing |
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

## 5. 2026-08-14 独立复核增量

- 旧 Java `InvestmentController/Service/Repository`、`investment-crm-master.sql` 和 `playground/src/api/investment/investment.ts` 显示传统登记与 Radar/External Lead/公开商机/触达模板并存；公开爬虫、代理池、企微和外呼均依赖外部网络、合规与凭据，不能作为本地真实完成项。
- 当前 Python `j6e24f9a1c08`、Investment ORM/Service/API 和 PC `/leads` 已证明去重、人工分配/公海、活动、匹配、PG 排他锁和转化，不再标作 `PLANNED`。
- 原始证据没有给出可直接采用的自动分配容量、意向审批步骤或渠道签名协议。因此 V2 只提供租户可配置版本化规则、通用 `LEAD_INTENT` 审批和默认禁用 HMAC 接收契约，不填充生产默认、不猜测旧审批人、不主动抓取外部网站。
- 新纵切完成后，旧 Radar 爬虫/代理池、企微、短信、外呼和真实渠道仍分别保持 `DEFERRED/ADAPTER_NOT_LIVE/BLOCKED_EXTERNAL`；不得借通用本地 HMAC fixture 声称 `LIVE_CONNECTED`。

本地产品范围已具备模型/API/PC UI/权限/合成迁移/真实栈测试证据，能力矩阵第 4 项可标记 `IMPLEMENTED_AND_VERIFIED`。真实外部供应商、真实旧数据迁移、企微/触达和 AI 评分仍由独立矩阵条目保持 `BLOCKED/MISSING`，不计入旧系统全量替代完成。
