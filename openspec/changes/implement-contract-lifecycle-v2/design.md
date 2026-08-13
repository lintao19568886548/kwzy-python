## Context

当前 `lease` 模块已经拥有 `lease_contracts`、`lease_contract_units`、`lease_terms`，支持 DRAFT→PENDING_ACTIVE→ACTIVE、cancel、terminate/breach、基础多单元占用和 `Unit.used_area` 投影。实现提交 `8adcd77` 还补入了 Lead 锁房与 Lease 激活串行化。现有不足是：已生效合同仍无乐观版本和不可覆盖历史，条款不形成可对账的费用/履约计划，变更和退租只能直接改状态，通用审批不会回调合同领域，附件没有合同版本语义，PC 仍手填内部 ID。

旧系统证据表明 `rental_tenant` 把主体、合同期、递增和状态混在一行，缺合同编号、版本历史、多房源组合、押金实体与变更闭环。V2 必须保持 Party→Lease→ParkProperty→Billing/Collection 的限界上下文：Lease 拥有合同与履约意图，ParkProperty 拥有单元可用性，Billing/Collection 拥有账单、核销、收退款；本 change 不用合同代码直接制造财务事实。

约束：PostgreSQL 16 是权威方言，同时保持 SQLite 快速测试；所有写入受 tenant/park/permission/expected-version 约束；无真实旧库、电子签章、支付或生产授权；现有 `/leases` 调用方需要可诊断的迁移路径。

## Goals / Non-Goals

**Goals:**

- 用稳定合同 ID + 不可变版本快照表达新签、续租、扩减租、换房、调价、主体变更和提前退租。
- 以结构化当前投影和确定性履约计划表达多单元、多费用、免租与递增，供后续出账消费。
- 将新签、变更和退租决定绑定审批、待办、审计和版本冲突，审批与业务生效同事务闭环。
- 退租先形成交接/财务清算快照，满足清算门禁后才释放单元并关闭合同。
- 提供范围一致的合同/租户画像 API 与可用 PC 工作台，并完成旧数据处置、合成 ETL 和全量本地门禁。

**Non-Goals:**

- 不自动创建、调整或冲销 Bill，不执行收款、退款、核销、会计凭证或银行/支付调用。
- 不宣称电子签章、OCR、印章、档案厂商已联调；只实现本地文档元数据和 fail-closed 端口。
- 不连接生产或真实旧库，不做 CDC、停写、生产迁移或部署。
- 不在本 change 创建员工移动端或租户小程序；相关合同旅程进入后续多端阶段。
- 不实现任意表达式计费、跨币种结算、会计税务规则或 AI 合同审查。

## Decisions

### 1. 稳定聚合根 + 不可变版本快照

`lease_contracts.id` 继续作为外部引用稳定的聚合根和当前投影，新增 `lock_version`、`current_version_no`、`contract_type`、`currency`、`approval_status`、`signed_at/effective_at/terminated_at` 与来源键。DRAFT 可编辑当前投影；首次激活写入版本 1，之后只有审批通过的变更单能写新版本并更新当前投影。

新增 `lease_contract_versions`，保存规范化 snapshot JSON、schema_version、SHA-256 checksum、base/change/approval 引用、创建者和时间，`(tenant_id, contract_id, version_no)` 唯一。快照包含合同头、排序后的 unit lines、charge items 和 schedule 摘要；写入后应用层禁止更新/删除。选择快照而不是复制整套 version 子表，是为了控制本阶段表数量并保证一次校验后的业务文档可重放；当前查询和约束仍使用关系化投影，避免把 JSON 当查询主库。

替代方案是“每个版本一条 lease_contracts”。该方案会改变所有现有外键、合同号和 Bill 引用，迁移风险更高，因此拒绝。

### 2. 基础状态机升级并保留兼容读

新写状态为 `DRAFT/PENDING_APPROVAL/PENDING_ACTIVE/ACTIVE/EXPIRING/EXIT_PENDING/TERMINATED/BREACHED/CANCELLED`。`submit` 不再直接进入 PENDING_ACTIVE，而是创建审批并进入 PENDING_APPROVAL；批准后才进入 PENDING_ACTIVE；激活写版本 1。旧 `RENEWED` 数据可读并在迁移中映射为终态历史，但新续租以同一合同根的新版本表达，不再产生新的 RENEWED。

这是有意的行为变化。旧客户端在 submit 后直接 activate 会得到 `LEASE_APPROVAL_REQUIRED` 409，并可根据返回的 approval 摘要进入批准流程，避免静默绕过审批。

### 3. 变更单使用“提议的完整未来快照”

新增 `lease_change_orders`：`change_type` 为 `RENEWAL/EXPANSION/REDUCTION/UNIT_TRANSFER/PRICE_ADJUSTMENT/PARTY_TRANSFER/EARLY_TERMINATION`，状态为 `DRAFT/SUBMITTED/APPROVED/APPLIED/REJECTED/WITHDRAWN/CANCELLED`，记录 `base_version_no`、`effective_date`、原因、schema-versioned proposal JSON、approval_id、applied_version_no、lock_version 与 idempotency_key。

命令创建时从当前投影生成完整候选快照，再应用类型专属补丁并执行统一不变量；批准不覆盖当前合同。`apply` 在 effective_date 到达后锁定合同和所有相关 current Unit（按 unit_id 升序），验证 base version、审批、占用和锁房，再原子写新版本、替换当前 unit/charge/schedule 投影、调整占用、关闭待办并审计。`apply-due` 是幂等服务/管理命令，不在本地验收中假装已有生产调度器。

同一合同至多一个 SUBMITTED/APPROVED 未应用变更，使用 PostgreSQL 部分唯一索引和应用校验双保险。替代方案“直接 PATCH ACTIVE 合同”无法保留历史和解决竞态，因此禁止。

### 4. 费用项与履约计划是 Billing 的只读上游意图

新增关系化 `lease_charge_items` 与 `lease_performance_schedules`。费用类型首版为 `RENT/PROPERTY/MANAGEMENT/PARKING/ENERGY_BASE/OTHER`；计价方式为 `FIXED/PER_AREA`；周期为 `MONTHLY/QUARTERLY/SEMI_ANNUAL/ANNUAL/ONE_TIME`。金额使用 Decimal，币种默认 CNY，税率只作为合同约定快照，不生成税务凭证。

计划生成规则必须确定：PER_AREA 使用合同 unit occupied_area 合计；金额以 0.01、ROUND_HALF_UP；周期从 charge start_date 对齐推进；免租和递增只能从周期边界生效，非边界输入拒绝，避免发明日均折算；每次提交前返回预览并由用户确认。schedule 行带 `(contract_id, version_no, charge_code, period_start)` 唯一 idempotency key。Bill 后续只能复制/引用已确认 schedule，不由本 change 写 Bill。

现有 `lease_terms` 在兼容期保留只读。可信的 INCREASE/RENT_FREE 在迁移中转换到 charge rule；OTHER 仅保留原文并标记 REVIEW_REQUIRED，不猜测金额。

### 5. 领域托管审批端口

Lease application 依赖 `ApprovalCommandPort`，不直接导入 workflow ORM。端口支持 `submit/approve/reject/withdraw/get` 的 `commit=False` 事务模式并写 append-only approval events。业务类型使用 `LEASE_CONTRACT_VERSION`、`LEASE_CHANGE_ORDER`、`LEASE_EXIT_SETTLEMENT`，biz_id 带业务 ID 和提交修订，允许驳回后重新提交新审批。

合同专用批准端点同时执行 approval decision 与合同状态推进；通用 `/approvals/{id}/approve|reject` 对上述 domain-managed 类型返回 `APPROVAL_DOMAIN_COMMAND_REQUIRED` 409，避免“审批已通过但合同没生效”的双写。批准者必须同时具备 `approval:decide` 与 `lease:approve`，且默认不得批准本人申请；`lease:approve_override` 仅管理员可用并强制理由审计。

### 6. 文档版本与外部签署 fail-closed

新增 `lease_contract_documents`，关联 contract/version/change/exit、attachment_id、document_type、document_version、checksum、status (`DRAFT/APPROVED/SIGNED/VOID`)、signature_provider/ref/time。附件内容继续由 attachments 上下文管理；Lease 只持引用和业务版本，不复制二进制。

`SignaturePort` 在 local/test 提供明确 fake 结果，production 配置不完整时返回 503 `SIGNATURE_PROVIDER_NOT_CONFIGURED`，不得把本地 `SIGNED` 模拟为外部签署成功。合同激活至少要求一个 APPROVED 或 SIGNED 主合同文档；测试 fixture 可通过本地批准文档满足，不要求真实签章。

### 7. 退租结算先清算、后释放

新增 `lease_exit_settlements` 与 `lease_exit_items`。结算状态为 `DRAFT/SUBMITTED/APPROVED/CLOSED/REJECTED/WITHDRAWN`，记录交接日、验房摘要、表计读数 JSON、押金持有快照、应收/扣减/应退明细、净应收/应退、billing outstanding snapshot、财务清算状态、证据附件和 lock_version。

ACTIVE/EXPIRING 合同提交退租后进入 EXIT_PENDING，但仍占用单元。只有结算已批准且 `financial_clearance_status=CONFIRMED`、无未解释余额、证据齐全时，`close` 才在同一事务释放占用、写终止版本、关闭待办并把合同置 TERMINATED。确认只记录经授权的线下/后续财务结果，不发起资金操作；金额不为零时必须引用外部结算证据和原因。

### 8. 查询与 PC 使用同一范围投影

仓储提供 tenant/park/permission 共用过滤器，列表、summary、详情、画像、版本和到期指标共用。租户合同画像按 Party 聚合当前/历史合同、current units、费用计划、审批/变更/退租状态和 Billing 只读余额摘要；无权园区不计入也不泄露计数。

PC `/leases` 重建为摘要+筛选+列表/到期视图+详情抽屉。创建/变更表单使用 `/parks`、`/parties` 和 current `/units` 选择器；所有冲突保留表单上下文并刷新 version。权限只控制展示，服务器仍是最终边界。共享布局必须保持 768px 无页面横向溢出及可见键盘焦点。

### 9. 事务与锁顺序

写命令统一检查 `expected_version`，冲突返回 `LEASE_VERSION_CONFLICT` 409 和最小最新版本摘要。变更应用、激活和退租关闭按 `lease_contract` → related `unit` ascending → domain approval/settlement rows 的顺序 `SELECT ... FOR UPDATE`，避免与 CRM unit lock 及 OccupancyService 死锁。任何 Party、version、schedule、Unit、WorkItem、audit 或 approval 写入失败都整体 rollback。

SQLite 覆盖领域/API 快速路径；并发唯一获胜、部分索引、JSON/Decimal 和事务回滚以 PostgreSQL 16 测试为权威。

### 10. 迁移和兼容

Alembic 在 `j6e24f9a1c08` 后新增唯一 revision。现有合同回填 `lock_version=1`；ACTIVE/EXPIRING/终态合同按当前头、units、terms 生成版本 1 和 checksum；DRAFT/PENDING_ACTIVE 保持 `current_version_no=0`，重新提交时进入新审批语义。`RENEWED` 只作为 legacy terminal 输入保留读取，迁移报告列出并映射血缘，不再接受新写。

独立 ETL 使用 loopback PostgreSQL schema `etl_contract_lifecycle_fixture`，覆盖传统 rental_tenant、附件、提醒和混合主体字段，执行 dry/apply/idempotent/reconcile/rollback。真实 schema、字段含义、PII、付款/押金余额无法确认时进入 quarantine 或 `BLOCKED_PENDING_SCHEMA_OR_SAMPLE`。

## Risks / Trade-offs

- [通用审批与领域状态可能分叉] → domain-managed 审批必须走合同命令，端口支持同事务且通用决定接口 fail-closed。
- [版本快照 JSON 不利于任意历史 SQL] → 当前运营查询使用关系化投影；快照用于审计/重放并带 schema_version/checksum，后续确需分析再投影。
- [费用规则过度设计或口径含糊] → 首版只支持有限枚举、周期边界和明确舍入；不支持的旧条款进入 REVIEW_REQUIRED，不猜测。
- [多单元变更与 CRM 锁房/Lease 激活死锁] → 统一锁顺序、短事务、PG 并发测试和稳定 409；读取不触发业务写。
- [退租“确认”被误解为已退款] → 字段命名为 clearance snapshot/evidence，API 与 UI 明示不执行资金动作，外部支付状态保持 NOT_LIVE。
- [submit 审批语义破坏旧客户端] → 返回稳定 409/审批摘要、更新 OpenAPI 和 PC/E2E，并在处置表记录兼容窗口。
- [表与 API 数量增长] → 保持单模块聚合、公共过滤器和端口边界；架构测试禁止 application→外域 infrastructure/ORM 依赖。

## Migration Plan

1. 发布旧接口处置、字段/枚举/PII 映射与 Alembic revision；在全新 PG16 做 base→head 和 head→-1→head。
2. 回填 lock/version/current projections 和可信 term 转换；生成校验 checksum，任何异常阻止事务提交。
3. 先上线兼容读取与新 selectors/query，再切换 PC 到 expected-version、审批和详情工作台。
4. 在 loopback 独立 schema 跑合成 dry/apply/idempotent/reconcile/rollback，并加入 full acceptance。
5. 预发/真实数据只能在人工提供脱敏 schema/sample 后另开批准步骤；生产迁移、CDC 和切换不在本计划执行。

回滚：本地/预发未切换前可 downgrade 单步并恢复备份；任何已创建 V2 版本/变更后不得在生产静默降级，必须走人工 Runbook 和数据导出确认。

## Open Questions

- 真实 `rental_tenant` schema、状态枚举、附件关联和押金/余额来源仍待授权样本；当前只允许合成映射并标记 conditional。
- 电子签章/OCR/档案厂商、验签协议和生产凭据未确定；本 change 只交付端口与 fail-closed 行为。
- 真实财务清算证明最终来自银行、支付还是人工凭证未确定；阶段 4 将选定权威来源，本 change 仅保存受审计 evidence reference。
