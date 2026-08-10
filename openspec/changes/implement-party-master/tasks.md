## 0. 规划边界（当前阶段）

- [x] 0.1 不 apply、不编码、不迁移、不启容器、不建分支、不提交推送
- [x] 0.2 只读 PG/Docker 预检并记录能力矩阵
- [x] 0.3 修订地址独立表、OpenAPI park_id、分支/PG 门禁
- [x] 0.4 `openspec validate implement-party-master --strict`
- [ ] 0.5 人工确认预检 → 再议 apply（等待）

**当前阻塞标签：**

- ~~`PARTY_APPLY_BLOCKED_NO_POSTGRES`~~（Docker + PG16 容器连接已验证）  
- **`POSTGRES_BASELINE_MIGRATION_FAILED`**（`9f17fd2e9180` 中 `all_parks = 1` 与 PG boolean 不兼容；未改历史 migration）  
- apply 仍 **阻塞** 直至基线 migration 在 PG 上可 upgrade head 且 downgrade/upgrade 往返成功

---

## A. Apply 前 Git 门禁（执行 apply 的会话中完成；本预检不创建分支）

- [ ] A.1 确认 main 工作区干净且 `main == origin/main`
- [ ] A.2 确认 design-party-domain 已归档推送
- [ ] A.3 确认本规划已人工审批（含预检关闭项）
- [ ] A.4 **创建并切换 `feat/party-master`**（禁止 main 开发 Party）
- [ ] A.5 确认禁止 force push；合并前 PG 测必过

---

## B. Apply 前 / 实现早期 PostgreSQL 16 门禁

- [ ] B.1 提供 Docker Compose PG 16 测试编排（127.0.0.1、库名含 test、密码占位）
  - 文件：`docker-compose*.yml` 或 `apps/api/docker-compose.party-test.yml`
  - DB：测试库 only  
- [ ] B.2 增加 `psycopg`（或等价）dev 依赖；文档 env 占位 `TEST_DATABASE_URL` / `POSTGRES_TEST_URL`
- [ ] B.3 **验证 PostgreSQL 16 连接**（真实可连；失败则停止 apply/Complete）
- [ ] B.4 Alembic **base → head**（PG）
- [ ] B.5 Alembic **head → down revision → head**
- [ ] B.6 运行 PostgreSQL 集成测试套件
- [ ] B.7 验证 ACTIVE 园关系部分唯一索引
- [ ] B.8 验证并发唯一冲突（Party credit_code / 有效 relation）
- [ ] B.9 验证事务与外键
- [ ] B.10 验证 tenant 隔离
- [ ] B.11 确认未连旧 Java/生产库

---

## 1. 领域模型与领域测试

- [ ] 1.1 Party/Role/Relation/Contact/Address/RiskEvent 实体（无主档 address/park_id/证件）
  - 测试：unit/party  
  - DB：否  
- [ ] 1.2 状态机、credit_code normalize、地址 primary 规则  
  - 测试：domain rules  
  - DB：否  

---

## 2. ORM 与 Mapper

- [ ] 2.1 models：含 `party_addresses`  
  - DB：模型  
- [ ] 2.2 mappers 双向  
  - 测试：roundtrip  
  - DB：否  

---

## 3. 迁移

- [ ] 3.1 Alembic 建表 + `uk_ppr_active` + `uk_party_addr_primary`（PG 权威）  
  - 回滚：downgrade + dump  
  - DB：是  
- [ ] 3.2 SQLite 开发兼容（非权威）  
  - DB：测试  

---

## 4. Repository 与隔离

- [ ] 4.1 可见性：scope ∩ relations / unscoped  
- [ ] 4.2 Address/Role/Relation/Contact/Risk repos  
  - 测试：repository isolation  
  - DB：是  

---

## 5. Party CRUD

- [ ] 5.1 create/list/get/update；**无主档 park_id/address**  
- [ ] 5.2 可选 `initial_park_relation` 组合命令  
  - 测试：api + service  
  - DB：是  

---

## 6. 业务角色

- [ ] 6.1 add/list/deactivate；PARTY_ROLE_IN_USE  
  - DB：是  

---

## 7. Party—Park 关系

- [ ] 7.1 create/end；party_role_id；并发冲突  
  - DB：是  

---

## 8. 联系人

- [ ] 8.1 嵌套 CRUD、primary、软删、脱敏  
  - DB：是  

---

## 9. 地址（独立表）

- [ ] 9.1 AddressService + 嵌套 API  
  - 规则：ORGANIZATION 可写；PERSON 禁止写；primary；软删；审计  
  - 测试：address_*  
  - DB：是  

---

## 10. 归档恢复

- [ ] 10.1 archive/restore；不自动解黑名单；credit 重检  
  - DB：是  

---

## 11. 风险

- [ ] 11.1 blacklist/remove-blacklist + risk_events + audit 同事务  
  - DB：是  

---

## 12. 权限

- [ ] 12.1 五权限码种子 + 路由 Depends  
  - 测试：permission matrix  
  - DB：种子  

---

## 13. 日志审计

- [ ] 13.1 写路径 log + audit；地址不进普通日志  
  - DB：是  

---

## 14. API 错误码

- [ ] 14.1 对齐草案；envelope  
  - DB：是  

---

## 15. OpenAPI 与旧 park_id 契约

- [ ] 15.1 同步 `openapi-v1-core.yaml`：移除 Party 主档 park_id 与模糊 address  
- [ ] 15.2 增加 `initial_park_relation`、addresses、risk 路径  
- [ ] 15.3 **契约测试**：Party schema 禁止主档 park_id 回潮  
- [ ] 15.4 openapi-spec-validator 严格通过  
  - DB：否  

---

## 16. PostgreSQL 集成测试（与 B 重叠验收）

- [ ] 16.1 `pytest -m pg` 全矩阵绿  
  - DB：PG 16  

---

## 17. 全量回归

- [ ] 17.1 Step1 + Party SQLite 快测绿  
  - DB：SQLite  

---

## 18. 文档

- [ ] 18.1 phase06-party-master-complete.md  
  - DB：否  

---

## 执行顺序（摘要）

`0/A 门禁 → B PG 门禁 → 1 领域 → 2–3 持久化 → 4–14 功能 → 15 OpenAPI → 16–17 测试 → 18 文档`

**tasks 规模：** 约 **40+** 可勾选步骤（含门禁 A/B）。

## Complete / 合并条件

- [ ] 全部 B 门禁通过  
- [ ] 功能与 OpenAPI 契约测试通过  
- [ ] 禁止：仅 SQLite 绿即 Complete  
