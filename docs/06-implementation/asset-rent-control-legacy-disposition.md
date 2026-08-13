# 资产租控旧能力处置

## 1. 结论

V2 不逐路径复刻旧 `factory` 与 `rental/manage` CRUD，而是拆为三个明确能力面：

- `/parks`：园区主档；
- `/spaces`：AREA / BUILDING / FLOOR 类型化空间树；
- `/units` 与 `/rent-control`：可租单元写模型、版本/拆并和运营查询模型。

旧移动园区管理、宿舍独立模型、图片/电梯资产和公开访客园区查询不在本纵切完成范围，必须保持 `NOT_REPLACED` 或进入后续独立变更。

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
| `GET /api/rental/manage/list` | `/api/v1/rent-control/summary`、`/units`、`/matrix` | REPLACED | 汇总、分页列表与空间矩阵使用同一 scoped filter builder |
| `POST/PUT/DELETE /api/rental/manage/*` | `/api/v1/units`、`/{id}/versions`、`/split`、`/merge` | REDESIGNED | 结构变更要求 expected lock version，拆并原子并保留血缘 |
| `/rental/manage` PC 页面 | `/rent-control` | REPLACED_PC | 授权园区、空间树、矩阵/列表、详情、版本/拆并已实现 |
| `/rental/manage/mobile` | — | NOT_REPLACED | 员工移动端不在此 change 范围 |
| `/api/dormitory/*` | — | NOT_REPLACED | 目标域允许 `building_type=DORMITORY`，但业务流程与迁移未实现 |
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

## 4. 本地证据

- Alembic：base → `i5d13e8f0b97`，并通过 down `-1` / up。
- SQLite/API/契约：空间、版本、拆并、租控、隔离与 OpenAPI 聚焦测试通过。
- PostgreSQL：根空间唯一竞争、并发 split、Lease activation vs split 三项通过。
- PC：typecheck、lint、Vitest、production build 通过；Playwright 主路径、只读/拒绝/故障态、tablet keyboard 三项通过。
- 合成资产 ETL：dry-run、first apply、idempotent reapply、数量/面积/孤儿/重复对账、rollback 全部通过。

以上只证明本地合成与代码路径，不替代真实旧库验证、生产备份恢复或部署审批。
