## ADDED Requirements

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
