# 瞰维智管 V2 当前能力状态

> 更新时间：2026-08-15（Asia/Shanghai）
> 最新已完成纵切：档案、电子签章与印章治理；精确提交 `b04d738bc75e865e1c6bfb180e93dc9b95109cf3` 全门禁已通过并正常推送
> 完整报告：`independent-final-acceptance-report-20260814.md`
> 能力权威表：`full-rebuild-traceability-matrix.md`

## 已独立验证的范围

- 合同 V2：多出租单元、多费用、履约计划、审批、文档门禁、不可变版本、七类变更、续租和退租结算。
- 现有 PC 切片：Identity/System、Party、资产租控、招商 CRM、合同、应收全生命周期、待办、租户服务与完整工单生命周期。
- 应收闭环：履约计划自动出账、到账单箱、可解释候选、财务确认/经理争议、多账单与预收后续核销、冲正、L1-L4 催缴和调整双人审批；外部渠道连接状态不伪造。
- 租户服务闭环：数据库派生 User→Party→园区主体授权、员工/租户受理、不可变规则发布/退役、自动与人工派单、SLA、版本报价/决定、追加式成本/冲正、完工证据、返工/验收、一次性评价及脱敏时间线。
- 设施闭环：设备台账/历史、周巡检模板/计划/任务、异常/漏检转工单、IoT 提供方真相/绑定/告警关联与升级；真实 IoT 仍保持 `NOT_CONNECTED`。
- 档案/签章/印章闭环：版本化分类与保管、档号/附件版本/哈希完整性、保全/借阅/处置、印章保管与高风险用印职责分离、签章信封/事件和真实提供方状态；沙箱不产生法律 `SIGNED`。
- 安全加固：密码策略、JWT/会话撤销、附件归属、RBAC/tenant/park scope、CSRF/Host/安全头、生产 fail-closed。
- 工程门禁：PG16 单 head 升降级、ORM/迁移契约、并发/回滚、OpenAPI、OpenSpec、依赖漏洞、容器、备份恢复和本地 HTTP 性能。

应收精确 SHA 已通过 335 pytest、真实 PG16、2 条专项 Playwright、1000/25 性能（p95 352.701 ms、107.841 RPS、0 错误）、合成 ETL、备份恢复和依赖审计；45/45 OpenSpec 任务已归档，归档后 strict 85/85、归档暂存树 915 文件 secrets scan 0 hits。综合机器证据为 `evidence/receivables-collection-lifecycle/acceptance-clean-1a11cfe.json`。既有精确 SHA 机器报告继续保留；所有证据只证明已实现范围。

租户服务/工单精确提交 `ffa72e2` 全验收已通过 33/33 步、342 pytest、真实 PG16、59 条全量 Playwright、前端 lint/typecheck/6 Vitest/production build、OpenAPI 13/13+YAML strict、OpenSpec 86/86、1000/25 性能（p95 302.333 ms、132.87 RPS、0 错误）、1,383,498 bytes/114 表备份恢复、工单合成 ETL 和 942 文件 secrets scan。机器报告为 `evidence/tenant-service-work-order-lifecycle/acceptance-clean-ffa72e2.json`；39/39 OpenSpec 任务、8 份主规格同步和归档后 strict 93/93 通过。真实旧 `repair_order` 与供应商接入仍按证据保持阻塞/未连接。

档案/签章/印章精确提交 `b04d738` 全验收已通过 36/36 步、366 pytest、真实 PG16、61 条全量 Playwright、前端 lint/typecheck/6 Vitest/production build、OpenAPI 15/15+YAML strict、OpenSpec 102/102、1000/25 性能（p95 240.541 ms、146.259 RPS、0 错误）、1,595,978 bytes/146 表备份恢复、21/21 真实 HTTP、档案合成 ETL和 1,041 文件 secrets scan。机器报告为 `evidence/records-signature-seal-governance/acceptance-clean-b04d738.json`；合法电子签/CA/时间戳/存证、真实印章设备及真实旧档案/二进制迁移没有凭据或授权，不计 live 完成。

## 不能外推为完成的范围

- 员工移动端和租户微信小程序不存在。
- HR、供应链、园企服务、完整驾驶舱、真实 AI 业务层缺失。
- 员工移动端、租户微信小程序、HR、供应链、园企服务、驾驶舱、AI、外部平台八个组合能力仍为 `MISSING`；设备/巡检/IoT 与档案/签章/印章只关闭本地产品纵切，live 供应商与真实旧数据仍由外部适配器/迁移条目保持缺口或阻塞。
- 没有经授权的旧生产 schema 或脱敏快照，无法完成真实迁移、对账、增量和切换演练。
- 没有外部厂商凭据、远程预发证据或生产部署授权。

## 状态摘要

```text
KWZY_INDEPENDENT_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_BUSINESS_CLOSURE=BLOCKED
KWZY_BACKEND_REBUILD=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_EMPLOYEE_MOBILE=MISSING
KWZY_TENANT_MINIPROGRAM=MISSING
KWZY_LEGACY_REPLACEMENT=BLOCKED
KWZY_DATA_MIGRATION_REHEARSAL=CONDITIONAL_SYNTHETIC_ONLY
KWZY_SECURITY_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_PERFORMANCE_ACCEPTANCE=CONDITIONAL_LOCAL_LOOPBACK_ONLY
KWZY_OPERATIONS_READINESS=CONDITIONAL_LOCAL_ONLY
KWZY_FULL_REBUILD_ACCEPTANCE=BLOCKED
KWZY_PRODUCTION_DEPLOYMENT=AWAITING_HUMAN_APPROVAL
```

禁止把上述任何 `CONDITIONAL` 改写为全产品 `PASS`。当前 P0 为 0，但 P1 产品/迁移/外部环境验收阻塞仍存在。
