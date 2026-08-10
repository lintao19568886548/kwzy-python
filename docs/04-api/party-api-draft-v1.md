# Party API 草案 v1.4（预检修订）

> 设计 only。生产方言 PostgreSQL 16。主档 **无 park_id、无 address**。

---

## 1. 权限

| 码 | 含义 |
| --- | --- |
| party:read | 读可见 Party；不含完整风险原因 |
| party:write | 主档/角色/关系/联系人/地址(组织)/归档 |
| party:manage_unscoped | 零园区关联 Party |
| party:risk_read / party:risk_manage | 风险 |

---

## 2. Party 主档契约（修订旧 park_id）

### 禁止（新 API 正式模型）

- Party 响应/请求主档字段 **`park_id`** 作为归属  
- Party 主档模糊 **`address`** 字符串  

### 创建 Party（示例）

```json
{
  "party_type": "ORGANIZATION",
  "name": "某某科技",
  "contact_name": "张三",
  "contact_phone": "13800000000",
  "credit_code": "91XXXXXXXXXXXXXX",
  "initial_park_relation": {
    "park_id": 10,
    "party_role_id": 9
  }
}
```

- `initial_park_relation`：**可选组合命令**（同事务建角色关系+园关系，或要求已有 role）  
- **不是** Party 主档上的 park_id  
- 无 initial 时创建零关联 Party，需 `party:manage_unscoped`  

### 查询园区关系

仅子资源：`/parties/{id}/park-relations`  

### 旧 OpenAPI / 草案兼容策略

| 旧契约 | 处理 |
| --- | --- |
| `Party.park_id` | **从正式 v1 Party schema 移除** |
| 创建 required park_id | **移除**；改用 initial_park_relation 可选 |
| 文档中的单 address | **移除**；改用 addresses 子资源 |

**不**将主档 park_id 标 deprecated 后继续作为事实来源。  
实现期：契约测试断言 Party schema **不含** `park_id` 属性。

---

## 3. 主资源路径

| 方法 | 路径 |
| --- | --- |
| GET/POST | `/parties` |
| GET/PATCH | `/parties/{party_id}` |
| POST | `/parties/{party_id}/archive` |
| POST | `/parties/{party_id}/restore` |
| GET | `/parties/{party_id}/risk-events` |
| POST | `/parties/{party_id}/blacklist` |
| POST | `/parties/{party_id}/remove-blacklist` |
| GET/POST | `/parties/{party_id}/roles` |
| GET/POST | `/parties/{party_id}/park-relations` |
| GET/POST | `/parties/{party_id}/contacts` |
| … | contacts/{id} PATCH/DELETE |

---

## 4. 地址子资源 `party_addresses`

| 方法 | 路径 |
| --- | --- |
| GET | `/parties/{party_id}/addresses` |
| POST | `/parties/{party_id}/addresses` |
| GET | `/parties/{party_id}/addresses/{address_id}` |
| PATCH | `/parties/{party_id}/addresses/{address_id}` |
| DELETE | `/parties/{party_id}/addresses/{address_id}` |

**规则：**

1. address 必须属于 path party_id + tenant  
2. 禁止跨 Party/tenant 用 address_id  
3. 默认排除软删  
4. 同 type 仅一条有效 primary  
5. type：REGISTERED / OFFICE / MAILING / BILLING / OTHER  
6. REGISTERED=法定注册地址；BILLING=账单通信地址（非收款账户）  
7. 写操作审计；明细不进普通业务日志  
8. **ORGANIZATION**：允许地址 CRUD（需 party:write + 可见性）  
9. **PERSON**：首版 **禁止地址写入**（403 / FEATURE_DISABLED）；无 PII 控制前不开放详细地址暴露  
10. Party 归档不物理删地址  

DELETE = 软删（deleted_at）。

---

## 5. 旧接口

removal_target_version: **v2.0.0**  
removal_gate_status: **NOT_READY**  
（门禁同前）

---

## 6. 错误码增补

| code | 场景 |
| --- | --- |
| ADDRESS_NOT_FOUND | 地址不可见/不存在 |
| ADDRESS_PRIMARY_CONFLICT | primary 冲突 |
| PERSON_ADDRESS_FORBIDDEN | PERSON 地址写入禁止 |
| PARTY_ROLE_MISMATCH | role 不属于 party |
| … | 既有 CREDIT_* / RELATION_* / RISK_* |
