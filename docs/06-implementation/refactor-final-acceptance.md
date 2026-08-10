# KWZY Python 重构最终验收包（开发侧）

> 生成时间：2026-08-10  
> 状态：**主链能力已在 feature 栈交付并推送**；**未合并 main、未部署生产**。  
> 人工需批准：merge 顺序、部署与延期项处理。

---

## 1. 完成范围（本阶段必须实现）

| 能力 | 分支 | 关键 commit / head | OpenSpec | 迁移 revision |
| --- | --- | --- | --- | --- |
| Step1 Identity+Park+Unit | main / 历史 | 已合历史 | archive | …→9f17fd2e9180 |
| Party | `feat/party-master` | `d7e1300` | implement-party-master | c3a91b2e4f10 |
| Lease | `feat/lease-contract` | `f173996` 一带 | implement-lease-contract | d4b02c3f5a21 |
| Bill | `feat/bill-master` | `d2de1e8` | implement-bill-master | e5c13d4a6b32 |
| Payment 收款登记 | `feat/payment-collection` | 本栈 tip | implement-payment-collection | f6d24e5b7c43 |

**API 主链：** Auth → Parks/Units → Parties → Leases → Bills → Payments  

**安全：** tenant 隔离、park scope、统一 AppError、审计、PERSON 地址 v1 全拒绝、Payment 非在线网关。

**测试（payment tip）：** 全量 pytest **78 passed**；Alembic 唯一 head `f6d24e5b7c43`；PG 16 base→head 验证通过。

---

## 2. 未完成 / 批准延期

| ID | 项 | 原因 | 后续 |
| --- | --- | --- | --- |
| D-PII-KMS | PERSON 地址可读/加密 | v1 安全边界全拒绝 | 独立 KMS/PII change |
| D-LATE-FEE | 滞纳金/复杂税费 | 无额外批准算法 | 产品规则 change |
| D-IMPORT-AI-METER | 导入/AI/表计出账 | 非人工主链 v1 | 独立 change |
| D-COLLECTION-CASE | 催缴案件/SMS | 主链未阻塞 | 独立 change |
| D-ONLINE-PAY | 在线支付网关 | 明确二期 | 二期 |
| D-ETL | 旧 Java ETL | 未批准连接旧库 | 人工方案 |
| D-MERGE-MAIN | 合并 main / 发布 | 强制人工 | 本报告 §5 |

---

## 3. 分支与合并顺序（建议）

```text
main
  └─ feat/party-master          (d7e1300)
       └─ feat/lease-contract   (含 Party)
            └─ feat/bill-master
                 └─ feat/payment-collection  ← 当前 tip（含全栈）
```

**推荐 merge：** 自底向上 PR 栈，或一次 squash merge `feat/payment-collection` → main（人工审阅后）。

---

## 4. 数据库 revision 链

```text
44cb70117ff4 → 8c2f4aa10b7d → 9f17fd2e9180
  → c3a91b2e4f10 (party)
  → d4b02c3f5a21 (lease)
  → e5c13d4a6b32 (bill)
  → f6d24e5b7c43 (payment)  [head]
```

---

## 5. 部署前检查清单

- [ ] 人工 code review 各 PR  
- [ ] 在预发 PostgreSQL 16 执行 alembic upgrade head  
- [ ] 确认无生产 `.env`/密钥入库  
- [ ] PERSON 地址策略与合规确认  
- [ ] 备份与回滚演练（downgrade 至上一业务 revision）  

## 6. 回滚方案

- 应用：回退部署镜像/标签至上一版本  
- 库：`alembic downgrade -1` 逐级；生产勿跳 revision  
- 数据：Payment/Bill 写操作依赖审计日志可追溯  

## 7. 已知风险

- SQLite 部分索引语义弱于 PG  
- Application 仍持有 ORM 实例（import 门禁通过）  
- EXPIRING 合同定时任务未产品化  
- OpenAPI 中部分历史 Bills 路径与实现细节需人工对照（核心 `/bills` `/payments` 已挂载）  

---

## 8. 结论标记

开发侧主链交付完成；**等待人工批准合并 main 与部署**。

`KWZY_PYTHON_REFACTOR_READY_FOR_FINAL_HUMAN_ACCEPTANCE`
