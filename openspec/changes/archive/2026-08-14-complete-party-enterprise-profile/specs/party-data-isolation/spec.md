## ADDED Requirements

### Requirement: Enterprise profile graph is tenant isolated
All profile, relationship, credential, tag, risk and resolution queries/writes SHALL derive tenant id from authenticated context and enforce tenant-scoped parent/child foreign keys. Client tenant ids SHALL be forbidden.

#### Scenario: Fabricated tenant id
- **WHEN** a request includes another tenant id in any body or query field
- **THEN** strict validation rejects it and no cross-tenant data is accessed

### Requirement: Relationship visibility requires both endpoints
A related-company edge SHALL be returned or mutated only when both endpoint Parties are visible under the caller's Party park scope, except an authorized `party:manage_unscoped` caller may manage an edge whose endpoints are both unscoped.

#### Scenario: One endpoint outside park scope
- **WHEN** the source Party is visible but the target Party has active relations only outside the caller's park scope
- **THEN** the relationship is hidden and identifier access returns not found

### Requirement: Enterprise child writes follow Party write visibility
Profile, relationship and tag writes SHALL require `party:write` plus existing Party visibility, or `party:manage_unscoped` for an unscoped Party. Credential and risk actions SHALL additionally require their dedicated permissions and SHALL not be granted by park scope alone.

#### Scenario: All parks without credential permission
- **WHEN** a caller has all-parks scope and party:write but lacks party:credential_manage
- **THEN** credential creation is denied

### Requirement: Field-level details are permission filtered
Enterprise directory/detail serializers SHALL omit credential detail without `party:credential_read` and omit local risk summary/history without `party:risk_read`. Query filters on hidden fields SHALL also require the matching read permission.

#### Scenario: Hidden risk filter
- **WHEN** a party:read-only caller supplies a local risk severity filter
- **THEN** the API denies the filter rather than revealing matching counts

### Requirement: Enterprise writes audit without sensitive payloads
Successful profile, relationship, credential, tag and risk-resolution writes SHALL commit audit records in the same transaction. Audit detail SHALL use ids, state transitions, masked suffixes and safe codes only, excluding raw identifiers, full contact/address values and risk evidence content.

#### Scenario: Credential audit
- **WHEN** a credential is created with an identifier and attachment
- **THEN** audit includes credential/Party/attachment ids and type but not the raw identifier or attachment content
