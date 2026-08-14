# 合同生命周期 V2：旧能力处置、字段映射与兼容边界

> 更新时间：2026-08-13（Asia/Shanghai）
> 证据范围：仅仓库 `docs/01-old-system-analysis`、当前 Python V1 代码与已归档规格；未连接旧库或生产。
> 真实旧数据状态：`BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`。

## 1. 处置原则

旧 `rental_tenant` 同时承载主体、联系人、合同期、递增、园区和状态，`tenant_image` 又混合租户/合同附件；V2 不做一表一页平移，而是拆为 Party、LeaseContract、Unit occupancy、charge/schedule、document、change/version 与 exit settlement。旧字段含义、单位、枚举或 PII 无法由仓库证据确认时，必须进入 quarantine 或 `BLOCKED_PENDING_SCHEMA_OR_SAMPLE`，不得猜值补齐。

## 2. 旧接口处置

| 旧接口 | 旧用途证据 | V2 处置 | 状态/备注 |
| --- | --- | --- | --- |
| `GET /api/rental/tenant/list` | 园区/状态/合同期/提醒列表 | `GET /api/v1/leases` + `GET /api/v1/leases/summary` | REDESIGN；tenant/park scope、稳定过滤/分页 |
| `GET /api/rental/tenant/{id}` | 混合租户合同详情 | `GET /api/v1/leases/{id}`；主体维度用 `GET /api/v1/tenant-contract-profiles/{party_id}` | SPLIT；不再把 Party 当合同行 |
| `POST /api/rental/tenant` | 名称、电话和合同条款一起新建 | Party 先建/复用，再 `POST /api/v1/leases` 建 DRAFT | SPLIT；不得按一行复制主体 |
| `PUT /api/rental/tenant/{id}` | 任意更新混合字段 | DRAFT 用 `PATCH /api/v1/leases/{id}`；ACTIVE 必须创建 typed change order | BREAKING；历史不可覆盖 |
| `DELETE /api/rental/tenant/{id}` | 删除租户/合同 | 激活前 cancel；激活后 exit settlement close | BREAKING；无合同硬删除 |
| `GET /api/rental/tenant/select` | 制单选租户 | 授权 eligible Party selector | REDESIGN；返回业务标签，不要求猜内部 ID |
| `GET /api/rental/tenant/{id}/sms-info` | 催缴联系人 | Party contact + Collection 专用受控读取 | DEFER_TO_COLLECTION；不由 Lease 返回完整电话 |
| `POST /api/llm/tenant-images` | 图片/OCR 分析 | attachments + contract document metadata + OCR port | ADAPTER_NOT_LIVE；生产无配置 503，不伪造识别 |
| `POST /api/investment/radar/crawler-task/run-internal-contract-expiry` | 内部合同到期爬取 | Lease expiry query + idempotent WorkItem projection | DEPRECATED_INTERNAL_CRAWLER；内部数据不再爬取 |
| `POST /api/investment/radar/crawler-task/sync-internal-contract-expiry` | 到期同步 | `GET /leases/summary` + 显式本地 due projection | REDESIGN；无生产调度器声明 |

仓库原始清单只证明上述 10 个入口和控制器名称存在，不证明请求字段、真实枚举、权限或副作用完整；任何未列长尾接口都保持 `NOT_DISPOSED_PENDING_SOURCE_EVIDENCE`。

## 3. 表与字段映射

| 旧来源/字段证据 | V2 目标 | 转换规则 | PII/就绪状态 |
| --- | --- | --- | --- |
| `rental_tenant.id` | `source_system=LEGACY_RENTAL_TENANT` + `source_ref` | tenant 内稳定字符串；不得作为新自增 id | READY_FROM_DOC |
| 租户/企业名称 | Party `display_name` / normalized name | 先 tenant 内匹配；一个 Party 可关联多合同 | PII_MINIMAL；真实去重待样本 |
| 联系人/电话 | PartyContact | 规范化后受 Party 权限管理；合同画像不默认返回原值 | PII_RESTRICTED |
| `park_id` | LeaseContract `park_id` + PartyParkRelation | 必须 tenant 内存在且授权；不写回 Party 单园字段 | READY_FROM_DOC |
| `contract_start/end` | Lease `start_date/end_date` | ISO date；end >= start；不推断时区 | READY_FROM_DOC |
| 合同状态字符串 | Lease V2 status / legacy disposition | 只映射有证据枚举；未知值 quarantine | BLOCKED_PENDING_SCHEMA_OR_SAMPLE |
| `increase_date/rate` | charge escalation rule | 仅日期、比率、基准费用和周期均可证明时转换；否则 REVIEW_REQUIRED | CONDITIONAL |
| 租金/费用/单位 | `lease_charge_items` | 仅确认 currency、周期、FIXED/PER_AREA 后生成；不猜税率/日折算 | BLOCKED_PENDING_SAMPLE |
| 地址 | PartyAddress 或合同通知地址 | 需证据区分企业地址/合同送达地址；PERSON 敏感地址不落 Party 普通字段 | PII_RESTRICTED |
| deposit/保证金 | Lease deposit snapshot | 只保存已证明金额/币种；不等于已收或可退 | BLOCKED_PENDING_LEDGER_EVIDENCE |
| `tenant_image` | Attachment + LeaseContractDocument | 保留 source ref、文件名、类型/校验和；二进制/路径需授权迁移 | PII_DOCUMENT_RESTRICTED |
| 合同到期提醒/backfill | WorkItem `CONTRACT_EXPIRING` | 由 Lease end_date 幂等投影；不迁移重复派生行 | DERIVED |
| `salary` / `salary_image` | HRM | 从 Lease 明确剥离，不进入合同迁移 | DEFER_TO_HRM |
| 押金/应收/实收/退款余额 | Billing/Collection + exit snapshot | 只有权威账务来源和对账签字后引用；Lease 不制造财务事实 | BLOCKED_EXTERNAL_DATA |

## 4. 枚举与 PII 规则

- V2 新写合同状态：`DRAFT/PENDING_APPROVAL/PENDING_ACTIVE/ACTIVE/EXPIRING/EXIT_PENDING/TERMINATED/BREACHED/CANCELLED`。
- V1 `RENEWED` 仅兼容读取/迁移历史，新续租通过同一合同根的新 version 表达；未知旧状态不自动映射。
- change type：`RENEWAL/EXPANSION/REDUCTION/UNIT_TRANSFER/PRICE_ADJUSTMENT/PARTY_TRANSFER/EARLY_TERMINATION`。
- charge method/cycle 仅支持规格明确枚举；非周期边界的免租/递增拒绝为 `LEASE_PRORATION_UNSUPPORTED`。
- 联系电话、地址、证件、附件内容、签名/证书、银行/支付信息均不得进入普通日志、OpenSpec fixture 或 Git；合成 fixture 使用明显虚构值。
- Quarantine 只保存 source ref、问题码、字段名和不可逆摘要；原始敏感值不得持久化到演练报告。

## 5. Python V1→V2 API/状态兼容

| V1 行为 | V2 行为 | 客户端迁移 |
| --- | --- | --- |
| `POST /leases/{id}/submit` 直接 DRAFT→PENDING_ACTIVE | **BREAKING**：DRAFT→PENDING_APPROVAL，并创建 `LEASE_CONTRACT_VERSION` 审批 | 读取 approval 摘要；由不同审批人走合同专用 approve，再 activate |
| submit/activate/terminate 等无版本体 | 每个 mutation 必须 `expected_version` | 缺失返回 422；过期返回 `LEASE_VERSION_CONFLICT` 409 + 最小最新摘要 |
| ACTIVE 可直接 terminate/breach 并释放单元 | 进入 EXIT_PENDING，完成 exit settlement/clearance 后 close 才释放 | 迁移到 exit create→submit→approve→clearance→close |
| ACTIVE 字段无版本更新路径 | ACTIVE 业务字段只允许 typed change order | 收到 `LEASE_CHANGE_ORDER_REQUIRED` 后保留表单并创建 change |
| `RENEWED` 是根终态 | 仅 legacy read；新 renewal 生成相同 contract id 的新 version | 不再等待/提交新的 RENEWED 状态 |
| 重试可能重复副作用 | apply/close 使用 tenant-scoped idempotency key | 相同 key+payload 返回原结果；不同 payload 冲突 409 |
| 通用 approval 可直接决定 | Lease-managed approval 必须走 Lease domain command | 通用 decide 返回 `APPROVAL_DOMAIN_COMMAND_REQUIRED` 409 |
| 签章/OCR 未建模 | document metadata 可用；外部 provider 未配置返回 503 | `SIGNATURE_PROVIDER_NOT_CONFIGURED` 不得当成功重试 |

保留现有 `/api/v1/leases` 资源路径和统一 envelope；具体新增 method/schema 以 OpenAPI YAML 和运行时契约测试为唯一可执行接口证据。

## 6. 业务边界与禁止声明

| 能力 | 本 change 可交付 | 本 change 禁止声称 |
| --- | --- | --- |
| Billing/Collection | 只读 outstanding snapshot、schedule 上游意图、clearance evidence reference | 自动出账、调账、收款、退款、核销、会计凭证 |
| 电子签章/OCR/档案 | port、local fake、fail-closed、契约测试 | 厂商已联调、签名合法有效、生产 LIVE |
| PC | 合同工作台关键链路、权限/错误/响应式 E2E | 全产品 PC 已完成 |
| 员工移动端/租户小程序 | 后续阶段保持 API 兼容 | 本阶段存在或完成任一移动端 |
| 数据迁移 | loopback 独立 schema 合成 dry/apply/idempotent/reconcile/rollback | 真实旧数据已验证、生产迁移可执行 |
| 运维/生产 | 本地 PG16、备份恢复、清理与机器报告 | 预发/生产部署、CDC、停写、切换或回切已执行 |

## 7. 当前结论

```text
CONTRACT_LEGACY_DISPOSITION=REPOSITORY_EVIDENCE_ONLY
CONTRACT_V1_API_MIGRATION=BREAKING_DOCUMENTED
CONTRACT_MONEY_MOVEMENT=OUT_OF_SCOPE
CONTRACT_SIGNATURE_OCR=ADAPTER_NOT_LIVE
CONTRACT_REAL_DATA_READINESS=BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE
CONTRACT_SYNTHETIC_MIGRATION_READINESS=PASS_CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA
CONTRACT_PRODUCTION_MIGRATION=NOT_EXECUTED
CONTRACT_PRODUCTION_DEPLOYMENT=NOT_EXECUTED
```
