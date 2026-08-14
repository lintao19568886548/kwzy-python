# 资产租控旧能力处置

## 1. 结论

V2 不逐路径复刻旧 `factory`、`dormitory` 与 `rental/manage` CRUD，而是拆为四个明确能力面：

- `/parks`：园区主档；
- `/spaces`：AREA / BUILDING / FLOOR 类型化空间树；
- `/units` 与 `/rent-control`：可租单元写模型、版本/拆并和运营查询模型。
- `/asset-templates`：七类内置及租户自定义业态模板、不可变发布版本和精确 Unit 历史绑定。

旧移动园区管理、宿舍入住/床位等专属流程、图片/电梯资产和公开访客园区查询不在本纵切完成范围，必须保持 `NOT_REPLACED` 或进入后续独立变更。宿舍/公寓的通用空间与可租单元主数据已由 DORMITORY 模板替代，不能据此宣称专属运营流程已替代。

## 2. 路径处置矩阵

| 旧路径/能力 | V2 路径 | 处置 | 说明 |
| --- | --- | --- | --- |
| `GET /api/system/park/*`、`GET /api/park/list` | `GET /api/v1/parks` | REDESIGNED | 统一租户与园区范围过滤；PC 使用授权园区选择器 |
| `POST/PUT/DELETE /api/system/park/*` | `POST/PATCH/DELETE /api/v1/parks/{id}` | REDESIGNED | 软删除与依赖保护沿用 V2 领域规则 |
| `GET /api/factory/list` | `GET /api/v1/spaces/tree` + `/rent-control/units` | SPLIT | 空间目录和可租库存不再混成一个列表 |
| `GET /api/factory/available-list` | `GET /api/v1/rent-control/units?status=VACANT` | REDESIGNED | 可叠加 park、space subtree、usage、keyword 服务端筛选 |
| `GET /api/factory/{id}` | `GET /api/v1/spaces/{id}` 或 `/rent-control/units/{unit_id}` | SPLIT | 根据请求主语分别读取空间或运营单元详情 |
| `POST/PUT/DELETE /api/factory` | `/api/v1/spaces` 与 `/api/v1/units` | SPLIT | 结构位置与出租产品使用不同命令 |
| `GET /api/factory/list-by-park` | `GET /api/v1/spaces/tree?park_id=...` | REPLACED | 返回真实层级树而非平铺下拉数据 |
| `GET /api/rental/manage/list` | `/api/v1/rent-control/summary`、`/units`、`/matrix`、`/map`、`/vacancies`、`/expiries`、`/analysis` | REPLACED | 汇总、多视图和分析使用同一 tenant/park/subtree scoped filter builder |
| `POST/PUT/DELETE /api/rental/manage/*` | `/api/v1/units`、`/{id}/versions`、`/split`、`/merge` | REDESIGNED | 结构变更要求 expected lock version，拆并原子并保留血缘 |
| `/rental/manage` PC 页面 | `/rent-control` | REPLACED_PC | 授权园区、空间树、矩阵/列表、详情、版本/拆并已实现 |
| `/rental/manage/mobile` | — | NOT_REPLACED | 员工移动端不在此 change 范围 |
| `/api/dormitory/*` 通用资产字段 | DORMITORY template + `/spaces` + `/units` | REDESIGNED_CORE_ASSET | 通用空间、可租面积和类型化属性已统一；床位/入住/退宿等专属流程仍 NOT_REPLACED |
| `/api/park/visitor-list` | — | NOT_REPLACED | 公开访客登记属于访客域，不能复用内部租控授权接口 |
| `factory_floor_image` / `factory_elevator` CRUD | — | PARTIAL_DATA_ONLY | 核心 attributes 可承接经批准字段；媒体与设施资产需独立纵切 |

## 3. 已实现不变量

- 仓储层强制 tenant + park scope；无范围返回空或 404/403，不放大权限。
- 空间父子类型固定为 AREA → BUILDING → FLOOR，支持同园区移动并阻断循环。
- 根节点与子节点编码均由 PostgreSQL/SQLite 条件唯一索引兜底。
- 正常库存查询默认只返回 `valid_to IS NULL` 的当前 Unit。
- 面积/位置/编码等结构变化生成新版本；租约历史 FK 不被重写。
- `used_area` 由有效 Lease 投影，客户端写入被忽略；手工设置 OCCUPIED 被拒绝。
- split/merge 使用 `SELECT ... FOR UPDATE`、精确面积对账、单事务血缘与审计。
- Lease 激活与结构拆并锁同一当前 Unit，竞争结果串行且不产生“合同已激活但单元已退役”的双成功状态。
- 七类内置模板按租户幂等物化；发布版本不可变，Unit 历史只引用当时的精确版本。
- 模板版本和 Unit 模板引用由 `(tenant_id, id)` 复合外键兜底；显式模板必须与单元业态一致。
- 受限字段语法拒绝 URL、表达式和未知嵌套结构；动态属性由服务端校验，前端不能绕过。
- Point/Polygon 与 CRS 受边界、自交、退化和几何版本乐观锁保护；缺坐标的库存计入 unmapped，不编造坐标。
- 空置与挂牌潜力只纳入 VACANT 或部分 OCCUPIED 的正可用面积，排除 DRAFT、RESERVED、MAINTENANCE、RETIRED；并明确挂牌潜力不是会计收入。

## 4. 本地证据

- Alembic：base → `q3f91b6c8d75` → `r4a02c7d9e86`，唯一 head/current，并通过 r4 down 到 q3 后再 up；已执行 q3 未修改。
- SQLite/API/契约：空间、版本、拆并、租控、隔离与 OpenAPI 聚焦测试通过。
- PostgreSQL：根空间唯一竞争、并发 split、Lease activation vs split 三项通过。
- PC：typecheck、lint、Vitest、production build 通过；完整 Playwright 52 条，资产专项 5 条覆盖模板/几何/六视图、只读/拒绝/冲突、offline/retry 与 tablet keyboard。
- 合成资产 ETL：dry-run、first apply、idempotent reapply、数量/面积/孤儿/重复对账、rollback 全部通过。
- 合成资产组合 ETL：8 templates/9 versions/2 spaces/2 units，中断恢复、精确模板绑定、几何 CRS、面积对账和 rollback 全部通过。

以上只证明本地合成与代码路径，不替代真实旧库验证、生产备份恢复或部署审批。
