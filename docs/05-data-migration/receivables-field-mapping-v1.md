# 应收、到账、核销与催缴迁移映射 V1

> 状态：本地产品纵切和合成 PostgreSQL 16 演练已实现。真实旧库迁移仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE`，本文不是生产切换授权。

## 1. 权威映射

| 旧证据 | V2 权威对象 | 迁移规则 |
| --- | --- | --- |
| `amount_bill` 头与宽表费项 | `bills` + `bill_lines` | 头金额必须等于可信费项行合计；未知费项隔离，不用 `OTHER` 静默吞并 |
| `receipt_time` / `receipt` | `receipt_transactions` | 先成为到账事实；只有旧核验有可追溯证据时才生成 `payments` |
| 已核验到账与账单关系 | `payments` + `payment_allocations` | 收款与核销分离；分配不得超过收款或账单可收余额 |
| 一次性催缴短信 | `collection_cases` + `collection_records` | 保留过程指纹；没有供应商回执时只能标记 `LEGACY_UNVERIFIED`，禁止写成已送达 |
| 无业务来源的 `finance` 行 | 隔离区 | `FINANCE_SOURCE_LINK_MISSING`，等待财务和数据负责人确认，不能伪造总账来源 |

付款账号只保留掩码或不可逆指纹；报告不得出现完整账号、手机号、姓名或原始短信正文。

## 2. 可执行合成演练

入口：`tools/etl/run_receivables_etl_drill.py`。脚本强制 PostgreSQL、loopback 主机以及包含 `test/local/dev` 的数据库名，并仅使用固定隔离 schema `etl_receivables_fixture`。

演练门禁：

1. dry-run 源金额、账期、外键和费项行合计；
2. 在 BillLine 后模拟中断，验证事务回滚零残留；
3. 首次 apply 与映射数量一致；
4. 第二次 apply 新增数全为零；
5. 对账账单总额、逐单行金额、实收、核销上限、孤儿、账号掩码、外部发送真实性和隔离原因；
6. 删除隔离 schema，并验证授权核心表行数未改变。

## 3. 真实迁移阻塞与责任

| 阻塞证据 | 责任人 | 关闭条件 |
| --- | --- | --- |
| `amount_bill/receipt/finance` 授权 schema dump 与字段字典 | 旧系统 DBA / 数据负责人（待指定） | 提供版本、类型、约束、状态字典和来源关系 |
| 脱敏生产规模快照及园区/主体/合同/账单主键映射 | 数据负责人（待指定） | 完成抽样、基数、金额、重复和孤儿基线签字 |
| 银行/支付渠道结算文件与回执口径 | 财务负责人 / 集成负责人（待指定） | 确认流水唯一键、退款/冲正、到账日和送达证据 |
| 停写窗口、增量水位、备份点、回滚时限 | 发布经理 / DBA（待指定） | 预发布全量+增量演练、恢复复核、人工授权 |

生产部署和真实数据读取均未获授权，脚本不得改为直连生产或旧生产库。
