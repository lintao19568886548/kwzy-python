# 技术架构评审（Technical Review）

> 评审对象：`apps/api` 模块化单体骨架 + 领域/部署设想  
> 原则：只评架构，不进入业务编码

---

## 1. 当前实现形态

```text
apps/api/app/
  core/          # config, db, security, errors
  shared/        # response, deps
  modules/*/api.py  # 多为 stub 路由
  main.py        # 组装路由
```

**事实：**

- 已选 FastAPI + SQLAlchemy 方向 + JWT 骨架  
- **按限界上下文分模块** — 正确  
- **尚未形成完整分层**（domain / application / infrastructure / interface）  
- 依赖注入与租户过滤器仅为占位  
- 无 Redis / MQ / 调度 / 对象存储 / 可观测性落地设计文档  

**技术架构综合评分：68 / 100**（方向分高，完备分低）

---

## 2. 分层检查：domain / application / infrastructure / interface

### 2.1 目标分层（评审推荐冻结）

```text
interface (api.py, schemas.py)     ← HTTP/DTO，无业务规则
        ↓
application (service.py, commands, queries, dto)
        ↓
domain (entities, value objects, domain services, events, state machines)
        ↑
infrastructure (models, repositories, mq, redis, sms, llm, storage)
```

### 2.2 现状对照

| 层 | 现状 | 评价 |
| --- | --- | --- |
| interface | 仅有 api stub | 有雏形 |
| application | 无 service 实现约定强制 | **缺** |
| domain | 仅在 docs，代码无 domain.py | **文档有、代码无** |
| infrastructure | db.py 全局 engine | 过简 |

### 2.3 模块内推荐落地（阶段 06 强制）

每个业务模块最小文件集（可先薄 domain）：

```text
modules/billing/
  api.py              # interface
  schemas.py          # interface DTO
  application/
    service.py
  domain/
    model.py          # 纯领域（可不依赖 SQLAlchemy）
    states.py
  infrastructure/
    models.py         # ORM
    repository.py
```

**一期允许简化为：**

```text
api.py / schemas.py / service.py / models.py / repository.py / domain.py
```

但 **禁止** Service 里堆裸 SQL 且 Controller 直接操作 Session 无边界（避免回到旧 Java JdbcTemplate 上帝服务）。

### 2.4 依赖规则（冻结）

| 允许 | 禁止 |
| --- | --- |
| api → application | api → infrastructure.repository 直调（可讨论，建议禁止） |
| application → domain | domain → fastapi / sqlalchemy |
| application → repository 接口 | modules 循环依赖 |
| infrastructure → domain 映射 | billing 改 lease 表 |

---

## 3. 模块化单体与未来拆微服务

### 3.1 优点

- `modules/*` 边界与 DDD 上下文基本对齐  
- OpenAPI 可按 tag 拆分  
- Outbox 表已在 DDL，利于去中心化消息  

### 3.2 拆分就绪度

| 上下文 | 可拆性 | 触发条件 |
| --- | --- | --- |
| AIAssist / Import | 高 | CPU 尖峰、长任务 |
| AcquisitionRadar | 高 | 爬虫隔离 |
| Analytics | 高 | 读多写少 |
| Billing+Collection | 中 | 与主库同事务多，慎早拆 |
| Identity | 中 | 可做独立认证服务 |

### 3.3 冻结要求

1. 模块间 **只通过 application service 或领域事件** 通信  
2. 禁止跨模块直接 import ORM Model 写库  
3. 每个模块自有 `public.py` 导出允许的服务接口  

**结论：当前结构「可演进微服务」，但需在阶段 06 把依赖规则写成 lint/评审制度，否则单体腐化后无法拆。**

---

## 4. 横切能力是否需要提前设计

### 4.1 决策表

| 能力 | 是否一期必须设计 | 是否一期必须实现 | 说明 |
| --- | --- | --- | --- |
| **多租户过滤器** | **必须设计** | **必须实现** | 串租是 P0 事故 |
| **园区 DataScope** | **必须设计** | **必须实现** | 与旧系统对等 |
| **JWT 鉴权** | 必须 | 必须 | 骨架有 |
| **审计日志** | 必须 | 主链写操作必须 | 表已有 |
| **Outbox** | 必须设计 | 可二期启用消费 | 表已有，应用先同进程调用也可 |
| **Redis** | **必须设计** | 建议实现 | 短信验证码、限流、缓存 scope |
| **消息队列** | 必须设计选型 | 可延后 | Redis Stream 一期够用 |
| **任务调度** | 必须设计 | 逾期账单/到期合同需要 | APScheduler/ Celery beat 二选一 |
| **文件存储** | 必须设计 | AI/附件需要 | 本地目录→OSS 可切换接口 |
| **日志** | 必须 | 必须 | 结构化 JSON + request_id/tenant_id |
| **监控** | 必须设计 | 最小 metrics | /health 有；补 Prometheus 可选 |
| **配置中心** | 否 | 否 | env 足够 |
| **服务网格** | 否 | 否 | 过早 |
| **搜索引擎** | 否 | 否 | 二期 |

### 4.2 基础设施目标架构（一期）

```text
                   ┌─────────────┐
                   │  Nginx/TLS  │
                   └──────┬──────┘
                          ▼
                   ┌─────────────┐
                   │ FastAPI API │
                   └──────┬──────┘
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
         MySQL         Redis        Object Storage
            │             │
            │             ├─ sms code / rate limit
            │             └─ (optional) stream
            ▼
      outbox dispatcher (进程内或 worker)
            ▼
      async worker（AI/导入，可同仓不同进程）
```

### 4.3 必须在编码前写成 ADR 的选型

| ADR | 内容 | 推荐默认 |
| --- | --- | --- |
| ADR-T01 | 任务队列 | 一期 Redis + 后台 worker；量大再 Celery |
| ADR-T02 | 对象存储端口 | `StoragePort` 本地实现 / S3 实现 |
| ADR-T03 | 短信端口 | `SmsSender` 接口，mock 可测 |
| ADR-T04 | 时钟与时区 | 一律 UTC 存，业务日 Asia/Shanghai |
| ADR-T05 | 事务边界 | 单模块本地事务；跨模块 outbox |
| ADR-T06 | 幂等 | Idempotency-Key 表或 Redis |

---

## 5. 安全架构

| 项 | 现状 | 要求 |
| --- | --- | --- |
| 密码哈希 | passlib bcrypt | 保持 |
| JWT 密钥 | env | 生产强制强密钥校验启动失败 |
| CORS | * | 生产收紧 |
| 开发 mock 免登 | deps 中存在 | **生产 profile 必须关闭** |
| SQL 注入 | ORM | 禁止拼接 SQL |
| 文件上传 | 未设计 | 类型/大小/病毒扫描策略 |
| 密钥进库 | dedicated_dsn | 禁止明文 |

---

## 6. 可测试性与质量门禁

阶段 06 起建议门禁：

1. 领域不变量单测（核销、占用、状态迁移）  
2. API 契约测试（与 OpenAPI 抽样）  
3. 多租户隔离测试（tenant A 不可见 B）  
4. 园区 scope 测试  
5. 无 DB 的 domain 纯测优先  

当前仅 health/login stub 测试 — **不足，但不阻塞架构冻结。**

---

## 7. 技术风险

| 风险 | 级别 | 缓解 |
| --- | --- | --- |
| 模块只停在 api stub，业务全进 service 上帝类 | 高 | 分层模板 + PR 模板 |
| 租户过滤遗漏 | 极高 | 统一 Repository 基类 |
| 同步调用 AI 阻塞 worker | 高 | 强制异步 job |
| 与旧系统并行双写 | 中 | 迁移期防腐层，不做长期双写 |
| Python 3.10 与注解 | 低 | 已兼容 |

---

## 8. 技术评审结论

| 维度 | 分数 |
| --- | --- |
| 技术选型合理性 | 8/10 |
| 模块边界 | 7/10 |
| 分层完备 | 4/10 |
| 拆服务就绪 | 7/10 |
| 基础设施规划 | 5/10 |
| 安全 | 6/10 |
| **综合** | **68/100** |

**结论：方向正确（FastAPI 模块化单体 + 上下文分包）。**  
**进入阶段 06 前必须冻结：分层模板、租户/园区过滤器、Redis/存储/任务 的端口设计（ADR），否则会在实现期架构失控。**
