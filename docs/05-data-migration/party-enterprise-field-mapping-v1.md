# Party 企业画像旧系统处置与迁移映射 V1

> 状态：本地产品纵切已实现；合成迁移演练可执行；真实旧数据迁移因缺少授权 schema dump、脱敏样本和主键映射而保持 `BLOCKED_PENDING_LEGACY_EVIDENCE`。本文不构成生产迁移授权。

## 1. 原始证据与可信边界

| 证据 | 已确认事实 | 限制 |
| --- | --- | --- |
| `D:\lintao\kwzg-Java\apps\backend-springboot\src\main\java\cn\yizuw\magic\backend\rental\tenant\RentalTenantCreateRequest.java` / `RentalTenantUpdateRequest.java` | 旧 `rental_tenant` 请求把企业名称、电话、租赁地址、园区、面积、租期、租金、递增、违约金和图片混为一个对象 | 只能证明代码期望字段，不能替代真实生产 schema 和数据样本 |
| `D:\lintao\kwzg-Java\apps\backend-springboot\src\main\java\cn\yizuw\magic\backend\rental\tenant\RentalTenantRepository.java` | 旧表直接读写 `tenant_name/phone_number/address/park_id/contract_start/contract_end/rental_amount/...`，并物理删除主行 | 旧表缺少 Party/Lease 领域边界、历史版本和 V2 租户复合外键 |
| `D:\lintao\kwzg-Java\apps\backend-springboot\src\main\java\cn\yizuw\magic\backend\investment\InvestmentRepository.java` | Radar `enterprise_profile` 投影包含 company、统一信用代码、行业、地区、注册资本、规模、经营范围、信号数和完整度；`enterprise_tag`、`signal_event` 通过公司名称关联 | 旧实现按表/列存在性降级为空；无法据此证明来源真实性、租户隔离或外部提供商在线 |
| `D:\lintao\kwzg-Java\playground\src\views\investment\radar\enterprise-profiles.vue` | 旧 PC 页面可查列表、详情、标签、信号和刷新；完整度由旧投影直接返回 | 刷新动作不等于真实外部核验，旧页面没有 V2 的本地主档、凭证权限和乐观锁证据 |
| `docs/01-old-system-analysis/08-python-rebuild-suggestion.md` | 蓝图要求将三套客户统一为 Party，并把 `rental_tenant` 拆成 Party、Lease 和版本化合同事实 | 仓库分析，不是生产数据证明 |

证据结论：旧 `rental_tenant` 和 Radar 画像是两个重叠但不同的旧概念。V2 以 `Party(ORGANIZATION)` 为唯一企业主档；租金、面积、租期、递增、违约金和合同图片进入 Lease/Unit/Attachment 上下文，不复制进企业画像。旧 Radar 的来源声明只按 `MIGRATION/EXTERNAL + UNVERIFIED` 导入，不能自动成为已核验事实。

## 2. 替代、保留与阻塞处置

| 旧能力 | V2 处置 | 状态 |
| --- | --- | --- |
| `rental_tenant` 企业名称/电话/地址/园区 | `parties` + `party_contacts` + `party_addresses` + `party_park_relations` | 本地替代已实现；真实映射阻塞 |
| `rental_tenant` 面积/租期/租金/递增/违约金 | `units`、`lease_contracts`、合同费用/条款/版本链 | 明确排除企业画像；由合同能力承接 |
| `tenant_image` | 受控 `attachments`，按业务对象和园区验证 | 本地替代已实现；对象存储生产凭据未提供 |
| Radar `enterprise_profile` | `party_enterprise_profiles` + Party 主档 + 地址/联系人实时维度 | 本地替代已实现；真实导入阻塞 |
| Radar `enterprise_tag` | 带来源、置信度、核验状态和生命周期的 `party_enterprise_tags` | 本地替代已实现；外部标签默认未核验 |
| Radar `signal_event` | append-only `party_enterprise_risk_signals` + resolution | 本地风险替代已实现；不宣称外部信用评分 |
| Radar 刷新/外部工商核验 | provider 状态固定 `NOT_CONNECTED`，本地 API 禁止写 `EXTERNALLY_VERIFIED` | 外部集成阻塞 |
| 自然人身份证件 | 不进入本变更的表、API、fixture 或日志 | 依据现有隐私/KMS 边界拒绝，不视为延期实现 |

## 3. 字段映射规则

| 旧字段/概念 | V2 目标 | 规则与隔离条件 |
| --- | --- | --- |
| `rental_tenant_id` / `enterprise_id` / `profile_id` | 迁移 source key + 外部映射表 | 不复用为 V2 主键；必须先解析 tenant、Party、park、attachment 映射 |
| `tenant_name` / `company_name` | `parties.name` | trim 后组织名称匹配；同租户多候选进入隔离，不按名称静默合并 |
| `unified_social_credit_code` | `parties.credit_code` | 仅组织标识；规范化后参与候选匹配；冲突进入隔离 |
| `phone_number` | `party_contacts.phone` | 作为主联系人候选；没有联系人姓名时不得伪造真实姓名 |
| `address`、region 三段 | `party_addresses` | `rental_tenant.address` 是租赁地址候选；Radar 地区是注册地址候选，来源必须保留 |
| `park_id` | `party_park_relations.park_id` | 必须通过旧园区→V2 园区映射并通过租户边界 |
| `registered_capital` | profile `registered_capital/capital_currency` | 资本存在时币种必填；旧币种未知则隔离或留空，禁止默认制造事实 |
| `industry_name` / tags JSON | profile industry + enterprise tags | 未知行业码可只保留名称；标签拆行、规范化、`source_type=MIGRATION`、未核验 |
| `employee_scale` | profile `employee_size_band` | 仅允许显式映射到枚举；未知值进入隔离报告 |
| `business_scope` | profile `business_scope` | 长度与控制字符校验；保留来源，不拼入合同备注 |
| `profile_completeness` | 不迁移 | V2 从当前主档和子记录重新计算，禁止信任旧分数 |
| `signal_event.*` | risk signal | 每条来源引用幂等；摘要安全化；严重度/类别未知则隔离；不能改变 blacklist 状态 |
| `enterprise_tag.*` | enterprise tag | active 名称按规范化值唯一；来源、置信度、核验状态不丢失 |
| 组织证照标识 | credential fingerprint + masked suffix | 传输中规范化，落库 SHA-256 和后四位掩码；响应、审计和日志不留原文 |
| 个人身份证号/个人证件 | quarantine | `PERSONAL_IDENTITY_FORBIDDEN`；需独立 KMS/信封加密 ADR 后才可重新评估 |

## 4. 可复算公式

### 完整度

总分严格限定 0–100：统一信用代码 15；法定代表人 10；成立日期 10；注册资本+币种 10；登记状态 5；行业代码/名称 10；经营范围 10；有效注册地址 10；有效主联系人 10；有效营业执照凭证 10。客户端分数与旧 `profile_completeness` 均被忽略；响应同时列出缺失维度。

### 关系规范化与防环

`COMMON_CONTROL`、`BUSINESS_PARTNER` 按较小 Party id 作为 source 存储；`PARENT_OF`、`INVESTED_IN` 保持方向。禁止自环、活动重复边；新增 `PARENT_OF` 前在租户 advisory transaction lock 下递归检查 target 是否能到达 source。

### 本地风险汇总

只统计尚无 resolution 的本地信号；总级别为 `CRITICAL > HIGH > MEDIUM > LOW > NONE` 的最大值，并返回各级数量和未解决总数。该结果与 `Party.risk_status` 黑名单独立，且不是外部信用评分。

### 凭证指纹

组织标识先转大写并删除非字母数字字符，再计算 SHA-256 十六进制 64 字符；展示值固定为 12 个 `*` 加最后四位。原文只存在于单次请求内存，不进入响应、业务事件、审计明细或数据库列。

## 5. 演练与真实切换门禁

可执行合成演练：`tools/etl/fixtures/party_enterprise_v1.json` + `tools/etl/run_party_enterprise_etl_drill.py`。门禁覆盖 dry-run、事务中断零残留、首次 apply、checkpoint 幂等复跑、逐表计数/孤儿/指纹/提供商状态对账和隔离 schema 回滚。fixture 明确 `synthetic_only=true`、`contains_real_customer_data=false`，不得作为真实迁移完成证据。

真实切换前必须由数据责任人提供并批准：

1. 旧租户库与 Radar 库的 schema dump、字段注释、枚举分布和约束；
2. 脱敏样本及记录总量/空值/重复/孤儿基线；
3. tenant、park、Party、user、attachment 主键映射与冲突裁决人；
4. 对账阈值、隔离处置责任人、停写窗口、备份点和回滚时限；
5. 生产数据库、对象存储和外部提供商的单独人工授权。

在以上证据缺失时，真实迁移状态必须保持 `BLOCKED`，外部提供商保持 `NOT_CONNECTED`，生产部署保持 `AWAITING_HUMAN_APPROVAL`。
