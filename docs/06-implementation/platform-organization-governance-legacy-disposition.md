# 平台组织治理旧系统证据与处置

> 取证日期：2026-08-14（Asia/Shanghai）
> 旧证据根：`D:\重构python\kwzg-Java-main`
> 新纵切：`complete-platform-organization-governance`
> 原则：本清单只裁决当前纵切；组织空间开通、邀请和真实旧数据迁移没有授权证据时保持阻塞，禁止冒充完成。

## 1. 原始入口证据

| 旧能力 | 后端证据 | PC 证据 | 数据证据 | 独立判断 |
| --- | --- | --- | --- | --- |
| SaaS 组织空间 | `organization/OrganizationController.java`：create、invitation、provisioning/status、failed-manual、requeue | `views/system/organization-provisioning/list.vue`、`api/organization*.ts` | 中心库运行时探测 `organization`、`organization_member`、`organization_tenant_mapping`、`tenant_provisioning_job` | 与本纵切的经营集团不同；租户开通/邀请由后续 TenantOps 纵切承接，真实开通依赖中心库 schema，保持 `BLOCKED_EXTERNAL` |
| 区域与园区 | `system/region/SystemRegionController.java`、Service、Repository、`RegionUpsertRequest.java` | `views/system/region/list.vue`、form、`api/system/region.ts` | Repository 运行时探测 `region`、`region_park`；前端字段 `regionId/regionName/parentId/parkIds/status/remark` | 重建为集团下区域 + 有效期园区归属，不能照搬覆盖式 `parkIds` |
| 部门树 | `system/dept/SystemDeptController.java`、Service | `views/system/dept/list.vue`、form、`api/system/dept.ts` | 旧租户 schema 中 `department`/`dept` 名称由运行时探测 | 当前 `org_units` 已承接部门树；本纵切只把岗位挂到同租户部门，不复制旧混杂字段 |
| 园区 | `park/SystemParkController.java`、Service、Repository、ScopeService | `views/system/park/list.vue`、`api/system/park.ts` | `magic.sql` 的 `park` 表；新系统已有 `parks` | 园区主档不复制；新增有历史的区域归属关系，继续执行显式园区 scope |
| 角色/园区范围 | 旧 `role`、`role_park`、`user_role`、`user_park` 表与系统角色 UI | `views/system/role/*` | `magic.sql` 中 `role`、`role_park`、`user_role` | 新系统已有角色、直接/角色园区授权；区域或岗位不得隐式放大 scope |
| 岗位/任职 | 旧 HR/employee 证据存在字符串 `position`，未发现独立、稳定的岗位主档与有效期任职契约 | 无独立岗位管理闭环证据 | 旧 SQL 多为员工/工资字段，不能证明完整岗位聚合 | 新建规范化岗位/任职模型；旧字段映射待授权 schema/脱敏样本后确认，当前不得伪造迁移 |
| 字段权限 | 旧角色 UI 有动作/菜单/园区权限证据，未发现服务端通用字段投影契约 | 角色模板页面不等于服务端字段级授权 | 无可证明的字段策略表 | 新增服务端白名单字段策略；首个真实落点为 `USER.phone`，默认脱敏、拒绝优先 |

## 2. 字段与枚举映射

| 旧字段/语义 | 新字段/语义 | 转换规则 | 状态 |
| --- | --- | --- | --- |
| `organization`（中心库） | `tenants` 或未来 TenantOps 开通实体 | 不与 `organization_groups` 自动等同；需授权中心库 schema 后裁决 | `BLOCKED_EXTERNAL` |
| `region.region_id` | `organization_regions.legacy_ref`（ETL 载荷映射，不作为业务主键） | 字符串化、租户内映射表解析 | `READY_SYNTHETIC_ONLY` |
| `region.region_name` | `organization_regions.name` | trim、非空、最大 128 | `READY` |
| `region.parent_id` | 集团/区域层级证据 | 当前产品冻结为区域直属集团；旧多级 region 进入迁移隔离清单，待业务确认 | `BLOCKED_EXTERNAL` |
| `region.parkIds` / `region_park` | `region_park_assignments` | 每园区只有一条 current；变更关闭旧行并留历史 | `READY` |
| `status` boolean/tinyint | `ACTIVE` / `DISABLED` | `1/true→ACTIVE`，`0/false→DISABLED`，其他隔离 | `READY` |
| 旧 employee `position` 文本 | `positions` + `user_position_assignments` | 仅授权样本可做去重/映射；当前合成 ETL 验证契约，不导入真实人名/手机号 | `BLOCKED_EXTERNAL` |
| 旧角色动作/园区关系 | 现有 `roles`、`role_permissions`、`role_park_scopes` | 继续沿用 Identity ETL；岗位关系不产生授权 | `IMPLEMENTED_BASELINE` |

## 3. API 处置

| 旧入口 | 新入口/处置 | 用户影响 |
| --- | --- | --- |
| `GET/POST/PUT/DELETE /system/region*` | `/api/v1/system/organization-governance/groups`、`regions`、`park-assignments` | 区域管理升级为集团层级和调区历史；删除改为依赖安全的启停 |
| `/system/dept*` | 现有 `/api/v1/system/org-units` | 保持部门树；岗位可引用部门 |
| `/system/park*` | 现有 `/api/v1/parks` | 园区主档继续由 ParkProperty 管理 |
| 旧角色与园区授权 | 现有 `/api/v1/system/roles`、users | 动作权限与园区范围保持正交 |
| 无稳定旧岗位 API | 新 `/positions`、`user-assignments` | 新增有效期、主岗位和历史闭环 |
| 无服务端字段策略 API | 新 `/field-policies`，并实际投影 `/system/users` | 受保护字段默认最小披露；管理员需显式配置可见 |
| `/organization/invitation/*`、`/organization/provisioning/*` | 本纵切不替代 | 保持真实缺口，后续 TenantOps/迁移纵切处理 |

## 4. 不能在本地关闭的证据

- 未获授权的中心库/租户库 schema dump，不能确认 `organization` 与经营集团的真实映射。
- 未获授权的脱敏员工/岗位样本，不能完成岗位去重、历史任职和用户关联对账。
- 未登记生产或远程预发环境，本纵切不得执行组织开通、真实数据库复制或生产切换。

这些阻塞不影响新模型、API、PC、PG16 和合成 ETL 的实现与验证，但最终数据迁移和旧系统下线仍必须保持 `BLOCKED`。
