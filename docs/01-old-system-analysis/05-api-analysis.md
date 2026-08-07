# 05 API 接口分析

> 扫描范围：`apps/backend-springboot` 全部 `*Controller.java`  
> 统计：**约 482 个** HTTP 映射  
> 统一前缀：`server.servlet.context-path=/api`  
> 完整原始清单：同目录 `_api-raw.tsv`（METHOD / PATH / Handler）  
> 下文按业务模块整理核心接口（非机械翻译全部 482 条，但覆盖主业务链）

---

## 0. 约定

- **路径**均写完整：`/api/...`  
- **鉴权**：除特别说明（访客登记、部分 OAuth/支付回调、status）外，默认需 JWT  
- **多租户**：业务接口在租户库执行，园区列表受 `ParkScope` 过滤  
- **返回**：统一包装 `ApiResponse`（兼容旧前端 code/data/message）

---

## 1. 认证 Auth

| 接口名称 | HTTP | 路径 | 参数 | 返回 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- | --- | --- |
| 密码登录 | POST | `/api/auth/login` | username, password | accessToken, 用户摘要 | 账号登录 | 认证 |
| 验证码登录 | POST | `/api/auth/code-login` | phone, code | 同登录 | 短信登录 | 认证 |
| 刷新令牌 | POST | `/api/auth/refresh` | Cookie jwt | 新 accessToken | 续期 | 认证 |
| 登出 | POST | `/api/auth/logout` | — | ok | 注销刷新令牌 | 认证 |
| 修改密码 | POST | `/api/auth/password` | old/new | ok | 改密 | 认证 |
| 发送登录验证码 | POST | `/api/auth/send-login-code` | phone | ok | 发短信 | 认证 |
| 页面访问验证码 | POST | `/api/auth/send-page-access-code` | — | ok | 高敏操作二次验证 | 认证 |
| 校验页面验证码 | POST | `/api/auth/verify-page-access-code` | code | proof | 获得短期凭证 | 认证 |
| 权限码列表 | GET | `/api/auth/codes` | — | string[] | 前端按钮权限 | 权限 |
| 页面验证就绪 | GET | `/api/auth/page-access-verification-readiness` | — | 配置状态 | 催缴前检查 | 认证 |

---

## 2. 用户与菜单

| 接口名称 | HTTP | 路径 | 参数 | 返回 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- | --- | --- |
| 当前用户信息 | GET | `/api/user/info` | — | 用户/角色/首页 | 登录后拉画像 | 用户 |
| 用户反馈 | POST | `/api/user/feedback` | 内容/图片 | ok | 意见反馈 | 用户 |
| 用户列表 | GET | `/api/user/list` | 分页筛选 | page | 用户管理 | 用户中心 |
| 创建用户 | POST | `/api/user` | 账号角色园区 | id | 开户 | 用户中心 |
| 更新用户 | PUT | `/api/user/{id}` | 字段 | ok | 编辑 | 用户中心 |
| 删除用户 | DELETE | `/api/user/{id}` | — | ok | 删除 | 用户中心 |
| 取消账号 | POST | `/api/user/cancel` | — | ok | 注销 | 用户中心 |
| 校验用户名 | GET | `/api/user/check-username` | username | bool | 唯一性 | 用户中心 |
| 全部菜单 | GET | `/api/menu/all` | — | 路由树 | 动态菜单 | 权限 |
| 按父角色菜单 | GET | `/api/menu/by-parent-role` | — | 树 | 角色授权 UI | 权限 |

---

## 3. 系统管理 System

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 角色 CRUD/权限 | GET/POST/PUT/DELETE | `/api/system/role/*` | 角色与权限码 | 权限 |
| 菜单 CRUD | * | `/api/system/menu/*` | 菜单维护 | 权限 |
| 部门 CRUD | * | `/api/system/dept/*` | 部门树 | 组织 |
| 区域 CRUD | * | `/api/system/region/*` | 区域字典 | 系统 |
| 反馈列表 | GET | `/api/system/feedback/list` | 管理端看反馈 | 系统 |
| 系统密钥 | GET | `/api/system/key` | 前端加密/配置键 | 系统 |
| 菜单模板同步 | POST/GET | `/api/system/menu-template-sync/*` | 多租户菜单对齐 | 运维 |
| App 版本 | GET | `/api/system/version` | 移动端更新 | 系统 |

---

## 4. 园区 Park

| 接口名称 | HTTP | 路径 | 参数 | 返回 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- | --- | --- |
| 系统园区列表 | GET | `/api/system/park/list` | 分页 | page | 管理园区 | 园区 |
| 园区详情 | GET | `/api/system/park/{id}` | id | 园区 | 详情 | 园区 |
| 创建园区 | POST | `/api/system/park` 或 `/api/park` | 园区字段 | id | 新建 | 园区 |
| 更新/删除园区 | PUT/DELETE | `/api/system/park/{id}` 等 | — | ok | 维护 | 园区 |
| 当前用户园区 | GET | `/api/park/list` | — | list | 切换园区 | 园区 |
| 访客园区列表 | GET | `/api/park/visitor-list` | — | list | 公开登记用 | 园区 |
| 园区看板统计 | GET | `/api/park/dashboard-stats` | parkId | stats | 概览 | 园区 |
| 租赁园区详情 | GET | `/api/rental/park/{id}` | id | 详情 | 租赁侧 | 园区 |

---

## 5. 房源 Factory / 宿舍

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 厂房列表 | GET | `/api/factory/list` | 房源查询 | 房源 |
| 可用厂房 | GET | `/api/factory/available-list` | 空置可租 | 房源 |
| 厂房详情 | GET | `/api/factory/{id}` | 详情 | 房源 |
| 创建/改/删厂房 | POST/PUT/DELETE | `/api/factory` | 维护 | 房源 |
| 按园区厂房 | GET | `/api/factory/list-by-park` | 下拉 | 房源 |
| 租赁管理列表 | GET | `/api/rental/manage/list` | 运营管理视图 | 房源 |
| 租赁管理 CRUD | * | `/api/rental/manage/*` | 楼层运营 | 房源 |
| 宿舍 CRUD | POST/PUT/DELETE | `/api/dormitory` | 宿舍房源 | 宿舍 |

---

## 6. 租户合同 / 工资

| 接口名称 | HTTP | 路径 | 参数要点 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- | --- |
| 租户列表 | GET | `/api/rental/tenant/list` | 园区/状态/合同期/提醒 | 合同查询 | 合同 |
| 租户详情 | GET | `/api/rental/tenant/{id}` | id | 详情 | 合同 |
| 创建租户 | POST | `/api/rental/tenant` | 名称电话合同条款 | 新签 | 合同 |
| 更新租户 | PUT | `/api/rental/tenant/{id}` | 字段 | 变更 | 合同 |
| 删除租户 | DELETE | `/api/rental/tenant/{id}` | — | 删除 | 合同 |
| 租户下拉 | GET | `/api/rental/tenant/select` | keyword | 制单选租户 | 合同 |
| 短信信息 | GET | `/api/rental/tenant/{id}/sms-info` | — | 催缴号码 | 催缴 |
| 工资列表/CRUD | * | `/api/rental/salary/*` | 账期/员工/租户 | 薪酬 | 薪酬 |
| 工资同步 | POST | `/api/rental/salary/sync` | — | 同步财务 | 薪酬 |
| 批量草稿/状态 | POST | `/api/rental/salary/batch-*` | 员工集合 | 批量计薪 | 薪酬 |

---

## 7. 账单 Billing

| 接口名称 | HTTP | 路径 | 参数要点 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- | --- |
| 账单列表 | GET | `/api/bill/amount/list` | 园区/租户/收款状态/账期 | 查询 | 账单 |
| 账单详情 | GET | `/api/bill/amount/{id}` | id | 含水电明细 | 账单 |
| 最近模板 | GET | `/api/bill/amount/latest-template` | parkId, tenantId | 继承表计单价 | 账单 |
| 项目名选项 | GET | `/api/bill/amount/project-options` | keyword | 项目下拉 | 账单 |
| 新建账单 | POST | `/api/bill/amount` | 头+明细 | 制单 | 账单 |
| 更新账单 | PUT | `/api/bill/amount/{id}` | 字段 | 改单 | 账单 |
| 确认收款 | PUT | `/api/bill/amount/{id}/receipt` | receiptTime 等 | 收费 | 收费 |
| 重复检查 | POST | `/api/bill/amount/duplicate-check` | 租户/账期 | 防重 | 账单 |
| 导出 | POST | `/api/bill/amount/export` | 筛选 | 导出 | 账单 |
| 删除 | DELETE | `/api/bill/amount/{id}` 或批量 | — | 删单 | 账单 |
| 催缴预览 | POST | `/api/bill/amount/collection-sms/preview` | billIds | 短信内容 | 催缴 |
| 催缴就绪 | GET | `/api/bill/amount/collection-sms/readiness` | — | 通道检查 | 催缴 |
| 催缴发送 | POST | `/api/bill/amount/collection-sms/send` | billIds + proof | 发送催缴 | 催缴 |

### 7.1 AI 识别制单 `/api/bill/ai-recognize`

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/capabilities` | GET | 能力开关 |
| `/jobs` | POST/GET | 创建/列表识别任务 |
| `/jobs/{id}` | GET/DELETE | 任务详情/删除 |
| `/jobs/{id}/items` | GET | 识别结果项 |
| `/items/{id}/commit` | POST | 单项入账 |
| `/jobs/{id}/batch-commit` | POST | 批量入账 |
| `/jobs/{id}/auto-match-commit` | POST | 自动匹配入账 |
| `/jobs/{id}/rollback` | POST | 回滚 |
| `/jobs/{id}/report` | GET | 报告 |

### 7.2 Excel 导入 `/api/bill/import`

| 能力组 | 路径模式 | 用途 |
| --- | --- | --- |
| 批次 | `/batches` | 创建/查询导入批次 |
| 文件/候选 | `/batches/{id}/files|candidates` | 解析结果 |
| 问题 | `/issues` | 审核问题与确认 |
| 发布 | `/publish` | 写入正式账单 |
| 重试/取消/回滚 | `/retry|/cancel|/rollback` | 运维控制 |
| 模板/别名 | `/templates|/aliases` | 治理 |
| 运维 | `/maintenance/*` | 健康度与源文件保留 |

---

## 8. 财务 / 核验

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 财务列表/详情 | GET | `/api/finance/list`、`/{id}` | 流水查询 | 财务 |
| 创建/改/删流水 | POST/PUT/DELETE | `/api/finance` | 手工记账 | 财务 |
| 账单名选项 | GET | `/api/finance/bill-name-options` | 下拉 | 财务 |
| 利润表 | GET | `/api/finance/profit-statement` | 经营利润 | 财务 |
| 创建核验任务 | POST | `/api/rent/verify/create` | 发起收款核验 | 核验 |
| 核验列表/详情 | GET | `/api/rent/verify/*` | 查询 | 核验 |
| 确认核验 | POST | `/api/rent/verify/{id}/confirm` | 通过 | 核验 |
| 异常核验 | POST | `/api/rent/verify/{id}/abnormal` | 异常 | 核验 |

---

## 9. 招商 Investment

### 9.1 传统招商登记

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 线索列表 | GET | `/api/investment/list` | 查询 | 招商 |
| 线索详情 | GET | `/api/investment/{id}` | 详情 | 招商 |
| 新建/更新/删除 | POST/PUT/DELETE | `/api/investment` | CRUD | 招商 |
| 跟进反馈 | POST | `/api/investment/{id}/follow-feedback` | 跟进 | 招商 |
| 转租户 | POST | `/api/investment/{id}/convert-to-tenant` | 签约转化 | 招商 |
| 中介统计 | GET | `/api/investment/agent-stats` | 绩效 | 招商 |
| CRM 回填 | POST | `/api/investment/crm/backfill` | 数据修复 | 招商 |

### 9.2 招商雷达（节选，接口极多）

| 能力 | 路径前缀 | 业务用途 |
| --- | --- | --- |
| 评分规则 | `/api/investment/radar/score-rule` | 线索打分 |
| 爬虫源/任务 | `/radar/crawler-source`、`crawler-task` | 采集 |
| 信号事件 | `/radar/signal-event` | 商机信号 |
| 外部线索 | `/radar/external-lead` | 线索池 |
| 企业画像 | `/radar/enterprise-profile` | 企业档案 |
| 公开商机 | `/radar/public-opportunity/*` | 公域商机 |
| 触达模板/任务 | `/radar/outreach-*` | 外联 |
| 分析 | `/radar/analytics/*` | 漏斗分析 |
| 房源匹配 | `/radar/lead/{id}/property-match` | 匹配 |
| 跟进/拜访/SOP | `/radar/lead/{id}/follow|visit|sop` | 销售过程 |
| 联系限制 | `/radar/contact-restriction/*` | 合规 |

---

## 10. CRM

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 概览 | GET | `/api/crm/overview` | CRM 看板 | CRM |
| 销售渠道 | GET/POST | `/api/crm/sales/channel/*` | 渠道与活码 | CRM |
| 扫码日志 | GET | `/api/crm/scan-log/list` | 获客分析 | CRM |
| 客户绑定 | POST | `/api/crm/binding/*` | 归属销售 | CRM |
| 邀请码/OAuth | GET/POST | `/api/crm/invite/*` | 拉新 | CRM |
| 小程序会话/手机 | POST | `/api/crm/miniprogram/*` | 小程序登录信息 | CRM |

---

## 11. 门禁 Access

| 接口名称 | HTTP | 路径 | 业务用途 | 模块 |
| --- | --- | --- | --- | --- |
| 品牌 CRUD | * | `/api/access/brand/*` | 设备品牌 | 门禁 |
| 门禁设备 | * | `/api/access/door/*` | 门状态 | 门禁 |
| 车辆 CRUD | * | `/api/access/car/*` | 车辆通行 | 车辆 |
| 访客 CRUD | * | `/api/access/visitor/*` | 访客管理 | 访客 |
| 访客公开登记 | POST | `/api/access/visitor/register` | 无登录登记 | 访客 |

---

## 12. 运维 Maintenance

统一前缀 `/api/maintenance/`：

| 子资源 | 典型接口 | 用途 |
| --- | --- | --- |
| `repair-order` | list/detail/CRUD | 报修工单 |
| `elevator` | CRUD + `register` | 电梯 |
| `firefighting` | CRUD + `register` | 消防 |
| `transformer` | CRUD + `register` | 变压器 |
| `hygieneCheck` | CRUD | 卫生 |
| `factoryMaint` | CRUD | 厂房维保 |
| `register/context` | GET | 公开登记上下文 |

---

## 13. 人事 HRM

| 资源 | 路径前缀 | 用途 |
| --- | --- | --- |
| 员工 | `/api/hrm/employee/*` | 档案与账号 |
| 考勤 | `/api/hrm/attendance/*` | 打卡/统计/设备 |
| 请假 | `/api/hrm/leaveapplication/*` | 请假流 |
| 轨迹 | `/api/hrm/trajectory/*` | 轨迹与导出 |
| 定位记录 | `/api/localization/*` | 定位台账 |

---

## 14. 智能表计与支付集成

| 接口 | 路径 | 用途 | 模块 |
| --- | --- | --- | --- |
| 表品牌 | `/api/smart-meter/brand/*` | 品牌字典 | 表计 |
| 合众水电 | `/api/hezhong/waterinfo/*`、`meterinfo/*` | 第三方抄表 | 表计 |
| 亿玛 | `/api/ymsino/*` | 原始数据 | 表计 |
| 微信支付 | `/api/wechat/pay/*` | 支付/退款/回调 | 支付 |
| 支付宝配置 | `/api/alipay/pay/app/config` | App 支付 | 支付 |
| 企微回调 | `/api/wework/callback` 等 | CRM 事件 | 集成 |

---

## 15. 报销 / 通知 / 看板 / AI

| 模块 | 路径 | 用途 |
| --- | --- | --- |
| 报销 | `/api/reimbursement/*` | 申请审核统计 |
| 通知 | `/api/notices/list` | 公告列表 |
| 看板 | `/api/dashboard/*`、`/api/analytics/*` | 经营指标 |
| 智能客服 | `/api/smart-service/chat` | RAG 对话 |
| 智谱 | `/api/chat/zhipu` | 通用对话 |
| LLM 工具 | `/api/llm/*` | 账单/图片分析 |
| Agent | `/api/agent/*` | skills/tasks/chat |
| 图片 | `/api/image/*` | 上传与访问 |
| 短信 | `/api/sms/send*` | 业务短信 |
| 状态 | `/api/status` | 健康探活 |
| Onboarding | `/api/onboarding/status` | 引导状态 |

---

## 16. 组织开通 / 内部接口

| 接口 | 路径 | 用途 | 备注 |
| --- | --- | --- | --- |
| 创建组织 | POST `/api/organization/create` | SaaS 开户 | 中心库 |
| 邀请 | `/api/organization/invitation/*` | 成员邀请 | |
| 开通状态 | GET `/api/organization/provisioning/status` | 进度 | |
| 失败重试 | POST `.../requeue-failed-manual` | 运维 | |
| Outbox 入队 | POST `/api/internal/outbox/events` | 内部 | Internal Token |
| Rabbit 任务 | POST `/api/internal/rabbit/*` | 内部 | Internal Token |
| 基础设施健康 | GET `/api/internal/health/infrastructure` | 运维 | |

---

## 17. API 设计问题（逆向结论）

1. **数量大且粒度不均**：招商雷达单模块接口密度过高。  
2. **兼容双路径**：`/park` 与 `/system/park`、部分 utils 兼容桩。  
3. **动词型路径与资源型混用**：如 `convert-to-tenant`、`collection-sms/send`。  
4. **返回 Map 为主**：缺稳定 OpenAPI schema。  
5. **写操作副作用隐式**：账单收款联动财务/核验，调用方难感知。  
6. **公开接口**（访客登记、register）与鉴权接口同控制器，安全边界靠方法级处理。

---

## 18. 对 Python 新 API 的方向

| 方向 | 建议 |
| --- | --- |
| 风格 | RESTful 资源 + 明确 RPC 动作（`/actions/*`） |
| 版本 | `/api/v1` |
| 文档 | OpenAPI 强制生成 |
| 聚合 | BFF 可按 PC/App/小程序裁剪 DTO |
| 事件 | 写操作返回资源状态，异步结果查 job |
| 权限 | 统一 scope：`park_id` + permission code |

---

## 附录：模块接口数量粗估

| 模块 | 约略占比 |
| --- | --- |
| investment/radar | 最高（约 1/4+） |
| bill + import + ai | 高 |
| hrm + maintenance + access | 中高 |
| system + auth + rental | 中 |
| 其它集成/内部 | 中低 |

详细逐条清单见：`_api-raw.tsv`。
