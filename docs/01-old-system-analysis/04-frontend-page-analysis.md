# 04 前端页面分析

> 前端主应用：`playground/`（`@vben/playground`，Vben Admin 5.5.4）  
> 路由：`playground/src/router/routes/modules/*`  
> API：`playground/src/api/**`  
> 页面：`playground/src/views/**`（约 316 个 Vue 文件）  
> 多端：PC Web + Capacitor App（大量 `mobile-*` 页面）+ 微信小程序壳

---

## 1. 前端技术架构摘要

| 项 | 说明 |
| --- | --- |
| 框架 | Vue3 + TS + Vite |
| 脚手架 | Vben Admin 5.x monorepo |
| 路由 | 静态模块路由 + 后端 `/menu/all` 动态菜单权限 |
| 请求 | 统一 `api/request.ts`，前缀 `/api` |
| 鉴权 | Access Token；Refresh Cookie；路由 guard |
| 移动端 | 同仓双 UI（list.vue + mobile-list.vue），Capacitor 打包 |
| 小程序 | `miniprogram/`：home / webview / share-bridge |

---

## 2. 页面总表（业务页，排除 demos/examples）

### 2.1 仪表盘 / 工作台

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 分析看板 | `/analytics` | 园区经营分析图表 | `/api/analytics/*`、`/api/dashboard/*` | 数据分析 |
| 工作台 | dashboard/workbench 相关 | 待办、快捷入口 | `/api/dashboard/workbench-todos`、`/api/dashboard/workspace/list` | 工作台 |
| Agent 工作台 | `/tools/agent-workbench` | AI Agent 操作台 | `/api/agent/*` | AI |
| Agent 任务 | `/tools/agent-tasks` | 任务列表/详情 | `/api/agent/tasks` | AI |
| Skill 中心 | `/tools/agent-skills` | Agent 技能 | `/api/agent/skills` | AI |
| AI 工具导航 | `/tools/webtools` | AI 工具入口 | 视具体工具 | AI |

---

### 2.2 租赁 / 园区 / 房源

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 园区管理 | `/rental/manage` | 园区列表、厂房楼层维护 | `/api/system/park/*`、`/api/park/*`、`/api/factory/*`、`/api/rental/manage/*` | 园区/房源 |
| 园区管理(移动) | `/rental/manage/mobile` | 移动端园区管理 | 同上 | 园区/房源 |
| 房源列表 | `/rental/list` | 可租厂房/楼层浏览 | `/api/factory/list`、`available-list` | 房源 |
| 房源详情 | `/rental/detail/:id` | 房源详情展示 | `/api/factory/{id}` | 房源 |
| 已入驻厂房 | `/rental/settled` | 已出租/入驻视图 | factory + tenant 组合查询 | 租赁 |
| 已入驻(移动) | `/rental/settled/mobile` | 移动端 | 同上 | 租赁 |
| 租户管理(入口) | `/rental/tenant` → 重定向 | 跳转合同管理 | — | 租赁 |
| 租户移动列表 | `/rental/tenant/mobile` | 移动端租户 | `/api/rental/tenant/*` | 租赁 |

---

### 2.3 合同 / 账单 / 财务

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 合同管理 | `/finance/contract` | 租户合同新增/查询/编辑/提醒 | `/api/rental/tenant/*` | 合同 |
| 账单管理 | `/bill` | 账单列表、制单、删除、筛选 | `/api/bill/amount/*` | 账单 |
| 确认收款 | `/bill/receipt-confirm` | 登记收款 | `PUT /api/bill/amount/{id}/receipt` | 收费 |
| 账单移动列表 | `/bill/mobile-list` | 移动端账单 | `/api/bill/amount/list` | 账单 |
| 完整制单(移动) | `/bill/mobile-full-create` | 对齐 PC 手工制单 | `POST /api/bill/amount` 等 | 账单 |
| AI 识别制单 | `/bill/mobile-ai` | 上传识别入账 | `/api/bill/ai-recognize/*` | AI 账单 |
| 账单导入 | `/bill/mobile-import` | Excel 导入流水线 | `/api/bill/import/*` | 账单导入 |
| 收款核验列表 | `/finance/rent-verify` | 核验任务列表 | `/api/rent/verify/*` | 收费核验 |
| 核验详情 | `/finance/rent-verify/:id` | 确认核验 | `POST .../confirm` | 收费核验 |
| 提交异常 | `/finance/rent-verify/:id/abnormal` | 异常上报 | `POST .../abnormal` | 收费核验 |
| 财务流水 | `/finance/manage` | 收支流水管理 | `/api/finance/*` | 财务 |
| 财务移动 | `/finance/mobile-manage` | 移动端流水 | 同上 | 财务 |
| 报销申请 | `/reimbursement/application` | 提交报销 | `/api/reimbursement` | 报销 |
| 报销审核 | `/reimbursement/audit` | 审核报销 | `PUT /api/reimbursement/{id}` | 报销 |
| 报销移动申请/审核 | `/reimbursement/mobile-*` | 移动端 | 同上 | 报销 |

**账单页核心功能拆解：**

- 客户/租户维度查询账单  
- 新增账单（继承上次模板：表计/单价）  
- 电费水费明细编辑  
- 重复检查  
- 导出  
- 催缴短信预览与发送（需页面二次验证）  
- AI / 导入 两种批量入口  

---

### 2.4 招商 / CRM

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 招商登记 | `/investment/agent` | 线索登记、跟进、进度 | `/api/investment/*` | 招商 |
| 招商记录(移动) | `/investment/mobile` | 移动端招商 | 同上 | 招商 |
| 招商雷达相关 | `views/investment/radar/*`、`app/*` | 雷达线索/商机/分析（菜单可能动态下发） | `/api/investment/radar/*` | 招商雷达 |
| CRM 二维码测试 | `/crm/qrcode-test` | 小程序码/活码测试 | `/api/crm/*` | CRM |

**招商功能点：**

- 客户新增与查询  
- 意向等级/面积  
- 跟进反馈  
- 转租户（convert-to-tenant）  
- 雷达：采集、评分、匹配房源、触达、SOP  

---

### 2.5 门禁通行

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 门禁管理 | `/access/door` | 门禁设备列表与状态 | `/api/access/door/*` | 门禁 |
| 门禁品牌 | `/access/brand` | 品牌维护 | `/api/access/brand/*` | 门禁 |
| 车辆管理 | `/access/car` | 车辆登记 | `/api/access/car/*` | 车辆 |
| 访客管理 | `/access/visitor` | 访客列表 | `/api/access/visitor/*` | 访客 |
| 访客登记 | `/access/visitor/register` | 公开/自助登记 | `POST /api/access/visitor/register` | 访客 |
| 各模块 mobile | `/access/*/mobile` | 移动端 | 同上 | 通行 |

---

### 2.6 运维维保

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 消防管理 | `/maintenance/firefighting` | 消防巡检记录 | `/api/maintenance/firefighting/*` | 运维 |
| 电梯管理 | `/maintenance/elevator` | 电梯维保 | `/api/maintenance/elevator/*` | 运维 |
| 变压器维保 | `/maintenance/transformer` | 变压器巡检 | `/api/maintenance/transformer/*` | 运维 |
| 卫生检查 | `/maintenance/hygieneCheck` | 卫生检查 | `/api/maintenance/hygieneCheck/*` | 运维 |
| 厂房维保 | `/maintenance/factoryMaint` | 厂房维修保养 | `/api/maintenance/factoryMaint/*` | 运维 |
| 报修工单 | `/maintenance/repair-order` | 报修闭环 | `/api/maintenance/repair-order/*` | 工单 |
| 各 mobile / 公开登记 | `*/mobile`、external register 路由 | 外勤登记 | `POST .../register` | 运维 |

---

### 2.7 人事 HRM

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 员工信息 | `/hrm/information` | 员工档案 | `/api/hrm/employee/*` | HRM |
| 考勤打卡 | `/hrm/attendance/punch` | 定位打卡 | `/api/hrm/attendance/*` | 考勤 |
| 考勤记录 | `/hrm/attendance/stats` | 记录与统计 | 同上 | 考勤 |
| 考勤轨迹 | `/hrm/trajectory` | 轨迹查询导出 | `/api/hrm/trajectory/*` | 考勤 |
| 工资管理 | `/hrm/salary` | 工资单 | `/api/rental/salary/*` | 薪酬 |
| 请假申请 | `/hrm/leaveapplication` | 请假 | `/api/hrm/leaveapplication/*` | 请假 |

---

### 2.8 智能表计

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 电表读数 | `/smart-meter/meter` | 电表数据 | `/api/hezhong/meterinfo/*` 等 | 表计 |
| 水表读数 | `/smart-meter/water` | 水表数据 | `/api/hezhong/waterinfo/*` | 表计 |
| 表品牌 | `/smart-meter/electric-brand`、`water-brand` | 品牌管理 | `/api/smart-meter/brand/*` | 表计 |
| 亿玛原始数据 | `/ymsino/meter` | 原始抄表 | `/api/ymsino/*` | 表计 |

---

### 2.9 系统管理

| 页面名称 | 路径 | 功能 | 对应后端接口 | 业务模块 |
| --- | --- | --- | --- | --- |
| 用户管理 | `/system/user` | 用户 CRUD | `/api/user/*` | 用户中心 |
| 角色管理 | `/system/role` | 角色权限 | `/api/system/role/*` | 权限 |
| 菜单管理 | `/system/menu` | 菜单维护 | `/api/system/menu/*` | 权限 |
| 部门管理 | `/system/dept` | 组织部门 | `/api/system/dept/*` | 组织 |
| 区域管理 | `/system/region` | 区域 | `/api/system/region/*` | 系统 |
| 园区(系统隐藏入口) | `/system/park` | 与租赁园区同源 | `/api/system/park/*` | 园区 |
| 意见反馈 | `/system/feedback` | 反馈列表 | `/api/system/feedback/list` | 系统 |
| 组织开通相关 | profile / system provisioning 视图 | 开通状态 | `/api/organization/*` | SaaS |

---

### 2.10 个人中心 / 通知 / 其它

| 页面名称 | 路径 | 功能 | 接口 | 模块 |
| --- | --- | --- | --- | --- |
| 企业邀请 | `/profile/organization-invitations` | 邀请管理 | `/api/organization/invitation/*` | 组织 |
| VIP 会员 | `/profile/vip-membership` | 会员 | 支付相关 | 订阅 |
| 会员退款 | `/profile/vip-refunds` | 退款单 | 微信退款 API | 订阅 |
| 智能客服 | `profile/smart-service` | 对话 | `/api/smart-service/chat` | AI |
| 通知列表 | `/notices` | 公告 | `/api/notices/list` | 通知 |
| 登录/认证 | `_core/authentication` | 密码/短信登录 | `/api/auth/*` | 认证 |

---

## 3. 前端 API 模块与后端映射

| 前端 API 目录 | 后端模块 |
| --- | --- |
| `api/core/auth.ts` | AuthController |
| `api/core/user.ts` / `menu.ts` | UserInfo / Menu |
| `api/system/*` | system/* Controllers |
| `api/park/*` | SystemParkController |
| `api/factory/*` | FactoryController |
| `api/rental/*` | RentalTenant + Factory rental manage |
| `api/bill/*` | AmountBill / AI / Import |
| `api/finance/*` | Finance + RentVerify |
| `api/investment/*` | Investment |
| `api/crm.ts` | Crm |
| `api/access/*` | Access |
| `api/maintenance/*` | Maintenance |
| `api/hrm/*` | Hrm |
| `api/smart-meter/*` / `hezhong` / `ymsino` | 表计集成 |
| `api/reimbursement/*` | Reimbursement |
| `api/dashboard/*` | Dashboard/Analytics |
| `api/chat/*` | LLM/SmartService |
| `api/organization*.ts` | Organization |
| `api/wechat*.ts` / `alipay-pay.ts` | 支付 |

---

## 4. 路由组织特点

1. **财务大模块聚合**：`/finance` 下挂账单、合同、核验、报销——符合园区运营「钱」相关一站式入口。  
2. **租赁模块偏空间**：园区、房源、入驻。  
3. **几乎每个业务都有 mobile 双页面**：说明 App 与 PC 同等重要。  
4. **bill 静态路由为空文件**，账单主路由挂在 finance 下。  
5. **大量菜单由后端 menu 表动态下发**，静态 routes 与线上菜单可能不完全一致（雷达等可能只在 DB 菜单中）。

---

## 5. 多端形态

| 端 | 实现 | 特点 |
| --- | --- | --- |
| PC Web | playground Vite 构建 | 完整管理功能 |
| Android/iOS | Capacitor 包装同一套前端 | 打卡定位、推送、原生能力 |
| 微信小程序 | 轻壳 + WebView | CRM 分享、邀请、打开 H5 |

---

## 6. 前端问题（影响 Python 新系统 API 设计）

1. **接口字段兼容旧 Nitro**：返回结构多 Map，前端容错多。  
2. **同一业务多路径**（park 双 API）。  
3. **移动/PC 重复页面**维护成本高，新系统宜响应式 + 少量原生差异。  
4. **工资页面挂在 HRM 路由但 API 在 rental/salary**——前后端命名不一致。  
5. **demos/examples 残留**增加仓库噪音。

---

## 7. 对 Python 重构的前端建议（仅方向）

- 继续 Vue3 或评估统一设计系统；**API 契约优先用 OpenAPI**。  
- 按业务域拆前端 package：`lease`、`billing`、`investment`、`facility`。  
- 三端共享 BFF/API，小程序能力页面 native 化关键路径（登录、支付、分享）。  
- 菜单权限继续动态，但权限码与路由 name 稳定化。
