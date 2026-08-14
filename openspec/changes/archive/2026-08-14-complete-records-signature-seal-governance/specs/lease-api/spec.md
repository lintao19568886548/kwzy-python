## ADDED Requirements

### Requirement: Sign command returns envelope truth
`POST /leases/{contract_id}/documents/{document_id}/sign` SHALL return linked signature envelope id, status, provider status and `live_verified` together with the lease detail. It SHALL not describe sandbox completion as live signed.

#### Scenario: Sandbox response
- **WHEN** the sign command runs under the local sandbox adapter
- **THEN** the response reports SANDBOX_COMPLETED and live_verified false while the source document status is APPROVED

### Requirement: Signature provider failures are stable and retryable
Missing provider configuration, timeout, rejected event and unavailable evidence SHALL return documented stable error codes without changing the lease document to SIGNED. Same command replay SHALL not create multiple envelopes.

#### Scenario: Provider not configured
- **WHEN** a production sign command has no CONNECTED provider
- **THEN** the API returns 503 `SIGNATURE_PROVIDER_NOT_CONFIGURED` and leaves document evidence unchanged
