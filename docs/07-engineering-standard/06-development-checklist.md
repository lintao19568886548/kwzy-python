# 06 模块开发检查清单（Development Checklist）

> 状态：**正式冻结**  
> 用途：每个业务模块（Party / Lease / Bill / Payment / …）开发完成前 **强制自检**  
> 未全部勾选不得宣称「模块完成」、不得进入下一模块

---

## 0. 使用方法

1. 复制本节「模块检查表」到 PR 描述或 `docs/06-implementation/<module>-checklist.md`  
2. 逐项勾选，证据链写清（文件路径 / 测试名）  
3. Reviewer 按清单验收  

---

## 1. 通用检查表（复制区）

```markdown
## 模块：________    日期：________    开发：________

### 1. 分层正确
- [ ] interface 仅路由 + Schema + Depends
- [ ] application 承载用例与事务
- [ ] domain 仅纯规则/状态机（无 SQLAlchemy/FastAPI）
- [ ] infrastructure 仅 ORM/Repository/适配器
- [ ] 无 Router 直访数据库
- [ ] 无 Service 散落复杂 SQL（查询在 Repository）
- [ ] 无 ORM Model 承载核心业务规则
- [ ] 跨模块未直接改对方表

### 2. 注释完整
- [ ] 所有 class 含中文 docstring（标准六段式）
- [ ] 所有公共 function/method 含中文 docstring
- [ ] 核心业务方法含：功能说明/业务职责/输入/返回/异常/业务规则
- [ ] 统一语言正确（如 Payment=收款登记）

### 3. 日志完整
- [ ] 无 print
- [ ] 使用 logging
- [ ] 写操作成功 INFO：module + action + tenant_id + user_id + request_id
- [ ] park 相关动作带 park_id
- [ ] 失败 WARNING/ERROR 带 code
- [ ] 无敏感信息（密码/Token/完整手机号）

### 4. 异常处理完整
- [ ] 使用统一异常（Domain/Application/Infrastructure → AppError）
- [ ] API 错误返回 {code, message, data}
- [ ] 跨租户不可见资源不泄露（404 策略一致）
- [ ] 基础设施错误不返回 SQL 原文

### 5. 测试完成
- [ ] unit test（领域规则）
- [ ] repository test（tenant/park 过滤）
- [ ] api test（envelope + 状态码）
- [ ] 租户隔离用例通过
- [ ] 园区权限用例通过
- [ ] 核心业务规则用例通过
- [ ] pytest 全绿

### 6. 文档完成
- [ ] 模块 README 或 implementation 记录（路径/接口/状态机）
- [ ] 若改表：Alembic migration 已生成并说明
- [ ] 若改 API：OpenAPI 或接口说明已更新
- [ ] 检查清单本文已填并贴 PR

### 7. 多租户与数据权限（生命线）
- [ ] 所有表含 tenant_id（或有充分理由）
- [ ] 写操作 stamp 上下文 tenant_id
- [ ] 查询默认 tenant 过滤
- [ ] 有 park_id 的资源走 DataScope
- [ ] 未使用「空 park_ids = 全权限」错误语义
- [ ] 超管动作用 `*`；全园用 `all_parks` / `park_scope_mode=ALL`（二者正交）

### 8. 安全与质量
- [ ] 无硬编码密钥
- [ ] 未连接旧系统数据库
- [ ] 幂等要求已识别（支付/出账等）
- [ ] 软删除/状态作废策略明确
```

---

## 2. 分模块附加项

### 2.1 Party（未来）

- [ ] 与合同分离（无合同字段塞 Party）  
- [ ] park_id 归属与 scope  
- [ ] 联系人策略（主电话 + contacts）符合设计  
- [ ] convert 自 Lead 时事件/应用服务边界清晰  

### 2.2 Lease（未来）

- [ ] 状态机：DRAFT/ACTIVE/TERMINATED…  
- [ ] 激活时占用 Unit，冲突检测  
- [ ] 退租释放与 used_area 投影更新  
- [ ] lease_terms / attachments 一致性  

### 2.3 Bill（未来）

- [ ] status **无 OVERDUE**  
- [ ] is_overdue 衍生计算有测试  
- [ ] bill_lines 费项模型  
- [ ] issue/void 权限与规则  
- [ ] 部分收款后 PARTIALLY_PAID  

### 2.4 Payment（未来）

- [ ] 语义为 **收款登记**（文档与日志 module=payment）  
- [ ] payment_allocations 分摊核销  
- [ ] 超额核销失败  
- [ ] 回写 bill.paid_amount/status  
- [ ] 非在线支付网关范围  

---

## 3. PR 合并门禁（Reviewer）

| 门禁 | 不通过则 |
| --- | --- |
| 清单未贴或空勾 | 拒绝合并 |
| 隔离测试缺失 | 拒绝合并 |
| 分层违规（Router 碰 DB） | 拒绝合并 |
| 无中文 docstring 的核心 Service | 拒绝合并 |
| 日志用 print | 拒绝合并 |

---

## 4. 与规范文档索引

| 文档 | 内容 |
| --- | --- |
| [01-architecture-standard.md](./01-architecture-standard.md) | 四层与禁止项 |
| [02-code-comment-standard.md](./02-code-comment-standard.md) | 中文 docstring |
| [03-logging-standard.md](./03-logging-standard.md) | logging 字段 |
| [04-exception-standard.md](./04-exception-standard.md) | 异常体系 |
| [05-testing-standard.md](./05-testing-standard.md) | 测试类型与覆盖 |

---

## 5. 冻结声明

**在未建立并遵守本清单前，不得开始 Party 业务开发。**  

本清单与 Step1 审查结论一致：基础模块已通过；后续模块必须按本工程规范交付。

```text
【ENGINEERING STANDARD FROZEN】

docs/07-engineering-standard/* 已生效。
等待下一阶段指令（业务模块开发前须勾选清单）。
```
