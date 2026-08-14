# 设施设备旧数据字段映射 v1

## 证据边界

旧 Java 证据把消防、电梯、变压器和厂房维护分别保存，且存在匿名登记与物理删除入口；V2 不继承匿名默认租户、物理删除或按设备类型分表的语义。当前仅有代码和静态 SQL 证据，没有获得授权的旧库 schema dump、脱敏生产样本、园区/单元映射或 IoT 厂商事件样本。因此本映射与演练只能证明工具链准备度，不能证明真实迁移完成。

## 核心映射

| 旧来源 | 旧字段 | V2 字段 | 规则 |
|---|---|---|---|
| firefighting/elevator/transformer/factory_maint | 主键 | source_key | `legacy_table:source_id`，仅迁移追踪使用 |
| 各设备表 | park_ref | facility_devices.park_id | 必须通过授权的园区键映射；缺失时隔离 |
| 各设备表 | device_code | facility_devices.device_code | 去空白、转大写；租户内唯一 |
| 各设备表 | name/location | name/location | 必填、限长，不允许伪造缺失值 |
| type/table | device_type | device_type | 显式字典映射到 FIRE/ELEVATOR/TRANSFORMER/ELECTRICAL/HVAC/WATER/SECURITY/CUSTOM |
| status | status | status | 正常→ACTIVE，维修中→MAINTENANCE，已停用→RETIRED；未知值隔离 |
| manufacturer/model | manufacturer/model_no | 原样限长；无证据则保持 null |
| last_check_time | — | 迁移证据字段 | 不据此伪造巡检计划、检查项、结果或验收 |

## 演练与切换约束

入口：`tools/etl/run_facility_device_etl_drill.py`；固定输入：`tools/etl/fixtures/facility_device_v1.json`。脚本强制 PostgreSQL、loopback 主机和非生产数据库名，仅使用隔离 schema `etl_facility_device_fixture`，验证中断事务回滚、首次写入、重复执行零新增、设备类型/历史外键对账以及整体回滚。

真实预演前必须补齐：授权 schema dump、脱敏样本、园区/单元键映射、设备去重规则、状态字典、附件清单与校验和。IoT 绑定、告警和巡检任务不得从缺失证据推测生成；生产冻结、备份、切换和回滚仍需人工授权。
