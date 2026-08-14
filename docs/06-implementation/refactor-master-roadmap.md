# 瞰维智管 V2 全量重建主路线图

> 更新时间：2026-08-15（Asia/Shanghai）
> 当前独立验收基线：HR/排班/考勤/绩效/资质闭环精确提交 `5577509a6ca2a473107038be1316a0ea9252fc8d` 的 37/37 后端/前端/浏览器/性能/迁移门禁通过；既有档案/签章/印章和设施设备/周巡检/IoT 证据继续有效
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
| Party 与合同 | Party/租户主档、组织企业画像/完整度、关联企业、受控证件指纹/附件、标签来源、本地风险处置；合同多单元/多费用/版本/变更/退租 | 个人身份材料不在本纵切；外部工商提供商和真实旧数据另项关闭 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 档案、签章与印章 | 版本化分类/保管、档号、附件版本/哈希完整性、保全/借阅/处置；印章台账/保管/用印/职责分离；签章提供方真相/信封/参与人/事件/沙箱和 PC 真栈 | 合法电子签、CA/时间戳/存证、真实印章设备与真实旧档案/二进制迁移需外部协议、凭据和授权数据 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 账单、收款和催缴 | 履约计划自动出账、到账单箱、可解释匹配、财务确认/经理争议、多账单/预收后续核销、冲正、L1-L4 催缴和调整双人审批 | 真实银行/支付/税票/财务软件联调由外部适配器条目保持 `NOT_CONNECTED`，真实旧财务数据由迁移条目保持阻塞 | CLOSED_LOCAL_PRODUCT_SCOPE |
| 服务与运营业务 | Party 绑定租户服务、完整工单；设备/周巡检/IoT 本地闭环；员工隐私档案、排班/考勤、原生审批请假、绩效/资质及 PC 真栈 | 员工移动端；库存/供应商联动；供应链、园企服务；真实 IoT/考勤设备 live 联调 | TENANT_SERVICE_FACILITY_AND_HR_CLOSED_LOCAL_PRODUCT_SCOPE / REMAINDER_MISSING |
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
8. `2026-08-15-complete-tenant-service-work-order-lifecycle`：实现 `ffa72e2` 已正常推送；唯一 head `y1b79d4e6f53`，精确提交 342 后端、59 浏览器、25 个 runtime/YAML 方法、1000/25 p95 302.333 ms/132.87 RPS/0 错误、1,383,498 bytes/114 表备份恢复、合成工单 ETL 与 942 文件密钥扫描通过；39/39 任务、8 份主规格同步和归档后 strict 93/93，纵切关闭。
9. `2026-08-14-complete-facility-device-inspection-iot`：实现 `00aaab6`，权限/浏览器竞态及证据稳定性修复至 `e28678b`，均正常推送；唯一 head `z2c80e5f6a64`，精确提交 352 后端、60 浏览器、32 个 runtime/YAML 方法、1000/25 p95 320.076 ms/135.6 RPS/0 错误、1,495,479 bytes/130 表备份恢复、设施合成 ETL 与 982 文件密钥扫描通过；39/39 任务、8 份主规格同步、归档后 strict 101/101，本地产品纵切关闭，真实 IoT/旧数据仍保持 NOT_CONNECTED/BLOCKED。
10. `2026-08-14-complete-records-signature-seal-governance`：实现 `95fa44d`，浏览器精确定位修复 `89c83b2`、Party 保存就绪竞态修复 `83697f9`、移动页签/表格无截断修复与证据提交 `b04d738`，均正常推送；唯一 head `b4ea2c7d8f86`，精确提交 36/36、366 后端、61 浏览器、33 个 runtime/YAML 方法、21/21 真实 HTTP、1000/25 p95 240.541 ms/146.259 RPS/0 错误、1,595,978 bytes/146 表备份恢复、合成档案 ETL 与 1,041 文件密钥扫描通过；40/40 任务、11 份主规格同步、归档后 strict 110/110，本地产品纵切关闭，合法电子签 live/真实旧数据仍保持 NOT_CONNECTED/BLOCKED。
11. `2026-08-14-complete-workforce-scheduling-attendance-performance`：实现 `370c7f8`、验收扩展 `5577509`；唯一 head `c5f02d8e9c87`，精确提交 37/37、380 后端、62 浏览器、28 个 workforce 路径、36 阶段真实 HTTP、1000/25 p95 264.836 ms/145.596 RPS/0 错误、1,697,402 bytes/162 表备份恢复和 HR 合成 ETL 通过；36/36 任务、9 份主规格同步、归档后 strict 119/119，本地产品纵切关闭，真实设备/旧数据仍 NOT_CONNECTED/BLOCKED。
12. 下一业务纵切按证据顺序关闭供应链，再处理园企服务、驾驶舱、AI/集成。
13. 建设员工移动端与租户微信小程序并完成真实 API/数据库/浏览器（或小程序运行器）旅程，不能用 WebView 壳或本地 JSON 替代。
14. 数据负责人/DBA 提供经授权旧 schema dump 与脱敏快照；在隔离 PG16 重跑全量/增量/中断/回滚/对账。
15. 集成负责人提供沙箱协议和短期凭据；SRE 在获批预发完成容量、监控告警和灾备。只有能力矩阵无 `MISSING/BLOCKED`、三端关键旅程通过、P0/P1=0 且生产部署另获人工授权后，才能非强制合并 main 并在最终 main 重验。

每个纵切固定执行：原始证据 → OpenSpec → DDD/API/迁移/UI → 单元/PG/HTTP/浏览器 → 安全/并发/性能 → 数据演练 → 截图/报告 → 正常提交与非强制推送。
