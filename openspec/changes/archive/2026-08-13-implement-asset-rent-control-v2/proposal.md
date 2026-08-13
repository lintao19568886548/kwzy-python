## Why

当前园区资产只有 Park、最小 Building 和扁平 Unit CRUD，PC 端仍要求手填园区 ID，无法表达分区/楼栋/楼层的稳定层级，也不能安全处理出租单元拆分合并和历史追溯。资产库存是招商、合同、计费、工单和经营分析的共同上游，因此必须先完成可版本化的资产与租控底座，避免后续领域继续建立在可覆盖、不可追溯的房源数据上。

## What Changes

- 建立园区内 `AREA / BUILDING / FLOOR` 空间节点树，支持租户/园区隔离、同级编码唯一、父子类型约束、停用和带占用保护的管理生命周期。
- 将出租单元绑定到空间节点，补充业态、计租面积、计价单位、挂牌价、可租日期、版本号和有效期，并保持 `used_area` 只能由有效合同占用投影计算。
- 增加受控拆分/合并命令：创建新版本单元、保留来源关系和历史快照，禁止覆盖历史或对有效占用执行破坏性变更。
- 提供统一租控查询和汇总 API，返回园区/空间/状态/业态过滤后的库存、空置、预留、占用、维修面积及出租率，并能下钻到单元、当前合同、Party 和工单摘要。
- 重建 PC 园区与租控页面，提供真实园区选择、空间树、矩阵/列表视图、筛选、状态图例、详情抽屉、创建编辑和拆并入口；满足桌面/平板响应式和键盘可达。
- 补齐 PostgreSQL 迁移、OpenAPI、权限/跨租户/并发/审计测试、浏览器 E2E、旧 `park/factory/factory_floor/rental/manage` 处置与合成迁移对账证据。
- **BREAKING**：`used_area` 不再接受任何客户端写入；对已有单元的空间归属、编码和计租面积变更通过版本/拆并命令完成，而不是原地覆盖。

## Capabilities

### New Capabilities

- `spatial-hierarchy-management`: 园区内分区、楼栋、楼层空间树的类型约束、唯一性、生命周期、审计和隔离。
- `rentable-unit-versioning`: 出租单元的业务字段、有效期、乐观并发、来源追踪以及受控拆分/合并规则。
- `rent-control-query`: 面向运营的租控库存查询、面积口径、出租率、状态聚合和详情下钻。
- `asset-rent-control-pc`: PC 空间树、租控矩阵/列表、详情和管理操作的交互、响应式与无障碍要求。
- `asset-data-migration`: 旧 park/factory/factory_floor/rental manage 到 V2 空间与单元的映射、幂等演练、对账和外部数据门禁。

### Modified Capabilities

- `park-scope-model`: 园区数据范围必须同样约束空间树、出租单元版本、租控汇总和下钻资源。

## Impact

- 后端：`park_property` domain/application/infrastructure/interface，lease 占用读取，审计与权限目录。
- 数据库：扩展 `buildings/units`，新增空间节点、单元版本来源关系和必要索引；Alembic 保持唯一 head 与可回滚。
- 前端：`ParksView.vue`、API 类型/调用和 Playwright 主链；不引入另一个 mock 数据源。
- 契约与证据：OpenAPI YAML、OpenSpec 主规格、旧能力处置、字段映射、合成 PostgreSQL ETL 与四份总控文档。
- 外部系统：不需要生产凭据；真实旧库 schema/data、生产迁移和生产发布继续需要人工授权。
