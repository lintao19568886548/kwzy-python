## 1. 变更边界与人工确认（Apply 前）

- [x] 1.1 确认本 change 仅关闭 Step1 验收缺口，不包含 Party/Lease/Bill/Payment
- [x] 1.2 人工确认 BREAKING：`*` 动作权限不再授予全园区
- [x] 1.3 人工确认 local 缺初始化密码时的行为（跳过创建 admin 并 ERROR，或 fail-fast）
- [x] 1.4 人工确认 DATABASE_URL 仅指向新系统 SQLite，绝不连接旧 Java 库
- [x] 1.5 人工批准后再进入 apply；本 propose 阶段不执行迁移与代码修改

## 2. 数据库版本闭环（写任务，Apply 时执行）

- [x] 2.1 记录升级前 `DATABASE_URL`、`alembic heads`、`alembic current` 与绝对路径 `D:\重构python\kwzy-python\apps\api\kwzy_step1.db`
- [x] 2.2 校验 URL 仅为新系统 SQLite（路径落在 `kwzy-python\apps\api`）；命中旧库模式则中止
- [x] 2.3 迁移前复制数据库为带时间戳备份文件（同目录 `kwzy_step1.backup.YYYYMMDD-HHMMSS.db`）
- [x] 2.4 记录升级前 tenants/users/parks/units 行数与关键抽样（如 default 租户、admin 用户）
- [x] 2.5 在 `apps/api` 下执行 `alembic upgrade head`
- [x] 2.6 验证 `alembic heads` 唯一且 `alembic current` 等于 head（目标 `8c2f4aa10b7d`）
- [x] 2.7 验证升级后业务表行数未丢失；抽样数据仍在
- [x] 2.8 验证 `permissions`、`role_permissions`、`user_roles`、`role_park_scopes`、`audit_logs` 表存在
- [x] 2.9 运行全部 `pytest` 并记录结果
- [x] 2.10 在 tasks/PR 说明中写明失败时用备份文件覆盖还原的步骤（优先文件级回滚）

## 3. 移除固定管理员密码

- [x] 3.1 从 bootstrap 源码移除固定管理员明文密码字面量
- [x] 3.2 增加配置项读取 `LOCAL_ADMIN_PASSWORD`（名称以最终 config 为准）
- [x] 3.3 local：env 有值且 admin 不存在时创建哈希；env 缺失时不静默使用固定密码
- [x] 3.4 admin 已存在时幂等跳过，不重置密码
- [x] 3.5 test：fixture/env 提供测试凭据；不在库代码写死生产口令
- [x] 3.6 production：断言/测试禁止自动 admin 种子
- [x] 3.7 更新 `.env.example` 为占位符，无真实默认密码
- [x] 3.8 确认日志、审计、API 响应不含密码或可逆秘密

## 4. 权限与园区范围分离

- [x] 4.1 设计落地 `park_scope_mode`（NONE/LIST/ALL）或等价字段于 `TenantContext`
- [x] 4.2 `has_all_park_access` 仅由明确全园授权推导，不再由 `permissions` 含 `*` 推导
- [x] 4.3 持久化 `all_parks`（推荐 Role/User 布尔）或经确认的等价方案 + Alembic migration（若需）
- [x] 4.4 AuthorizationRepository：tenant 过滤下合并 user/role 园区与 all_parks
- [x] 4.5 AuthService JWT claims：permissions 与 park scope 独立写入
- [x] 4.6 deps 鉴权使用新 scope 语义；Repository 行为对齐
- [x] 4.7 ADMIN 种子：动作 `*` + 显式 all_parks；兼容已有库回填
- [x] 4.8 测试：有全部动作权限但无园区范围
- [x] 4.9 测试：有园区范围但无动作权限
- [x] 4.10 测试：全部动作权限 + 指定园区 LIST
- [x] 4.11 测试：明确全园区权限 ALL
- [x] 4.12 测试：跨租户角色/权限关联被忽略
- [x] 4.13 测试：跨园区访问被拒绝

## 5. DDD 分层修复（Identity / Park / Unit）

- [x] 5.1 列出 Identity/Park/Unit 当前 Application 直接构造 ORM 的违规点清单（实现笔记）
- [x] 5.2 Domain：Park/Unit 实体（无 SQLAlchemy）
- [x] 5.3 Infrastructure：Mapper ORM ↔ Domain
- [x] 5.4 Repository 公共边界改为接收/返回 Domain 或 DTO
- [x] 5.5 重构 ParkService 去掉直接 ORM 构造
- [x] 5.6 重构 UnitService（含默认 Building）去掉直接 ORM 构造
- [x] 5.7 Auth 路径保持 API 兼容；User ORM 收敛在 infrastructure 边界
- [x] 5.8 增加架构依赖测试/静态检查：禁止 application 导入 `database.models`（白名单极小且文档化）
- [x] 5.9 全量回归：现有 API 响应字段与表结构兼容、pytest 绿

## 6. 日志字段与 OpenAPI

- [x] 6.1 业务日志 extra 统一使用 `module` 字段名
- [x] 6.2 过渡期可选双写 `business_module`；文档说明兼容期
- [x] 6.3 增加 OpenAPI 3.1 严格校验依赖与命令（如 openapi-spec-validator）
- [x] 6.4 校验 `docs/04-api/openapi-v1-core.yaml` 通过
- [x] 6.5 核对运行时 Identity/Park/Unit 路由与 OpenAPI 一致性并修复缺口（不扩展 Party）
- [x] 6.6 更新相关工程规范表述（若 `*` 全园描述仍残留）

## 7. Git 保护（仅操作建议任务，默认不自动执行）

- [x] 7.1 检查 `.env`、`*.db`、备份、日志、缓存、密钥、IDE 文件是否存在于工作区
- [x] 7.2 完善根目录 `.gitignore` 建议内容（db/backup/env/venv/cache）
- [x] 7.3 文档化：`git init`、首个 Step1 基线 commit 消息建议
- [x] 7.4 明确不配置 remote、不推送 GitHub
- [x] 7.5 明确 SQLite 与备份文件不得提交
- [x] 7.6 （可选，人工执行）初始化 Git 并创建基线提交——**不在无确认时由代理自动执行**

## 8. 验证与收尾

- [x] 8.1 运行全部 pytest 并记录数量与结果
- [x] 8.2 `openspec validate close-step1-acceptance-gaps`（及 strict）通过
- [x] 8.3 更新 Step1 验收/完成文档中的已知缺口状态（current=head、密码、权限分离）
- [x] 8.4 列出残留风险：失败审计仍不落库、JWT 快照时效等
- [x] 8.5 输出 apply 完成标识（仅 apply 阶段）：`STEP1-ACCEPTANCE-GAPS-CLOSED`
