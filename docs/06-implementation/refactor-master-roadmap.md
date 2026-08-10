# KWZY Python 重构总路线图（Master Roadmap）

> 更新：2026-08-10（Payment 交付）

## 1. 能力模块

| 序 | 能力 | OpenSpec | 分支 | 状态 |
| --- | --- | --- | --- | --- |
| 0 | Step1 | archive | main | 完成 |
| 1 | Party | implement-party-master | feat/party-master | 完成并推送 |
| 2 | Lease | implement-lease-contract | feat/lease-contract | 完成并推送 |
| 3 | Bill | implement-bill-master | feat/bill-master | 完成并推送 |
| 4 | Payment | implement-payment-collection | feat/payment-collection | 完成（本 tip） |
| 5 | 收口/最终验收 | — | tip | 见 refactor-final-acceptance.md |
| 6 | 合并 main | — | — | **人工** |

## 2. 延期

见 refactor-final-acceptance.md §2。

## 3. 方言

PostgreSQL 16 权威；SQLite 测。
