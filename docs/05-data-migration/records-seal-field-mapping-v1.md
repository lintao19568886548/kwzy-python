# 档案、签章与印章旧数据字段映射 v1

## 证据边界

现有旧 Java、旧前端和静态数据库证据只有通用附件与合同文档，没有找到可独立验证的档案分类/保管/借阅/处置聚合、印章台账/保管链或电子签章提供方事件聚合。旧合同本地模拟曾写入 `SIGNED`，但缺少证书、提供方回执和回调验签证据；V2 不继承该法律效力声明。

当前没有获得授权的旧库 schema dump、脱敏生产元数据与二进制、园区/分类/责任人键映射、文件 SHA-256 清单或真实签章证据。本映射和合成演练只能证明工具链准备度，不能证明真实数据迁移或外部签章连接完成。

## 核心映射

| 旧来源 | 旧字段 | V2 目标 | 规则 |
|---|---|---|---|
| 通用附件/合同文档 | `table:id` | 迁移 `source_key` | 来源表与主键组合；禁止仅按文件名去重 |
| 业务来源 | 类型 + 业务 ID | `records.source_type/source_id` | 需显式字典；未知来源隔离 |
| 园区/责任人 | 旧外键 | `park_id/created_by` | 必须使用授权键表；缺失或多义隔离，不猜测 |
| 档案分类 | 旧分类/人工决策 | `record_categories` | 分类、密级上限、按年/永久保管必须签字确认 |
| 文件二进制 | 内容 | `record_revisions` | 服务端读取二进制计算 SHA-256、大小和 MIME；无内容或校验清单隔离 |
| 合同 `signed` 标志 | 布尔值 | `LEGACY_SIGNATURE_UNVERIFIED` | 无提供方证书/事件不得导入为 `SIGNED` 或 `live_verified=true` |
| 旧印章 | 无可验证聚合 | `seal_assets` | 映射为 0；禁止依据合同图片或文本伪造印章台账、保管人或历史 |

## 隔离代码

- `CATEGORY_KEY_UNMAPPED`：分类键无唯一映射。
- `BINARY_MISSING_OR_INVALID`：二进制缺失、不可读取或 Base64/清单无效。
- `SIGNATURE_EVIDENCE_MISSING`：旧数据声称已签但无证书、提供方引用或验签事件。
- 真实预演还必须增加 `PARK_KEY_UNMAPPED`、`OWNER_KEY_AMBIGUOUS`、`DUPLICATE_BINARY_CONFLICT`、`CHECKSUM_MISMATCH` 和 `UNRESTRICTED_EXTERNAL_URL`。

## 演练与切换约束

入口为 `tools/etl/run_records_seal_etl_drill.py`，固定输入为 `tools/etl/fixtures/records_seal_v1.json`。脚本只允许 loopback PostgreSQL 与名称包含 test/local/dev/audit 的数据库，并仅使用隔离 schema `etl_records_seal_fixture`。它验证预检、事务中断零残留、首次写入、重复执行零新增、二进制校验、外键/数量/签章真实性对账，以及整体回滚不影响授权表。

真实预演前必须补齐授权 schema 与字典、脱敏元数据和二进制、SHA-256 清单、园区/分类/责任人/来源键表、重复决策、保管期决策及签字对账。生产冻结、备份、切换、对象存储删除和回滚仍需单独人工授权。
