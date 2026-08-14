# 档案、签章与印章迁移切换 Runbook

状态：`CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA`。未取得授权旧库、脱敏二进制和外部签章证据，真实迁移保持 `BLOCKED`；本文不授权生产操作。

## 准入门槛

1. 数据所有者签字确认旧 schema、字典、保管期、分类、园区、责任人与业务来源映射。
2. 二进制清单包含来源键、路径/对象键、大小、MIME 与 SHA-256，且无开放 URL、明文身份材料或生产凭据。
3. 合规/法务确认历史 `signed` 状态处置；无证书和提供方验签事件的一律为未验证，不产生法律签署事实。
4. 印章台账与保管链必须有独立权威来源；若仍不存在，则迁移数量明确为 0。
5. 生产冻结、备份、目标环境、维护窗口、回滚负责人和业务签字均获人工授权。

## 预演步骤

1. 在隔离 PostgreSQL 16 空库执行 Alembic `upgrade head`，确认 `current == heads` 且唯一 head。
2. 对授权脱敏输入运行只读预检：结构、必填键、重复、枚举、文件可读性、大小与 SHA-256；输出不可逆指纹隔离表。
3. 在单事务内导入分类、档案元数据与二进制版本；注入故障后确认事务零残留，再从检查点重启。
4. 重复执行相同批次，确认档案号、来源键、版本号和校验值均零新增。
5. 对账来源/目标数量、分类/园区/密级分布、文件总字节、逐文件 SHA-256、孤儿外键、未验证签署、隔离原因和 0 个伪造印章/事件。
6. 导出签字报告，执行回滚，确认隔离 schema/对象存储测试前缀清空且身份授权数据未变化。

合成工具命令示例（仅本地测试库）：

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://<test-user>:<password>@127.0.0.1:<port>/<test-db>'
apps/api/.venv/Scripts/python.exe tools/etl/run_records_seal_etl_drill.py --out docs/06-implementation/evidence/records-signature-seal-governance/records-seal-etl-report.json
```

## 切换、验收与回滚

- 切换前：冻结旧写入、记录水位、完成数据库与二进制存储备份并实测恢复；保留旧系统只读窗口。
- 切换中：只处理已签字批次；任何数量/字节/校验和差异、未映射关键键或权限泄漏立即停止。
- 验收：业务所有者、档案管理员、印章保管人、法务/合规与技术负责人分别签署对账；外部签章需独立联调和证书验签报告。
- 回滚：停止 V2 写入，按批次清理迁移元数据与测试对象前缀，恢复备份并核对水位；不得删除旧生产二进制或撤销审计证据。

责任人目前均为 `UNASSIGNED / BLOCKED_PENDING_PROJECT_OWNER`，不得据此进入生产。
