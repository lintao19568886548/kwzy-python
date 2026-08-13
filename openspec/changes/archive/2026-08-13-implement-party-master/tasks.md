## 0. 规划边界（当前阶段）

- [x] 0.1 不 apply、不编码、不迁移、不启容器、不建分支、不提交推送（预检阶段已完成）
- [x] 0.2 只读 PG/Docker 预检并记录能力矩阵
- [x] 0.3 修订地址独立表、OpenAPI park_id、分支/PG 门禁
- [x] 0.4 `openspec validate implement-party-master --strict`
- [x] 0.5 人工确认预检 → apply 已批准

**门禁状态：** PG16 容器可连；基线 `9f17fd2e9180` boolean 可移植已修复；Party head `c3a91b2e4f10`。

---

## A. Apply 前 Git 门禁

- [x] A.1 确认 main 工作区干净且可对照 origin（实现在 feat 分支进行）
- [x] A.2 确认 design-party-domain 已归档推送
- [x] A.3 确认本规划已人工审批（含预检关闭项）
- [x] A.4 **创建并切换 `feat/party-master`**（禁止 main 开发 Party）
- [x] A.5 确认禁止 force push；合并前 PG 测必过

---

## B. Apply 前 / 实现早期 PostgreSQL 16 门禁

- [x] B.1 提供 Docker Compose PG 16 测试编排（127.0.0.1、库名含 test、密码占位）
- [x] B.2 增加 `psycopg`（或等价）dev 依赖；文档 env 占位 `TEST_DATABASE_URL` / `POSTGRES_TEST_URL`
- [x] B.3 **验证 PostgreSQL 16 连接**
- [x] B.4 Alembic **base → head**（PG）
- [x] B.5 Alembic **head → down revision → head**
- [x] B.6 运行 PostgreSQL 集成测试套件（`pytest -m pg`）
- [x] B.7 验证 ACTIVE 园关系部分唯一索引（`uk_ppr_active` 存在）
- [x] B.8 验证唯一冲突路径（API/IntegrityError → CREDIT/RELATION 冲突码；SQLite+约束）
- [x] B.9 验证事务与外键（PG harness + 迁移）
- [x] B.10 验证 tenant 隔离（API 跨租户 404）
- [x] B.11 确认未连旧 Java/生产库（仅 127.0.0.1 kwzy_party_test）

---

## 1. 领域模型与领域测试

- [x] 1.1 Party/Role/Relation/Contact/Address/RiskEvent 实体（无主档 address/park_id/证件）
- [x] 1.2 状态机、credit_code normalize、地址 primary 规则

---

## 2. ORM 与 Mapper

- [x] 2.1 models：含 `party_addresses`
- [x] 2.2 mappers 双向

---

## 3. 迁移

- [x] 3.1 Alembic 建表 + `uk_ppr_active` + `uk_party_addr_primary`（PG 权威）
- [x] 3.2 SQLite 开发兼容（临时库 base→head）

---

## 4. Repository 与隔离

- [x] 4.1 可见性：scope ∩ relations / unscoped
- [x] 4.2 Address/Role/Relation/Contact/Risk repos

---

## 5. Party CRUD

- [x] 5.1 create/list/get/update；**无主档 park_id/address**
- [x] 5.2 可选 `initial_park_relation` 组合命令

---

## 6. 业务角色

- [x] 6.1 add/list/deactivate；PARTY_ROLE_IN_USE

---

## 7. Party—Park 关系

- [x] 7.1 create/end；party_role_id；冲突码

---

## 8. 联系人

- [x] 8.1 嵌套 CRUD、primary、软删、脱敏

---

## 9. 地址（独立表）

- [x] 9.1 AddressService + 嵌套 API（ORGANIZATION 可写；PERSON 禁止写）

---

## 10. 归档恢复

- [x] 10.1 archive/restore；不自动解黑名单；credit 重检

---

## 11. 风险

- [x] 11.1 blacklist/remove-blacklist + risk_events + audit 同事务

---

## 12. 权限

- [x] 12.1 五权限码种子 + 路由/服务层 Depends

---

## 13. 日志审计

- [x] 13.1 写路径 log + audit；地址不进普通日志

---

## 14. API 错误码

- [x] 14.1 对齐草案；envelope

---

## 15. OpenAPI 与旧 park_id 契约

- [x] 15.1 同步 `openapi-v1-core.yaml`：移除 Party 主档 park_id 与模糊 address
- [x] 15.2 增加 `initial_park_relation`、addresses、risk 路径
- [x] 15.3 **契约测试**：Party schema 禁止主档 park_id 回潮
- [x] 15.4 openapi-spec-validator 严格通过

---

## 16. PostgreSQL 集成测试（与 B 重叠验收）

- [x] 16.1 `pytest -m pg` 全矩阵绿

---

## 17. 全量回归

- [x] 17.1 Step1 + Party SQLite 快测绿

---

## 18. 文档

- [x] 18.1 phase06-party-master-complete.md

---

## 执行顺序（摘要）

`0/A 门禁 → B PG 门禁 → 1 领域 → 2–3 持久化 → 4–14 功能 → 15 OpenAPI → 16–17 测试 → 18 文档`

## 19. 验收缺陷修复（PII 阻塞 · 人工确认后追加）

> 验收结论：`PARTY_MASTER_ACCEPTANCE=BLOCKED` / `PARTY_ACCEPTANCE_BLOCKED_PII`
> 本段为 **新增** 任务，不回写改写既有已勾选完成记录。

- [x] 19.1 OpenSpec：PERSON 地址 v1 读写全拒绝 Requirement/Scenario（含预存行不泄露、ORGANIZATION 不受影响）
- [x] 19.2 Application：list/create/update/delete 统一 `_reject_person_address_access`（禁止仅 Router）
- [x] 19.3 删除 list_addresses 与行为不一致的 pass/注释；查询地址表前即拒绝
- [x] 19.4 OpenAPI 同步 PERSON_ADDRESS_FORBIDDEN（403）
- [x] 19.5 安全回归：PERSON 写/读/删/列表 403；DB 预置后仍 403；主档不嵌地址
- [x] 19.6 日志与 audit detail 不含完整地址；错误 body 不含地址
- [x] 19.7 ORGANIZATION 地址 CRUD 回归
- [x] 19.8 Repository 专项测试 + 中文 docstring 补齐（Party 本 change 范围）
- [x] 19.9 PG 矩阵：credit 并发唯一、risk 同事务、primary 约束、PERSON 预存不可读
- [x] 19.10 全量复验（SQLite/PG 迁移、pytest pg/not pg/全量、openspec、OpenAPI）

---

## Complete / 合并条件

- [x] 全部 B 门禁通过
- [x] 功能与 OpenAPI 契约测试通过
- [x] 19 验收缺陷修复全部通过（PII）
- [x] 20 中文 docstring P1 补齐（07-engineering-standard 六段式）
- [x] 21 第三次独立验收：P0=0、P1=0；迁移/SQLite/PG/全量测试/openspec/OpenAPI 通过
- [x] 人工批准后合并 main（`feat/party-master@c181e7f` 已为 `main` 祖先；2026-08-13 `main@d9c0b0b` PG16/全量验收通过；生产部署仍禁止自动执行）
