# Design: investment leads

## Decisions

1. Lead 为独立聚合，状态与合同分离。
2. convert 需要 `lead:convert` + `party:write`；若建合同另需 `lease:write`。
3. 转化仅创建 DRAFT 合同，不自动激活/占用。
4. 创建线索幂等打开 `LEAD_FOLLOW` 待办；WON 完成、LOST 取消。
5. 电话字段原样存储（长度校验）；不在日志打印全号（审计仅 name 截断）。

## Status machine

```
NEW → FOLLOWING | WON | LOST | CANCELLED
FOLLOWING → WON | LOST | CANCELLED | NEW
LOST → FOLLOWING
WON / CANCELLED 终态
```
