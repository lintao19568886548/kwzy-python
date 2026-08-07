# API 设计架构评审（API Review）

> 评审对象：`docs/04-api/openapi-v1-core.yaml`  
> 对照：领域主链、旧系统 ~482 接口、三端 + AI Agent 诉求

---

## 1. 总体评价

OpenAPI v1 **覆盖主链骨架**，资源命名整体清晰，动作型接口（activate/issue/void/convert）与状态机匹配。  
作为「全业务迁移 API」**不完整**；作为「一期核心交易 API」**基本合格**，但仍有 REST 一致性与多端/ Agent 友好性问题。

**API 综合评分：73 / 100**

---

## 2. 核心业务覆盖检查

| 域 | OpenAPI 覆盖 | 评级 | 缺口 |
| --- | --- | --- | --- |
| Auth | login/sms/refresh/me | 良 | 改密、登出、权限码列表、页面二次验证 |
| Parks | CRUD 列表/详情/补丁 | 良 | 删除/停用、园区统计 |
| Buildings | 列表/创建（挂 park 下） | 中 | 更新/删除、详情 |
| Units | 列表/创建/详情/补丁 | 良 | 批量状态、空置筛选文档化不足 |
| Parties | 列表/创建 | **中** | 详情/更新/删除/停用 |
| Leases | 列表/创建/详情/activate/terminate | 良 | 续租、更新草稿、附件 |
| Bills | 列表/创建/详情/改/issue/void/duplicate | 良 | 导出、模板继承 latest-template |
| Payments | 列表/创建 | 良 | 冲正、详情 |
| Collection | cases 列表、短信 preview/send | 中 | case 详情/动作记录、建案 API |
| Leads | 列表/创建/convert | 中 | 跟进 activity、状态流转 |
| AI | recognize jobs | 中 | commit 与 Draft 对齐文档弱 |
| Finance ledger | **OpenAPI 无** | **缺** | 仅代码 stub `/ledger` |
| Analytics | **OpenAPI 无** | **缺** | 仅代码 stub |
| 用户角色菜单 | **无** | **缺** | 管理端不可配置 |
| 通知消息 | **无** | **缺** | — |

### 2.1 重点资源结论

| API | 是否覆盖核心 | 是否可进入一期开发 |
| --- | --- | --- |
| Park API | 是 | 是 |
| Unit API | 是 | 是 |
| Party API | 部分 | 需补 GET/PATCH |
| Lease API | 是 | 是（补续租可选） |
| Bill API | 是 | 是 |
| Payment API | 是 | 是 |

---

## 3. REST 规范检查

### 3.1 符合项

- 前缀 `/api/v1`  
- 复数资源路径  
- GET 列表/详情，POST 创建，PATCH 更新  
- 业务动作用 `POST /resource/{id}/action`（activate/issue/void/convert）— **可接受的 pragmatic REST**  
- Bearer JWT  
- 分页 page/page_size  

### 3.2 问题项

| # | 问题 | 建议 |
| --- | --- | --- |
| A1 | 成功响应未统一 envelope（OpenAPI 直接 schema vs 代码 `code/message/data`） | **统一一种**写入 OpenAPI |
| A2 | 错误模型未定义 | 补 `ErrorResponse` |
| A3 | `POST /bills/duplicate-check` 放在 `/{billId}` 路由旁可能冲突 | 保持静态路径优先（实现注意顺序） |
| A4 | Building 更新/删除缺失 | 补齐 |
| A5 | Party 只有 list/create | 补 `/{id}` |
| A6 | 删除语义不清（硬删/软删） | 统一 `DELETE` 或 `status=INACTIVE` |
| A7 | 缺 `Idempotency-Key` 说明（支付/出账） | 组件级参数已可复用，写到写接口 |
| A8 | 列表筛选参数不完整（排序、updated_after） | Agent/同步需要 |
| A9 | 无 HATEOAS（不强制） | 可不做 |
| A10 | 驼峰 parkId vs 蛇形 park_id 混用 | **全 API 统一 snake_case** |

**A10 为必须修订：** path 参数 `parkId` 与 body `park_id` 不一致，前端/小程序/Agent 易错。

---

## 4. 三端适配性

### 4.1 PC 管理端

| 需求 | 现状 |
| --- | --- |
| 高密度表格查询 | 分页+筛选基本够，缺导出 |
| 批量操作 | 基本无 |
| 权限菜单 | API 无 |
| 复杂制单 | Bill create 够用 |

**结论：PC 主链可用；管理配置类 API 不足。**

### 4.2 微信小程序

| 需求 | 现状 |
| --- | --- |
| 轻登录（手机号） | 有 sms login 方向 |
| 租户自助查账单/缴费 | **无 tenant-portal 角色模型与 API 裁剪** |
| 访客登记 | 无 |
| 包体字段精简 | 未定义 view DTO |

**结论：未设计「租户端/访客端」audience；当前 API 是运营后台向。**  
小程序若一期只做运营移动办工，可复用；若做入驻企业端，**必须另开 BFF 或 scope。**

### 4.3 APP（管家/招商）

| 需求 | 现状 |
| --- | --- |
| 待办工作台 | OpenAPI 无 analytics |
| 外勤催缴 | 短信 API 有，案件弱 |
| 离线/弱网 | 无同步游标 |
| 推送 | 无 |

**结论：APP 可先复用主 API；工作台与推送需补。**

### 4.4 AI Agent 调用

| 需求 | 现状 |
| --- | --- |
| 稳定 operationId | **有**（很好） |
| 强 schema | 中等 |
| 工具调用幂等 | 弱 |
| 可读错误码 | 弱 |
| 列表增量同步 | 弱 |
| 危险操作二次确认 | 催缴有 proof，删改无 |

**结论：具备 Agent 化基础（operationId）；需错误码枚举 + 幂等 + 统一 envelope 才能安全生产接入。**

---

## 5. 与旧系统接口差距（架构视角）

旧系统约 482 接口；新 OpenAPI 约 30+ 路径。  
**这是正确的减法**，但需官方「范围声明」避免业务方期望 100% 对等。

| 旧能力簇 | 新 API | 策略 |
| --- | --- | --- |
| 账单导入流水线 | 无（仅 AI job） | 二期或后续 |
| 招商雷达 | 无 | 二期独立 |
| 门禁/运维/HRM | 无 | 二期 |
| 支付回调微信 | 无 | 二期 |
| 组织开通 | 极简 tenant | 二期 |

---

## 6. 安全与权限在 API 层的缺失

| 项 | 状态 |
| --- | --- |
| 401/403 schema | 未描述 |
| 权限码与 operation 映射表 | 无 |
| 园区 scope 失败码 | 无 |
| 公开接口（访客）标记 | 无 |
| 速率限制 | 无 |
| 文件上传大小/类型 | AI multipart 未约束 |

**必须补：权限矩阵表（operationId → permission code）。**

---

## 7. API 必须修订清单

### P0

1. **统一 snake_case**（path/query/body）  
2. **统一响应 envelope** 与 ErrorResponse 写入 OpenAPI  
3. **Party GET/PATCH**  
4. **Building PATCH/DELETE**  
5. **写操作 Idempotency-Key 规范**（至少 payments、bills/issue）  
6. **范围声明文档**：v1 覆盖边界 / 明确不做清单  

### P1

7. Auth：logout、codes、page-access  
8. Collection case 详情与 action  
9. Ledger / workbench 入 OpenAPI  
10. 导出与 latest-template  
11. 权限码映射表  

### P2

12. 租户端 BFF  
13. Webhook/支付回调  
14. 批量接口  

---

## 8. API 评审结论

| 维度 | 分数 |
| --- | --- |
| 主链覆盖 | 8/10 |
| REST 一致性 | 6/10 |
| 多端友好 | 5/10 |
| Agent 友好 | 6/10 |
| 安全可描述性 | 5/10 |
| **综合** | **73/100** |

**结论：主链 API 可支撑阶段 06 开发，但 P0 契约一致性问题必须先修订 OpenAPI，否则实现与文档会再次分叉。**
