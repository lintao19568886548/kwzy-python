# Tasks: implement-lease-contract

## 0. 门禁

- [x] 0.1 确认 parent 分支 `feat/lease-contract` 基于已推送 Party HEAD（c181e7f）
- [x] 0.2 `openspec validate implement-lease-contract --strict` → valid
- [x] 0.3 PG 测试容器可用（127.0.0.1）

## 1. 领域

- [x] 1.1 Lease 实体与状态机规则（无框架依赖）
- [x] 1.2 Occupancy 冲突与 used_area 投影规则
- [x] 1.3 Domain 单测

## 2. 持久化

- [x] 2.1 ORM models
- [x] 2.2 Alembic revision（唯一 head）
- [x] 2.3 Mapper + Repository（tenant + park scope）
- [x] 2.4 SQLite/PG base→head 与 down/up

## 3. 应用与接口

- [x] 3.1 LeaseService 用例：create/update/list/get/submit/activate/terminate/cancel
- [x] 3.2 单元占用行与条款行维护
- [x] 3.3 OccupancyService 接入 Unit 投影
- [x] 3.4 Router + schemas；替换 stub；注册 main
- [x] 3.5 权限码 bootstrap

## 4. OpenAPI 与文档

- [x] 4.1 更新 openapi-v1-core.yaml
- [x] 4.2 契约与路由一致性测试
- [x] 4.3 实施完成报告

## 5. 测试与验收

- [x] 5.1 API/权限/隔离/冲突/审计测试
- [x] 5.2 pytest -m pg / not pg / 全量（74 passed）
- [x] 5.3 中文 docstring（公开 API 核心方法）
- [x] 5.4 自审 P0/P1=0；容器停止
- [ ] 5.5 commit + 正常 push `feat/lease-contract`（不 merge main）

## 明确不做

- Bill/Payment/押金退还流水
- 旧 rental 适配
- 自动合并 main
