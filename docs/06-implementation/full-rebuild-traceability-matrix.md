# 瞰维智管 V2 独立验收能力矩阵

> 审计日期：2026-08-14（Asia/Shanghai）
> 实现证据提交：`a9267d4c30096a7c80d66588ab06bc6838b32b0d`
> 判定规则：只使用 `IMPLEMENTED_AND_VERIFIED`、`APPROVED_RETIRED`、`APPROVED_DEFERRED`、`BLOCKED`、`MISSING`。子能力通过但组合需求未闭环时，组合项必须判为 `MISSING`；没有人工批准，不使用 retired/deferred。

## 产品能力

| # | 能力 | 独立核验证据 | 未关闭事实 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | 组织/RBAC/园区范围/审批/审计 | 登录会话、角色权限、园区 grant、最小审批、审计日志有 API/PG/E2E | 集团/区域治理、岗位、字段权限、完整审批中心与审计中心未闭环 | `MISSING` |
| 2 | 统一工作台和自动待办 | WorkItem、摘要、合同治理待办可运行 | 多角色组件配置、全事件源、自动升级/改派/复核未完成 | `MISSING` |
| 3 | 资产模板、租控矩阵、拆分合并和历史 | 空间树、单元版本/血缘、拆并并发、矩阵/列表 UI 已验证 | 业态模板、地图/GIS/CAD/BIM、组合分析未完成 | `MISSING` |
| 4 | 招商线索、分配、公共池、跟进、带看和锁房 | 去重、人工分配/改派、公海、活动、匹配、限时锁房和转化有 PG/E2E | 自动分配、意向审批和外部渠道未完成 | `MISSING` |
| 5 | 客户、租户、联系人和企业画像 | Party、联系人、地址、角色、园区关系已实现 | 完整企业画像、关联企业、受控证件/风险画像未完成 | `MISSING` |
| 6 | 多出租单元、多费用合同 | 多单元、多费用、确定性履约计划、占用冲突、API/UI/PG 事务证据 | — | `IMPLEMENTED_AND_VERIFIED` |
| 7 | 合同变更单和版本链 | 不可变快照、校验和、七类变更、审批、续租/退租、并发和回滚证据 | — | `IMPLEMENTED_AND_VERIFIED` |
| 8 | 账单、收款、匹配、核销、欠费和催缴 | 基础账单、收款、分配、冲正、简版催缴案件可运行 | 自动出账、银行流水、自动匹配、异常复核、多账单/预收核销、分级催缴未完成 | `MISSING` |
| 9 | 租户服务、工单、报价、验收和评价 | 简版工单创建/开始/完成/取消有 E2E | 租户入口、自动派单、报价、材料工时、验收评价、返工/SLA 未完成 | `MISSING` |
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

汇总：`IMPLEMENTED_AND_VERIFIED=2`，`BLOCKED=1`，`MISSING=17`，`APPROVED_RETIRED=0`，`APPROVED_DEFERRED=0`。

## 22 条关键旅程

| # | 旅程 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 集团、区域、园区、角色、用户 | `MISSING` | 园区/角色/用户有证据，集团与区域闭环缺失 |
| 2 | 不同业态资产 | `MISSING` | 空间/单元可建，业态模板未完成 |
| 3 | 拆分/合并及历史 | `IMPLEMENTED_AND_VERIFIED` | UI/API/PG 并发与血缘历史通过 |
| 4 | 录入线索 | `IMPLEMENTED_AND_VERIFIED` | 真实 HTTP/UI/PG 通过 |
| 5 | 自动分配与改派 | `MISSING` | 人工分配/改派通过，自动分配缺失 |
| 6 | 跟进、带看、意向审批、限时锁房 | `MISSING` | 跟进/带看/锁房通过，意向审批缺失 |
| 7 | 创建租户 | `IMPLEMENTED_AND_VERIFIED` | Party 租户主档通过 |
| 8 | 多单元、多费用合同 | `IMPLEMENTED_AND_VERIFIED` | 合同 V2 主旅程通过 |
| 9 | 生成账单 | `IMPLEMENTED_AND_VERIFIED` | 当前基础账单创建/签发通过 |
| 10 | 模拟到账 | `IMPLEMENTED_AND_VERIFIED` | 收款登记通过，不代表在线支付 |
| 11 | 自动匹配、异常核对、复核核销 | `MISSING` | 当前仅基础分配/冲正 |
| 12 | 欠费分级催缴 | `MISSING` | 仅简版催缴案件 |
| 13 | 租户报修 | `MISSING` | 无租户端入口 |
| 14 | 自动派单、报价、处理、租户验收 | `MISSING` | 仅简版内部工单状态机 |
| 15 | 周巡检与异常转工单 | `MISSING` | 无巡检模块 |
| 16 | IoT 告警分级、去重和升级 | `MISSING` | 无 IoT 告警模块 |
| 17 | 合同变更、续租和退租 | `IMPLEMENTED_AND_VERIFIED` | 变更/版本/结算/占用释放通过 |
| 18 | 驾驶舱指标与原始记录对账 | `MISSING` | 无完整驾驶舱 |
| 19 | 员工移动端现场任务 | `MISSING` | 应用不存在 |
| 20 | 租户小程序缴费/报修/访客/预约 | `MISSING` | 应用不存在 |
| 21 | 越权、跨租户、重复提交、并发冲突 | `IMPLEMENTED_AND_VERIFIED` | 已实现切片的 HTTP/E2E/PG 测试通过 |
| 22 | AI 低风险操作与高风险确认 | `MISSING` | AI 业务层未实现 |

## 旧系统替代判定

旧证据库 `D:\重构python\kwzg-Java-main` 的静态取证为 54 个 Controller、约 484 个 HTTP mapping、316 个 Vue 文件、30 张 SQL DDL 表。Python 仓库只有 API 与 PC Web 两个应用，且上表有 17 项组合能力缺失，因此：

```text
KWZY_LEGACY_REPLACEMENT=BLOCKED
```

旧能力只有逐项达到 `IMPLEMENTED_AND_VERIFIED`，或获得有责任人和依据的 `APPROVED_RETIRED/APPROVED_DEFERRED`，才可关闭。当前没有这类人工批准。
