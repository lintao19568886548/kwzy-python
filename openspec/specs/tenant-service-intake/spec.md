# Tenant Service Intake Specification

## Purpose

Define tenant-bound and staff-on-behalf service intake with traceability, minimization and strict ownership checks.

## Requirements

### Requirement: Tenant service identity is bound by persisted grants
An authenticated tenant-service user SHALL resolve to one active same-tenant organization Party and bounded same-tenant parks through persisted principal grants. Tenant-facing bodies SHALL NOT accept an authoritative Party or tenant override.

#### Scenario: Forged Party id
- **WHEN** a tenant principal adds another Party id to a request payload or query
- **THEN** the request is rejected and no data outside the bound Party is read or written

### Requirement: Tenant requests are idempotent and traceable
Request creation SHALL require a bounded Idempotency-Key or source reference, create one stable order number, preserve source and reporter evidence and return the same result on an exact replay.

#### Scenario: Mobile retry after timeout
- **WHEN** the same principal retries an identical request with the same Idempotency-Key
- **THEN** one WorkOrder exists and the retry returns that order without duplicate work items or events

### Requirement: Staff on-behalf intake validates every relationship
Staff intake SHALL resolve Party, park, optional unit and contact inside the current tenant and park scope. A Party SHALL have an active lease or park relation for the requested park unless a privileged, reasoned exception is recorded.

#### Scenario: Party from another park
- **WHEN** staff submits a Party and unit that do not belong to the requested park
- **THEN** the whole request fails without creating a WorkOrder or timeline event

### Requirement: Contact and attachment evidence is minimized
Responses, events, audit and logs SHALL return masked phone or controlled contact ids and safe attachment metadata only. Raw attachment bodies, secrets and unrestricted URLs SHALL NOT be stored in the WorkOrder timeline.

#### Scenario: Tenant phone in request
- **WHEN** a tenant request uses its bound primary contact
- **THEN** staff sees only the permitted masked projection and logs contain no raw phone
