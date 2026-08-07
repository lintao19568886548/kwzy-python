# 05 测试规范（Testing Standard）

> 状态：**正式冻结**  
> 框架：`pytest` + `httpx`/`TestClient`  
> 数据库：测试默认使用隔离 SQLite 内存库；**禁止连接旧 Java/生产库**

---

## 1. 目标

1. 每个业务模块可独立证明「做对了」。  
2. 强制覆盖 **租户隔离** 与 **园区权限**（系统生命线）。  
3. 业务规则（状态机、核销、占用）有自动化守护。  

---

## 2. 测试金字塔（每模块最低要求）

| 类型 | 目录建议 | 必须 |
| --- | --- | --- |
| **unit test** | `tests/unit/<module>/` | 领域规则、纯函数、状态机 |
| **repository test** | `tests/repository/<module>/` | tenant/park 过滤、CRUD、软删 |
| **api test** | `tests/api/<module>/` | 路由、鉴权、envelope、状态码 |
| application/service test | `tests/application/<module>/` | 强烈建议（可与 repository 合并初期） |

> 模块未达到三类测试前，**不得合并主分支、不得宣称完成**。

---

## 3. 强制覆盖矩阵

每个写模型模块（Park/Unit/Party/Lease/Bill/Payment…）至少覆盖：

### 3.1 权限

| 用例 | 期望 |
| --- | --- |
| 无 Token 且 production | 401 |
| 有 Token 无园区权限访问资源 | 403 或 404（模块统一） |
| `permissions=["*"]` 且 `park_scope_mode=NONE` | 有全部动作权限，**不可**访问任何园区数据 |
| `park_scope_mode=ALL`（`roles/users.all_parks`） | 同租户内可跨园；与 `*` 无关 |
| `park_scope_mode=LIST` + 指定 `park_ids` | 仅列表内园区 |

### 3.2 租户隔离

| 用例 | 期望 |
| --- | --- |
| 租户 A 创建资源，租户 B get/list | 不可见（404/空列表） |
| 创建时伪造其他 tenant_id | 被覆盖为上下文 tenant，或拒绝 |
| 同 username 跨租户 | 登录歧义处理符合规范 |

### 3.3 业务规则

| 模块示例 | 必须用例 |
| --- | --- |
| Unit | 非法状态迁移失败；合法迁移成功 |
| Lease（未来） | 激活占用冲突；退租释放 |
| Bill（未来） | 禁止 status=OVERDUE；部分收款 → PARTIALLY_PAID |
| Payment（未来） | allocation 超额失败；核销回写账单 |

### 3.4 API 契约

| 用例 | 期望 |
| --- | --- |
| 成功 | `code=="OK"` 且 data 结构稳定 |
| 业务失败 | body 含 `code/message/data` |
| 分页 | total/page/page_size/items |

---

## 4. 命名与组织

```text
tests/
  conftest.py                 # 全局 fixture：引擎、session、client、上下文工厂
  unit/
    park_property/
      test_unit_states.py
  repository/
    park_property/
      test_park_repository.py
  api/
    park_property/
      test_park_api.py
  application/                # 可选
    park_property/
      test_park_service.py
```

测试函数命名：

```text
test_<场景>_<期望>
# test_tenant_b_cannot_see_tenant_a_park
# test_partial_payment_sets_bill_partially_paid
```

---

## 5. Fixture 与数据隔离

| 规定 |
| --- |
| 每个测试文件/用例不依赖真实外网 |
| 使用内存库或临时文件库，测试结束清理 |
| 禁止 `DATABASE_URL` 指向旧系统 MySQL |
| 构造 `TenantContext` 明确 `tenant_id` / `park_ids` / `permissions` |
| 需要多租户时在用例内创建第二个 Tenant |

推荐上下文工厂：

```text
admin_ctx(tenant_id)   → permissions=["*"] + park_scope_mode=ALL
scoped_ctx(tenant_id, park_ids) → permissions=[]
```

---

## 6. 断言标准

1. 不仅 assert status_code，还 assert `body["code"]`  
2. 隔离类测试必须 assert「反向不可见」  
3. 金额用 Decimal 或转为分整数比较，避免 float 模糊  
4. 时间比较允许秒级误差或只比较日期  

---

## 7. 覆盖率与 CI（目标）

| 项 | 最低目标（建议） |
| --- | --- |
| 新增模块行覆盖率 | ≥ 70%（核心 domain ≥ 90%） |
| CI | push/PR 必跑 pytest |
| 失败策略 | 红线：隔离/权限用例失败禁止合并 |

（具体 CI 配置在工程落地时接入，规范先冻结要求。）

---

## 8. 与开发清单关系

未满足本测试规范 = `06-development-checklist.md` 中「测试完成」不得勾选。

---

## 9. 审查门禁

1. 仅有「能跑通 happy path」无隔离测试 → 打回  
2. 测试连真实旧库 → 打回  
3. 用 sleep 等待代替断言 → 打回  
4. 测试中 `print` 调试残留 → 建议清理  

---

## 10. 冻结声明

自 Party 模块起，PR 模板必须粘贴测试清单自检结果。  
Step1 已有 `test_isolation.py` 作为范例，后续模块按同等标准扩展。
