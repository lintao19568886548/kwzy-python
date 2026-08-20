# 政策、园企服务、活动与公告旧系统处置及字段映射

> 取证日期：2026-08-20（Asia/Shanghai）
> 当前分支：`feat/full-rebuild-completion`
> 状态：下一纵切进入实现；真实旧公告库与其他来源迁移仍为 `BLOCKED_PENDING_AUTHORIZED_EXPORT_KEYMAPS_AND_SIGNOFF`

## 原始证据裁决

本轮独立检查当前 Python/API/PC、两份最新旧 Java/PC 副本和随仓 SQL：

- `D:\重构python\kwzg-Java-main` 与 `D:\lintao\kwzg-Java` 的 `NoticesController.java`、`NoticesRepository.java`、`magic.sql` 和公告 PC 列表哈希一致；后者 Git HEAD 为 `c41f1dd8bbe4326124c73734b3fc07cccb690a58`。
- 旧系统只有登录后 `GET /notices/list` 只读分页。Repository 读取独立配置 `NOTICES_DATABASE_URL` 下的 `notices` 表；没有配置或发生异常时返回空页。
- 旧列表字段为 `noticeId/title/date/owner/category/projectType/type/platform/siteCode/link/createdAt/updatedAt`。`validOnly` 会同步探测外链；页面只打开外部链接，没有本地详情、草稿、版本、审批、发布、受众、阅读回执或撤回聚合。
- 旧 PC `/notices` 路由被隐藏；注释写明小程序外链详情暂不可用。一个隐藏列表和按钮不构成完整公告产品证据。
- 随仓 `magic.sql` 没有 notice、policy、enterprise-service 或 park-activity 表，也没有独立公告库 DDL、行数水位、状态字典、内容对象清单、园区/Party 主键映射或脱敏快照。
- 旧代码未发现可证明的政策治理、政策匹配、园企服务目录/案件、园区活动发布/报名/签到聚合。CRM 的跟进 activity、维修 WorkOrder、Party 企业画像和站内 notification 只是其他上下文的事实，不能重命名为本纵切完成。

旧目录 `D:\kwzg-Java` 仅作为更早快照做漂移对比；其 Notice Repository、PC 列表和 `magic.sql` 哈希不同，不覆盖上述两份最新一致证据，也不提供缺失的权威数据导出。

## 证据哈希

| 文件 | 两份最新副本 SHA-256 |
| --- | --- |
| `NoticesController.java` | `887F1FF8A17AD7E4FADB64FCAB3C86372631A863DF80901A587258E053B14167` |
| `NoticesRepository.java` | `8D539AEF5B101652A421DDAFBF73DAEF5B1CE0D4C0B047302A2E40BABCED58D8` |
| `magic.sql` | `A14A6D580F33418E8A8C5E8D3CF80636420DA299E1F316A0BD2A39809247DAA8` |
| `playground/src/views/notices/list.vue` | `98A06EE424DB5614119CF9D5B6BE4188BE5819CDA7FA57E6F8648D31E0FF5A96` |

## 能力处置

| 旧/现有证据 | V2 处置 | 边界 |
| --- | --- | --- |
| 旧外部 `notices` 只读列表 | `SOURCE_CANDIDATE_BLOCKED` | 只有获得独立库授权导出、字段字典和来源归属后，才能分类进入政策或公告；不能把列表可读当迁移完成 |
| 旧同步外链有效性探测 | `REBUILD_WITH_SSRF_HARDENING` | 写请求不访问调用者 URL；仅保存通过 scheme/host 策略的链接，未来探测必须异步且防 DNS rebinding |
| Party 企业画像/园区关系 | `REUSE_AS_MATCH_INPUT` | 只读取获授权投影用于可解释匹配和 tenant-principal 绑定；Party 不是政策/服务/活动聚合 |
| 维修 WorkOrder | `OPTIONAL_GOVERNED_HANDOFF` | 园企服务案件保持独立；确需维修时创建有证据链接，不能用工单状态冒充园企服务结果 |
| CRM LeadActivity | `OUT_OF_CONTEXT` | 招商跟进活动不是园区活动，禁止迁移或合并语义 |
| Approval | `REUSE_PLATFORM_TRUTH` | 政策/活动/公告发布使用原生审批，但审批行不是业务内容版本 |
| Attachment | `REUSE_CONTROLLED_EVIDENCE` | 只保存同租户、可见、哈希可校验的附件引用；路径或外链不证明对象存在 |
| Event outbox / Notification inbox | `REUSE_DELIVERY_PROJECTION` | 公告发布产生事务事件和站内投递；notification 不替代公告版本/受众/阅读账本，不伪造外部渠道成功 |
| 当前 `tenant_ops` | `DO_NOT_EXTEND_AS_STUB` | 仅有未挂载 `/tenants/current` 固定摘要；新建 engagement bounded context |

## 旧公告候选字段映射

| 旧字段 | V2 候选目标 | 迁移规则 |
| --- | --- | --- |
| `notice_id` | migration `source_key` | 与 `source_system` 组成幂等键；空值、重复或同键异载荷隔离 |
| `title` | policy/announcement version `title` | 规范化并限长；为空隔离，不从链接反推 |
| `date` | `source_published_at` | 必须有明确格式和时区；不能当 V2 审批或发布时间 |
| `owner` | `source_publisher` | 只作来源文本，不按名称猜 Party、政府机构或责任人 |
| `category/type/project_type` | controlled taxonomy + `source_taxonomy` | 经业务签字映射；未知值保留原值并隔离或待复核 |
| `platform` | `source_system/source_type` | 只标来源，不证明平台仍可用或已接入 |
| `site_code` | region/park applicability candidate | 需要 region/park key map；禁止截断或名称猜测形成园区授权 |
| `link` | validated `source_url` | 只允许安全 HTTP(S) 公网目标；危险、私网、脚本或无法归属的链接隔离，不在导入请求同步抓取 |
| `created_at/updated_at` | source audit timestamps | 保留来源时刻；不能生成 V2 actor、审批、版本或阅读证据 |
| 缺失内容/受众/阅读/撤回 | 无自动目标 | 不补造；需权威内容对象、受众规则或历史账本，否则数量为 0 |

## 本地产品真相

本纵切可建立的本地真相仅包括：

- V2 内创建并经原生审批发布的政策、服务目录、活动和公告不可变版本；
- 由持久化 tenant/Party/park grant 驱动的匹配、服务请求、报名/候补、签到、阅读回执和反馈；
- 事务 outbox 与站内 notification 的可核验投递，不包含外部渠道成功；
- 明确标为 synthetic 的迁移演练、隔离、对账和回滚结果。

以下状态必须继续显式保留：

- 政府政策源/申报平台：`NOT_CONNECTED`；政策匹配不是官方资格或申报决定。
- 外部园企服务商、场地/票务和支付：`NOT_CONNECTED/NOT_INTEGRATED`。
- SMS、微信、邮件和真实小程序投递：`NOT_CONNECTED`；PC 响应式租户视图不等于租户小程序。
- 独立旧公告库及其他真实数据迁移：`BLOCKED_PENDING_AUTHORIZED_EXPORT_KEYMAPS_RECONCILIATION_AND_SIGNOFF`。
- 生产部署、生产凭据和生产切换：`NOT_EXECUTED/AWAITING_HUMAN_APPROVAL`。

## 真实迁移与替代门禁

只有在数据所有者提供独立公告库 schema/export、内容及附件清单、来源归属、region/park/Party/user key map、分类规则、链接安全策略、全量/增量水位、对账容差和业务签字后，才能执行真实迁移。外部服务和通知还需各自合同、沙箱协议、短期凭据和回执定义。当前任何 synthetic PASS 都不得改写上述阻塞，也不得把能力矩阵第 11、12、17、18、19、20 项宣告完成。
