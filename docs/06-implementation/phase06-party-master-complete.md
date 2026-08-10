# Phase06 Party Master 实施完成报告

> 分支：`feat/party-master`  
> OpenSpec change：`implement-party-master`  
> 状态：**第三次验收通过（P0=0/P1=0）**；feature 分支提交并推送；**未合 main / 未部署**

## 1. 范围

已实现租户级 Party 主数据：主档、业务角色、Party–Park 多对多、联系人、独立地址表、风险事件与黑名单。

**明确未实现：**

- Lease / Bill / Payment 业务（仓库中 `app/modules/lease` 等为**既有占位 stub**，本轮 Party **未实现** Lease）
- 旧 `/rental/tenant*` 适配器
- PERSON 身份证号码存储
- PERSON 地址全部读写（v1 临时安全边界：创建/改/删/列表/详情均 403；见验收缺陷修复）
- 旧库 ETL / 生产数据迁移

**PII 验收缺陷修复（后补）：**

- Application 层 `_reject_person_address_access`：PERSON 地址读写全拒绝（`PERSON_ADDRESS_FORBIDDEN`）
- 库中预存 PERSON 地址亦不得经 API 返回
- ORGANIZATION 地址功能保持不变

## 2. DDD 分层

| 层 | 路径 | 说明 |
| --- | --- | --- |
| Domain | `app/modules/party/domain/` | 实体 + 规则；无 SQLAlchemy/FastAPI |
| Application | `app/modules/party/application/party_service.py` | 用例编排；经 Repository/Mapper；不直接 import ORM models |
| Infrastructure | `app/modules/party/infrastructure/` + `models/party.py` | ORM、Mapper、Repository（强制 tenant_id / 可见性） |
| Interface | `app/modules/party/interface/` | Router + Pydantic Schema；禁止直连 DB |

## 3. ORM 表 / 约束 / 索引

| 表 | 要点 |
| --- | --- |
| `parties` | `uk_parties_tenant_credit (tenant_id, credit_code)`；索引 status/risk/name |
| `party_roles` | `uk_party_role_code (tenant_id, party_id, role_code)` |
| `party_park_relations` | FK `party_role_id`；部分唯一 `uk_ppr_active`（ACTIVE 且未删） |
| `party_contacts` | 软删；主联系人业务规则在服务层 |
| `party_addresses` | 部分唯一 `uk_party_addr_primary`（同 type 有效 primary） |
| `party_risk_events` | 仅插入历史；无更新路径 |

Alembic revision：`c3a91b2e4f10` → down_revision `9f17fd2e9180`（唯一 head）。

## 4. API 路由（前缀 `/api/v1`）

- `GET/POST /parties`
- `GET/PATCH /parties/{id}`
- `POST .../archive` `.../restore`
- `GET/POST .../roles` `POST .../roles/{id}/deactivate`
- `GET/POST .../park-relations` `POST .../park-relations/{id}/end`
- `GET/POST .../contacts` `PATCH/DELETE .../contacts/{id}`
- `GET/POST .../addresses` `PATCH/DELETE .../addresses/{id}`
- `GET .../risk-events`
- `POST .../blacklist` `.../remove-blacklist`

主档 **无** `park_id` / 模糊 `address`；OpenAPI 已同步并加契约测试。

## 5. 权限与园区范围

| 码 | 用途 |
| --- | --- |
| `party:read` | 列表/详情/子资源读 |
| `party:write` | 已关联园区主体写 |
| `party:manage_unscoped` | 零园区关联创建/维护/首个关系 |
| `party:risk_read` | 风险历史 |
| `party:risk_manage` | 黑名单操作 |

可见性：`ALL` / `LIST ∩ ACTIVE relations` / `NONE`（仅 unscoped 权限可见零关系主体）。空园区范围不泄露已关联主体。

## 6. 审计与敏感信息

- 写路径：`AuditRecorder` 同事务 + `log_business_success`
- 审计 detail：地址正文不入；电话脱敏
- 禁止 PERSON 地址写；无身份证字段

## 7. 验证结果（本机）

| 项 | 结果 |
| --- | --- |
| SQLite 临时库 base→head | 通过 → `c3a91b2e4f10` |
| PostgreSQL 16 空库 base→head | 通过 |
| PG downgrade/upgrade 往返（party revision） | 通过 |
| `alembic current == heads` 唯一 head | `c3a91b2e4f10` |
| `pytest -m pg` | 通过 |
| `pytest -m "not pg"` | 54 passed |
| 全量 pytest | 58+ passed |
| `openspec validate implement-party-master --strict` | valid |
| OpenAPI YAML + openapi-spec-validator | OK |
| 路由/契约一致性 + 主档无 park_id | 通过 |
| 敏感扫描（Party 新增文件） | 0 hits |
| `git diff --check` | 通过（仅 CRLF 提示） |

## 8. 已知风险 / 后续

1. PERSON 地址 v1 **读写全拒绝**；可读/可写需独立 KMS/PII change  
2. SQLite 部分唯一索引语义弱于 PG（权威以 PG 为准）  
3. 并发 credit_code / relation 冲突主要依赖 DB 唯一约束 + IntegrityError 映射  
4. 未实现旧 rental 适配与证件加密  

## 9. 交付标记

`PHASE06-PARTY-MASTER-THIRD-ACCEPTANCE-PASS`
