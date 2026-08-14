# kwzy-python — AI 智慧园区平台

基于旧系统 `kwzg-Java-main`（易租维）业务逆向后的 **Python 重建工程**。

## 当前阶段

| 阶段 | 状态 |
| --- | --- |
| 01 旧系统逆向分析 | ✅ 完成 |
| 02 领域设计 | ✅ 完成 |
| 03 核心库表 DDL v1 | ✅ 完成 |
| 04 OpenAPI 主链草稿 | ✅ 完成 |
| 05 模块化单体 API 骨架 | ✅ 主链已实现（非全域） |
| 05 架构冻结评审 | ✅ 条件通过 |
| 05.1 P0 设计修订包 | ✅ 完成 |
| 06 Step1 Identity+Park+Unit | ✅ 完成并审查 |
| 06 Step1 基础加固（RBAC/错误/日志/审计） | ✅ 完成 |
| 06 Party/Lease/Bill/Payment | ✅ v1 scoped 完成 |
| 06 Workbench 待办 | ⏳ 进行中（账单+合同挂接+summary） |
| 06 前端 `apps/web` | ⏳ 脚手架 |
| 06 ETL | ⏳ 骨架 dry-run |
| 07 工程规范冻结 | ✅ 完成 |
| 全系统验收 | ❌ BLOCKED（见 docs/06-implementation） |

## 目录

```text
kwzy-python/
├── docs/                 # 分析、领域、DDL、OpenAPI、实现与规范
├── apps/
│   ├── api/              # FastAPI 模块化单体
│   └── web/              # Vue3 创新前端（脚手架）
├── tools/etl/            # 迁移映射与 dry-run
└── openspec/             # 变更管理
```

追踪矩阵：`docs/06-implementation/full-rebuild-traceability-matrix.md`

## 快速开始 API

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

应用启动不会调用 `create_all`。首次本地初始化如需默认租户/管理员，请先完成 Alembic，再在 `.env` 显式设置 `BOOTSTRAP_LOCAL_IDENTITY=true` 和一次性 `LOCAL_ADMIN_PASSWORD`；预发与生产禁止该开关。

- 文档：http://127.0.0.1:8000/docs  
- 健康检查：http://127.0.0.1:8000/health  

## 核心设计结论（摘要）

1. **合同与入驻方分离**（旧 `rental_tenant` 拆分）  
2. **账单行模型** + 账期一等公民  
3. **收款/核销/催缴案件** 过程化  
4. **AI 只产草稿**，入账走 Billing  
5. **默认共享库 tenant_id**，兼容独立库  

## 文档入口

- [旧系统分析](docs/01-old-system-analysis/01-project-structure.md)  
- [领域总览](docs/02-domain-design/01-domain-overview.md)  
- [DDL](docs/03-database/01-core-ddl-v1.sql)  
- [OpenAPI](docs/04-api/openapi-v1-core.yaml)  
- [API 工程说明](apps/api/README.md)  
