## Why

身份与系统管理是所有业务纵切的安全底座。早期方案停留在 main@6090c97 的“仅设计、0/65”状态，但当前 main@d9c0b0b 已交付数据库认证、刷新令牌、用户/角色/菜单、园区范围、组织/字典/参数和 PC 管理页；继续沿用旧计划会同时掩盖已完成能力和剩余安全缺口。

本变更现进入实施阶段：以现有实现为基线，补齐即时吊销、限流、审计、菜单生命周期、授权数据校验、PC 授权体验和可复验证据。生产数据库、真实短信凭据、真实租户数据迁移与生产发布仍保持人工门禁。

## What Changes

- 校准 Identity/System/Admin 的实现事实、测试证据和 OpenSpec 任务，不再把已经合入 main 的能力记为未开始。
- 加固认证会话：短期访问令牌、哈希存储的轮换 refresh、登出/密码变更/停用后的会话吊销、token_version 与用户状态在线校验、重放检测、登录限流。
- 完成租户内用户、角色、权限、菜单和园区范围管理；动作权限与菜单可见性继续正交，星号动作权限绝不隐含全园区。
- 为身份管理写操作和敏感认证失败提供不含密码、令牌或验证码的审计/可观测证据。
- 补齐菜单更新/停用、关联对象租户校验、冲突错误映射，以及 PC 端用户/角色/权限/园区/菜单的可用配置体验。
- 采用多客户端会话传输：PC 浏览器优先 HttpOnly refresh cookie；员工移动端/租户小程序可使用响应体 refresh token，二者共享轮换和吊销语义。
- 为验证码/页面二次验证定义供应商无关接口、本地 fake 验收与生产 fail-closed 门禁；没有真实供应商凭据时保持 NOT_LIVE。
- 维护旧 Java 74 个 Identity/System/Admin 接口的处置矩阵和身份字段迁移映射；没有真实租户 schema/data 时迁移结论保持 BLOCKED。

## Capabilities

### New Capabilities

- `identity-authentication`: 密码登录、登录限流、供应商无关验证码与页面二次验证。
- `user-lifecycle-management`: 用户创建、更新、启停、密码修改/重置与会话吊销。
- `role-permission-management`: 角色、动作权限及其租户内绑定。
- `menu-page-access-control`: 菜单生命周期、角色菜单和动态菜单。
- `tenant-park-authorization`: 用户/角色园区范围以及 ALL/LIST/NONE 语义。
- `token-session-security`: access/refresh 生命周期、轮换、重放检测和即时失效。
- `identity-audit-observability`: 身份管理审计、失败认证可观测与敏感字段保护。
- `legacy-identity-compatibility`: 旧路径/契约逐接口处置和兼容窗口。
- `identity-data-migration`: 身份字段映射、试迁移、对账与生产门禁。

### Modified Capabilities

- `identity-authorization`: 从 claims 级授权扩展为用户状态/token_version 在线校验和管理面授权闭环。
- `park-scope-model`: 增加用户/角色授权写入、租户内引用校验和 ALL/LIST/NONE 配置语义。
- `foundation-compliance`: 身份管理写操作纳入事务内审计、统一错误 envelope 与跨租户拒绝。

## Impact

- 后端：`apps/api/app/modules/identity/**`、`app/shared/deps.py`、安全配置、数据库模型/Alembic、审计和集成适配。
- PC：`apps/web/src/views/SystemAdminView.vue`、认证 store、权限路由与 E2E。
- 契约：`docs/04-api/**` 和 OpenAPI；保持 `/api/v1` 为 V2 主契约，旧 `/api` 仅按矩阵显式适配。
- 数据：PostgreSQL 16 为权威；SQLite 仅单元测试。真实旧库只读抽取、生产 cutover 和回滚必须单独授权。
- 外部系统：短信/微信等生产适配器在凭据与联调前必须 fail-closed 并标记 NOT_LIVE。

## Authorization

用户在 2026-08-13 的当前任务中已明确要求在无人值守条件下持续实施、测试、提交并推送，因此本 change 的 apply 已获授权。该授权不包含生产数据库访问、真实第三方凭据配置、不可逆生产操作或生产发布。
