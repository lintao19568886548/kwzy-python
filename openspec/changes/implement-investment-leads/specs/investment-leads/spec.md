# investment-leads Specification

## ADDED Requirements

### Requirement: Lead lifecycle

系统 MUST 支持线索创建、列表、更新、输单与转化；状态机须拒绝非法转换。

#### Scenario: Create lead

- **WHEN** 具备 lead:write 的用户提交合法线索
- **THEN** 返回 status=NEW 且 id>0

#### Scenario: Convert creates party

- **WHEN** 对 NEW/FOLLOWING 线索执行 convert
- **THEN** 线索 status=WON 且 party_id 非空

#### Scenario: Permission denied

- **WHEN** 无 lead:read 调用列表
- **THEN** 返回 403
