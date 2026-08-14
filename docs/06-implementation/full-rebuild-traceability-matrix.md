# 瞰维智管 V2 独立验收能力矩阵

> 审计日期：2026-08-15（Asia/Shanghai）
> 最近已完成纵切：租户服务、工单、自动派单/SLA、报价、履约成本、返工验收与评价；clean-SHA 提交号将在本轮正常提交后补记。应收精确提交 `1a11cfe08b8d2b800c7121d7462995ebb75eb75d` 的证据继续保留。
> 判定规则：只使用 `IMPLEMENTED_AND_VERIFIED`、`APPROVED_RETIRED`、`APPROVED_DEFERRED`、`BLOCKED`、`MISSING`。子能力通过但组合需求未闭环时，组合项必须判为 `MISSING`；没有人工批准，不使用 retired/deferred。

## 当前整改纵切

- 分支：`feat/full-rebuild-completion`，起点 `37d7cf7da768eef8d7bcc743635117b8f34c7bbb`。
- OpenSpec：`complete-party-enterprise-profile` 已完成 clean-SHA 验收、同步 9 份 delta 并归档为 `2026-08-14-complete-party-enterprise-profile`；`complete-investment-crm-journey` 已完成实现及 clean-SHA 验收，但任务 5.5 的 `revoked` 与审批 delta 状态定义冲突，保持 active、未同步归档。
- 已关闭证据：Party 绑定的租户服务主体、员工代受理/租户自助受理、不可变派单规则版本及显式退役、自动/人工派单、SLA、版本化报价、追加式成本/冲正、完工证据、返工/验收/评价和 PC 响应式工作区。PG16、342 条后端、59 条全量浏览器、25 个 runtime/YAML 方法对、性能、备份恢复和合成 ETL 的工作树总门禁均通过。
- 不变阻塞：授权旧 schema/脱敏快照、旧密码样本、真实集成凭据、远程预发与生产授权均未获得，不得因本纵切降低为完成。

## 产品能力

| # | 能力 | 独立核验证据 | 未关闭事实 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | 组织/RBAC/园区范围/审批/审计 | 集团/区域/园区历史归属、岗位任职、字段策略、会话/RBAC/园区 grant；版本化定义、ANY/ALL 多步实例、任务/委托/SLA、自审批门禁、幂等/并发、事务哈希审计、查询/校验/导出和 PC 真栈均通过 | — | `IMPLEMENTED_AND_VERIFIED` |
| 2 | 统一工作台和自动待办 | 事务事件和消费者、受限版本化规则、通知、持久调度、独立 worker、来源待办、升级/改派、用户→角色→服务器布局、实时 PC 工作台/控制面；PG16/真实 HTTP/50 条浏览器/性能/合成 ETL 均通过 | — | `IMPLEMENTED_AND_VERIFIED` |
| 3 | 资产模板、租控矩阵、拆分合并和历史 | 七类内置及租户自定义模板、不可变发布版本、精确 Unit 版本绑定和复合租户外键；空间树/合法 Point/简单 Polygon、拆并血缘与并发；矩阵/真实几何示意地图/列表/空置/到期/分析及 PC 响应式真栈均通过 | 商业 GIS、CAD/BIM 和真实旧坐标迁移未获合同/数据，不作为本能力的伪完成声明 | `IMPLEMENTED_AND_VERIFIED` |
| 4 | 招商线索、分配、公共池、跟进、带看和锁房 | 去重；人工/版本化自动分配与公海回退；活动、第一类带看、匹配；不可变意向→统一审批→限时锁房→合同转化；签名渠道适配器均有 PG16/真实 HTTP/浏览器/并发/合成 ETL 证据 | 真实供应商联调和真实旧数据迁移分别由第 19/20 项保持阻塞，不伪装成本能力本地产品缺口 | `IMPLEMENTED_AND_VERIFIED` |
| 5 | 客户、租户、联系人和企业画像 | Party/租户、联系人、地址、角色、园区关系；组织主体企业画像与精确完整度、关联企业、受控证件指纹/附件、来源标签、追加式风险/处置、目录筛选和 PC 响应式真栈；PG16/真实 HTTP/浏览器/并发/合成 ETL 均通过 | 个人身份材料禁止进入该纵切；外部工商提供商保持 `NOT_CONNECTED`，其真实联调与旧数据分别由第 19/20 项保持阻塞 | `IMPLEMENTED_AND_VERIFIED` |
| 6 | 多出租单元、多费用合同 | 多单元、多费用、确定性履约计划、占用冲突、API/UI/PG 事务证据 | — | `IMPLEMENTED_AND_VERIFIED` |
| 7 | 合同变更单和版本链 | 不可变快照、校验和、七类变更、审批、续租/退租、并发和回滚证据 | — | `IMPLEMENTED_AND_VERIFIED` |
| 8 | 账单、收款、匹配、核销、欠费和催缴 | 当前合同版本履约计划预览/批量出账、来源血缘；到账单箱与渠道真相；确定性候选与理由；财务确认、异常/争议经理复核；多账单分配、预收余额、后续核销、冲正历史；L1-L4 欠费、催缴记录、调整双人审批、结清联动；API/PC/PG16/真实 HTTP/浏览器/并发/合成 ETL 均通过 | 银行/支付供应商仍为 `NOT_CONNECTED`，真实旧财务数据与生产切换分别由第 19/20 项保持缺口或阻塞，不伪装成本能力的本地产品缺口 | `IMPLEMENTED_AND_VERIFIED` |
| 9 | 租户服务、工单、报价、验收和评价 | User→Party→园区租户服务授权；租户自助与员工代受理；不可变派单规则草稿/发布/显式退役、确定性自动派单与人工改派；响应/解决 SLA 与幂等升级；Decimal 版本报价及租户决定；追加式人工/材料/外包/其他成本和冲正；完工证据、租户返工/验收、一次性评价；PC/移动响应式真栈、PG16 并发、真实 HTTP、合成迁移、性能与备份恢复均通过 | 员工独立移动应用、租户微信小程序、库存扣减、IoT/巡检来源、短信/企微/对象存储 live 和真实旧 `repair_order` 迁移由第 10/11/12/15/19/20 项保持缺口或阻塞，不伪装为本地 PC 产品能力 | `IMPLEMENTED_AND_VERIFIED` |
| 10 | 设备台账、周巡检、告警和 IoT 接入 | 无挂载的完整业务模块 | 全能力缺失 | `MISSING` |
| 11 | 员工移动端 | 仓库仅有 `apps/api` 和 `apps/web` | 独立应用、现场旅程和设备/离线能力缺失 | `MISSING` |
| 12 | 租户微信小程序 | 仓库无小程序应用 | 缴费、报修、访客、预约等端到端能力缺失 | `MISSING` |
| 13 | 档案、签章、印章 | 附件元数据、合同文档和签章端口 fail-closed 已测 | 档案/印章业务、合法签章与真实厂商联调缺失 | `MISSING` |
| 14 | HR、排班、考勤、绩效和资质 | 无挂载业务模块 | 全能力缺失 | `MISSING` |
| 15 | 供应商、采购、库存、领用和外包 | 无挂载业务模块 | 全能力缺失 | `MISSING` |
| 16 | 政策、园企服务、活动和公告 | 无挂载业务模块 | 全能力缺失 | `MISSING` |
| 17 | 驾驶舱、指标下钻和多园区比较 | 工作台窄摘要可运行；`analytics` 未挂载 | 深色驾驶舱、指标口径/原单下钻、多园区比较缺失 | `MISSING` |
| 18 | AI 业务能力与人工确认门禁 | `ai_assist` 是未挂载固定 stub | 可审计 AI 网关、风险分级、人工确认、超时/非 AI 降级缺失 | `MISSING` |
| 19 | 外部平台适配器 | SMS/通知/对象存储/签章有局部 fake/local/fail-closed 端口 | 银行、支付、税票、IoT、企微等多数适配器缺失；已有端口也未真实联调 | `MISSING` |
| 20 | 数据迁移和切换 Runbook | PG16 合成 dry/apply/中断/幂等/对账/回滚和备份恢复通过 | 缺经授权旧 schema/脱敏快照、增量同步、停写切换与真实对账 | `BLOCKED` |

汇总：`IMPLEMENTED_AND_VERIFIED=9`，`BLOCKED=1`，`MISSING=10`，`APPROVED_RETIRED=0`，`APPROVED_DEFERRED=0`。

## 22 条关键旅程

| # | 旅程 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 集团、区域、园区、角色、用户 | `IMPLEMENTED_AND_VERIFIED` | 集团/区域/园区历史归属、角色、用户、岗位任职及字段策略的 API/PG/浏览器旅程通过 |
| 2 | 不同业态资产 | `IMPLEMENTED_AND_VERIFIED` | FACTORY/WAREHOUSE/SHOP/OFFICE/DORMITORY/PARKING/PUBLIC_SPACE 七类版本化模板、动态字段和真实 HTTP/浏览器旅程通过 |
| 3 | 拆分/合并及历史 | `IMPLEMENTED_AND_VERIFIED` | UI/API/PG 并发与血缘历史通过 |
| 4 | 录入线索 | `IMPLEMENTED_AND_VERIFIED` | 真实 HTTP/UI/PG 通过 |
| 5 | 自动分配与改派 | `IMPLEMENTED_AND_VERIFIED` | 版本化规则/成员容量、确定性选择、创建/渠道/回收触发、公海回退和人工覆盖均有并发/API/UI 证据 |
| 6 | 跟进、带看、意向审批、限时锁房 | `IMPLEMENTED_AND_VERIFIED` | 第一类 Viewing、不可变 Intent、统一 Approval 权威状态、负向门禁、锁房/续锁/转合同真实 HTTP 和浏览器主路径通过 |
| 7 | 创建租户 | `IMPLEMENTED_AND_VERIFIED` | Party 租户主档、组织企业画像、联系人/注册地址、关联企业、受控证件、标签和本地风险均有 API/PG/浏览器证据 |
| 8 | 多单元、多费用合同 | `IMPLEMENTED_AND_VERIFIED` | 合同 V2 主旅程通过 |
| 9 | 生成账单 | `IMPLEMENTED_AND_VERIFIED` | 当前 Lease 版本履约计划 preview/apply、分组签发、来源血缘、同事务计划更新、重放/并发冲突及审计/outbox 均通过 |
| 10 | 模拟到账 | `IMPLEMENTED_AND_VERIFIED` | 单笔/批量财务到账导入、来源幂等、渠道能力真相和异常单箱通过；只表示模拟/文件导入，不代表银行或在线支付已联通 |
| 11 | 自动匹配、异常核对、复核核销 | `IMPLEMENTED_AND_VERIFIED` | 确定性候选及规则理由、禁止自动过账、财务确认、经理争议复核、多账单/预收后续分配、冲正与并发/幂等通过 |
| 12 | 欠费分级催缴 | `IMPLEMENTED_AND_VERIFIED` | L1-L4 账龄、每账单唯一活动案件、preview/apply、重复安全升级、hold 抑制、记录/待办及调整双人审批通过 |
| 13 | 租户报修 | `IMPLEMENTED_AND_VERIFIED` | Party 绑定主体通过真实 API/PC 租户视图提交、列表与查看脱敏请求；跨 Party 返回 404，离线提交保留草稿并可重试。微信小程序入口仍由第 20 条独立保持缺失 |
| 14 | 自动派单、报价、处理、租户验收 | `IMPLEMENTED_AND_VERIFIED` | 规则版本、确定性派单/改派、SLA、报价接受、实际成本、完工证据、返工、验收、评价和 WorkItem/事件投影的 API/PG/真实浏览器主链通过 |
| 15 | 周巡检与异常转工单 | `MISSING` | 无巡检模块 |
| 16 | IoT 告警分级、去重和升级 | `MISSING` | 无 IoT 告警模块 |
| 17 | 合同变更、续租和退租 | `IMPLEMENTED_AND_VERIFIED` | 变更/版本/结算/占用释放通过 |
| 18 | 驾驶舱指标与原始记录对账 | `MISSING` | 无完整驾驶舱 |
| 19 | 员工移动端现场任务 | `MISSING` | 应用不存在 |
| 20 | 租户小程序缴费/报修/访客/预约 | `MISSING` | 应用不存在 |
| 21 | 越权、跨租户、重复提交、并发冲突 | `IMPLEMENTED_AND_VERIFIED` | 已实现切片的 HTTP/E2E/PG 测试通过；工单纵切新增数据库派生租户服务权限、Party/园区/联系人/子资源 404 隔离、伪造 JWT 权限拒绝、未知字段 422、重复查询参数 400、同键异命令 409、复合租户外键，以及派单和验收恰好一方提交的行锁回归；此前财务和 Party 门禁继续有效 |
| 22 | AI 低风险操作与高风险确认 | `MISSING` | AI 业务层未实现 |

## 旧系统替代判定

旧证据库 `D:\重构python\kwzg-Java-main` 的静态取证为 54 个 Controller、约 484 个 HTTP mapping、316 个 Vue 文件、30 张 SQL DDL 表。Python 仓库只有 API 与 PC Web 两个应用，且上表仍有 10 项 `MISSING` 和 1 项 `BLOCKED`，因此：

```text
KWZY_LEGACY_REPLACEMENT=BLOCKED
```

旧能力只有逐项达到 `IMPLEMENTED_AND_VERIFIED`，或获得有责任人和依据的 `APPROVED_RETIRED/APPROVED_DEFERRED`，才可关闭。当前没有这类人工批准。
