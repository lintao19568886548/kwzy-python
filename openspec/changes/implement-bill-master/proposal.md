# Change: implement-bill-master

## Why
Lease 已交付。阶段 06 需账单主数据与签发，支撑收款核销。依据 `docs/02-domain-design/02-aggregates-and-state-machines.md` §3 与 DDL。

## What
- fee_catalog、bills、bill_lines
- DRAFT/issue/void/discard；禁止 status=OVERDUE；is_overdue 衍生
- 人工出账 API；paid_amount 仅由 Payment 回写（本 change 只预留接口与字段）
- tenant + park scope、权限、审计

## Out
- 自动滞纳金/税费算法、导入/AI/表计出账流水线
- Payment 核销（独立 change）
- 合并 main
