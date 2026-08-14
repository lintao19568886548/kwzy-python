## ADDED Requirements

### Requirement: Asset template permission separation
The system SHALL seed and enforce separate `asset.template.read` and `asset.template.write` permissions from park/unit read and write permissions using current database grants.

#### Scenario: Fabricated template permission
- **WHEN** a caller without template write declares that permission in a token claim, header or body
- **THEN** current database authorization denies the mutation and no success audit is recorded
