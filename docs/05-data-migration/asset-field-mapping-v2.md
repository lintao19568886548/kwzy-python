# 资产与租控 V2 字段映射

## 1. 适用边界

本文定义旧 `park / factory / factory_floor / rental manage` 到 V2 `parks / buildings / units / unit_lineages` 的迁移口径。当前证据来自仓库内旧系统分析，不代表已读取真实旧库。真实表结构快照、脱敏样例和状态字典未提供前，状态保持：

`ASSET_REAL_DATA_READINESS=BLOCKED_PENDING_SCHEMA_AND_SAMPLE_EXPORT`

基础合成演练入口为 `tools/etl/run_asset_etl_drill.py`；模板/几何/组合视图演练入口为 `tools/etl/run_asset_portfolio_etl_drill.py`。两者仅允许 loopback PostgreSQL 且拒绝 production-like 库名。

## 2. 表级映射

| 旧来源 | V2 目标 | 策略 | 身份保持 |
| --- | --- | --- | --- |
| `park` | `parks` | 一园区一记录；租户归属必须先解析 | 建立 `(source_tenant, source_park_id) → parks.id` 映射 |
| `factory` | `buildings(node_type=BUILDING)` | 厂房统一为类型化空间节点 | 建立 source factory id → node id 映射 |
| `factory_floor` | `buildings(node_type=FLOOR)` + `units` | 楼层作为空间定位；旧可租库存事实以一对一初始 Unit 承接 | 同时保留 floor node 与 unit 两套 source id 映射 |
| `factory_floor_image` | 后续附件/媒体资源 | 本纵切不迁二进制，只登记待迁清单与校验和 | 不允许把 URL/路径当已迁移文件 |
| `factory_elevator` | 后续设施资产/空间 attributes | 本纵切不建电梯资产台账；可验证字段暂存 `buildings.attributes_json` | 原始 id 写入受控迁移元数据 |
| `rental/manage` 派生视图 | 不建重复主表 | 改由 `/rent-control/*` 根据当前 Unit、租约占用与空间树查询 | 禁止把旧视图行再次写成主数据 |
| 旧厂房/宿舍/车位/商铺等类型字段 | `asset_templates` + `asset_template_versions` | 先映射七类内置模板；类型化扩展字段进入受限 schema | Unit 保存精确 `asset_template_version_id`，禁止只保留可变模板 code |
| 旧平面坐标/示意图元数据 | `buildings.geometry_json/geometry_type/coordinate_reference/geometry_version` | 仅接收可证明 Point/Polygon 和明确 CRS；图片/CAD 文件不当作坐标 | 保留 source space mapping；无法证明的坐标进入 quarantine/unmapped |

## 3. 字段口径

### 3.1 园区与空间

| 旧语义/候选字段 | V2 字段 | 规则 |
| --- | --- | --- |
| 旧企业/组织库归属 | `tenant_id` | 必须由迁移批次显式绑定，禁止使用前端传值或默认租户猜测 |
| `park.id` | `parks.id`（映射表） | 目标 id 可重排，所有下游 FK 必须经映射表解析 |
| 园区名称、地址、总面积、联系人、经理、启停 | `parks.name/address/area/contact/manager/status` | 文本去首尾空白；状态经批准字典转换；未知状态进入失败清单 |
| `factory.id` | `buildings` source mapping | 不直接假定新旧 id 相同 |
| `factory.park_id` | `buildings.park_id` | 经 park 映射；跨租户或孤儿直接失败 |
| 厂房名称 | `buildings.name` | 必填；空名称不得自动造业务事实 |
| 厂房编码（若有） | `buildings.code` | 同父级大小写不敏感唯一；缺失时用经批准的确定性 `B-{source_id}`，并报告补值数 |
| 厂房类型 | `buildings.building_type` | 映射到 `FACTORY/DORMITORY/MIXED/OTHER`；未知值不静默吞掉 |
| `factory_floor.factory_id` | FLOOR `parent_id` | 经 factory 映射，同园区校验 |
| 楼层号/名称 | FLOOR `code/name` | 同父级唯一；缺失编码用确定性 `F-{source_id}` 并报告 |
| 承重、层高、消防、电梯、变压器等 | FLOOR `attributes_json` | 仅放非核心、已知类型的结构化字段；原始自由 JSON 需字段白名单 |

### 3.2 可租单元与占用

| 旧语义/候选字段 | V2 字段 | 规则 |
| --- | --- | --- |
| `factory_floor.id` | `units` source mapping | 初迁生成稳定 `logical_id = UUIDv5(namespace, tenant + source table + source id)` |
| FLOOR node id | `units.building_id` | V2 字段名为兼容物理表，语义是任意有效 BUILDING/FLOOR 空间节点 |
| 楼层/房源编码 | `units.code` | 当前版本在空间内大小写不敏感唯一 |
| 名称 | `units.name` | 必填；缺失需失败或由已批准编码规则补值 |
| 总/可租面积 | `units.rentable_area` | Decimal(12,2)，必须 `>= 0` |
| `used_area` | `units.used_area` | 只作为对账输入；目标最终值必须由 ACTIVE/EXPIRING Lease 占用行重算，不接受旧值直接成为权威 |
| 租金 | `units.base_rent_price` | Decimal(12,2)，必须 `>= 0`；币种/周期歧义需先解决 |
| 房源用途 | `units.usage_type` | 映射到批准字典；缺省 `FACTORY` 仅适用于已确认的 factory_floor 来源 |
| 计费单位 | `units.billing_unit` | 明确为 `SQM/UNIT` 等批准值，禁止由价格数值猜测 |
| 可租日期 | `units.available_from` | 只接收可验证日期；非法值进失败清单 |
| 旧房源状态 | `units.status` | 旧状态 → `DRAFT/VACANT/RESERVED/OCCUPIED/MAINTENANCE/RETIRED` 显式字典；`OCCUPIED` 还须与有效合同重算一致 |
| 首次迁入 | `version_no=1, valid_to=NULL, lock_version=1` | `valid_from` 优先旧创建时间，否则使用批次切点并记录 |
| 历史结构变更 | 新 Unit version + `supersedes_id` | 仅在旧库存在可证明版本链时重建；不可从更新时间猜版本 |
| 拆分/合并 | `unit_lineages` | 仅迁可证明的来源关系；缺证据时不伪造血缘 |

### 3.3 模板、动态属性与几何

| 旧语义/候选字段 | V2 字段 | 规则 |
| --- | --- | --- |
| 厂房/仓库/商铺/办公/宿舍或公寓/停车/公共空间 | `asset_templates.category` | 显式映射为七类；未知类别 quarantine，禁止默认猜为 FACTORY |
| 旧类型专属字段 | `asset_template_versions.field_schema_json` | 只允许 TEXT/NUMBER/BOOLEAN/ENUM、最多 32 字段；URL、表达式、嵌套执行结构拒绝 |
| 旧默认值 | `defaults_json` | 必须先通过同一 schema 校验；缺证据不生成默认值 |
| 单元扩展属性 | `units.attributes_json` | 只保留模板声明键和值；历史 Unit 行引用当时的 published version |
| 坐标/图形 | `geometry_json` | 只接收受限 GeoJSON Point 或闭合 simple Polygon；非法范围/过大坐标集失败 |
| 坐标参考 | `coordinate_reference` | 仅 LOCAL/WGS84/GCJ02/BD09；来源不明确则 geometry 不迁并计入 unmapped |
| CAD/BIM/图片 | 后续附件/专业适配器 | 当前没有格式合同和解析器，不得转换为伪 GeoJSON 或宣称 live provider |

## 4. 对账门禁

每个批次至少输出并校验：

1. source/target 园区、空间节点、全部 Unit、当前 Unit、血缘边数。
2. 全部历史计租面积、当前计租面积、当前已用面积。
3. 空间父节点、Unit 空间、血缘 source/target 零孤儿。
4. 同级空间编码、当前空间内 Unit 编码零重复。
5. Unit `used_area` 与有效租约占用总和逐单元一致，且 `0 <= used_area <= rentable_area`。
6. 同一 `logical_id` 版本号唯一、有效期不重叠、最多一个当前版本。
7. 重跑插入数为零；回滚后隔离目标不存在且不影响正式 V2 schema。
8. 每个 Unit 的模板版本存在、已发布且 tenant 一致；模板 checksum 与字段/默认值一致。
9. 有 geometry 的空间 CRS 合法；无可信坐标的单元保留并计入 unmapped，不允许随机构造点位。

## 5. 人工输入清单

真实迁移前必须由负责人提供并批准：

- 旧库 DDL/索引/FK/字符集及时区快照；
- `park/factory/factory_floor/factory_floor_image/factory_elevator` 脱敏样例与行数/面积基线；
- `rental manage` 实际查询或 Controller/Service 版本，确认它是视图还是写模型；
- 所有状态、房源类型、计费单位字典；
- 七类模板映射、动态字段类型/单位/枚举和默认值的业务签字；
- 坐标来源、坐标系、精度和合法使用范围；CAD/BIM/图片文件格式、校验和与处理授权；
- `used_area` 与合同占用差异清单及裁决规则；
- 图片/附件存储清单、校验和与合法授权；
- 生产切换窗口、备份恢复演练与不可逆操作审批。

缺少任一项时，只能声明“合成演练通过”，不能声明真实数据可迁或生产切换就绪。
