# 供应链、采购、库存与外包独立验收证据

> 证据日期：2026-08-15（Asia/Shanghai）
> 分支：`feat/full-rebuild-completion`
> 精确实现提交：`3e3c815285025e0462122cbc845c447995c28aaf`

## 判定

供应商治理、物料与仓库目录、采购申请与原生审批、订单确认与分批收货、库存预留/领用/退回/盘点/冲正，以及外包申请、执行、返工、验收和供应商评价已达到 `IMPLEMENTED_AND_VERIFIED` 的本地产品范围。

以下事实没有被扩大为完成：

- ERP、WMS、供应商门户均为 `NOT_CONNECTED`，验收未接触生产。
- 外包结算/发票为 `NOT_INTEGRATED`，本能力不伪造已付款或已同步状态。
- 真实旧数据迁移为 `BLOCKED_PENDING_AUTHORIZED_SCHEMA_EXPORT_TRANSACTION_SNAPSHOT_AND_KEYMAPS`；当前只证明合成数据迁移机制。
- 员工移动端、租户小程序、园企服务、驾驶舱、AI 与全局外部适配器仍由总矩阵保持缺失或阻塞。

## 精确 SHA 全量验收

机器报告：[acceptance-clean-3e3c815.json](acceptance-clean-3e3c815.json)

- 38/38 阶段退出码为 0，总耗时 786,776 ms；报告内 HEAD 精确为 `3e3c815285025e0462122cbc845c447995c28aaf`。
- PostgreSQL 16 空卷从 base 升级到唯一 Alembic head `d6a13e9f0b98`；`current == heads`，并完成 `d6 → c5 → d6`。
- 后端 390 passed，0 failed，0 skipped；370 条为既有上游/时区 API 弃用警告。
- 真实 Uvicorn + PostgreSQL 供应链 HTTP 旅程 56/56，通过采购取消时原生审批撤回、分批收货、领用退回、盘点和外包返工验收；库存按 `10 - 3 + 1 = 8` 对账。
- 性能门禁为 1,000 请求、并发 25、p95 297.794 ms、139.457 RPS、0% 错误。
- 前端 lint、typecheck、6 条 Vitest、production build 和 63 条 Playwright 全部通过。
- OpenAPI 17 条 strict 回归及 YAML strict 通过；供应链有 33 个路径、41 个方法。
- OpenSpec 120/120 strict；敏感信息扫描 1,142 文件、0 命中。
- `pg_dump` 后删除恢复库并再验收，dump 1,830,705 bytes、恢复 182 张表。
- `pip-audit --local` 无已知漏洞（本地非 PyPI 包按工具语义跳过）；Web `npm audit --audit-level=high` 为 0 vulnerabilities。

## 数据迁移演练

合成供应链 fixture 完成 dry run、中断事务回滚、仓库 checkpoint 后恢复、首次应用、幂等重放、隔离、对账和回滚：

- 重放新增数全部为 0；中断后部分行数为 0；回滚后临时 schema 不存在。
- 1 个供应商、1 个园区范围、2 个物料、1 个仓库、1 个采购订单、2 条库存流水、1 个余额和 1 个外包单精确对账。
- 余额为 7.0000，孤儿流水、账实不一致、负余额、原始资质值、伪造审批和伪造集成结算均为 0。
- 4 条记录按 `APPROVAL_EVIDENCE_MISSING`、`PARK_KEY_UNMAPPED`、`SETTLEMENT_EVIDENCE_MISSING`、`STOCK_REFERENCE_UNMAPPED` 隔离。

真实旧数据没有 schema/export/snapshot/key map，不能执行新旧生产数据对账，因此全局数据迁移门禁继续为 `BLOCKED`。

## UI 与视觉证据

浏览器使用真实 FastAPI、PostgreSQL 与 production Vite，执行供应商建档/资质脱敏/停用恢复、采购编辑与审批收货、库存审批领用和盘点、外包返工验收；截图由精确 SHA 全量 Playwright 重新生成并人工复核。

| 视口 | 证据 | 人工复核 |
| --- | --- | --- |
| Desktop | [pc-desktop-supply-outsourcing.png](pc-desktop-supply-outsourcing.png) | 外包验收状态、未集成结算和外部/迁移真相清晰；无重叠、乱码或页面级横向溢出 |
| Tablet 820px | [pc-tablet-supply-procurement.png](pc-tablet-supply-procurement.png) | 采购审批、撤回、订单与收货均来自真实 API；导航、表格与卡片可读 |
| Mobile 390px | [pc-mobile-supply-offline-retry.png](pc-mobile-supply-offline-retry.png) | 断网错误、刷新动作和数据保留可见；表格卡片化，无字段截断或 body 横向溢出 |

## SHA-256

```text
C959B99BB843FF1F13A0B5D395D952B0313436975B942D79B024A0BBFA6AC1C4  acceptance-clean-3e3c815.json
3C48AF4C205B8DF8CD2D04B5AF0C4D5B03DB3604FFED541A912623C81DDB487D  pc-desktop-supply-outsourcing.png
1A5C31CC686243D58AD7C0B67B172B76CD711A98A33E5B4E0F0AEAB667F86367  pc-tablet-supply-procurement.png
5C174DFA16D4D03CA7D5F09C2041FB1185204DD890A978596DB5F54018A03625  pc-mobile-supply-offline-retry.png
```

## 安全、并发与扫描结论

- 权限从数据库派生；供应链资源按租户/园区 404 隔离，资质只保存掩码与独立密钥指纹，未知字段和重复参数 fail closed。
- 采购、收货、领用、退回、盘点、冲正和外包命令绑定幂等键与载荷；同键异载荷拒绝。
- PostgreSQL 行锁和唯一/检查/复合外键保证并发收货只有一个完整赢家、库存不为负且流水追加不可变。
- 新增供应链代码人工复核了 TODO/FIXME/pass/NotImplemented、stub/mock/placeholder/demo/fake、固定成功、静态业务 JSON、未挂载路由、Router/Application 直连 ORM 等扫描命中；未发现把空壳或外部集成计为完成的项。

本纵切 P0/P1/P2 未关闭数均为 0；全项目仍有 6 个未关闭 P1 总控项，因此禁止合并 main 或输出全量 PASS。
