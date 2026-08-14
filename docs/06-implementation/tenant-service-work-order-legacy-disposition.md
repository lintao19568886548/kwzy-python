# 租户服务与工单旧系统处置

> 日期：2026-08-15
> 结论：本地 V2 API/PC 产品纵切替代旧维修工单 CRUD；真实旧数据、附件和外部通知切换仍阻塞。

## 原始证据裁决

旧 Java `MaintenanceController` 暴露维修工单列表、详情和增删改查；`MaintenanceRepository` 动态探测 `repair_order` 字段。旧后端新增逻辑的注释明确表示只写工单主表，不执行派单或通知。旧前端虽然展示“待接单→处理中→待验收→已完成”和 workflow 操作，但在已检查后端中没有对应 workflow 路由，因此 UI affordance 不能作为后端完成证据。

仓库未提供 `repair_order` 权威 DDL、约束、状态字典、生产行数、脱敏快照或附件对象清单。V2 不根据候选字段反推生产事实，也不补造旧系统没有留下的报价、评价、SLA、供应商送达或 IoT 来源。

## 处置矩阵

| 旧能力/证据 | V2 处置 | 状态 |
| --- | --- | --- |
| 维修工单列表/详情/创建/编辑 | Party/园区范围的员工与租户受理、列表、详情和版本化命令 | REPLACED_LOCAL |
| 宽表可变状态 | WorkOrder 聚合 + append-only 事件、报价、成本、验收和评价 | REPLACED_LOCAL |
| 旧前端 workflow 按钮 | 以真实 API 的派单、开工、报价决定、完工、返工和验收替代 | REPLACED_LOCAL |
| 人工负责人字段 | 规则版本自动派单、原因化改派、合格处理人和 WorkItem 所有权 | REPLACED_LOCAL |
| 图片/处理图片路径 | 只迁移获授权对象清单中可校验的安全引用；不把路径当作对象存在证据 | BLOCKED_EXTERNAL_DATA |
| 手机号/租户名称 | 手机仅保留掩码；租户名称必须经 Party key map，不按名称猜测 | BLOCKED_EXTERNAL_DATA |
| 短信/企微通知 | 端口保持 fake/local/fail-closed，未标记真实联通 | NOT_CONNECTED |
| 旧 `repair_order` 数据 | 合成 PG16 演练就绪；真实迁移需授权 schema、状态字典、脱敏样本和映射签字 | BLOCKED_EXTERNAL_DATA |
| 生产切换 | 未执行，需停写窗口、备份、对账、回切演练和人工授权 | AWAITING_HUMAN_APPROVAL |

## 切换门禁

真实替代只有在旧 schema/状态字典、Party/park/user/unit 映射、附件哈希清单、全量与增量对账、业务签字和回切演练全部完成后才能关闭。当前本地产品纵切已验证，但全系统旧系统替代仍为 `BLOCKED`。
