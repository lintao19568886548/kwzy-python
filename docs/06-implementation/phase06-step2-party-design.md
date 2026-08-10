# Phase06-Step2 Party / implement 预检记录

> 状态：**PREFLIGHT READY**（**未**批准 apply）  
> 标记：`PARTY_APPLY_BLOCKED_NO_POSTGRES`（PG 连接未验证）  
> 日期：2026-08-10  

---

## 1. PostgreSQL 能力矩阵（只读预检）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| Docker | AVAILABLE | `Docker version 29.6.2` |
| Docker Compose | AVAILABLE | `Docker Compose version v5.3.1` |
| Podman | NOT_AVAILABLE | 命令不存在 |
| psql | NOT_AVAILABLE | 命令不存在 |
| pg_isready | NOT_AVAILABLE | 命令不存在 |
| TEST_DATABASE_URL | NOT_SET | 进程环境 |
| POSTGRES_TEST_URL | NOT_SET | 进程环境 |
| DATABASE_URL | NOT_SET | 进程环境 |
| 项目 Docker Compose PG 配置 | NOT_AVAILABLE | 无 compose 文件 |
| Testcontainers | NOT_AVAILABLE | 代码库未检出 |
| PostgreSQL pytest fixture | NOT_AVAILABLE | 仅 SQLite memory |
| CI PostgreSQL service | NOT_AVAILABLE | 无 `.github/workflows` |
| psycopg 驱动 | NOT_AVAILABLE | pyproject 仅 pymysql + sqlite |
| pytest PG marker | NOT_AVAILABLE | 未配置 |

**结论：** 具备用 Docker 拉起 PG 的**本机能力**，但 **PG 16 测试栈与连接均未验证** → **`PARTY_APPLY_BLOCKED_NO_POSTGRES`**。  
**禁止**用 SQLite 代替生产方言验证。

---

## 2. 首选测试方案（规划）

Docker Compose 一次性 `postgres:16`，绑定 127.0.0.1，库名含 test，凭据 env，无真密码入库。  
apply 后实现 compose 文件与 `pytest.mark.pg`；**apply 前须人工/后续会话实际连通验证**。

---

## 3. 分支门禁（apply 前，本阶段不建分支）

- main 干净且同步 origin  
- design 已归档推送（`0a2e75d`）  
- 规划审批通过  
- 创建 `feat/party-master` 再开发  
- 禁 main 直开、禁 force push、禁无 PG 测合并  

---

## 4. 地址与 OpenAPI

- ADR-003g：`party_addresses`  
- 主档无 address / 无 park_id  
- `initial_park_relation` 可选组合命令  
- PERSON 地址写入首版禁止  

---

## 5. 是否可申请 apply

| 项 | 状态 |
| --- | --- |
| 规划结构 | 通过 |
| PG 实际可连 | **未通过** |
| 申请 apply 批准 | **否** |

---

```text
PHASE06-PARTY-IMPLEMENTATION-PREFLIGHT-READY
```
