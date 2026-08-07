# 04 异常处理规范（Exception Standard）

> 状态：**正式冻结**  
> 目标：统一错误语义、API 返回形态、分层抛出纪律

---

## 1. 异常体系总览

```text
AppError / 业务 API 异常（现有）
        ▲
        │  映射
┌───────┴────────┬──────────────────┬────────────────────┐
│ DomainException│ ApplicationException│ InfrastructureException│
└────────────────┴──────────────────┴────────────────────┘
```

| 类型 | 层 | 含义 |
| --- | --- | --- |
| **DomainException** | domain | 业务规则/不变量被违反（状态不可迁、金额为负等） |
| **ApplicationException** | application | 用例失败（资源不存在、权限不足、校验失败、冲突） |
| **InfrastructureException** | infrastructure | 技术失败（DB、Redis、HTTP 下游、磁盘） |

现有 `AppError` 可作为 **对外统一承载**（含 `code` / `status_code` / `message`），由 application 捕获 domain/infra 后转换。

---

## 2. 类型职责与示例

### 2.1 DomainException

**何时抛：**

- 状态机非法迁移  
- 不变量破坏（核销超额、占用冲突）  
- 领域前置条件不满足  

**示例 code：**

| code | 说明 |
| --- | --- |
| `DOMAIN_STATE_INVALID` | 状态不可迁移 |
| `DOMAIN_INVARIANT_BROKEN` | 不变量失败 |
| `DOMAIN_AMOUNT_INVALID` | 金额/精度非法 |

**禁止：** Domain 抛 HTTP 状态码细节；Domain 不依赖 FastAPI。

### 2.2 ApplicationException

**何时抛：**

- 资源不存在  
- 租户/园区权限拒绝  
- 入参业务校验（非 Pydantic 语法层）  
- 幂等冲突、重复创建  

**示例 code：**

| code | HTTP 建议 | 说明 |
| --- | --- | --- |
| `VALIDATION_ERROR` | 400 | 业务校验 |
| `UNAUTHORIZED` | 401 | 未登录 |
| `PARK_SCOPE_DENIED` | 403 | 无园区权限 |
| `TENANT_MISMATCH` | 403 | 租户不匹配 |
| `NOT_FOUND` / `PARK_NOT_FOUND` / `UNIT_NOT_FOUND` | 404 | 不存在或不可见 |
| `CONFLICT` / `UNIT_CODE_DUP` | 409 | 冲突 |
| `AUTH_BAD_PASSWORD` | 403 | 登录失败 |

**说明：** 当前代码中的 `AppError` 即 Application 层对外异常的实现形态，后续可别名或继承理顺，但 **字段契约不变**。

### 2.3 InfrastructureException

**何时抛：**

- 数据库连接失败、死锁重试耗尽  
- 外部短信/支付/OSS 超时  
- 序列化/磁盘错误  

**示例 code：**

| code | HTTP 建议 | 说明 |
| --- | --- | --- |
| `DB_ERROR` | 500 | 数据库 |
| `DEPENDENCY_ERROR` | 502/503 | 下游依赖 |
| `STORAGE_ERROR` | 500 | 文件存储 |

Infrastructure 异常 **不应** 把内部 SQL 原文直接返回给客户端。

---

## 3. 分层抛出纪律

| 层 | 可抛 | 应捕获 |
| --- | --- | --- |
| domain | DomainException | — |
| infrastructure | InfrastructureException；可选包装原生异常 | 驱动原始异常 |
| application | ApplicationException / AppError；转换 Domain/Infra | Domain + Infra |
| interface | 尽量不抛业务异常；转 Service | ApplicationException → HTTP |

```text
domain raises DomainException
        → application catches → AppError(code, message, status)
                → interface handler → JSON envelope
```

---

## 4. API 统一返回

### 4.1 成功

```json
{
  "code": "OK",
  "message": "success",
  "data": { }
}
```

### 4.2 失败（业务/应用）

HTTP 状态码按上表；Body **必须** 为：

```json
{
  "code": "PARK_NOT_FOUND",
  "message": "园区不存在",
  "data": null
}
```

可选扩展（不破坏现有客户端时）：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "名称必填",
  "data": {
    "fields": { "name": "required" }
  }
}
```

### 4.3 未捕获异常

- 返回 500  
- body：`code=INTERNAL_ERROR`，message 不暴露堆栈  
- 服务端 ERROR 日志带 `request_id` / `tenant_id`

### 4.4 FastAPI 422

应逐步统一为 envelope（工程实现阶段加 exception handler）。  
规范要求：**最终形态与业务错误一致**，不得长期返回默认 `detail: []` 给外部正式客户端。

---

## 5. code 命名规范

| 规则 |
| --- |
| `UPPER_SNAKE_CASE` |
| 优先 `资源_动作_结果` 或 `领域语义`：`PARK_NOT_FOUND`、`UNIT_STATUS_INVALID` |
| 稳定：一旦对前端公开，不得随意改名（可新增） |
| 禁止中文 code、禁止随便 `ERROR1` |

---

## 6. 权限与「不存在」

为防枚举：

| 场景 | 推荐 |
| --- | --- |
| 跨租户访问资源 | 统一 `NOT_FOUND`（404），不暴露「在别人租户」 |
| 无园区权限 | `PARK_SCOPE_DENIED`（403）或对 get 场景 404（模块内统一，推荐 get→404） |
| 登录失败 | 统一文案，不区分用户是否存在（已有实践） |

---

## 7. 与日志配合

| 异常类型 | 日志级别 |
| --- | --- |
| 预期业务失败（校验、404、403） | WARNING |
| Domain 不变量（理论上不应被正常 UI 触发） | WARNING 或 ERROR |
| Infrastructure | ERROR |
| 未知 | ERROR + stack |

日志必须带：`request_id, user_id, tenant_id, park_id, module, action, code`。

---

## 8. 审查门禁

1. 新模块随意 `raise Exception("xxx")` 无 code → 打回  
2. 把 DB 异常原文返回前端 → 打回  
3. Domain 依赖 HTTPException → 打回  
4. 成功与失败 envelope 不一致 → 打回  

---

## 9. 冻结声明

Party / Lease / Bill / Payment 开发必须使用本异常体系。  
实现类名可放在 `app/core/exceptions.py` 或 `app/shared/exceptions.py`（实现阶段落地），**语义以本文为准**。
