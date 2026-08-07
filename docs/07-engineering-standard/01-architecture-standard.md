# 01 架构分层规范（Architecture Standard）

> 项目：`kwzy-python`  
> 状态：**正式冻结**  
> 适用范围：自 Phase06 起全部后端模块（含后续 Party / Lease / Bill / Payment）  
> 依据：DDD 模块化单体 + 架构评审 ADR-006

---

## 1. 目标

1. 保证代码长期可维护、可测试、可按限界上下文演进。  
2. 防止 Router/Service 腐化成「上帝类」与旧 Java 迁移式 Jdbc 堆叠。  
3. 为多租户（`tenant_id`）与园区权限（`park_id`）提供统一落点。  

---

## 2. 四层定义与职责

每个业务模块目录（推荐）结构：

```text
app/modules/<context>/
  interface/          # 接口层
  application/        # 应用层
  domain/             # 领域层
  infrastructure/     # 基础设施层
```

共享内核：

```text
app/core/                    # 配置、安全、全局异常类型（非业务）
app/shared/                  # TenantContext、统一响应、公共依赖
app/infrastructure/database/ # 全局 Base、Session、Repository 基类、ORM models 包
```

### 2.1 interface（接口层）

**职责：**

- 定义 HTTP 路由（FastAPI Router）
- 定义请求/响应 Schema（Pydantic）
- 参数校验、鉴权依赖注入（`get_tenant_context`）
- 将 HTTP 语义转换为 Application 调用
- 将结果封装为统一 envelope：`{code, message, data}`

**允许：**

- 依赖 `application` 服务
- 依赖 `shared` / `core` 的依赖注入与响应工具

**禁止：**

- 直接 `Session` / `engine` 查询
- 直接 `import` ORM Model 并 `session.add`
- 编写业务规则、状态机、计费公式
- 调用其他模块的 `infrastructure` 仓储

### 2.2 application（应用层）

**职责：**

- 用例编排（创建园区、激活合同、出账、收款登记等）
- 事务边界（`commit` / `rollback` 的归属层）
- 权限与数据范围的**应用级**校验协调（调用仓储/上下文）
- DTO ↔ 领域对象/命令的转换（若有 domain entity）
- 发布领域事件 / 写入 outbox（未来）

**允许：**

- 依赖 `domain`（规则、状态机、领域服务接口）
- 依赖本模块 `infrastructure` 的 Repository **接口或实现**（阶段约定：可直接依赖具体 Repository 类，但禁止跨模块）
- 依赖 `TenantContext`

**禁止：**

- 直接拼接 SQL / 裸 `session.execute` 写业务（应进 Repository）
- 依赖 FastAPI `Request`/`Response` 类型
- 在 ORM Model 上堆业务方法当领域模型长期使用（见 §4）
- 调用其他模块 Service 时绕过公开 API 去改其表

### 2.3 domain（领域层）

**职责：**

- 业务不变量与状态机（如 Unit 状态迁移、Bill 状态、合同激活规则）
- 领域异常（`DomainException` 及子类）
- 纯函数/领域服务（无 IO）
- 值对象与枚举常量

**允许：**

- 纯 Python 标准库
- 本层内类型

**禁止：**

- `sqlalchemy` / `fastapi` / `httpx` / Redis 客户端
- 读配置中的密钥做外部调用
- 依赖 `Session`、Repository、Pydantic Request 模型

### 2.4 infrastructure（基础设施层）

**职责：**

- ORM Model 映射（SQLAlchemy）
- Repository 实现（含 `tenant_id` / `park_id` 过滤）
- 外部适配器：短信、对象存储、LLM、支付网关（未来）
- 与框架/库的技术细节

**允许：**

- SQLAlchemy、驱动、第三方 SDK
- 将 ORM 行映射为 application 需要的结构

**禁止：**

- HTTP 路由
- 业务流程编排（应上移 application）
- 在 Model 类中实现复杂业务规则（状态机应在 domain）

---

## 3. 允许的依赖方向（强制）

```text
interface
    ↓
application
    ↓
  domain
    ↑
infrastructure  ──(实现/映射)──▶ 可为 application 提供仓储
```

### 3.1 合法调用

| 从 | 到 | 是否允许 |
| --- | --- | --- |
| interface → application | ✅ |
| application → domain | ✅ |
| application → infrastructure(Repository) | ✅（本模块内） |
| infrastructure → domain（可选：映射辅助） | ⚠️ 仅限简单转换，禁止反向依赖 application |
| shared/core → 无业务模块 | ✅ |

### 3.2 非法调用（禁止）

| 调用 | 原因 |
| --- | --- |
| **Router 直接访问数据库** | 绕过用例与权限统一入口 |
| **Service 直接操作 Session 写复杂查询** | 仓储职责被掏空，tenant 过滤易漏 |
| **ORM Model 承载业务规则** | 领域与持久化耦合，难测难迁 |
| interface → infrastructure | 跳过 application |
| domain → infrastructure | 领域被技术绑架 |
| domain → interface | 倒置 |
| modules/A/infrastructure → modules/B/infrastructure 改表 | 破坏上下文边界 |

### 3.3 图示

```text
        ┌─────────────────────────────────────┐
        │            interface                │
        │  Router / Schema / Depends          │
        └─────────────────┬───────────────────┘
                          │ 仅调用 Service
                          ▼
        ┌─────────────────────────────────────┐
        │           application               │
        │  UseCase / 事务 / 编排              │
        └───────────┬─────────────┬───────────┘
                    │             │
         规则/状态机 │             │ 持久化
                    ▼             ▼
        ┌──────────────┐   ┌──────────────────┐
        │    domain    │   │ infrastructure   │
        │ 纯业务       │   │ ORM / Repo / IO  │
        └──────────────┘   └──────────────────┘
```

---

## 4. ORM Model 使用边界

| 允许 | 禁止 |
| --- | --- |
| 字段映射、关系、简单 `@property` 展示 | 计费、核销、状态迁移完整规则 |
| 默认值、列注释 | 发短信、写 outbox 副作用 |
| 与表 1:1 的数据形状 | 跨聚合事务逻辑 |

**约定：**  
Step1 中 Application 直接 `Park(...)` 构造 ORM 为务实债务；自 Party 起优先：

- domain 定义规则与命令结果  
- infrastructure 负责 ORM 创建/更新  

不得在 Model 上新增 `def issue_bill(self): ...` 一类业务方法。

---

## 5. 跨模块协作

| 方式 | 何时使用 |
| --- | --- |
| Application 调用**本模块** Repository | 默认 |
| Application 调用**他模块 Application Service**（公开方法） | 同步编排且边界清晰 |
| 领域事件 + Outbox | 跨上下文最终一致（BillIssued、PaymentReceived） |
| 禁止跨模块直接 Repository / 改表 | 永远 |

---

## 6. 多租户与园区权限落点

| 关注点 | 落点 |
| --- | --- |
| `tenant_id` 强制 | `TenantParkRepositoryBase` + Service 不信任入参 tenant |
| `park_id` 范围 | `TenantContext` + Repository `assert_park_in_scope` / `apply_park_scope` |
| 鉴权 | interface Depends |
| 超管动作 | `permissions` 含 `*`（仅动作，不授全园） |
| 超管全园 | 显式 `park_scope_mode=ALL`（`roles/users.all_parks`）；**空 park_ids ≠ 全园** |

---

## 7. 模块与目录命名

| 限界上下文 | 模块名（示例） |
| --- | --- |
| IdentityAccess | `identity` |
| ParkProperty | `park_property` |
| Lease | `lease`（未来） |
| Billing | `billing`（未来） |
| Collection | `collection`（未来） |

全局 ORM 可放 `app/infrastructure/database/models/`，但**仓储与用例必须按模块分包**。

---

## 8. 审查门禁（PR）

任一 PR 若出现下列情况，**必须打回**：

1. Router 内出现 `session.query` / `session.execute` 业务 SQL  
2. domain 文件 import sqlalchemy / fastapi  
3. 新增业务 API 无 Application Service  
4. 查询未走 Repository 基类导致可能漏 `tenant_id`  
5. 用 `park_ids=[]` 表示超级权限  

---

## 9. 冻结声明

本规范自发布日起生效。  
与旧 Java 代码风格冲突时，**以本规范为准**，禁止以「旧系统就是这样」为由跨层。
