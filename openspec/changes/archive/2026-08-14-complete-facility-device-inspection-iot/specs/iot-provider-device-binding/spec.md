## ADDED Requirements

### Requirement: Provider records state connection truth
An IoT provider SHALL record adapter kind, credential reference, environment and one of `NOT_CONNECTED`, `SANDBOX`, `CONNECTED` or `DEGRADED`. Secrets SHALL not be persisted in provider rows, API responses, audit or logs.

#### Scenario: Production provider lacks credential
- **WHEN** an operator attempts to mark a production provider CONNECTED without a resolvable credential reference
- **THEN** the transition fails closed and status remains NOT_CONNECTED

### Requirement: Device bindings are tenant and park consistent
A binding SHALL connect one active same-tenant/park FacilityDevice to one same-tenant provider and bounded external device key. Active provider/external keys and active device/provider pairs SHALL be unique.

#### Scenario: Bind foreign park device
- **WHEN** a caller combines a provider with a device from another tenant or park
- **THEN** the request receives non-disclosing denial and no binding is created

### Requirement: Binding lifecycle preserves provenance
Binding activation, external-key rotation and retirement SHALL append actor, reason and time history. Historical alarm events SHALL continue to resolve through the binding version used at ingestion.

#### Scenario: Rotate external device key
- **WHEN** a manager replaces a provider key after hardware swap
- **THEN** the old binding evidence is retired and a new active binding version is recorded without rewriting prior events

### Requirement: Health state cannot be fabricated
Local/sandbox adapters MAY return deterministic health evidence; CONNECTED/DEGRADED production health SHALL require a real adapter result with checked time and bounded diagnostic code. A configuration-only save SHALL not claim a successful provider call.

#### Scenario: Sandbox health check
- **WHEN** a sandbox adapter is checked
- **THEN** the response identifies SANDBOX evidence and is not reported as live production verification
