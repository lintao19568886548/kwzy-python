# Party 领域设计 v1（含 implement 预检修订）

> 状态：设计已批准归档；implement **预检修订中**（地址表 / OpenAPI / PG 门禁）  
> 正式 specs：`openspec/specs/party-*`  
> ADR：003a–003g  

---

## 1. 决策追踪表（增量）

| 决策 | 采用方案 | 原因 | 影响 |
| --- | --- | --- | --- |
| 地址 | **`party_addresses` 独立表**；主档无 address | 多类型/primary；禁第二事实来源 | ADR-003g、DDL、API |
| PERSON 地址 | 首版禁止写入 | 个人敏感；无 PII ACL | API |
| 主档 park | 无 park_id；可选 initial_park_relation 命令 | 租户主档 + 关系表 | OpenAPI |
| PG 测试 | Compose 首选；apply 前必须可连 | 生产 PG 16 | implement 门禁 |
| 分支 | apply 前 feat/party-master | 隔离实现 | tasks |

（其余决策见已归档 design-party-domain / ADR-003a–f。）

---

## 2. 地址聚合规则

- 类型：REGISTERED / OFFICE / MAILING / BILLING / OTHER  
- 多地址；同 type 一条有效 primary  
- 软删；归档 Party 保留地址行  
- 写审计；日志不落地址明细  
- ORGANIZATION 可用；PERSON 首版不写  

---

## 3. 主档字段（实现对齐）

tenant 级：party_type, name, contact_*, credit_code, status, risk_*, remark  
**无** park_id、**无** address、**无** 证件列  

关系 / 角色 / 联系人 / 地址 / 风险事件：独立表与子资源。  
