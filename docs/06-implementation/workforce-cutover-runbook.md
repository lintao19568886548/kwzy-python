# HR、排班、考勤、绩效与资质迁移切换 Runbook

状态：`CONDITIONAL_SYNTHETIC_READY_FOR_AUTHORIZED_STAGING_DATA`。真实旧库、脱敏快照和主键/字典映射未取得，真实迁移保持 `BLOCKED`；本文不授权生产操作。

## 准入门槛

1. 数据所有者签字确认旧 schema、行数水位、员工/园区/用户映射、在离职/请假/打卡状态和时区规则。
2. 输入是授权脱敏快照；手机号、证件号、精确坐标、设备标识和附件均有传输、临时存储、销毁和审计方案。
3. 旧 `APPROVED` 请假须有审批实例或签字证据；无证据记录只能进入隔离和人工复核。
4. 绩效、资质没有权威聚合时迁移数量明确为 0；不得根据姓名、岗位或附件文件名补造记录。
5. 生产冻结、备份/恢复、维护窗口、回滚负责人、HR/隐私/技术验收和生产授权全部签字。

## 本地合成演练

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://<test-user>:<password>@127.0.0.1:<port>/<test-db>'
apps/api/.venv/Scripts/alembic.exe upgrade head
apps/api/.venv/Scripts/python.exe tools/etl/run_workforce_etl_drill.py --out docs/06-implementation/evidence/workforce-scheduling-attendance-performance/workforce-etl-report.json
```

演练步骤：

1. PG16 空库通过 Alembic base→head，确认唯一 `current == heads`；禁止 `create_all`。
2. dry-run 验证结构、必填键、重复、枚举、时区、主键映射和来源水位。
3. 只在受控进程读取原文 PII；目标仅写掩码/密钥指纹，精确坐标和轨迹列数量必须为 0。
4. 单事务导入员工、班次版本、排班、打卡、日汇总和请假；注入故障确认事务零残留。
5. 重复执行同一批次，所有表新增数必须为 0；同来源键异载荷必须中止。
6. 对账数量、状态、园区、排班日期、IN/OUT、异常、请假审批真相、隔离原因和孤儿外键；绩效/资质伪造数、工资结果生成数必须为 0。
7. 回滚隔离 schema，确认身份/RBAC 表行数不变。

## 授权预发与生产切换

- 全量前冻结字典和主键映射版本，记录旧库水位；全量后以 CDC/增量批次追平并验证重复安全。
- 停写窗口内再次对账员工、在职状态、当日排班/打卡、活动请假和资质到期；任何差异立即停止切换。
- 备份必须同时覆盖 V2 数据库、附件对象和密钥配置引用，并在独立恢复库验证 RTO/RPO。
- 切换后旧系统保持只读；业务所有者抽样完成入职、排班、打卡、请假、考勤汇总、绩效和资质旅程。
- 回滚时停止 V2 HR 写入，保存审计/隔离证据，按已签批批次反向清理或恢复备份；禁止删除旧生产记录。

责任人目前均为 `UNASSIGNED / BLOCKED_PENDING_PROJECT_OWNER`。生产部署与不可逆迁移仍等待人工授权。
