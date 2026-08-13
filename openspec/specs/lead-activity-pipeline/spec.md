# lead-activity-pipeline Specification

## Purpose
定义线索电话、备注、拜访、报价和谈判活动的不可覆盖时间线，以及受控阶段推进和跟进 SLA 投影。该规格确保业务事实可审计、非法跳转被拒绝，并使列表、待办与漏斗逾期口径保持一致。

## Requirements

### Requirement: Append-only activity timeline
系统 MUST 以 append-only 活动记录电话、备注、拜访、报价和谈判事实，包含操作者、发生时间、内容、下一跟进和阶段变化，禁止覆盖历史活动。

#### Scenario: Add visit activity
- **WHEN** 负责人为线索提交合法拜访活动和下一跟进时间
- **THEN** 活动追加到时间线，Lead 的最近/下一跟进投影更新且旧活动不变

### Requirement: Controlled pipeline transitions
阶段 MUST 按 `NEW→CONTACTING→VISITING→QUOTING→NEGOTIATING→WON/LOST` 前进；允许带理由回退到开放阶段，终态只能通过明确的 reopen/merge 策略处理。

#### Scenario: Invalid stage jump
- **WHEN** 用户尝试从 NEW 直接推进到 NEGOTIATING 且无管理覆盖理由
- **THEN** 返回 `LEAD_STAGE_INVALID`，Lead 和活动均不变化

#### Scenario: Lost reason required
- **WHEN** 用户将线索标记 LOST
- **THEN** 必须提供输单原因，系统关闭跟进待办并保留终态事件

### Requirement: Follow-up SLA projection
开放线索 MUST 维护下一跟进时间并与 `LEAD_FOLLOW` 待办一致；列表和指标 MUST 能识别逾期但不得因读取修改业务历史。

#### Scenario: Follow-up becomes overdue
- **WHEN** `next_follow_up_at` 早于当前时间且线索仍开放
- **THEN** 查询返回 overdue=true，待办仍 OPEN，漏斗逾期数与列表一致
