# 资产业态模板与组合租控纵切验收证据

> 验收日期：2026-08-14（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`；精确实现提交 `44ae618aa4b0a83bbb89eff2b040475bbfcb0479` 已正常推送并完成 clean-SHA 复验。
> 判定：能力矩阵第 3 项“资产模板、租控矩阵、拆分合并和历史”已在本地真实栈闭环；全项目仍为 `CONDITIONAL/BLOCKED`。

## 已验收产品范围

- FACTORY、WAREHOUSE、SHOP、OFFICE、DORMITORY、PARKING、PUBLIC_SPACE 七类租户内置模板，以及租户自定义模板；
- 受限 TEXT/NUMBER/BOOLEAN/ENUM 字段语法、草稿更新、不可变发布版本、新草稿、停用、乐观锁和独立读写权限；
- 单元创建、结构版本、拆分、合并时的精确已发布模板版本绑定和历史保留；
- 空间 Point/Polygon GeoJSON、CRS、坐标/大小边界、自交/退化拒绝和几何乐观锁；
- 模板与版本、单元与模板版本均由复合租户外键兜底，显式模板不能跨租户或跨业态绑定；
- 同一真实数据源下的矩阵、示意地图、列表、空置、到期与分类/空间分析；
- 桌面、平板、手机的加载、空态、403、409、断网、恢复重试、键盘焦点和无横向溢出；
- 明示 `NOT_CONNECTED_LOCAL_SCHEMATIC`，未把 SVG 示意图宣称为外部 GIS、CAD/BIM 或数字孪生。

## clean-SHA 完整闸门

权威机器报告为 `acceptance-clean-44ae618.json`：精确 HEAD `44ae618aa4b0a83bbb89eff2b040475bbfcb0479`，30/30 步 exit 0；SHA-256 `40DF282B687A044AEF7AC93763818F9BDF1E646782CCB42BC36E72E28D850541`。

| 类别 | clean-SHA 结果 |
| --- | --- |
| Alembic / PostgreSQL 16 | fresh base→q3→唯一 `r4a02c7d9e86`；`current == heads`；`downgrade r4→q3 → upgrade r4` 后再次相等 |
| 后端 | `286 passed, 1 warning`，pytest 自报 118.31 秒；全仓 Ruff 错误级规则 PASS |
| 真实 HTTP / ETL | 资产独立 HTTP 与 synthetic dry/interruption/apply/reapply/reconcile/rollback 均 PASS；证据为 `asset-portfolio-http-clean-44ae618.json`、`asset-portfolio-etl-clean-44ae618.json` |
| 性能 | 1,000 请求、并发 25、0 错误、p95 268.361 ms、135.946 RPS；报告 SHA-256 `1FE7FC1FE1901F3E0A27DD4E4626F4DB681C28F9E78C054A565F2F78BA3A3FA8` |
| 备份恢复 | `pg_dump -Fc` 1,133,418 bytes；删除/创建临时恢复库、`pg_restore`、84 表复核和恢复库清理均 PASS |
| 前端 / 浏览器 | ESLint、typecheck、Vitest 3 files / 6 tests、production build、Playwright 52/52 全通过 |
| 契约 / 安全 | OpenAPI 10 + YAML strict、OpenSpec 67/67、781 文件 secrets scan、diff check 与资源清理均 PASS |

## 提交前工作树完整闸门

权威机器报告为 `acceptance-worktree-20260814.json`：30/30 步 exit 0，18:29:18–18:39:38 +08:00，总耗时 619,403 ms；SHA-256 `6E2322C9C63F3FDAC4EE0A29B0EF1B3D17A3BF474C1EB121DADDE4DB3BD72C75`。

| 类别 | 结果 |
| --- | --- |
| Alembic / PostgreSQL 16 | fresh base→q3→唯一 `r4a02c7d9e86`；`current == heads`；`downgrade r4→q3 → upgrade r4` 后再次相等；历史 q3 未修改 |
| 后端 | 完整 `286 passed, 1 warning`，pytest 自报 121.59 秒；全仓 Ruff 错误级规则 PASS；资产 metadata/OpenAPI/分层、模板、复合租户外键与 PG 并发均在内 |
| 真实 HTTP | 资产组合独立旅程 22 阶段、1,705.09 ms；覆盖七类 bootstrap 幂等、模板 409、不安全语法、几何/单元/多视图对账、几何 409、历史、伪造权限头 403、跨租户 IDOR 404 |
| 性能 | 1,000 请求、并发 25、0 错误、p95 260.28 ms、137.877 RPS；门槛 p95≤500 ms、错误率≤1%、RPS≥20，PASS |
| 备份恢复 | `pg_dump -Fc` 1,133,495 bytes；删除/创建临时恢复库、`pg_restore`、84 表复核与恢复库清理均 PASS |
| 迁移演练 | 8 模板/9 版本/2 空间/2 单元；中断后 0 残留、重跑 0 新增、208.00㎡/20.00㎡一致、rollback 后 schema 不存在且授权表不变 |
| 前端 | ESLint、Vue typecheck、Vitest 3 files / 6 tests、production build 均 PASS |
| 浏览器 | 完整真实栈 Playwright `52 passed`；资产专项 5 条覆盖拆并、只读/403/故障、模板/几何/多视图、手机 offline/retry、平板键盘 |
| OpenAPI / OpenSpec | OpenAPI runtime/YAML 10 passed + YAML strict；OpenSpec strict 67/67 |
| 安全/清理 | 780 文件 secrets scan、diff check、测试 API/Web/PG 容器/网络/卷清理均 PASS；未连接生产 |

## 自动扫描人工分类

| 命中 | 分类 |
| --- | --- |
| `pass` | `JourneyFailure` 空异常类体，不是业务固定成功 |
| `demo` | 仅 synthetic ETL 的 `tenant-demo` 隔离 fixture；报告同时标记 `synthetic_only=true`，不计真实迁移 |
| `placeholder` | 仅表单输入提示属性；不是静态业务数据或空壳页面 |
| mock/fake/static chart | 资产生产路径无命中；地图由数据库 geometry 投影，分析由当前 Unit/Lease 查询计算 |
| 本地 JSON | 资产页面未导入或读取本地业务 JSON |
| 路由 | FastAPI `park_router` 和 Vue `/rent-control` 均挂载；OpenAPI 精确方法集通过 |
| 分层 | Router 只做依赖注入/调用 Service，无直接查询；Application 未导入 ORM model 或执行裸 SQL，仓储依赖符合阶段架构标准 |
| 权限/隔离 | `asset.template.read/write` 来自数据库角色；伪造 `X-Permissions` 不生效；tenant/park/IDOR 与参数上限均有回归 |
| 敏感信息 | 定向扫描只命中旅程参数名和运行期 token 变量，无硬编码凭据；全仓 780 文件扫描 PASS |

同条件首轮报告 `acceptance-worktree-performance-transient-failure-20260814.json` 在性能门禁以 p95 2,928.855 ms 失败，SHA-256 `C631F792743F6FFC8EE5E453789D1D713BC75FB584E5F2AB3E47BD02107B3F6B`；0 HTTP 错误且所有端点同步变慢。该失败证据被保留，没有调低 500 ms 门槛；随后从空库完整复跑才取得上述 30/30 PASS。

## 视觉人工复核

- `pc-desktop-rent-control-map.png`：数据库 Polygon 真实投影、CRS `LOCAL`、空间和库存信息可读，并明确“外部底图未接入”；
- `pc-desktop-rent-control-analysis.png`：OFFICE 88㎡、挂牌潜力 ¥880.00，与原始单元 88×10 对账，且标明“非会计收入”；
- `pc-mobile-rent-control-offline.png`：390×844 下当前“资产租控”导航完整可见，离线提示和禁用重试状态可读，正文无 body 横向溢出。

三张图均由 PostgreSQL + FastAPI + production Vite build 的 Playwright 旅程生成，不是手工拼图或假数据页面。

## 数据与外部边界

`asset-portfolio-etl-worktree.json` 只证明合成 dry/interruption/apply/reapply/reconcile/rollback：

```text
ASSET_PORTFOLIO_MIGRATION=CONDITIONAL_SYNTHETIC_READY_FOR_STAGING_DATA
REAL_LEGACY_MIGRATION=BLOCKED_PENDING_AUTHORIZED_SCHEMA_AND_DESENSITIZED_SAMPLE
EXTERNAL_MAP_PROVIDER=NOT_CONNECTED_LOCAL_SCHEMATIC
```

真实旧表结构、脱敏记录、坐标口径、状态字典和面积/租约对账基线均未获授权；商业 GIS、地理编码、CAD/BIM 导入也没有协议或凭据。它们不影响本地产品能力第 3 项关闭，但继续阻塞真实迁移、外部集成与全旧系统替代。

## 组合能力结论

20 项矩阵中的第 3 项升级为 `IMPLEMENTED_AND_VERIFIED`，矩阵现为 5 implemented / 1 blocked / 14 missing。此结论不外推为员工移动端、租户小程序、完整驾驶舱、外部平台、真实旧数据迁移或生产就绪。
