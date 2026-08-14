## ADDED Requirements

### Requirement: Enterprise directory uses live API data
The PC application SHALL provide an enterprise directory sourced only from current API/database responses, with keyword, status, blacklist, local-risk, registration, industry and completeness filters, bounded pagination and truthful totals. It SHALL NOT use bundled local JSON or static chart values.

#### Scenario: Filtered directory
- **WHEN** an authorized user filters by industry and minimum completeness
- **THEN** the displayed cards/table and total match the live API response

### Requirement: Enterprise detail consolidates governed subresources
Selecting an organization SHALL open a drawer/workspace containing overview/completeness, contacts, addresses, park roles, related companies, credential evidence, tags, local risk history and blacklist state subject to permissions.

#### Scenario: Credential permission absent
- **WHEN** a user without credential-read permission opens detail
- **THEN** the credential panel is unavailable and no credential metadata is fetched or rendered

### Requirement: Enterprise mutations use visible permission and conflict states
Profile, relationship, credential, tag and risk actions SHALL be visible only for their database-derived permissions and SHALL handle 403/404/409/422 without optimistic UI claims. A 409 SHALL preserve the user's input and offer reload/retry.

#### Scenario: Stale profile save
- **WHEN** a profile save returns 409
- **THEN** the drawer shows a conflict state, retains the draft and offers a reload action

### Requirement: Responsive layouts remain usable
Desktop SHALL use a table and side drawer; tablet and mobile SHALL use non-overflowing cards and a full-width detail surface. Controls SHALL have visible focus and accessible labels, and body-level horizontal overflow SHALL be absent at 1440, 820 and 390 pixel widths.

#### Scenario: Mobile enterprise detail
- **WHEN** the directory and detail are used at 390 pixels width
- **THEN** all required content and actions remain readable without body horizontal scrolling

### Requirement: Runtime states are first-class
The directory and every detail section SHALL show loading, empty, permission-denied, offline/error and retry states. Provider-dependent sections SHALL show `NOT_CONNECTED` when no verified adapter exists and SHALL NOT offer a fake refresh success.

#### Scenario: Offline then retry
- **WHEN** a live directory request fails and a later retry succeeds
- **THEN** the page first shows an error/retry state and then renders server records without a full reload
