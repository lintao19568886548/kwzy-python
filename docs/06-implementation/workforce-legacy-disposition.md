# HR、排班、考勤、绩效与资质旧系统处置

状态：本地产品纵切已实现，真实旧数据迁移仍为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_SNAPSHOT_DICTIONARIES_AND_KEYMAPS`。本文件不授权生产连接或数据变更。

## 证据裁决

旧 Java/前端证据包含员工 CRUD、固定办公点打卡、请假 CRUD、考勤统计/工资准备摘要和轨迹查询。仓库没有权威生产 DDL、行数水位、状态字典、脱敏快照、园区/用户主键映射，也没有可证明的绩效或资质历史聚合。

| 旧能力 | V2 处置 | 说明 |
| --- | --- | --- |
| 员工 CRUD | REBUILD | 受租户/园区约束的员工档案、用户绑定、状态历史、乐观锁；手机号/证件号仅存掩码与密钥指纹 |
| 固定办公点打卡 | REBUILD_WITH_HARDENING | 可配置地点只保存密钥/配置引用；打卡幂等，不保存精确经纬度或轨迹 |
| 请假 CRUD | REBUILD_WITH_APPROVAL_TRUTH | 提交原生审批并以审批实例为权威；旧 `APPROVED` 无证据时进入 `PENDING_REVIEW`/隔离，禁止伪造审批完成 |
| 考勤统计 | REBUILD | 不可变班次版本、日排班、打卡汇总、缺卡/迟到等异常与人工有因调整 |
| 工资摘要 | PAYROLL_READY_ONLY | 输出工资规则可消费的考勤汇总；不计算、签发或支付工资 |
| 轨迹查询 | RETIRED_BY_SECURITY_DESIGN | V2 不建设员工轨迹库；此为隐私最小化设计，不是已获业务退休批准，能力矩阵不据此记 `APPROVED_RETIRED` |
| 绩效 | REBUILD_NEW_LOCAL_SCOPE | 周期、目标权重、禁止自评、发布和员工确认；无旧聚合时迁移数量为 0 |
| 资质 | REBUILD_NEW_LOCAL_SCOPE | 类型、附件证据、证书号掩码/指纹、复核/吊销/到期待办；无旧聚合时禁止伪造 |
| 考勤设备/生物识别 | NOT_CONNECTED | 只保留严格适配边界；没有协议、凭据和合法性证据，不宣称 live |

## 字段与隐私映射

| 来源候选 | V2 目标 | 规则 |
| --- | --- | --- |
| employee id/no | `source_key` / `employee_no` | 先完成租户、园区、用户主键映射；重复或未映射即隔离 |
| mobile/id number | `*_masked` + `*_fingerprint` | 原文只在受控导入进程内短暂存在；日志、报告和目标表禁止原文 |
| office latitude/longitude | location `config_ref` / `location_fingerprint` | 精确坐标进入外部密钥/地理围栏服务；业务库禁止经纬度和轨迹列 |
| punch | `workforce_attendance_punches` | 来源键绑定幂等；同键异载荷冲突；时区必须明确 |
| leave approved | `workforce_leave_requests` + Approval | 缺原生审批或签字证据时只能待复核并隔离 |
| salary summary | attendance summary | 只迁移可复算事实，不迁移或生成工资结果 |
| performance/qualification | corresponding aggregates | 权威聚合缺失时数量必须为 0 |

## 禁止外推

- 合成迁移通过不等于真实旧库迁移、增量同步或切换完成。
- `MANUAL/MOBILE/DEVICE` 打卡接口通过不等于真实考勤机、生物识别或定位服务已接入。
- 工资准备摘要不等于薪资核算、个税、社保或支付能力。
- PC 响应式页面不等于员工独立移动端；员工移动端仍由能力矩阵第 11 项独立关闭。

真实迁移责任人仍为 `UNASSIGNED / BLOCKED_PENDING_PROJECT_OWNER`；必须由数据所有者、HR 业务负责人、安全/隐私负责人和 DBA 共同签字。
