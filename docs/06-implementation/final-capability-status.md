# 瞰维智管 V2 当前能力状态

> 更新时间：2026-08-14（Asia/Shanghai）
> 独立验收实现 SHA：`a9267d4c30096a7c80d66588ab06bc6838b32b0d`
> 完整报告：`independent-final-acceptance-report-20260814.md`
> 能力权威表：`full-rebuild-traceability-matrix.md`

## 已独立验证的范围

- 合同 V2：多出租单元、多费用、履约计划、审批、文档门禁、不可变版本、七类变更、续租和退租结算。
- 现有 PC 切片：Identity/System、Party、资产租控、招商 CRM、合同、基础账单/收款、待办、简版工单/催缴。
- 安全加固：密码策略、JWT/会话撤销、附件归属、RBAC/tenant/park scope、CSRF/Host/安全头、生产 fail-closed。
- 工程门禁：PG16 单 head 升降级、ORM/迁移契约、并发/回滚、OpenAPI、OpenSpec、依赖漏洞、容器、备份恢复和本地 HTTP 性能。

精确 SHA 的机器报告为 `evidence/independent-final-audit/acceptance-a9267d4.json`，24/24 步通过；这只证明已实现范围。

## 不能外推为完成的范围

- 员工移动端和租户微信小程序不存在。
- 设备/巡检/IoT、HR、供应链、园企服务、完整驾驶舱、真实 AI 业务层缺失。
- 组织/资产/招商/Party/账收/工单/档案/外部平台等组合能力仍有关键环节缺失。
- 没有经授权的旧生产 schema 或脱敏快照，无法完成真实迁移、对账、增量和切换演练。
- 没有外部厂商凭据、远程预发证据或生产部署授权。

## 状态摘要

```text
KWZY_INDEPENDENT_ACCEPTANCE=CONDITIONAL_IMPLEMENTED_SCOPE_ONLY
KWZY_BUSINESS_CLOSURE=BLOCKED
KWZY_BACKEND_REBUILD=CONDITIONAL_CORE_AND_CONTRACT_SLICE_ONLY
KWZY_PC_UI_REBUILD=CONDITIONAL_CORE_AND_CONTRACT_SLICE_ONLY
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
