# lease-occupancy Specification

## Purpose
定义合同激活时的出租单元容量冲突检查及 `used_area` 占用投影规则。该规格确保有效合同占用不会超过可租容量，激活和终止会一致重算投影，并禁止客户端直接修改派生占用面积。

## Requirements

### Requirement: Occupancy conflict detection on activate
Before activating a contract, the system SHALL verify that each contracted unit is rentable and that projected occupied area does not exceed rentable capacity for active occupancy set.

#### Scenario: Overlapping active occupancy blocked
- **WHEN** unit U is fully occupied by an ACTIVE contract and another contract tries to activate overlapping area on U
- **THEN** activation fails with a conflict business code

### Requirement: used_area projection
units.used_area SHALL be maintained as the sum of occupied_area from contracts in ACTIVE or EXPIRING status. Business APIs SHALL NOT accept direct client writes to used_area.

#### Scenario: Activate updates used_area
- **WHEN** a contract activates with occupied_area A on unit U
- **THEN** U.used_area increases by A (subject to recomputation rules)

#### Scenario: Terminate decreases used_area
- **WHEN** that contract terminates
- **THEN** U.used_area is recomputed without that contract's occupancy
