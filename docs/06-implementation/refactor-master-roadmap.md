# 瞰维智管 V2 全量重建主路线图

> 更新时间：2026-08-14（Asia/Shanghai）
> 当前独立验收基线：工作台/自动化实现提交 `fedc98efb7a33f39240216fbb861b57f6142649b`，28/28 clean-SHA 总门禁通过
> 当前完成分支：`feat/full-rebuild-completion`，从 repair 推送记录 `37d7cf7da768eef8d7bcc743635117b8f34c7bbb` 创建；三条本地 safety ref 已保留。
> 总体状态：**BLOCKED — 已实现纵切通过，不等于三端、旧系统和全业务完成。**

## 权威顺序与永久门禁

冲突按真实业务规则与用户操作 → `docs/` 蓝图 → 旧 Java/旧前端/数据库证据 → OpenSpec/OpenAPI/ADR/测试 → 当前代码与历史报告裁决。

不连接生产，不覆盖用户未提交修改，不改已应用历史迁移，不 force push。没有真实凭据时只允许交付 fake/sandbox/fail-closed 适配和契约测试；没有旧数据时只允许给出合成迁移就绪结论。

## 当前阶段

| 阶段 | 已关闭范围 | 仍需关闭 | 状态 |
| --- | --- | --- | --- |
| 平台安全与工程底座 | 会话/JWT/密码、scope、组织/岗位/字段策略、版本化审批/任务/委托/SLA、哈希审计、事务事件、受限规则、站内通知、持久调度/独立 worker、多角色布局、附件、生产配置、PG pool/readiness、CI/容器/Runbook | 远程监控/告警/灾备证据 | IN_PROGRESS |
| 资产与租控 | 空间树、单元版本/拆并血缘、矩阵/列表 | 业态模板、地图/GIS/CAD/BIM、组合分析 | IN_PROGRESS |
| 招商 CRM | 去重、分配/改派、公海、活动、匹配、锁房、转化 | 自动分配、意向审批、外部渠道/企微、AI 评分 | IN_PROGRESS |
| Party 与合同 | Party 基础；合同多单元/多费用/版本/变更/退租 | 企业画像、完整档案/签章/印章和真实提供商 | IN_PROGRESS |
| 账单、收款和催缴 | 基础账单/收款/分配/冲正/案件 | 自动出账、流水匹配、异常复核、多账单核销、分级催缴 | IN_PROGRESS |
| 服务与运营业务 | 简版工单 | 租户服务、派单/SLA/报价/验收、设备巡检 IoT、HR、供应链、园企服务 | MISSING |
| 决策与 AI | 多角色可配置实时运营工作台、待办/通知/自动化控制面和基础原单下钻 | 深色经营驾驶舱、完整指标口径、多园区比较、AI/人工确认门禁 | MISSING |
| 员工移动端 | — | 独立应用与现场 E2E | MISSING |
| 租户微信小程序 | — | 缴费/报修/访客/预约 E2E | MISSING |
| 迁移与切换 | 合成 dry/apply/中断/幂等/对账/回滚；本地备份恢复 | 旧 schema/脱敏快照、全量对账、CDC、停写、切换/回切 | BLOCKED_EXTERNAL_EVIDENCE |
| 生产交付 | 本地生产镜像/Compose 契约和操作 Runbook | 远程预发、监控告警、容量/灾备、生产授权 | BLOCKED_EXTERNAL_EVIDENCE |

## 下一执行队列

1. `complete-platform-organization-governance`：已提交、clean-SHA 复验、同步并归档。
2. `complete-platform-approval-audit-center`：实现提交 `13243b4` 与归档证据 `008d6ac` 已推送；PG16、264 后端、46 浏览器、独立 HTTP、性能、备份恢复和合成 ETL 的 26/26 clean-SHA 总门禁通过；9 个 delta 已同步主规格并归档，纵切关闭。
3. `complete-platform-workbench-automation`：实现提交 `fedc98e` 已正常推送；28/28 clean-SHA 总门禁、277 后端、50 浏览器、真实 HTTP、p95 250.49 ms、备份恢复和合成 ETL 已通过；正在同步主规格并归档后关闭纵切。
4. 下一业务纵切从资产业态模板、招商自动分配/意向审批、企业画像、账收匹配催缴、租户服务、设备巡检 IoT、档案签章、HR、供应链、园企服务、驾驶舱、AI/集成中按证据顺序继续关闭。
5. 建设员工移动端与租户微信小程序并完成真实 API/数据库/浏览器（或小程序运行器）旅程，不能用 WebView 壳或本地 JSON替代。
6. 数据负责人/DBA 提供经授权旧 schema dump 与脱敏快照；在隔离 PG16 重跑全量/增量/中断/回滚/对账。
7. 集成负责人提供沙箱协议和短期凭据；SRE 在获批预发完成容量、监控告警和灾备。只有能力矩阵无 `MISSING/BLOCKED`、三端关键旅程通过、P0/P1=0 且生产部署另获人工授权后，才能非强制合并 main 并在最终 main 重验。

每个纵切固定执行：原始证据 → OpenSpec → DDD/API/迁移/UI → 单元/PG/HTTP/浏览器 → 安全/并发/性能 → 数据演练 → 截图/报告 → 正常提交与非强制推送。
