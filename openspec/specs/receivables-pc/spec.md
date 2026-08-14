# receivables-pc Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Finance workspace uses live API truth
The PC application SHALL show scheduled billing, issued receivables, receipt inbox, match candidates, Payments, unapplied balance, aging cases and treatment approvals from current APIs only. It SHALL NOT use bundled business JSON or static success values.

#### Scenario: Receipt appears after import
- **WHEN** a finance user imports a receipt and reloads the inbox
- **THEN** the row, state and amount match the persisted API response

### Requirement: High-risk actions use explicit review surfaces
Receipt confirmation, later allocation, reversal, dispute resolution and adjustment application SHALL use a drawer/dialog with authoritative amounts, candidate rule explanations and confirmation. Permission-hidden actions SHALL not issue network calls.

#### Scenario: Viewer opens a suggestion
- **WHEN** a user has payment:read but lacks payment:review
- **THEN** candidate details may be read but no confirm action is rendered or called

### Requirement: Provider and workflow state is truthful
The UI SHALL label each external receipt/payment/notification capability `AVAILABLE`, `NOT_CONNECTED` or failed according to the API and SHALL show pending/rejected/applied approval state without optimistic completion claims.

#### Scenario: WeChat provider absent
- **WHEN** capability data reports WeChat NOT_CONNECTED
- **THEN** the page disables live WeChat ingestion and never shows a simulated payment success

### Requirement: Responsive operational states remain usable
At 1440, 820 and 390 pixel widths, workspace tables SHALL collapse to readable cards/drawers without body overflow. Loading, empty, 403, 409, offline and retry states SHALL preserve user input and accessible focus.

#### Scenario: Conflict then reload
- **WHEN** finance confirmation returns 409
- **THEN** the draft remains visible and the user can reload server state before retrying
