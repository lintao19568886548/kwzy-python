## ADDED Requirements

### Requirement: Party master schema has no park_id
The formal Party API schema for the new model SHALL NOT include a top-level park_id field representing Party ownership.

#### Scenario: Contract test rejects master park_id
- **WHEN** OpenAPI or schema contract tests run
- **THEN** Party components do not define required or optional park_id as master ownership

### Requirement: Optional initial_park_relation command
Create Party MAY accept an optional initial_park_relation object containing park linkage fields such as park_id and party_role_id. This command SHALL create a park relation and SHALL NOT store park_id on the Party master row.

#### Scenario: Create with initial relation
- **WHEN** create includes initial_park_relation
- **THEN** a party_park_relations row is created and Party master has no park_id column value

### Requirement: Park relations via sub-resource
Listing and managing Party parks SHALL use the park-relations sub-resource, not a master park_id field.

#### Scenario: Query relations endpoint
- **WHEN** clients need Party parks
- **THEN** they use /parties/{id}/park-relations

### Requirement: Legacy OpenAPI park_id removed from new contract
Existing draft or stub OpenAPI Party.park_id SHALL be removed from the new formal contract or must not remain a source of truth. Compatibility adapters for legacy rental APIs are out of this change.

#### Scenario: openapi-v1-core Party without ownership park_id
- **WHEN** docs/04-api/openapi-v1-core.yaml is synchronized for Party
- **THEN** Party schema does not present park_id as master ownership

### Requirement: Cross-document consistency
Domain design, DDL, DTO, and OpenAPI for Party ownership and addresses SHALL remain consistent: no master park_id, no master address free-form fact field, addresses via party_addresses.

#### Scenario: Docs alignment checklist
- **WHEN** implementation tasks complete documentation sync
- **THEN** the three sources agree on ownership and address models
