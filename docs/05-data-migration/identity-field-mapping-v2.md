# Identity 字段迁移映射 V2

> 更新时间：2026-08-13
> 来源：旧 `magic.sql` 静态 schema、Java repository 证据包和当前 SQLAlchemy 模型
> 结论：目标映射已设计；真实租户 schema/data 与密码哈希算法未授权取得，生产迁移仍为 BLOCKED。

## 通用规则

- 所有目标业务表都写入显式 `tenant_id`；旧多库/企业中心映射只在 ETL adapter 中转换。
- 旧整数主键可在单租户 dry-run 保留；多租户合库时先建立 `source_tenant + old_id -> new_id` 映射表，禁止直接碰撞。
- `create_time/update_time` 转为 UTC 语义的 `created_at/updated_at`；源时区未知时停止真实迁移。
- 旧 `is_deleted` 不直接丢弃：有效数据导入主表，删除数据进入迁移审计/归档清单。
- 状态枚举统一为字符串；未知值进入 quarantine，不使用默认 ACTIVE 掩盖。
- 口令、手机号、refresh、验证码属于敏感数据；日志、对账文件和错误不得包含明文。

## 核心字段映射

| 旧表.字段 | V2 表.字段 | 转换 |
|---|---|---|
| `user.id` | `users.id` 或 id 映射表 | 单租户可保留；合库重建 |
| `user.username` | `users.username` | trim；租户内唯一；冲突 quarantine |
| `user.real_name` | `users.real_name` | trim；空值回退 username，并记修复计数 |
| `user.phone` | `users.phone` | 规范化国家/地区号；格式异常 quarantine |
| `user.password` | `users.password_hash` | **不**按明文重哈希；算法确认后双验证/登录时升级，或受控重置 |
| `user.home_path` | `users.home_path` | 只保留 V2 已注册路由，否则回退 dashboard |
| `role.role_id` | `roles.id` 或 id 映射表 | 同主键规则 |
| `role.name` | `roles.name` | trim |
| 旧角色业务标识 | `roles.code` | 从权限/旧 code 证据生成稳定大写码；无证据时人工映射 |
| `role.status` | `roles.status` | `1 -> ACTIVE`，`0 -> DISABLED`，其他 quarantine |
| `role.remark` | `roles.remark` | 原样清洗 |
| `menu.menu_id` | `menus.id` 或 id 映射表 | 同主键规则 |
| `menu.pid` | `menus.parent_id` | 第二遍按 id 映射回填；缺父节点 quarantine |
| `menu.name` | `menus.name` | trim |
| `menu.path` | `menus.path` | 规范化前导 `/`；重复路径人工处置 |
| `menu.component` | `menus.component` | 旧组件名映射到 V2 注册组件；未知值 DEFERRED |
| `menu.type` | `menus.menu_type` | 映射 `DIR/MENU/BUTTON`；未知值 quarantine |
| `menu.status` | `menus.status` | 有效 -> ACTIVE，否则 DISABLED |
| `menu.auth_code` | `menus.permission_code` | 映射到 V2 permission catalog；菜单可见性不等于 API 授权 |
| `role_menu.role_id/menu_id` | `role_menus.role_id/menu_id` | 两端 id 映射后插入；孤儿记录 quarantine |
| `role_park.role_id/park_id` | `role_park_scopes.role_id/park_id` | 两端 id 映射；同租户校验 |
| `user_role.user_id/role_id` | `user_roles.user_id/role_id` | 两端 id 映射；同租户校验 |
| 旧全园区隐式语义 | `users.all_parks` / `roles.all_parks` | 必须由业务证据显式推导；`*` 权限不得推导全园区 |
| 旧权限绑定 | `permissions` + `role_permissions` | 旧 code 映射到 V2 动作权限码；未知码 quarantine |
| 旧 refresh token | 不迁移 | V2 切换时全部会话重新登录 |
| 旧验证码/page proof | 不迁移 | 短时安全凭证一律丢弃 |

## 必须对账

1. 每租户用户、角色、菜单和关系表源/目标计数。
2. 用户名租户内唯一、角色码租户内唯一、菜单父子无环。
3. user_role、role_menu、role_park、role_permission 零孤儿且 tenant 一致。
4. 每个 ACTIVE 用户可解析出 NONE/LIST/ALL 园区范围；动作 `*` 与全园区独立统计。
5. 所有口令状态分类为 VERIFIED_LEGACY_HASH、RESET_REQUIRED 或 QUARANTINED，不允许 UNKNOWN 静默上线。
6. dry-run、apply、第二次 apply 幂等以及 rollback/reconcile 报告均为 PASS 后，才可申请真实 cutover。

## 人工门禁

- 脱敏只读真实 schema dump；
- 合法授权的密码哈希样本/算法说明；
- 源时区、租户拓扑和旧权限码字典；
- 生产备份、维护窗口、回滚负责人和 cutover 授权。
