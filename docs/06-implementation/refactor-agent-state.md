# KWZY Python Workspace Agent 状态

| 字段 | 值 |
| --- | --- |
| 更新时间 | 2026-08-10 |
| 当前分支 | `main` |
| HEAD | 见 `git rev-parse HEAD`（merge commit 已推送 origin/main） |
| 状态 | **main 已合并 phase06 主链**（Party/Lease/Bill/Payment） |
| 部署 | **未部署**（合并 ≠ 部署） |
| 允许继续 | 可做部署前检查；生产部署仍须人工确认环境 |

## 合并记录

- 源分支：`feat/payment-collection`（含 stacked 全栈）
- 策略：`merge --no-ff` 进 `main`
- 远程：`origin/main` 已 push（非 force）

## 下一条动作

1. 预发/生产：`alembic upgrade head` 至 `f6d24e5b7c43`
2. 冒烟：登录、园区、主体、合同、账单、收款
3. 延期项：KMS/PII、滞纳金、催缴、在线支付、ETL
