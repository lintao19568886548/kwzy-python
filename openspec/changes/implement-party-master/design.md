## Context

- 正式 specs：`openspec/specs/party-*`  
- 批准设计包 + 本预检修订（地址表、PG 门禁、分支、OpenAPI）  
- 预检结论（只读，未启容器）：Docker/Compose **可用**；本机 `psql`/`pg_isready` **不可用**；项目内 **无** compose/CI/psycopg/PG fixture；测试 env **NOT_SET**  
- **标记：`PARTY_APPLY_BLOCKED_NO_POSTGRES`**（PG 16 连接尚未验证；不得以 SQLite 代替）

## Goals / Non-Goals

**Goals:** 关闭 apply 前规划门禁描述；地址模型独立表；分支与 OpenAPI 契约写入 tasks。  

**Non-Goals:** apply、编码、migration 执行、启容器、建分支、提交。

## Decisions

### D1 — PostgreSQL 16 测试方案（首选固定）

| 优先级 | 方案 |
| --- | --- |
| **首选** | Docker Compose 运行**一次性** PostgreSQL **16** 测试库 |
| 备选 | 本机已安装 PostgreSQL 16（仅 127.0.0.1） |

**强制规则：**

1. 只监听 **127.0.0.1**  
2. 非生产库/账号；库名含 **`test`**（如 `kwzy_party_test`）  
3. 凭据仅 **未跟踪** 环境变量（建议 `TEST_DATABASE_URL` 或 `POSTGRES_TEST_URL`）  
4. Compose **示例**密码占位，**禁止**真实密码入库  
5. 禁止连旧 Java 库与生产库  
6. 每次集成测：独立 database 或 schema；结束后可销毁  
7. CI 与本地 **同一主版本 16**  
8. **apply 前**必须实际验证可连接（本预检阶段未做）  
9. PG 不可用 → **禁止** Complete / 合并 main  

**计划产物（apply 后创建，本阶段仅规划）：**

- `apps/api/docker-compose.party-test.yml`（或仓库 `docker-compose.test.yml`）  
- `psycopg[binary]` dev 依赖  
- `pytest.mark.pg` + `tests/integration/pg/`  
- 文档：`.env.example` 中 `TEST_DATABASE_URL=` 空占位  

### D2 — party_addresses 独立表（ADR-003g）

见 ADR-003g。主档 **删除** 模糊 `address` 第二事实来源。
ORGANIZATION：允许地址 CRUD（授权 + 可见性）。

### D2b — PERSON 地址 v1 临时安全边界（验收缺陷修复）

在 KMS、字段加密、数据分级与专用 PII 权限完成前（独立 change）：

1. PERSON 地址 **禁止** 创建 / 修改 / 删除 / 列表 / 详情
2. Party 列表与详情 **不得** 嵌入 PERSON 地址或数量摘要
3. 即使 `party_addresses` 已有 PERSON 行，API **不得** 返回任何地址字段
4. 不得将 PERSON 地址写入日志、审计 detail、异常信息
5. **不** 新增临时 `party:pii:*` 权限
6. 规则在 **Application Service** 强制执行（禁止仅 Router 拦截）
7. 错误：统一 `AppError`，HTTP 403，code=`PERSON_ADDRESS_FORBIDDEN`
8. 本边界由未来 KMS/PII change 替换，非永久领域模型

### D3 — Git 分支门禁（apply 前必须满足，本阶段不创建）

1. main 干净且与 origin/main 同步  
2. design-party-domain 已归档并推送（**已完成** `0a2e75d`）  
3. implement-party-master 规划人工审批通过（含本预检）  
4. 创建并切换 **`feat/party-master`**  
5. 全部 Party 实现只在该分支  
6. 禁止 main 上开发 Party；禁止 force push  
7. 未过 PG 测试不得合并 main  

### D4 — OpenAPI / 主档无 park_id

1. Party 主档 **无** `park_id` 字段  
2. 园区经 `party_park_relations`  
3. 创建可选 **`initial_park_relation`**（`park_id` + `party_role_id` 或 role_code）— 组合命令，**不是**主档归属  
4. 旧草案/OpenAPI 中主档 `park_id`：**移除**；不作为新模型事实来源  
5. 契约测试：防止 `Party` schema 再出现主档 `park_id`  
6. 同步：DDL、领域、DTO、OpenAPI 一致  

### D5 — 模块布局（apply 后）

同前：`app/modules/party/` + `models/party.py`；增加 Address 实体/服务/仓储。

### D6 — 分层与规则

沿用批准的 20 条强制实现规则；地址写操作审计、不进普通业务日志。

## 实施前门禁清单（apply 批准前）

| # | 门禁 | 当前状态 |
| --- | --- | --- |
| G1 | Docker Compose PG 16 方案写入设计 | **已写** |
| G2 | 实际 `TEST_DATABASE_URL` 可连 PG 16 | **未验证** → BLOCK |
| G3 | party_addresses ADR + 草案 | **已写** |
| G4 | feat/party-master 在 apply 时创建 | **规划已写 / 分支未建** |
| G5 | OpenAPI park_id 任务与契约测试 | **tasks 已写** |
| G6 | openspec validate implement-party-master | 本修订后执行 |

**结论：尚不具备 apply 批准条件（G2）。**

## Risks

| 风险 | 缓解 |
| --- | --- |
| 仅有 Docker 未跑通 PG | 显式 BLOCK；不得用 SQLite 代替 |
| PERSON 地址隐私 | v1 读写全拒绝（含预存行）；Application 层强制；ORGANIZATION 不受影响 |

## Open Questions

结构性：**无**。  
阻塞 apply：PG 16 实际可连尚未完成（人工/后续会话验证后关闭 G2）。  
