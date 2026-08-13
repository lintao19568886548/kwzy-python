## Context

当前模型已有 `parks`、最小 `buildings`、`units` 与合同占用投影，但 Building 没有管理 API，Unit 是扁平可覆盖记录，PC 页面仅有两个简表和手填 ID。已有合同通过 `lease_contract_units.unit_id` 引用单元，`used_area` 由 `OccupancyService` 汇总有效合同；新设计必须保留这条已验证链路、租户/园区过滤和 SQLite/PostgreSQL 双测试能力，同时把资产变成可追溯的多层库存。

旧系统以 park/factory/factory_floor 表达园区、厂房、楼层，`factory_floor.used_area` 与租赁信息混杂。V2 不复刻旧表，而用明确空间树、版本化出租单元和查询投影承接。

## Goals / Non-Goals

**Goals:**

- 在现有模块内交付 AREA/BUILDING/FLOOR 空间树和真实管理 API。
- 让结构性单元变化、拆分和合并保留历史、来源关系与面积对账。
- 建立一个服务端口径统一、园区范围安全的租控查询与 PC 运营工作区。
- 保持旧合同引用和占用投影可用，迁移可升级/回滚且并发失败可解释。
- 交付自动测试、OpenAPI、合成 ETL、旧能力处置和本地验收证据。

**Non-Goals:**

- GIS/CAD/BIM 编辑器、真实地图底图采购或三维数字孪生。
- 本变更内重写合同变更、自动计费、IoT、员工移动端或租户小程序。
- 连接旧生产库、执行生产迁移/部署或取得供应商凭据。
- 将合成 fixture 证明描述成真实旧数据迁移完成。

## Decisions

### D1 — 演进现有 buildings 表为通用空间节点

保留表名与 `Building` ORM 以避免破坏现有 `units.building_id` 外键，但增加 `parent_id`、`node_type`、`code`、`sort_order`、`status` 和扩展属性；应用接口使用“space/spatial node”语言。迁移把既有 Building 标为 BUILDING 并生成确定性 code。

备选的新建 `spatial_nodes` 会要求一次性迁移所有 unit 外键并增加双写期；当前仓库没有真实数据授权，不值得引入两棵树。

### D2 — 单表多版本保留合同引用

在 `units` 增加 `logical_id`、`version_no`、`valid_from`、`valid_to`、`supersedes_id`、`usage_type`、`billing_unit`、`available_from` 和整数 `lock_version`。旧合同继续引用创建时的 unit row；运营查询只取 `valid_to IS NULL` 的 current rows。结构变更新建行，原行变历史，不重写旧合同外键。

备选的独立 unit/version 双表更纯粹，但会同时改造合同、招商、工单和所有现有 API，迁移风险高于本纵切收益。

### D3 — 归一化 lineage 记录拆分合并

新增 `unit_lineages(operation_id, operation_type, source_unit_id, target_unit_id)`。一次拆并共享 operation_id，可双向查询且支持多对多。命令锁定全部 source rows，验证 current/version/tenant/park/占用/面积后，在一个事务中关闭来源、创建目标、记录 lineage 和审计。

只存 JSON source IDs 无法建立引用完整性和高效双向查询，因此不采用。

### D4 — DB 约束与服务规则共同处理并发

current unit 的 `(building_id, normalized code)` 使用部分唯一索引；`lock_version` 与 `SELECT ... FOR UPDATE` 保护结构变更、拆分和合并。SQLite 测试验证规则，PostgreSQL 16 测试验证行锁/唯一冲突，统一映射 409。

### D5 — used_area 仍是合同投影

所有客户端 schema 删除/禁止 `used_area` 写入。租控查询从 current unit 的投影读取并在测试中与有效合同聚合交叉核对；拆并要求 effective occupied area 为 0。这样保持 Lease 为占用事实源，避免资产和合同双主写。

### D6 — 租控采用服务端查询模型

新增 `/rent-control/summary`、`/rent-control/units`、`/rent-control/units/{id}`；repository 使用同一 filter builder 生成列表与聚合，防止统计口径漂移。空间子树用递归 CTE（PostgreSQL）并提供可移植的应用层 fallback 供 SQLite 测试。

### D7 — PC 使用渐进式单页工作区

现有 `ParksView` 改成 park selector + spatial tree + summary + matrix/list + detail drawer。矩阵按空间分组展示状态卡，不伪装 GIS；小屏切为列表和抽屉。所有 mutation 由权限指令控制显示，但服务端继续独立校验。

### D8 — 兼容边界明确

保留现有 `/parks`、`/units` 基本读取和非结构字段更新；新增 `/spaces`、`/units/{id}/versions`、`/units/split`、`/units/merge` 和 `/rent-control/*`。原 `UnitUpdate` 对 park/building/code/area 等结构字段不再原地更新，客户端迁到 version 命令。

## Risks / Trade-offs

- [表名 Building 与领域名 SpatialNode 不完全一致] → repository/interface 统一使用 spatial 术语，并在后续真实迁移窗口再决定物理重命名。
- [部分唯一索引的 SQLite/PostgreSQL 行为差异] → 服务预校验 + 两库测试，最终并发门禁以 PostgreSQL 16 为准。
- [历史 unit row 仍可能被旧列表误读] → 所有 operational repository 默认 current-only；历史只能从显式 history 查询进入。
- [拆并与合同激活竞争] → 对 unit rows 排序加锁，事务内重新汇总有效占用，冲突返回 409。
- [矩阵大量单元造成前端卡顿] → 服务端分页/分组，默认单园区与空间过滤，限制 page_size 并提供列表降级。

## Migration Plan

1. Alembic 增加空间/版本字段、lineage 表和索引；回填旧 Building/Unit 的确定性 code/logical_id/version/current validity。
2. 部署兼容读路径，新写入同时满足新字段；运行 base→head、-1→head 和历史数据回填断言。
3. 上线 spaces/version/split/merge/rent-control API 与 PC 工作区；保留旧基础 endpoints 的兼容窗口。
4. 用合成 fixture 演练 old park/factory/floor 到 V2，验证幂等、层级、面积、状态和 rollback。
5. 只有人工提供授权的只读 schema/data 后才执行真实预发映射、差异单和切换评审。

回滚：在没有新版本/lineage 业务写入前可 Alembic downgrade；一旦产生新业务数据，只允许应用回退并保留 schema，使用前向修复，不删除历史。

## Open Questions

- 真实旧库是否存在跨厂房楼层、重复 floor code 或已用面积大于总面积的数据，只能在授权样本到位后回答。
- GIS 地图、CAD/BIM 和多园区集团视图的供应商/数据格式尚未确定，保持为后续 change。
