# 01 旧系统项目结构分析

> 分析对象：`D:\重构python\kwzg-Java-main`  
> 产品域名：`www.yizuw.cn`（易租维 / 智能园区管理）  
> 仓库标识：`Zhang-HM-Stu/kwzg-Java`（基于 Vue Vben Admin 5.x 二次开发）  
> 分析性质：只读逆向，未修改任何旧系统文件

---

## 1. 项目名称与定位

| 项 | 说明 |
| --- | --- |
| 项目名称 | **易租维智慧园区管理系统**（代码名 `magic` / monorepo 名 `new-admin`） |
| 业务定位 | 面向产业园区/厂房租赁运营方的 SaaS 管理平台 |
| 核心能力 | 园区与房源、租户合同、账单收费、催缴、招商雷达、门禁访客、运维工单、HRM、财务、AI 制单 |
| 当前形态 | **前后端 monorepo**：Vue3 管理端 + Spring Boot 后端（从 Nitro/Node 后端迁移中） |
| 多端形态 | PC Web + Capacitor 打包 Android/iOS + 微信小程序壳（WebView/分享桥） |

**一句话**：这是一套「园区运营 SaaS + 招商获客 + 账单财务 + 物联表计 + AI 辅助」的综合业务系统，后端处于 **Node → Java 迁移收尾期**。

---

## 2. 技术栈总览

### 2.1 后端

| 技术 | 版本/证据 | 用途 |
| --- | --- | --- |
| Java | 17 | 运行时 |
| Spring Boot | 4.1.0 | WebMVC API 服务 |
| MyBatis-Plus | 3.5.16 | 已接入；迁移代码仍以 JdbcTemplate 为主 |
| Spring JDBC / HikariCP | 随 Boot | 中心库 + 动态租户库 |
| MySQL | 8.0 | 多库：`magic` / `magic_center` / `public_magic` / `spider` / 租户库 `customer_*` |
| Redis | 7 | 菜单/权限缓存、短信验证码、组织开通刷新 |
| Kafka | 可选 | Outbox 事件流（组织开通等） |
| RabbitMQ | 可选 | 通知、轻任务、延迟重试 |
| XXL-Job | 3.4.2 | 批处理、补偿、对账、导入任务 |
| JWT (jjwt) | 0.12.6 | Access/Refresh Token |
| BCrypt | spring-security-crypto | 密码哈希（未引入完整 Spring Security 链） |
| Apache POI | 5.5.1 | Excel 账单导入 / AI 识别解析 |
| ZXing | 3.5.3 | CRM 二维码 |
| 阿里云百炼 / 智谱 | 配置项 | 智能客服、账单 AI 识别与复核 |
| 合众 / 亿玛 | HTTP 集成 | 智能水电表 |
| 微信/支付宝 | HTTP 集成 | 支付、小程序、企业微信 CRM |

### 2.2 前端

| 技术 | 说明 |
| --- | --- |
| Vue 3 + TypeScript | 主应用（`playground`） |
| Vite | 构建 |
| Vben Admin 5.5.4 | 脚手架与组件体系 |
| pnpm + Turbo | monorepo 工作区 |
| Ant Design Vue / VXE Table | UI 与表格 |
| Capacitor 8 | 原生 App 壳（Android/iOS） |
| 微信小程序 | `playground/miniprogram`（H5 WebView + 分享桥） |

### 2.3 基础设施与部署

| 组件 | 说明 |
| --- | --- |
| Docker Compose | 生产：`deploy/yz_java_cicd_flow`；遗留：根目录 `docker-compose.yaml`（Node 栈） |
| Nginx | TLS 终止、静态资源、`/api` 反代 |
| MySQL + Redis | 核心依赖 |
| Kafka / RabbitMQ / XXL-Job | 生产可选，配置开关灰度 |

---

## 3. 整体目录结构

```text
kwzg-Java-main/
├── apps/
│   └── backend-springboot/          # Java 后端（主分析对象）
│       ├── pom.xml
│       ├── project-guide.md         # 后端学习文档（重要）
│       ├── config/                  # 本地配置样例
│       ├── data/                    # AI 识别/账单导入运行时数据
│       ├── scripts/                 # 菜单修复、CRM SQL 等
│       └── src/main/
│           ├── java/cn/yizuw/magic/backend/
│           └── resources/
│               ├── application.yml
│               ├── application-local.yml
│               ├── application-prod.yml
│               └── db/manual/       # 增量 DDL
├── playground/                      # 主前端应用（@vben/playground）
│   ├── src/
│   │   ├── api/                     # 前端 API 封装
│   │   ├── views/                   # 业务页面
│   │   ├── router/                  # 路由
│   │   ├── components/
│   │   ├── store/
│   │   └── layouts/
│   ├── android/ / ios/              # Capacitor 原生工程
│   └── miniprogram/                 # 微信小程序壳
├── packages/                        # Vben 共享包（UI/请求/布局等）
├── internal/                        # lint/vite/tsconfig 等工具配置
├── deploy/yz_java_cicd_flow/        # 当前 Java 生产部署包
├── docs/                            # 产品/AI 升级文档
├── magic.sql                        # 租户业务库 dump（约 30 张核心表）
├── docker-compose.yaml              # 遗留 Node 栈
├── nginx.conf
├── package.json                     # monorepo 根（name: new-admin）
└── pnpm-workspace.yaml
```

### 3.1 后端包结构（按业务域纵向分包）

路径：`cn.yizuw.magic.backend`

| 包 | 业务职责 |
| --- | --- |
| `auth` / `security` / `permission` | 登录、JWT、权限码 |
| `tenant` | 多租户上下文与动态数据源 |
| `system/*` | 用户/角色/菜单/部门/区域/反馈/版本 |
| `park` | 园区 |
| `factory` | 厂房/楼层/租赁管理 |
| `rental/tenant` | 租户合同、工资（salary 耦合在此） |
| `bill` / `billimport` | 总账单、收款、催缴、Excel/AI 导入 |
| `finance` / `rentverify` | 财务流水、收款核验 |
| `investment` | 招商登记 + 招商雷达（体量大） |
| `crm` | 销售渠道、企微客户绑定、扫码 |
| `access` | 门禁/车辆/访客/品牌 |
| `maintenance` | 电梯/消防/变压器/卫生/报修/厂房维保 |
| `hrm` | 员工/考勤/请假/轨迹 |
| `smartmeter` + `integration/*` | 智能表品牌与第三方表计 |
| `reimbursement` | 报销 |
| `dashboard` | 工作台/分析统计 |
| `messaging` / `job` | Outbox、Kafka/Rabbit、XXL-Job |
| `llm` / `agent` | 智能客服、Agent 工作台 |
| `organization` / `onboarding` | 企业开通、邀请、引导 |
| `dormitory` | 宿舍 |
| `notices` | 公告通知 |

**Java 源文件约 564 个**；**Controller 约 50+ 个**；**HTTP 接口约 482 个**。

### 3.2 前端业务视图结构

路径：`playground/src/views`（约 316 个 Vue 文件）

| 目录 | 业务 |
| --- | --- |
| `dashboard` | 分析看板、工作台 |
| `rental` | 园区管理、房源列表、租户、已入驻、工资 |
| `bill` | 账单制单/列表/AI/导入/收款确认 |
| `finance` | 财务流水、收款核验、利润表相关 |
| `investment` | 招商登记、雷达（部分在 app 子目录） |
| `crm` | CRM/二维码 |
| `access` | 门禁/车辆/访客 |
| `maintenance` | 运维维保全套 |
| `hrm` | 人事考勤 |
| `smart-meter` / `ymsino` | 智能表 / 亿玛原始数据 |
| `reimbursement` | 报销申请与审核 |
| `system` | 用户角色菜单部门园区区域 |
| `agent` / `tools` | Agent 与 AI 工具 |
| `_core` | 登录/关于/错误页 |

---

## 4. 模块结构（业务视角）

```text
┌─────────────────────────────────────────────────────────────┐
│                     前端 Playground (Vue3)                   │
│  PC Web / Capacitor App / 小程序 WebView                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP /api
┌───────────────────────────▼─────────────────────────────────┐
│              Spring Boot backend-springboot                  │
│  AuthFilter → TenantContext → Controller → Service → Repo    │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │                   │                   │
   magic_center        租户库 customer_*      public_magic / spider
   (账号/组织/Token)   (园区业务数据)         (公开/爬虫数据)
        │
   Redis / Kafka / RabbitMQ / XXL-Job / 第三方 IoT & 支付
```

### 4.1 多租户模型

1. **中心库 `magic_center`**：全局用户、customer、租户映射、refresh_token、组织开通任务、CRM 部分表、支付会员等。
2. **租户业务库**：默认样例 `magic`；生产按 `customer_{id}` 动态建库。
3. **公共库 `public_magic`**：跨租户公共数据。
4. **爬虫库 `spider`**：通知/雷达相关采集数据。
5. JWT payload 携带 `customerId` / `dbName`，`TenantDataSourceRegistry` 按需建连接池。

---

## 5. 启动方式

### 5.1 前端

```bash
# 仓库根目录
corepack enable
pnpm install
pnpm dev:play          # 或 pnpm -F @vben/playground run dev
```

### 5.2 后端

```bash
cd apps/backend-springboot
# 配置 CENTER_DATABASE_URL / DATABASE_URL / ACCESS_TOKEN_SECRET 等
mvn spring-boot:run
# 默认端口 8080，context-path: /api
```

关键环境变量（节选）：

- `CENTER_DATABASE_URL`（硬依赖）
- `DATABASE_URL` / `PUBLIC_DATABASE_URL` / `CUSTOMER_DATABASE_URL_TEMPLATE`
- `ACCESS_TOKEN_SECRET` / `REFRESH_TOKEN_SECRET`
- `REDIS_URL`
- 可选：`KAFKA_*`、`RABBITMQ_*`、`XXL_JOB_*`、短信、微信、合众、亿玛、百炼 Key

### 5.3 根脚本中的联调

`package.json` 中：

- `pnpm test` → `scripts/dev-java-local.mjs`（本地 Java 联调）
- `pnpm test:mysql-tunnel` → SSH 隧道连远端 MySQL

---

## 6. 环境依赖

| 类别 | 依赖 |
| --- | --- |
| 运行时 | JDK 17、Node 22+（前端）、pnpm |
| 数据 | MySQL 8、Redis 7 |
| 消息/任务（生产） | Kafka、RabbitMQ、XXL-Job Admin |
| 外部服务 | 联麓短信、微信/支付宝、企业微信、合众表计、亿玛表计、阿里云百炼 |
| 本地开发 | 可关闭 Kafka/Rabbit 强制依赖（`application-local.yml`） |

---

## 7. 部署方式

### 7.1 当前主路径（Java）

目录：`deploy/yz_java_cicd_flow`

1. 本机执行 `package-runtime.ps1` 产出 `backend.jar` + 前端静态资源  
2. 上传整目录到服务器（示例 `/opt/kwzg-java/yz_java_cicd_flow`）  
3. 配置 `.env`  
4. `docker compose -f docker-compose.prod.yml up -d --build`  
5. Nginx 证书：`www.yizuw.cn` / `yizuw.cn`  
6. 健康检查：`/api/status`

### 7.2 遗留路径（Node Nitro）

根目录 `docker-compose.yaml` 仍描述 Node + MySQL + Redis + Nginx 栈，注释明确 **仅作遗留维护，生产以 Java 部署为准**。

---

## 8. 数据库文件清单

| 文件 | 作用 |
| --- | --- |
| `magic.sql` | 租户业务库全量结构+数据 dump（核心约 30 表） |
| `deploy/.../mysql-init/01-create-databases.sql` | 创建 magic / magic_center / public_magic / spider |
| `apps/backend-springboot/src/main/resources/db/manual/*.sql` | 增量：outbox、通知、账单导入、AI 识别、工资字段、收款核验等 |
| `apps/backend-springboot/scripts/investment-crm-master.sql` | 招商 CRM 相关表 |
| `apps/backend-springboot/scripts/*.sql` | 菜单修复等运维脚本 |

---

## 9. 配置文件清单

| 文件 | 作用 |
| --- | --- |
| `application.yml` | 主配置：端口、多数据源、Redis、Kafka、Rabbit、JWT、短信、AI、表计 |
| `application-local.yml` | 本地：弱化 MQ 强依赖 |
| `application-prod.yml` | 生产：强化 MQ/Job |
| `config/application-local.properties` | 本地属性样例 |
| `.env.example` / `proxy.env.example` | 环境变量模板 |
| `deploy/yz_java_cicd_flow/.env.example` | 部署密钥模板 |
| `nginx.conf` / `deploy/.../nginx-*.conf` | 网关与站点配置 |

---

## 10. 第三方依赖（业务向）

| 依赖 | 业务用途 |
| --- | --- |
| 联麓短信 | 登录验证码、催缴短信 |
| 微信服务号/小程序/支付 | 登录桥接、CRM 邀请、支付退款 |
| 企业微信 | 客户联系回调、销售活码 |
| 支付宝 | App 支付配置 |
| 合众平台 | 水电表树与抄表数据 |
| 亿玛（ymsino） | 水电表原始数据 |
| 阿里云百炼（Qwen） | 智能客服 RAG、账单 AI 复核 |
| 智谱 | 对话能力（`/chat/zhipu`） |
| 代理池（招商雷达） | 公开商机爬取 |

---

## 11. 规模画像（逆向结论）

| 指标 | 量级 |
| --- | --- |
| 后端 Java 文件 | ~564 |
| HTTP API | ~482 |
| 前端 Vue 页面文件 | ~316 |
| 业务 Controller | ~50+ |
| 核心 dump 表 | ~30（+ 大量运行期增量/雷达/导入表） |
| 逻辑数据库 | ≥4（中心+样例租户+公共+爬虫，另加每客户独立库） |

---

## 12. 对 Python 新系统的结构启示

1. **保留「中心库 + 租户库」多租户思想**，但应用层用更清晰的 schema/connection 策略。  
2. **按园区运营领域拆包**，不要按 controller/service 技术分层堆砌。  
3. 账单/导入/招商雷达是复杂度峰值，需独立限界上下文。  
4. 前端已具备 PC/移动/小程序三端意识，Python 后端 API 应统一契约。  
5. 旧系统大量 Feature Toggle 与兼容逻辑是迁移痕迹，新系统应通过领域模型消解，而不是继续堆开关。

---

## 附录：与文档体系的对应

| 下一阶段文档 | 内容 |
| --- | --- |
| 02-backend-business-analysis.md | 按业务模块的后端分析 |
| 03-database-analysis.md | 库表与 ER |
| 04-frontend-page-analysis.md | 页面与接口映射 |
| 05-api-analysis.md | 全量 API 清单 |
| 06-business-process-analysis.md | 园区真实业务流程 |
| 07-system-problem-analysis.md | 问题诊断 |
| 08-python-rebuild-suggestion.md | Python 重构方向 |
