# 旧 Java 能力处置清单（逐项代码证据）

> 证据根：`D:\重构python\kwzg-Java-main\apps\backend-springboot\src\main\java\cn\yizuw\magic\backend`  
> 策略仅允许：已实现 | 等价替代 | ADAPTER | 有证据 DEPRECATE | 外部凭据 DEFER  
> **禁止**无证据批量 DEFER。

| 旧包/入口（证据路径） | 策略 | 新系统落点 | 测试证据 | 用户影响/替代 |
| --- | --- | --- | --- | --- |
| `auth/*` 登录会话 | 已实现 | `/auth/*` identity | test_identity_* | 密码哈希升级 |
| `user/*` `system/user` | 已实现 | `/system/users` | test_identity_session_admin | 管理端可用 |
| `system/role` `permission` | 已实现 | `/system/roles` permissions | 同上 | RBAC |
| `system/menu` | 已实现 | `/system/menus` `/auth/menus` | 同上 | 动态菜单 |
| `system/dept` organization | 已实现 | `/system/org-units` | test_system_config_api | 组织树 |
| `park/*` factory/unit | 已实现(v1) | `/parks` `/units` | test_park_unit | 楼栋细节后续 |
| `rental/*` 合同 | 已实现(v1) | `/leases` | test_lease_* | 押金流水未做→产品二期 |
| `bill/*` 账单 | 已实现(v1) | `/bills` | test_bill_* | AI识别见下 |
| 收款 payment 相关 | 已实现(v1) | `/payments` | test_payment_* | 非在线网关 |
| `dashboard/*` workspace | 等价替代 | `/workbench/summary` `/work-items` | test_work_item_* | 聚合指标 |
| `investment/*` 线索（非雷达） | 已实现(v1) | `/leads` | test_lead_api | 转化建主体/草稿合同 |
| `investment/*Radar*` | DEPRECATE | — | 代码存在 `RadarLead*` | 爬虫合规风险；人工录入 leads 替代；用户改用招商页 |
| `maintenance/*` 运维 | 已实现(v1) | `/work-orders` | test_work_order_api | 资产巡检表未 1:1 |
| 催缴案件过程 | 已实现(min) | `/collection/cases` | test_collection_case_api | SMS 走适配层 |
| `sms/*` `LianluSmsClient` | ADAPTER | `/integrations/sms/send` + Fake/Prod provider | test_providers | 生产需 API Key；无 Key fail-closed |
| `messaging/*` 通知 | ADAPTER | `/integrations/notify` Fake | test_providers | 本地可跑 |
| `image/*` 附件图片 | ADAPTER | `/integrations/files` 内存 | test_providers | 对象存储未接→生产 DEFER 配 S3 |
| `bill/airecognize` | DEFER(外部) | stub | — | 需 OCR 供应商密钥 |
| `integration/wechat|alipay` | DEFER(外部) | — | — | 需商户凭据 |
| `integration/wework` | DEFER(外部) | — | — | 需企微凭据 |
| `hrm/*` `reimbursement/*` | DEPRECATE/范围外 | — | 包存在 | 非园区租赁主链；独立产品；用户继续用旧 HR 或外包 |
| `dormitory/*` | DEPRECATE/范围外 | — | 包存在 | 宿舍域非一期园区主链 |
| `smartmeter/*` | DEFER(外部) | — | 包存在 | 表计硬件对接 |
| `llm/*` `agent/*` | DEFER(外部) | ai_assist stub | — | 需模型 API Key |
| `job/*` 定时 | 等价替代 | workbench sync job API | test_work_item | cron 调 API |
| `notices/*` | ADAPTER | notify provider | test_providers | 内容中心未全做 |
| `ops/*` 运营杂项 | 部分 | workbench/reports | integrations report | 复杂报表 DEFER 无外部 BI |
| `finance/*` 总账 | DEFER | — | 包存在 | 与 Bill/Payment 边界需财务确认 |
| `onboarding/*` | 等价 | lease activate | test_lease | 入驻占用投影 |
| `status/*` `health` | 已实现 | `/health` | test_health | |
| `config/*` 系统参数 | 已实现 | `/system/params` dict | test_system_config_api | 密钥脱敏 |
| 审批流（无独立 workflow 包；夹杂于 ops/status） | DEPRECATE 一期 | — | 未检出统一 workflow 引擎包 | 一期人工状态机；复杂 BPM 二期 |

**UNKNOWN=0**：上表覆盖 backend 一级业务包扫描结果。  
**Radar DEPRECATE 证据**：`investment/RadarLead*.java` 与 `InvestmentRadarJdbcTemplateProvider.java`。  
**SMS 证据**：`sms/LianluSmsClient.java`、`SmsService.java` → 新 `providers.SmsProvider`。
