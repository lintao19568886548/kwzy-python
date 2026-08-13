## Why

当前 Lease 只闭合了基础草稿、提交、激活、终止和占用投影；PC 仍要求手填园区/主体/单元 ID，条款不形成可执行费用计划，也没有乐观并发、审批、不可覆盖版本、续扩减调退、合同文档和退租结算证据。旧 `rental_tenant` 又把主体与合同揉在一表，无法安全支撑一个主体多合同、多单元与长期履约，因此阶段 3 必须在已归档基础合同规格上完成可审计的合同生命周期纵切。

## What Changes

- 强化 LeaseContract 聚合：合同类型、签署/生效信息、币种、版本号和乐观锁；维持 Party 与合同分离、租户/园区范围和合同号唯一。
- **BREAKING**：`submit` 改为进入 `PENDING_APPROVAL` 并创建领域托管审批，批准后才进入 `PENDING_ACTIVE`；新续租以同一合同根的新版本表达，不再写新的 `RENEWED` 根状态。
- 以不可覆盖的变更单实现续租、扩租、减租、换房、调价、主体变更和提前退租；审批生效时原子生成新合同版本、调整占用并保留前后血缘，禁止直接覆盖已生效合同历史。
- 建模多单元、多费用项与履约计划快照，支持固定金额/按面积、月/季/年周期、免租和递增规则；只产出确定性计费输入，不在本 change 自动创建 Bill。
- 将合同提交、变更和退租接入可审计审批：提交、批准、驳回、撤回及待办关闭均要求版本一致，并与现有 workflow/workbench 协作而不绕过服务边界。
- 增加合同文档版本与签署状态治理；本地附件元数据可用，电子签章/OCR/印章外部适配器保持 fail-closed `NOT_LIVE`。
- 增加退租交接与结算单：验房/表计/应收应退项目、押金抵扣和未结余额快照可审计；实际收款、退款、核销和财务凭证仍由后续 Billing/Collection 纵切执行。
- 提供租户合同画像与合同工作台查询：主体、当前/历史合同、占用单元、费用计划、变更、审批、文档和结算的范围化详情及到期/待审批/待交接指标。
- 重建 PC 合同工作台，使用授权园区、主体和 current 单元选择器，覆盖桌面/平板、键盘、loading/empty/error/403/409/503 和只读状态，不再要求手填内部 ID。
- 发布旧 `rental_tenant`/附件/提醒接口处置和字段映射，并以 loopback PostgreSQL 独立 schema 完成合成 dry-run、apply、幂等复跑、对账和 rollback；真实旧库与生产切换保持人工门禁。
- 扩展 Alembic、OpenAPI、领域/API/PostgreSQL 并发与事务测试、PC E2E 和全量本地验收；所有写命令使用 `expected_version` 和稳定 409 业务码。

## Capabilities

### New Capabilities

- `contract-change-lifecycle`: 合同变更单、不可覆盖版本血缘、审批生效和原子占用调整。
- `contract-pricing-schedule`: 多费用项、周期、计价方式、免租/递增及确定性履约计划快照。
- `contract-governance`: 合同/变更/退租审批、文档版本、签署状态、审计与外部签章 fail-closed 门禁。
- `contract-exit-settlement`: 退租交接、应收应退/押金抵扣快照、未结余额门禁和结算关闭规则。
- `tenant-contract-profile`: 主体维度的当前/历史合同、占用、费用、风险与运营指标查询。
- `contract-lifecycle-pc`: PC 合同工作台、真实选择器、详情/版本/审批/文档/结算交互与完整页面状态。
- `contract-data-migration`: 旧租户合同双轨处置、字段/枚举/PII 映射和隔离 PostgreSQL 合成演练。

### Modified Capabilities

- `lease-domain`: 从基础合同状态机扩展为带版本、乐观锁、多单元和生效变更约束的聚合规则。
- `lease-api`: 增加范围一致的查询/命令接口、`expected_version`、稳定冲突码和运行时/YAML 契约。
- `lease-occupancy`: 将变更单生效、换房、减租和退租纳入 Unit 行锁与占用投影原子更新。

## Impact

- 后端：`modules/lease`、`workflow`、`workbench`、`party`、`park_property`，以及只读协作的 `billing`/`collection` 边界。
- 数据库：扩展 `lease_contracts`/units/terms，并新增版本、变更、费用计划、文档和退租结算表；Alembic 保持唯一 head 和可回退。
- API/PC：扩展 `/api/v1/leases` 及合同工作台；更新 OpenAPI 与授权选择器，不保留要求用户输入内部 ID 的新主链。
- 迁移：新增本地合成合同 ETL；不连接生产、不导出真实 PII、不执行增量切换或生产部署。
- 外部系统：电子签章、OCR、支付/退款和财务凭证仅定义端口、fake/fail-closed 与契约测试，明确 `NOT_LIVE`。
- 产品边界：员工移动端、租户小程序、自动出账/收退款核销、真实外部联调、真实旧数据迁移和生产切换不在本 change 内，不得因本地验收宣称完成。
