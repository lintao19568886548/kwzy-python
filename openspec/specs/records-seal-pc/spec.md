# records-seal-pc Specification

## Purpose
TBD - created by archiving change complete-records-signature-seal-governance. Update Purpose after archive.
## Requirements
### Requirement: PC workspace uses live APIs
The PC SHALL provide records catalogue/detail, retention/hold/access/disposition, seal registry/custody/use and signature-envelope views backed by live APIs. It SHALL NOT treat local JSON, placeholders or fixed success responses as evidence.

#### Scenario: Record filed from desktop
- **WHEN** an authorized records manager uploads, revises and files a record
- **THEN** the resulting number, checksum, retention and timeline are reloaded from the API

### Requirement: Actions are role aware
The UI SHALL request only data allowed by the current permissions, hide or disable unauthorized actions and preserve server 403/404 distinctions without using client visibility as authorization.

#### Scenario: Custodian-only execution
- **WHEN** a reader without seal execution permission opens an approved use
- **THEN** evidence is readable as allowed but the execution control is absent and no execute request is sent

### Requirement: Truth states are legible
Signature provider and envelope state SHALL display text labels for SANDBOX, NOT_CONNECTED, DEGRADED and live verification in addition to color. Sandbox completion SHALL never be labelled legal/production signed.

#### Scenario: Sandbox envelope displayed
- **WHEN** a sandbox envelope completes
- **THEN** the page displays simulated/sandbox evidence and live verification false

### Requirement: Responsive and failure states are actionable
Desktop, tablet and 390-pixel layouts SHALL support loading, empty, validation, 403, 409, offline and retry states without horizontal body overflow, clipped actions or loss of entered purpose/reason data.

#### Scenario: Mobile offline use application
- **WHEN** submission fails offline at 390 pixels
- **THEN** seal, record, purpose and copy count remain populated for retry
