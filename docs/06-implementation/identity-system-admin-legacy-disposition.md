# Identity / System / Admin 旧接口处置基线

> 更新时间：2026-08-13
> 证据源：仓库外只读审计包 `identity-system-admin-design-review-v2.2`
> 旧 Java canonical 接口：74；旧字段映射行：52
> 重要：本表按控制器分组汇总，74 行逐接口源数据仍由审计包 `identity-java-endpoints.csv` 保留；任何未列为 V2 目标的接口均不得静默宣称完成。

## 处置规则

| 处置 | 含义 |
|---|---|
| EXACT / REDESIGNED | V2 已有可复验目标能力；路径或 envelope 可重设计 |
| PARTIAL | 只覆盖部分旧语义，仍须单独计划 |
| DEFERRED | 业务仍合理，但属于后续纵切或需要外部事实 |
| REMOVED | 旧实现不应照搬，V2 以更安全/更清晰能力替代 |
| BLOCKED | 需要生产/旧库/供应商事实或人工授权 |

## 74 接口分组处置

| 旧控制器 | 数量 | V2 目标 | 处置 | 说明 |
|---|---:|---|---|---|
| AuthController | 11 | `/api/v1/auth/login|refresh|logout|password|codes|page-access/*` | REDESIGNED / PARTIAL | 密码登录、refresh 轮换、cookie、会话吊销和 page-access 已实现；旧 GET password 删除；短信“登录”仍未实现 |
| MenuController | 2 | `/api/v1/auth/menus`、`/api/v1/system/menus` | REDESIGNED | 角色菜单与动作权限分离；旧 parent-role 查询由当前用户动态菜单替代 |
| MenuTemplateSyncController | 4 | 后续平台模板发布纵切 | DEFERRED | 当前租户菜单 CRUD 已有；跨租户模板 dry-run/execute/jobs 未实现 |
| OnboardingController | 1 | tenant-ops onboarding | DEFERRED | 属于租户开通/引导，不在身份管理纵切内 |
| OrganizationController | 8 | tenant-ops provisioning/invitation | DEFERRED | 邀请、开通、重试是独立租户运营聚合，不伪装成用户 CRUD |
| SmsController | 2 | `/api/v1/integrations/sms/send`、page-access send | PARTIAL / BLOCKED | fake/outbox 已实现；bulk、真实供应商、签名/回执需凭据和联调 |
| SystemDeptController | 4 | `/api/v1/system/org-units` | REDESIGNED | V2 采用树形组织单元 create/list/patch；删除按停用策略后续补齐 |
| SystemFeedbackController | 1 | tenant-ops/service-feedback | DEFERRED | 不是身份安全底座 |
| SystemKeyController | 1 | secret/KMS 管理 | REMOVED / BLOCKED | 禁止通过通用 API 返回系统密钥；生产 KMS 需安全决策 |
| SystemMenuController | 6 | `/api/v1/system/menus[/{id}]` | REDESIGNED | list/create/update/deactivate 已实现；name/path 冲突用写入 409 代替探测接口 |
| SystemParkController | 12 | `/api/v1/parks[/{id}]`、workbench/report | REDESIGNED / PARTIAL | 园区 CRUD 已实现；visitor/rental/dashboard 语义归属相应业务纵切 |
| SystemRegionController | 4 | 地址字典/region capability | DEFERRED | 需要产品确认行政区版本与外部数据源 |
| SystemRoleController | 9 | `/api/v1/system/roles[/{id}]` | REDESIGNED | 角色、权限、菜单、园区范围使用整体替换式命令；add/remove/code 路径不保留 |
| SystemUserController | 6 | `/api/v1/system/users[/{id}]`、revoke-sessions | REDESIGNED | list/create/update/disable/session revoke 已实现；username 冲突通过 409；cancel 需明确业务语义 |
| UserFeedbackController | 1 | tenant-ops/service-feedback | DEFERRED | 后续服务反馈纵切 |
| UserInfoController | 1 | `/api/v1/auth/me` | REDESIGNED | 返回租户、动作权限和园区范围，不返回敏感字段 |
| VersionController | 1 | `/health` + 发布元数据 | PARTIAL | 运行版本已在 health；面向客户端的升级策略尚未实现 |
| **合计** | **74** |  |  | 与审计包集合相等 |

## 当前闭环与阻断

- 已闭环：密码登录、租户消歧、refresh 轮换/重放处理、access 即时吊销、用户/角色/菜单/园区授权、组织/字典/参数、事务审计、登录限流、page-access fake/outbox、PC 授权管理。
- 未闭环：短信登录、菜单模板发布、租户邀请/开通、region、feedback、客户端升级策略、bulk SMS。
- 外部阻断：真实短信沙箱、旧租户 schema/data、旧密码哈希样本、生产 KMS 和生产发布授权。
- 因此本文件支持“Identity 核心底座纵切完成度提升”，不支持“74 个旧接口全部等价替换”结论。
