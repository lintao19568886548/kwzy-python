# 租户服务与工单迁移映射 V1

> 状态：本地产品纵切和合成 PostgreSQL 16 演练已实现。真实旧库迁移仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`。本文不构成生产数据读取、切换或回滚授权。

## 1. 旧证据边界

旧 Java `MaintenanceRepository` 证明存在动态探测的 `repair_order` 表及以下候选字段：`repair_order_id/order_no/source/tenant_id/tenant_name/tenant_phone/repair_type/description/images/status/priority/assignee/assignee_phone/process_images/process_remark/accept_time/finish_time/confirm_time/factory_id/park_id`。仓库没有权威建表 SQL、约束、状态字典、真实行数或脱敏生产快照，因此字段是否存在、类型和空值规则均不能由适配代码反推为生产事实。

旧实现的新增注释明确说明只写主表，不触发短信、企微或派单 worker；旧前端呈现的流程按钮也不能证明后端已持久化报价、验收、评价、SLA 或不可变事件。因此迁移不得补造这些事实。

## 2. 权威映射

| 旧候选字段 | V2 目标 | 规则 |
| --- | --- | --- |
| `repair_order_id` | `work_orders.source_type/source_id` | 固定来源 `LEGACY_REPAIR_ORDER`，原主键只作为外部引用；重复执行不得新增 |
| `park_id` | `work_orders.park_id` | 必须经已签字园区 key map；缺失或歧义进入隔离区 |
| `tenant_id` | `work_orders.party_id` | 旧 tenant 不是 V2 用户或租户隔离键，必须经 Party key map，不允许按名称猜测 |
| `tenant_name/tenant_phone` | 联系快照 | 姓名只在授权迁移窗口按脱敏策略处理；电话只保留掩码，报告不得出现原值 |
| `repair_type/description` | `category/title/description` | 类型用签字字典；描述按 PII 规则清洗，合成演练仅保存摘要指纹 |
| `status` | V2 状态机 | `待接单→SUBMITTED`、`处理中→IN_PROGRESS`、`待验收→WAITING_ACCEPTANCE`、`已完成→COMPLETED`、`已取消→CANCELLED`；未知值隔离 |
| `priority` | `priority` | `紧急→URGENT`、`高→HIGH`、`普通→MEDIUM`、`低→LOW`；未知值隔离 |
| `assignee` | `assignee_user_id` | 必须经员工 User key map；姓名或手机号不能直接关联 |
| `accept_time/finish_time/confirm_time` | 响应、送验、完成时间 | 必须单调且与状态一致；缺失不推算 |
| `images/process_images` | 证据引用 | 仅在对象清单、哈希和访问授权齐备后迁移；旧路径不等于对象已存在 |
| `process_remark` | 处理摘要 | PII 清洗后导入；不能据此生成报价、成本或验收记录 |

所有历史事件标为 `LEGACY_RECONSTRUCTED_NOT_PROVIDER_VERIFIED`，操作者为 `SYSTEM`；没有证据时不得创建租户确认、评价、外部通知送达、报价或实际成本。

## 3. 可执行合成演练

入口：`tools/etl/run_work_order_etl_drill.py`；固定输入：`tools/etl/fixtures/work_order_v1.json`。脚本强制 PostgreSQL、loopback 主机以及数据库名包含 `test/local/dev/audit`，只使用隔离 schema `etl_work_order_fixture`。

门禁：

1. dry-run 校验必填字段、主键/工单号重复和时间单调性；
2. 对未知状态执行指纹隔离，禁止静默映射；
3. 在工单写入后模拟中断并验证事务零残留；
4. 首次 apply 与映射数量一致，第二次 apply 新增数全为零；
5. 对账工单/事件/隔离数量、状态分布、孤儿、时间顺序、手机号掩码与 PII 泄漏；
6. 验证没有伪造报价、评价或外部送达；
7. 删除隔离 schema，并验证用户/角色/权限授权表行数不变。

## 4. 真实迁移阻塞与责任

| 阻塞证据 | 责任人 | 关闭条件 |
| --- | --- | --- |
| `repair_order` 授权 schema dump、DDL、约束、状态与优先级字典 | 旧系统 DBA / 数据负责人（待指定） | 提供版本化只读导出并签字 |
| 脱敏生产规模快照、基数、重复、孤儿和时间异常基线 | 数据负责人（待指定） | 在隔离预发布库完成全量对账 |
| 园区、Party、员工 User、出租单元 key map | 业务负责人 / 数据负责人（待指定） | 冲突清单关闭且映射版本冻结 |
| 历史附件对象清单、校验和、访问授权 | 运维 / 对象存储负责人（待指定） | 抽样下载与哈希一致 |
| 停写窗口、增量水位、备份点、恢复时间与回滚决策人 | 发布经理 / DBA（待指定） | 预发布全量+增量+恢复演练并获人工授权 |

生产部署和真实旧库读取均未获授权；不得将合成演练的 `PASS` 写成真实迁移完成。
