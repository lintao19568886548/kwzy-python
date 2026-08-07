# 03 数据库逆向分析

> 主要依据：`magic.sql`、`deploy/.../mysql-init/01-create-databases.sql`、`db/manual/*.sql`、Repository SQL 引用  
> 目标：理解业务表职责与关系，而非罗列全部字段类型

---

## 1. 数据库数量与职责

| 库名 | 职责 | 典型数据 |
| --- | --- | --- |
| **magic_center** | 中心库：全局身份与 SaaS 控制面 | 中心 user、customer、映射、refresh_token、组织开通、部分 CRM/支付 |
| **magic**（样例租户库） | 默认/演示租户业务库 | 园区、房源、租户、账单、运维… |
| **customer_{id}** | 生产租户隔离库（按客户动态创建） | 与 magic 同构的业务表 |
| **public_magic** | 公共/跨租户数据 | 公共配置、共享资源 |
| **spider** | 爬虫/通知源数据 | notices、公开采集相关 |
| **investment_crawl**（配置） | 招商雷达共享爬取库 | 雷达公开商机等 |
| **rag**（配置） | 智能客服向量/知识库 | 百炼 RAG |

**结论：逻辑库 ≥ 4，生产按租户水平扩展「一客户一库」。**

---

## 2. 数据表规模

| 来源 | 表数量量级 | 说明 |
| --- | --- | --- |
| `magic.sql` dump | **约 30 张** | 早期核心业务表 |
| manual 迁移脚本 | **+20 张** 量级 | outbox、通知、账单导入、AI 识别、核验任务等 |
| 招商雷达/CRM 运行表 | **+30 张** 量级 | 线索、爬虫、触达、限制名单等 |
| 中心库表 | **十余张** | customer、mapping、invitation、provisioning… |

**实际运行总表数远大于 dump 中 30 张**，属于「核心表精简 dump + 线上演进表」模式。

---

## 3. 核心业务表（按领域）

### 3.1 用户与权限

| 表 | 业务职责 |
| --- | --- |
| `user` | 租户内系统用户（姓名、用户名、密码、手机、首页路径） |
| `role` | 角色定义与启停 |
| `user_role` | 用户-角色多对多 |
| `role_menu` | 角色可见菜单 |
| `role_park` | **角色可访问园区**（数据权限关键） |
| `user_park` | 用户直接绑定园区（与角色园区并存） |
| `user_code` | 用户权限码/扩展码 |
| `menu` / `menu_meta` | 动态路由菜单及 Vben 元数据 |
| `user_tenant_mapping`（中心） | 中心用户 ↔ 租户客户映射 |
| `customer`（中心） | SaaS 客户/租户主体、状态 |
| `refresh_token`（中心） | 刷新令牌 |

**业务解释：**  
登录发生在中心库；进入系统后业务读写在租户库。权限 = 功能菜单/权限码 + 园区范围。

### 3.2 园区与空间资产

| 表 | 业务职责 |
| --- | --- |
| `park` | 园区主数据：名称、地址、面积、负责人、状态 |
| `factory` | 园区下厂房/楼栋 |
| `factory_floor` | 楼层可租单元：租金、总/已用面积、消防、电梯、承重 |
| `factory_floor_image` | 楼层图片 |
| `factory_elevator` | 电梯规格（后期补强） |
| `dormitory` / `dormitory_image` | 宿舍类房源 |
| `image` / `image_binding` | 通用图片与绑定 |

**业务解释：**  
空间层级：**园区 → 厂房 → 楼层**。楼层是主要「可租单元」；宿舍是平行产品线。

### 3.3 租户 / 合同 / 客户

| 表 | 业务职责 |
| --- | --- |
| `rental_tenant` | **在园企业/租户 + 合同信息合体**（名称、电话、合同起止、递增、地址、状态、园区） |
| `tenant_image` | 租户/合同附件图 |
| `investment` | 招商线索（未转正租户前） |
| `investment_tenant` | 命名误导：结构像财务流水，非租户主数据 |
| `investment_customer` / `investment_lead` 等 | 后期 CRM 化线索模型 |

**业务解释：**  
「客户」在系统中分裂为：招商线索、在租租户、CRM 绑定客户。`rental_tenant` 是收费与合同主轴。

### 3.4 账单 / 表计 / 收费

| 表 | 业务职责 |
| --- | --- |
| `amount_bill` | 月度/期次 **总账单**：水/电/租/管理/服务/税费合计、收款时间、项目名、租户 |
| `ele_bill` | 电费明细行：表名、上次/本次读数、倍率、单价、金额 |
| `water_bill` | 水费明细行，结构同电费 |
| `bill_import_*` | 导入批次/文件/工作表/候选账单/问题/模板/别名/审计 |
| `ai_bill_job*` / `ai_bill_item` | AI 识别任务与识别结果项 |
| `meter_brand` | 智能表品牌 |
| 合众/亿玛数据 | 多在外部 API，本地落库有限 |

**业务解释：**  
收费中心是 `amount_bill`。明细拆水电；租金等费用在头表字段。导入/AI 是两条「草稿 → 正式账单」管道。

### 3.5 财务与核验

| 表 | 业务职责 |
| --- | --- |
| `finance` | 收支流水台账（名称、分类、金额、收/支类型、时间、园区） |
| `rent_verify_task` | 收款核验任务（确认/异常） |
| `salary` | 工资单（已从简单表扩展大量薪资分项字段） |
| `salary_image` | 工资附件 |
| `reimbursement` | 报销单 |

**业务解释：**  
财务不是完整总账，而是运营流水。账单收款、工资、报销都会向流水靠拢。核验任务补「收款真实性」流程。

### 3.6 通行与安全

| 表 | 业务职责 |
| --- | --- |
| `access_visitor` | 访客预约/登记 |
| `access_car` | 车辆通行登记 |
| 门禁设备/品牌表 | 设备台账 |

### 3.7 运维资产巡检

| 表 | 业务职责 |
| --- | --- |
| `firefighting` | 消防检查记录 |
| `transformer` | 变压器巡检 |
| 电梯/卫生/报修/厂房维保表 | 对应巡检与工单 |

### 3.8 消息与基础设施

| 表 | 业务职责 |
| --- | --- |
| `event_outbox` / `event_consume_log` | 可靠消息 Outbox 与消费幂等 |
| `in_app_notification` | 站内通知 |
| `api_log` | API 日志 |
| `_prisma_migrations` | 历史 Prisma 迁移痕迹（旧 Node 栈） |

### 3.9 招商雷达（扩展）

| 表族 | 业务职责 |
| --- | --- |
| `crawler_*` | 爬虫源、任务、明细、日志 |
| `signal_event` / `lead_evidence` | 商机信号与证据 |
| `enterprise_profile` / `enterprise_tag` | 企业画像与标签 |
| `investment_public_opportunity` | 公开商机 |
| `investment_outreach_*` | 触达模板与任务 |
| `contact_restriction*` | 合规联系限制 |
| `property_match_result` | 线索-房源匹配 |
| `lead_score_*` | 评分规则与拆解 |

---

## 4. 业务 ER 关系说明

### 4.1 核心运营主链

```text
customer (中心)
   │ 1
   │ 开通
   ▼
tenant DB
   │
   ├── park 1──* factory 1──* factory_floor
   │     │
   │     ├── * rental_tenant (在租合同/企业)
   │     │         │
   │     │         ├── * amount_bill
   │     │         │         ├── * ele_bill
   │     │         │         └── * water_bill
   │     │         └── * salary (历史耦合)
   │     │
   │     ├── * investment (线索，可 convert → rental_tenant)
   │     ├── * access_visitor / access_car
   │     ├── * finance
   │     └── * maintenance assets (firefighting/transformer/...)
   │
   ├── user *──* role *──* menu
   │            role *──* park   ← 数据权限
   └── user *──* park            ← 用户直接授权
```

### 4.2 身份与多租户

```text
center.user ──* user_tenant_mapping *── center.customer
     │                                      │
     │ 同步/映射                              │ db_name / customer_id
     ▼                                      ▼
tenant.user                          TenantDataSourceRegistry
     │
     └── user_role → role → role_menu / role_park
```

### 4.3 账单生成与入账

```text
rental_tenant
     │
     ▼
amount_bill (头：合计费用 + 账期/项目 + receipt_time)
     ├── ele_bill (电表明细)
     └── water_bill (水表明细)
            │
            ├─(收款)→ receipt_time 更新 + rent_verify_task
            └─(同步)→ finance 流水

并行入口：
  Excel → bill_import_batch → candidate → publish → amount_bill
  AI 工作簿 → ai_bill_job → item → commit → amount_bill
```

### 4.4 招商转化

```text
公开商机 / 爬虫信号
        │
        ▼
 external_lead / signal_event → 评分 → 分配销售
        │
        ▼
 investment / investment_lead (跟进/拜访/SOP)
        │ convert
        ▼
 rental_tenant (入驻合同)
        │
        ▼
 amount_bill (开始收费)
```

### 4.5 组织开通

```text
organization.create
   → tenant_provisioning_job
   → 创建 customer + 租户库 + 初始 user/role
   → event_outbox (OrganizationProvisioningCompleted)
   → Kafka/Rabbit → 站内通知 / Redis 缓存刷新
```

---

## 5. 重点领域表解读（不只列字段）

### 5.1 用户权限

- **负责**：谁能登录、能看哪些菜单、能操作哪些园区数据。  
- **关键关系**：`role_park` 与 `user_park` 双通道授权，Service 层 `ParkScopeService` 汇总。  
- **问题**：双通道易导致「角色有园区但用户无 / 反之」理解成本；中心用户与租户用户 ID 不一定同一套。

### 5.2 企业（SaaS 客户）

- **负责**：付费组织、租户库标识、开通状态。  
- **表**：中心 `customer` + `organization*`。  
- **问题**：产品语义上「企业客户」与园区内「入驻企业租户」同词不同物，需在新模型中用不同实体名区分。

### 5.3 园区

- **负责**：空间与数据隔离边界、运营统计维度。  
- **字段业务**：`area` 园区总面积、`manager/contact` 运营联系人、`status` 启停。  
- **问题**：缺少与行政区域、产权主体、多经纬度地图字段的系统化设计（区域表独立在 system/region）。

### 5.4 房源

- **负责**：可租产品库存。  
- **`factory_floor`**：真正的库存单元；`used_area` 表达占用。  
- **问题**：占用与合同缺少强制一致性；状态 `status` 为字符串自由值；宿舍模型不统一。

### 5.5 合同

- **负责**：`rental_tenant` 同时存租户主体与合同条款。  
- **关键业务字段**：`contract_start/end`、`increase_date/rate`、`status`。  
- **问题**：无合同编号、无版本历史、无多房源组合合同、无押金/保证金实体。

### 5.6 招商

- **负责**：漏斗前段获客与跟进。  
- **传统表 `investment`**：登记式 CRM。  
- **雷达表族**：营销自动化与公域获客。  
- **问题**：双模型并存；`investment_tenant` 命名与职责严重不符（像财务）。

### 5.7 客户

- 在园：**rental_tenant**  
- 意向：**investment / lead**  
- 企微：**crm_customer_owner_binding**  
- **问题：客户主数据不统一**。

### 5.8 账单

- **负责**：应收汇总与收款状态（以 `receipt_time` 是否为空表达是否收款）。  
- **问题**：  
  - 部分收款、坏账、减免缺少模型  
  - 头表塞多种费用，扩展新费项要加列  
  - `tenant_name` 冗余  
  - 账期字段弱（多靠 create_time/project_name 约定）

### 5.9 财务

- **负责**：运营向收支流水与利润分析输入。  
- **问题**：无会计科目、无凭证、无核销关系表；与账单是弱关联（名称匹配/同步服务）。

### 5.10 设备 / 工单

- 巡检表以「记录行」为主，缺资产台账主数据与工单标准状态机。  
- `factory_id` 默认值 20 等硬编码痕迹说明历史数据质量风险。

---

## 6. 字段与模型设计问题汇总

| 问题 | 表现 | 影响 |
| --- | --- | --- |
| 实体混合 | 租户+合同同表 | 续租/换房/多合同难建模 |
| 命名误导 | `investment_tenant` | 维护误用 |
| 冗余字段 | bill.tenant_name | 改名不一致 |
| 状态简陋 | 多处 varchar/int 无枚举约束 | 流程漂移 |
| 软删不统一 | 有的 is_deleted，有的物理删 | 审计困难 |
| 金额精度 | 多数 decimal(10,2)，电价 decimal(10,8) | 尚可，大客户金额可能不够 |
| 缺审计列 | 谁创建/修改不完整 | 追责弱 |
| 缺外键 | 逻辑关联靠应用层 | 脏数据风险 |
| schema 漂移 | 代码探测 information_schema | 迁移期必要，长期债 |
| 一客户一库 | 强隔离 | 跨园分析与运维成本高 |
| 工资宽表爆炸 | salary 大量 ALTER 加列 | 说明需求驱动缺抽象 |

---

## 7. 推荐的「核心业务表」优先级（给新系统）

**P0（没有就不是园区租赁系统）：**  
园区、可租单元、租户主体、合同、账单头、账单行、收款、用户、角色、园区授权

**P1（运营闭环）：**  
财务流水/核销、催缴记录、招商线索、访客车辆、报修工单

**P2（增强）：**  
雷达获客、智能表计同步、AI 导入流水线、HRM 薪资、会员支付

---

## 8. 数据迁移注意点

1. `magic.sql` 不能代表生产全量 schema，必须叠加 manual 脚本与线上实际库结构。  
2. 中心库与租户库都要迁，映射关系是生命线。  
3. 账单历史与财务流水要对账后再迁，不能只迁结构。  
4. 招商雷达表可分期迁移，避免阻塞核心租赁上线。  
5. Prisma 迁移表仅历史痕迹，Python 应用应使用新的 migration 工具链（Alembic 等）。

---

## 9. 小结

旧库是 **「多库多租户 + 园区过滤」** 的运营型模型：强在租赁收费主链，弱在主数据统一与财务严谨性。  
新系统数据库应 **围绕合同与账单重新规范化**，同时保留多租户隔离与园区数据权限这两个产品基因。
