# kwzy-python — AI 智慧园区平台

基于旧系统 `kwzg-Java-main`（易租维）业务逆向后的 **Python 重建工程**。

## 当前阶段

| 阶段 | 状态 |
| --- | --- |
| 01 旧系统逆向分析 | ✅ 完成 |
| 02 领域设计 | ✅ 完成 |
| 03 核心库表 DDL v1 | ✅ 完成 |
| 04 OpenAPI 主链草稿 | ✅ 完成 |
| 05 模块化单体 API 骨架 | ✅ 完成（stub） |
| 05 架构冻结评审 | ✅ 条件通过 |
| 05.1 P0 设计修订包 | ✅ 完成 |
| 06 Step1 Identity+Park+Unit | ✅ 完成并审查 |
| 06 Step1 基础加固（RBAC/错误/日志/审计） | ✅ 完成 |
| 07 工程规范冻结 | ✅ 完成 |
| 06 后续 Party/Lease/Bill… | ⏳ 待指令 |

## 目录

```text
kwzy-python/
├── docs/
│   ├── 01-old-system-analysis/   # 旧系统八阶段分析
│   ├── 02-domain-design/         # 领域设计
│   ├── 03-database/              # DDL + 说明
│   └── 04-api/                   # OpenAPI
└── apps/
    └── api/                      # FastAPI 模块化单体
```

## 快速开始 API

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

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
