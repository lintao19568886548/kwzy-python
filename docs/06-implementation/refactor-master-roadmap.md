# 瞰维智管 V2 全量重建主路线图

> 更新时间：2026-08-15（Asia/Shanghai）
> 当前独立验收基线：应收闭环精确提交 `1a11cfe08b8d2b800c7121d7462995ebb75eb75d` 的 clean-SHA 后端/前端/浏览器/性能门禁通过；上一 Party 精确提交证据继续有效
> 当前完成分支：`feat/full-rebuild-completion`，从 repair 推送记录 `37d7cf7da768eef8d7bcc743635117b8f34c7bbb` 创建；三条本地 safety ref 已保留。
> 总体状态：**BLOCKED — 已实现纵切通过，不等于三端、旧系统和全业务完成。**

## 权威顺序与永久门禁

冲突按真实业务规则与用户操作 → `docs/` 蓝图 → 旧 Java/旧前端/数据库证据 → OpenSpec/OpenAPI/ADR/测试 → 当前代码与历史报告裁决。

不连接生产，不覆盖用户未提交修改，不改已应用历史迁移，不 force push。没有真实凭据时只允许交付 fake/sandbox/fail-closed 适配和契约测试；没有旧数据时只允许给出合成迁移就绪结论。

## 当前阶段

| 阶段 | 已关闭范围 | 仍需关闭 | 状态 |
| --- | --- | --- | --- |
| 平台安全与工程底座 | 会话/JWT/密码、scope、组织/岗位/字段策略、版本化审批/任务/委托/SLA、哈希审计、事务事件、受限规则、站内通知、持久调度/独立 worker、多角色布局、附件、生产配置、PG pool/readiness、CI/容器/Runbook | 远程监控/告警/灾备证据 | IN_PROGRESS |
| 资产与租控 | 七类版本化业态模板、空间树/几何、单元精确模板版本、拆并血缘、矩阵/示意地图/列表/空置/到期/分析 | 商业 GIS/CAD/BIM 与真实旧坐标迁移需另有合同和授权数据，不冒充已接入 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 招商 CRM | 去重、人工/自动分配、公海、活动、第一类带看、匹配、版本化意向与统一审批、锁房、签名渠道适配器、转化 | OpenSpec 5.5 的审批撤销语义待业务架构裁决；真实渠道/企微联调、自动触达与 AI 评分由外部/AI 条目继续关闭 | CONDITIONAL_LOCAL_PRODUCT_SCOPE |
| Party 与合同 | Party/租户主档、组织企业画像/完整度、关联企业、受控证件指纹/附件、标签来源、本地风险处置；合同多单元/多费用/版本/变更/退租 | 个人身份材料不在本纵切；完整档案/签章/印章、外部工商提供商和真实旧数据另项关闭 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 账单、收款和催缴 | 履约计划自动出账、到账单箱、可解释匹配、财务确认/经理争议、多账单/预收后续核销、冲正、L1-L4 催缴和调整双人审批 | 真实银行/支付/税票/财务软件联调由外部适配器条目保持 `NOT_CONNECTED`，真实旧财务数据由迁移条目保持阻塞 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 服务与运营业务 | 简版工单 | 租户服务、派单/SLA/报价/验收、设备巡检 IoT、HR、供应链、园企服务 | MISSING |
| 决策与 AI | 多角色可配置实时运营工作台、待办/通知/自动化控制面和基础原单下钻 | 深色经营驾驶舱、完整指标口径、多园区比较、AI/人工确认门禁 | MISSING |
| 员工移动端 | — | 独立应用与现场 E2E | MISSING |
| 租户微信小程序 | — | 缴费/报修/访客/预约 E2E | MISSING |
| 迁移与切换 | 合成 dry/apply/中断/幂等/对账/回滚；本地备份恢复 | 旧 schema/脱敏快照、全量对账、CDC、停写、切换/回切 | BLOCKED_EXTERNAL_EVIDENCE |
| 生产交付 | 本地生产镜像/Compose 契约和操作 Runbook | 远程预发、监控告警、容量/灾备、生产授权 | BLOCKED_EXTERNAL_EVIDENCE |

## 下一执行队列

1. `complete-platform-organization-governance`：已提交、clean-SHA 复验、同步并归档。
2. `complete-platform-approval-audit-center`：实现提交 `13243b4` 与归档证据 `008d6ac` 已推送；PG16、264 后端、46 浏览器、独立 HTTP、性能、备份恢复和合成 ETL 的 26/26 clean-SHA 总门禁通过；9 个 delta 已同步主规格并归档，纵切关闭。
3. `2026-08-14-complete-platform-workbench-automation`：实现提交 `fedc98e` 与证据/主规格同步 `7741351` 已正常推送；28/28 clean-SHA 总门禁、277 后端、50 浏览器、真实 HTTP、p95 250.49 ms、备份恢复和合成 ETL 已通过；归档后 strict 66/66，纵切关闭。
4. `2026-08-14-complete-asset-portfolio-views`：实现提交 `44ae618` 已正常推送，30/30 clean-SHA 门禁、286 后端、52 浏览器、22 阶段真实 HTTP、七类模板/几何/多视图与合成 ETL 已通过；新增 r4 复合租户外键，拒绝跨租户/跨业态模板、空白名称和无效多边形；8 份 delta 已同步主规格并归档。
5. `complete-investment-crm-journey`：实现提交 `4f870af` 已正常推送，30/30 clean-SHA 门禁、298 后端、54 浏览器、真实 HTTP、p95 239.342 ms、备份恢复和 17 类合成迁移已通过；任务 5.5 的 `revoked` 与 delta spec 状态定义冲突，保持 active 且不伪归档，真实旧数据与供应商仍在独立条目阻塞。
6. `2026-08-14-complete-party-enterprise-profile`：实现提交 `e7d7263` 与 N+1 修复提交 `3680582` 已正常推送；31/31 clean-SHA、315 后端、57 浏览器、21 阶段真实 HTTP、p95 225.85 ms、PG 并发和合成迁移通过；9 份 delta 已同步主规格并归档，43/43 任务、归档后 strict 77/77。
7. `2026-08-14-complete-receivables-collection-lifecycle`：实现 `500efa5` 与 N+1/手机无截断修复 `1a11cfe` 已正常推送；唯一 head `w9f57b2c4d31`，clean-SHA 335 后端、真实 PG16/HTTP、2 条应收浏览器、p95 352.701 ms、合成 ETL、备份恢复和依赖审计通过；45/45 任务、8 份主规格同步、归档后 OpenSpec strict 85/85 和归档暂存树 915 文件 secrets scan 通过，纵切关闭。
8. 下一业务纵切从能力矩阵第 9 项租户服务/工单/报价/验收/评价开始，再按证据顺序关闭设备巡检 IoT、档案签章、HR、供应链、园企服务、驾驶舱、AI/集成。
9. 建设员工移动端与租户微信小程序并完成真实 API/数据库/浏览器（或小程序运行器）旅程，不能用 WebView 壳或本地 JSON 替代。
10. 数据负责人/DBA 提供经授权旧 schema dump 与脱敏快照；在隔离 PG16 重跑全量/增量/中断/回滚/对账。
11. 集成负责人提供沙箱协议和短期凭据；SRE 在获批预发完成容量、监控告警和灾备。只有能力矩阵无 `MISSING/BLOCKED`、三端关键旅程通过、P0/P1=0 且生产部署另获人工授权后，才能非强制合并 main 并在最终 main 重验。

每个纵切固定执行：原始证据 → OpenSpec → DDD/API/迁移/UI → 单元/PG/HTTP/浏览器 → 安全/并发/性能 → 数据演练 → 截图/报告 → 正常提交与非强制推送。
