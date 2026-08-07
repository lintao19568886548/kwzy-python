# 02 后端业务分析

> 代码根路径：`apps/backend-springboot/src/main/java/cn/yizuw/magic/backend`  
> 分层模式：**按业务域纵向分包**（Controller + Service + Repository + Request/Query 同包）  
> 数据访问：迁移期以 **JdbcTemplate 显式 SQL** 为主，MyBatis-Plus 已接入但使用有限

---

## 总览：业务域地图

| 业务域 | 包路径 | 重要度 | 一句话 |
| --- | --- | --- | --- |
| 认证与会话 | `auth` / `security` | 极高 | 中心库登录 + JWT + 租户切库 |
| 权限与菜单 | `permission` / `menu` / `system/*` | 极高 | RBAC + 园区授权 |
| 组织/企业开通 | `organization` / `onboarding` | 高 | SaaS 租户生命周期 |
| 园区 | `park` | 极高 | 几乎所有业务的数据边界 |
| 房源（厂房/楼层） | `factory` | 高 | 可租面积与租赁管理 |
| 租户/合同 | `rental/tenant` | 极高 | 合同主数据 + 工资耦合 |
| 账单收费 | `bill` / `billimport` | 极高 | 制单、导入、AI、催缴 |
| 财务/核验 | `finance` / `rentverify` | 高 | 流水与收款确认闭环 |
| 招商 | `investment` | 高 | 线索登记 + 雷达获客 |
| CRM | `crm` | 中高 | 销售渠道与企微客户 |
| 门禁通行 | `access` | 中高 | 访客/车辆/门禁 |
| 运维工单 | `maintenance` | 中 | 消防电梯变压器卫生报修 |
| 人事 | `hrm` | 中高 | 员工考勤请假 |
| 智能表计 | `smartmeter` / `integration` | 中 | 品牌与第三方抄表 |
| 报销 | `reimbursement` | 中 | 申请审核 |
| 数据看板 | `dashboard` | 中 | 聚合统计 |
| 消息与任务 | `messaging` / `job` | 高 | Outbox/MQ/XXL-Job |
| AI 能力 | `llm` / `agent` / bill AI | 中高 | 客服、Agent、AI 制单 |

---

## 模块：认证与会话中心

**代码位置：**  
`auth/*`、`security/AuthFilter.java`、`security/JwtService.java`、`security/UserTokenPayload.java`

**核心 Controller：**  
`AuthController` — `/auth/*`

**核心 Service：**  
`AuthService`、`SmsCodeService`、`PageAccessProofService`、`JwtService`

**数据库表（中心库为主）：**  
`user`、`customer`、`user_tenant_mapping`、`refresh_token`；租户库同步 `user` / `user_role` / `user_park`

**业务功能：**

1. 用户名/手机号 + 密码登录（中心库校验）
2. 短信验证码登录
3. Access Token + Refresh Token（Cookie `jwt`）
4. 修改密码、登出、权限码列表 `/auth/codes`
5. 页面二次验证（催缴等高敏操作的 page-access code）
6. 登录成功后写入 TenantContext，绑定 `customerId` / `dbName`

**当前设计问题：**

- 密码兼容多套存储（中心库/租户库 heal 同步），迁移痕迹重
- 未使用完整 Spring Security 过滤器链，安全策略分散在自定义 Filter
- 登录失败文案统一，但错误码内部很多，运维可观测性依赖日志字段

**未来 Python 重构建议：**

- 独立 **Identity 限界上下文**（AuthN/AuthZ 分离）
- 统一用户身份模型：中心账号 ↔ 租户成员 ↔ 园区范围
- OAuth2/OIDC 或标准 JWT 声明；Refresh 旋转与黑名单用 Redis
- 高敏操作统一「二次验证」中间件，而不是散落在账单服务

---

## 模块：用户与权限中心（RBAC + 园区）

**代码位置：**  
`system/user`、`system/role`、`system/menu`、`system/dept`、`system/region`、`menu`、`permission`

**核心 Controller：**  
`SystemUserController`、`SystemRoleController`、`SystemMenuController`、`MenuController`、`SystemDeptController`、`SystemRegionController`

**核心 Service：**  
`SystemUserService`、`SystemRoleService`、`PermissionService`、`MenuService`、`RoleWritePermissionService`、`UserWriteGrantService`

**数据库表：**  
`user`、`role`、`user_role`、`role_menu`、`role_park`、`user_park`、`user_code`、`menu`、`menu_meta`、部门/区域相关表

**业务功能：**

1. 系统用户 CRUD、取消账号、用户名校验
2. 角色 CRUD、绑定/解绑权限码、角色菜单
3. 角色绑定园区（数据范围）
4. 菜单树维护 + 前端动态路由 `/menu/all`
5. 部门组织树、区域管理
6. 写权限按领域细分（`WriteDomain`）

**当前设计问题：**

- 权限模型混用：菜单 auth_code + 角色权限码 + 园区过滤，三层逻辑交织
- 用户写接口路径在 `/user/*` 与 system 命名不完全一致（历史兼容）
- 菜单结构与 Vben 前端强耦合（meta 字段极多）

**未来 Python 重构建议：**

- 明确三层权限：**功能权限 / 数据权限（园区） / 字段/操作权限**
- Casbin 或自研 Policy 引擎；菜单仅作导航，不承载业务授权
- 组织、成员、角色、园区授权独立聚合根

---

## 模块：企业/组织开通（SaaS 租户）

**代码位置：**  
`organization/*`、`onboarding/*`、`messaging/*OrganizationProvisioning*`

**核心 Controller：**  
`OrganizationController`、`OnboardingController`

**核心 Service：**  
`OrganizationService` + 大量 Provisioning 相关 messaging 计划服务

**数据库表：**  
`organization`、`organization_member`、`organization_tenant_mapping`、`customer`、`tenant_invitation`、`tenant_provisioning_job`、`tenant_invitation_join_log`、`vip_membership_payment` 等

**业务功能：**

1. 创建组织/企业
2. 邀请成员加入、撤销邀请
3. 租户库开通任务（provisioning job）
4. 失败任务人工重试
5. 开通完成事件 → Kafka Outbox → Rabbit 通知/站内信
6. Onboarding 状态查询

**当前设计问题：**

- messaging 包类名极度膨胀（灰度开关拆成大量 *PlanService），可读性差
- 组织开通链路跨中心库、租户库、MQ、Redis，事务边界复杂
- 会员支付与开通耦合在同一组织域

**未来 Python 重构建议：**

- 明确 **TenantLifecycle** 聚合：开通、邀请、停用、扩容
- 使用 Outbox + 有限状态机，而不是海量开关类
- VIP/支付独立为 Billing/Subscription 上下文

---

## 模块：园区管理

**代码位置：**  
`park/*`

**核心 Controller：**  
`SystemParkController`（同时兼容 `/system/park` 与 `/park`）

**核心 Service：**  
`ParkService`、`ParkScopeService`、`ParkRepository`

**数据库表：**  
`park`（及园区图片关联）

**业务功能：**

1. 园区 CRUD（系统侧/租赁侧双入口）
2. 当前用户可见园区列表
3. 访客可用园区列表
4. 园区维度仪表盘统计
5. **园区授权范围解析**（几乎所有业务 Service 都依赖 `ParkScopeService`）

**当前设计问题：**

- 同一园区实体多路径 API（legacy 兼容）
- 园区与行政区划、组织归属关系在模型上较浅

**未来 Python 重构建议：**

- 园区作为 **核心聚合根**（Park Aggregate）
- 统一园区 API，废弃双路径
- 明确园区-厂房-楼层-房间/铺位四级空间模型（现有模型到楼层）

---

## 模块：房源（厂房 / 楼层 / 租赁管理）

**代码位置：**  
`factory/*`、`dormitory/*`

**核心 Controller：**  
`FactoryController`、`DormitoryController`

**核心 Service：**  
`FactoryService`、`DormitoryService`

**数据库表：**  
`factory`、`factory_floor`、`factory_floor_image`、`factory_elevator`、`dormitory`、`dormitory_image`

**业务功能：**

1. 厂房列表/详情/可用列表/按园区列表
2. 厂房创建更新删除
3. 租赁管理（rental manage）CRUD — 房源运营视图
4. 楼层属性：面积、租金、承重、层高、消防等级、电梯、变压器功率
5. 宿舍房源管理（相对独立）

**当前设计问题：**

- 房源状态与租户占用关系未形成强一致领域约束（used_area 等易漂移）
- 宿舍与厂房模型分裂，缺少统一「可租单元」抽象
- 电梯规格既有独立表又有 floor JSON 字段演进痕迹

**未来 Python 重构建议：**

- 引入 **PropertyUnit**（可租单元）统一厂房楼层/宿舍/铺位
- 状态机：空置/预定/在租/装修/停用
- 面积与合同占用通过领域服务计算，禁止双写不一致

---

## 模块：租户与合同（租赁核心）

**代码位置：**  
`rental/tenant/*`

**核心 Controller：**  
`RentalTenantController`

**核心 Service：**  
`RentalTenantService`、`ContractReminderBackfillService`、`FinanceLedgerSyncService`（联动）

**数据库表：**  
`rental_tenant`、`tenant_image`、`salary`、`salary_image`

**业务功能：**

1. 租户/合同列表、详情、CRUD
2. 合同起止、递增日/递增率、地址、状态、所属园区
3. 合同到期提醒视图（含 backfill）
4. 租户下拉选择（账单/工资等引用）
5. **工资 salary 管理**（与员工、考勤耦合）—— 命名在 rental 包下
6. 工资批量草稿、状态变更、同步财务

**当前设计问题：**

- 「租户」与「合同」未拆表：一份 rental_tenant 同时承担客户主体 + 合同条款
- 工资业务挂在 rental 包，领域边界混乱
- 图片、短信、部分财务联动仍标注「部分逻辑在旧 Nitro」

**未来 Python 重构建议：**

- 拆分：**Tenant（客户主体）**、**LeaseContract（合同）**、**ContractTerm（条款/递增）**
- 工资迁到 HRM/Payroll 上下文
- 合同状态机 + 续租/退租/变更历史

---

## 模块：账单与收费（核心现金流）

**代码位置：**  
`bill/*`、`bill/airecognize/*`、`billimport/*`（约 50+ 类）

**核心 Controller：**  
`AmountBillController`、`AiBillRecognizeController`、`BillImportController`

**核心 Service：**  
`AmountBillService`、`AiBillRecognizeService`、`BillImportBatchService` 及大量导入子服务

**数据库表：**  
`amount_bill`、`ele_bill`、`water_bill`  
导入：`bill_import_*` 系列  
AI：`ai_bill_job`、`ai_bill_job_file`、`ai_bill_item`

**业务功能：**

1. 总账单列表/详情/新增/修改/删除
2. 费用分项：电费、水费、厂房租金、管理费、服务费、发票税费
3. 电/水表明细（读数、倍率、单价、金额）
4. 收款登记（receipt）
5. 重复账单检查、导出
6. **催缴短信**预览/就绪检查/发送（高敏二次验证）
7. Excel 批量导入流水线：解析 → 候选 → 问题 → 审核 → 发布 → 回滚
8. AI 识别制单：上传工作簿 → 识别匹配租户 → 人工/自动入账

**当前设计问题：**

- 账单模型宽表 + 明细子表，税率/账期/应收应付概念不清晰
- `tenant_name` 冗余字段与 `tenant_id` 并存，易不一致
- billimport 类爆炸，是迁移期复杂度黑洞
- 账单与 finance 流水双写同步风险

**未来 Python 重构建议：**

- **Billing 上下文**：Bill（头）+ BillLine（行）+ Payment + CollectionCase
- 导入作为独立 **Import Pipeline** 限界上下文，事件驱动入账
- AI 识别作为防腐层适配器，输出标准 BillDraft DTO
- 明确账期、应收日、逾期、部分收款状态机

---

## 模块：财务与收款核验

**代码位置：**  
`finance/*`、`rentverify/*`

**核心 Controller：**  
`FinanceController`、`RentVerifyController`

**核心 Service：**  
`FinanceService`、`FinanceLedgerSyncService`、`RentVerifyService`

**数据库表：**  
`finance`、`rent_verify_task`

**业务功能：**

1. 财务流水 CRUD、按园区过滤
2. 账单名称选项、利润表查询
3. 账单/工资等业务触发财务台账同步
4. 收款核验任务：创建 → 确认 / 异常
5. 核验与项目名、园区、负责人选项

**当前设计问题：**

- finance 表字段偏简单（bill_name/category/amount/type），不是完整会计模型
- 业务侧同步财务属于「隐式副作用」，缺少统一账务入口
- 核验任务与账单状态关系需靠约定而非强 FK 约束

**未来 Python 重构建议：**

- 引入 **Ledger（总账）** 与 **PaymentApplication（收款核销）**
- 所有入账走统一领域服务，禁止业务模块直接插 finance 表
- 核验任务作为收款流程子状态

---

## 模块：招商（登记 + 雷达）

**代码位置：**  
`investment/*`（约 51 文件，Controller 超 1000 行）

**核心 Controller：**  
`InvestmentController`、`PublicOpportunityImageController`

**核心 Service：**  
大量雷达/爬虫/评分/触达服务

**数据库表：**  
传统：`investment`、`investment_image`、`investment_tenant`  
CRM 化：`investment_agent`、`investment_customer`、`investment_lead`…  
雷达：`crawler_*`、`signal_event`、`enterprise_profile`、`investment_public_opportunity`、`investment_outreach_*`、`contact_restriction*`、`property_match_result` 等

**业务功能：**

1. **传统招商登记**：中介/客户、意向面积/等级、进度、跟进、转租户
2. **招商雷达**：爬虫源/任务、信号事件、外部线索、企业画像
3. 公开商机采集、导入 URL、需求页解析、修复
4. 线索评分规则、房源匹配
5. 触达模板审批与外呼任务
6. SOP 提醒、拜访、关闭线索、分配负责人
7. 联系限制（合规）导入/审批释放
8. 雷达分析看板

**当前设计问题：**

- 一个 Controller 承载「登记 + 雷达」全部 API，违反单一职责
- 表数量与流程极多，与核心租赁域耦合点（转租户）脆弱
- 爬虫/代理池配置复杂，运维成本高

**未来 Python 重构建议：**

- 拆成 **Lead CRM** 与 **Acquisition Radar** 两个上下文
- 转租户通过领域事件 `LeadConverted` 进入合同上下文
- 爬虫服务独立部署，主应用只消费标准化 Lead DTO

---

## 模块：CRM（销售渠道 / 企微）

**代码位置：**  
`crm/*`、`integration/wework/*`

**核心 Controller：**  
`CrmController`、`WeworkCallbackController`

**核心 Service：**  
`CrmService`、`WeworkCallbackService`

**数据库表：**  
`crm_sales_channel`、`crm_scan_log`、`crm_customer_owner_binding`、`crm_wework_contact_way`、`crm_external_contact_log`

**业务功能：**

1. 销售渠道与活码
2. 扫码日志
3. 客户-销售绑定/转移/状态
4. 小程序会话/手机号、H5/OAuth 邀请
5. 企微回调

**当前设计问题：**

- CRM 与招商雷达客户模型并行，存在双客户主数据风险
- 强依赖企微配置，本地难完整联调

**未来 Python 重构建议：**

- 统一 **Customer** 主数据，渠道绑定作为关系实体
- 企微作为适配器，不侵入领域核心

---

## 模块：门禁与通行

**代码位置：**  
`access/*`

**核心 Controller：**  
`AccessController`

**核心 Service：**  
`AccessService`、`AccessRepository`

**数据库表：**  
`access_car`、`access_visitor`、门禁设备/品牌相关表

**业务功能：**

1. 门禁品牌、门禁设备
2. 车辆白名单
3. 访客登记（含公开 register 接口）
4. 状态管理

**当前设计问题：**

- 与真实门禁硬件联动深度有限（偏台账）
- 访客公开接口需严格防刷与审计

**未来 Python 重构建议：**

- Access 上下文：VisitorPass / VehiclePermit / Device
- 公开登记 API 限流 + 园区级 token

---

## 模块：运维维保与工单

**代码位置：**  
`maintenance/*`

**核心 Controller：**  
`MaintenanceController`（电梯/消防/变压器/卫生/报修/厂房维保合一）

**核心 Service：**  
Maintenance 相关 service/repository

**数据库表：**  
`firefighting`、`transformer`、电梯/卫生/报修/厂房维保等表

**业务功能：**

1. 各类巡检维保记录 CRUD
2. 外链公开 **register** 登记（电梯/消防/变压器）
3. 报修工单闭环

**当前设计问题：**

- 多资产类型 CRUD 模式重复，缺统一 WorkOrder 模型
- 检查字段多为字符串（是否合格等），结构化不足

**未来 Python 重构建议：**

- 统一 **Asset + Inspection + WorkOrder** 模型
- 不同资产类型用策略/子类型扩展

---

## 模块：人事 HRM

**代码位置：**  
`hrm/*`、`localization/*`

**核心 Controller：**  
`HrmController`、`LocalizationController`

**核心 Service：**  
`HrmService`、`AttendanceCalculator`、`AttendanceLocationValidator`

**数据库表：**  
员工、考勤、请假、轨迹、定位相关表；与 `salary` 联动

**业务功能：**

1. 员工信息 CRUD、账号绑定
2. 打卡、异常确认、位置确认
3. 考勤统计、工资摘要规则
4. 请假申请
5. 轨迹列表/导出

**当前设计问题：**

- 考勤办公地点硬编码痕迹（`AttendanceOfficeLocations`）
- 工资逻辑跨 hrm 与 rental 包

**未来 Python 重构建议：**

- HRM 聚合：Employee / Attendance / Leave / Payroll
- 园区/办公点配置化
- 与权限用户体系「员工账号」明确映射规则

---

## 模块：智能表计与第三方集成

**代码位置：**  
`smartmeter/*`、`integration/hezhong/*`、`integration/ymsino/*`、`integration/wechat/*`、`integration/alipay/*`

**核心 Controller：**  
`SmartMeterBrandController`、`HezhongController`、`YmsinoController`、`WechatPayController`、`AlipayPayController`

**业务功能：**

1. 表品牌管理
2. 合众/亿玛水电数据查询
3. 微信支付/退款/回调验签
4. 支付宝配置

**当前设计问题：**

- 抄表数据与账单电水明细的自动同步链路不完整（多依赖人工/导入）
- 支付能力与会员/VIP 场景绑定，通用收款能力不足

**未来 Python 重构建议：**

- Metering 上下文 + IoT 适配器
- 支付作为通用 Payment Gateway，账单收款可挂接

---

## 模块：报销

**代码位置：**  
`reimbursement/*`

**核心 Controller：**  
`ReimbursementController`

**数据库表：**  
`reimbursement`

**业务功能：**  
申请、审核、删除、待审数量、汇总分析

**问题与建议：**  
审批流过简（status 整型）；新系统应接入通用工作流引擎或轻量状态机。

---

## 模块：数据看板

**代码位置：**  
`dashboard/overview/*`、`dashboard/workspace/*`

**核心 Controller：**  
`DashboardOverviewController`、`AnalyticsController`、`WorkspaceController`

**业务功能：**  
厂房出租统计、合同统计、客户概览、待办、能耗、营收、工作台列表、批量 overview

**问题与建议：**  
实时聚合 SQL 压力大；新系统应建设 **只读分析库/物化视图/定时指标表**。

---

## 模块：消息、Outbox 与定时任务

**代码位置：**  
`messaging/*`、`job/*`、`ops/*`

**业务功能：**

1. 事件 Outbox 写入与派发（Kafka）
2. Rabbit 通知/轻任务/延迟重试
3. 组织开通完成消费与站内信
4. XXL-Job 迁移/补偿/导入运维任务
5. 内部 API 入队（`/internal/outbox`、`/internal/rabbit/*`）

**问题与建议：**  
开关矩阵过密；Python 侧建议用明确的事件总线 + 状态机 + 少量环境配置。

---

## 模块：AI / Agent / 智能客服

**代码位置：**  
`llm/*`、`agent/*`、`bill/airecognize/*`

**业务功能：**

1. 智谱对话、百炼智能客服（RAG 库）
2. 账单图片/表单分析
3. Agent skills/tasks/chat
4. AI 账单识别入账

**问题与建议：**  
AI 与业务核心耦合在同一单体；新系统 AI 应作为 **能力层/侧车服务**，通过标准 DTO 进入领域。

---

## 后端横切设计（所有业务共用）

| 横切点 | 实现 | 业务影响 |
| --- | --- | --- |
| 多租户 | `TenantContext` + 动态数据源 | 所有业务 SQL 默认进当前租户库 |
| 园区范围 | `ParkScopeService` | 列表/详情几乎都带 park 过滤 |
| 统一响应 | `ApiResponse` + `GlobalExceptionHandler` | 兼容旧前端 code/message |
| 鉴权 | `AuthFilter` | JWT 解析失败即拒绝 |
| 字段漂移兼容 | `information_schema` 探测 | 迁移期 schema 不一致可运行 |
| 事务 | `tenantTransactionManager` | 租户库事务 |

---

## 业务依赖关系（简图）

```text
登录(中心库) → 租户上下文
     ↓
用户/角色/菜单 ←→ 园区授权
     ↓
园区 → 厂房/楼层 → 租户合同 → 账单 → 收款/核验 → 财务流水
                ↘ 招商线索转租户
能耗表计 → 账单明细
催缴短信 ← 账单逾期
运维/门禁/HRM 相对独立，但都挂 park_id
组织开通 → 创建租户库与初始用户
```

---

## 对 Python 重构的后端结论

1. **不要按 Java 包 1:1 翻译**，按领域重切：Identity、TenantOps、ParkProperty、Lease、Billing、Finance、Investment、Facility、HRM、Integration、AI。  
2. **JdbcTemplate 兼容层是迁移遗产**，Python 应用 SQLAlchemy/模型层 + 明确迁移脚本。  
3. **账单与招商雷达**是复杂度最高的两座山，优先领域建模再写 API。  
4. **salary 归 HRM，contract 归 Lease，customer 归 CRM 主数据**，消解当前错位。  
5. 保留多租户与园区数据权限，这是产品核心而非技术债。
