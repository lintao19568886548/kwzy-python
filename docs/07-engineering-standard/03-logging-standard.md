# 03 日志规范（Logging Standard）

> 状态：**正式冻结**  
> 统一库：Python 标准库 `logging`  
> **禁止 `print` 用于业务与诊断输出**

---

## 1. 目标

1. 生产可检索、可关联一次请求全链路。  
2. 多租户系统必须能按 `tenant_id` / `park_id` 过滤日志。  
3. 与审计表、告警系统字段对齐。  

---

## 2. 日志框架

| 项 | 规定 |
| --- | --- |
| 库 | `logging`（可后续接 structlog，但字段契约不变） |
| 获取 logger | `logger = logging.getLogger(__name__)` |
| 禁止 | `print` / `pprint` 作为正式日志 |
| 配置 | 应用启动时统一 `dictConfig` 或 basicConfig（阶段实现） |

测试中允许临时 caplog，仍不得依赖 print。

---

## 3. 日志级别

| 级别 | 使用场景 |
| --- | --- |
| **DEBUG** | 开发排障、SQL 细节开关、非敏感中间状态 |
| **INFO** | 关键业务动作成功：创建/更新/签发/核销/登录成功 |
| **WARNING** | 可恢复异常、权限拒绝、重复提交、降级 |
| **ERROR** | 用例失败、未预期业务失败、外部依赖失败 |
| **CRITICAL** | 系统不可用、数据损坏风险、安全事件 |

**禁止：** 用 INFO 刷循环每行；用 ERROR 表示正常校验失败（应用校验用 WARNING 或业务返回即可，并视情况记 WARNING）。

---

## 4. 强制上下文字段

每一条**业务相关**日志（INFO 及以上，建议 DEBUG 也尽量带）必须能解析出：

| 字段 | 说明 | 示例 |
| --- | --- | --- |
| `request_id` | 单次 HTTP/任务唯一 ID | uuid4 |
| `user_id` | 操作者，系统任务可用 0 | 12 |
| `tenant_id` | 租户 | 1 |
| `park_id` | 园区；无则 `null` 或不传 | 5 |
| `module` | 限界上下文/模块短名 | `park` / `lease` / `bill` / `payment` |
| `action` | 动作短名 | `create` / `update` / `delete` / `issue` |

### 4.1 推荐结构化写法

优先 **extra** 字段，便于 JSON 采集：

```python
logger.info(
    "创建园区成功",
    extra={
        "request_id": request_id,
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "park_id": park_id,
        "module": "park",
        "action": "create",
        "resource_id": park_id,
    },
)
```

消息正文用中文简述结果；细节进 extra。

### 4.2 模块与动作命名

| module | 典型 action |
| --- | --- |
| `identity` | `login`, `logout`, `me` |
| `park` | `create`, `update`, `delete`, `list`, `get` |
| `unit` | `create`, `update`, `change_status`, `delete` |
| `party` | `create`, `update`, `list`（未来） |
| `lease` | `create`, `activate`, `terminate`（未来） |
| `bill` | `create`, `issue`, `void`（未来） |
| `payment` | `create`, `reverse`（未来，收款登记） |
| `collection` | `case_create`, `sms_send`（未来） |

action 使用 **snake_case 英文动词**，module 使用短英文。

---

## 5. request_id 规范

| 项 | 规定 |
| --- | --- |
| 来源 | 请求头 `X-Request-Id`，无则服务端生成 |
| 传递 | contextvars 贯穿 application / infrastructure |
| 响应 | 建议回写响应头 `X-Request-Id` |
| 异步任务 | 继承触发时的 request_id 或生成 `job_id` 并双写 |

---

## 6. 按层的日志要求

| 层 | 要求 |
| --- | --- |
| interface | 可选：入口 DEBUG；不要在路由打敏感 body 全量 |
| application | **必须**：用例成功 INFO；失败 WARNING/ERROR + code |
| domain | 一般不打 IO 日志；纯规则无需日志 |
| infrastructure | 外部调用失败 ERROR；慢查询 WARNING；禁止默认打密码/Token |

---

## 7. 安全与合规

**禁止写入日志：**

- 密码、验证码明文、JWT 全文  
- 银行卡完整号、身份证完整号  
- 客户完整手机号（如需可脱敏 `138****0000`）  

**允许：**

- 资源 ID、状态机迁移前后状态  
- 错误 code、外部依赖名称与耗时  

---

## 8. 示例：创建园区

```text
level: INFO
message: 创建园区成功
module: park
action: create
tenant_id: 1
user_id: 9
park_id: 15
request_id: 7c2e...
```

```text
level: WARNING
message: 无园区数据权限
module: unit
action: create
tenant_id: 1
user_id: 9
park_id: 99
request_id: 7c2e...
```

---

## 9. 与审计日志关系

| 类型 | 用途 |
| --- | --- |
| application logging | 运维观测、排障 |
| `audit_logs` 表 | 合规审计、谁改了什么 |

关键写操作（创建/删除/签发/核销）应 **日志 + 审计** 双落地（审计表后续模块实现时强制）。

---

## 10. 审查门禁

1. 新增业务代码出现 `print(` → 打回  
2. 应用层写操作无 INFO 日志（缺 module/action/tenant）→ 打回  
3. 日志含明文密码/Token → 打回  

---

## 11. 冻结声明

后续 Party/Lease/Bill/Payment 实现时，必须按本规范埋点。  
基础设施（logging Filter 注入 request_id 等）可在工程骨架中统一提供，业务只负责填 module/action。
