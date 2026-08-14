## Context

Party v1 is already the tenant-scoped customer/tenant master used by Investment and Lease. It has Party, roles, park relations, contacts, organization addresses and a dedicated blacklist history, but its PC page is only a create form and table. The legacy Java estate contains two different concepts that must not be copied blindly: `rental_tenant` mixes customer, contract and rent fields, while Radar `enterprise_profile` derives company profiles, tags and signals from crawler/provider data. V2 must keep Party as the local master, keep Lease facts in Lease, and keep provider claims explicitly unverified.

The shared approval, audit, attachment, workbench event and park-scope facilities already exist. PostgreSQL 16 and Alembic are authoritative. The legacy schema/sample, external registry credentials and production object storage are unavailable, and no production call is authorized.

## Goals / Non-Goals

**Goals:**

- Close the local product journey for organization profile maintenance, company relationships, credential evidence, tags and explainable risk.
- Preserve strict tenant and park visibility on every node and edge, including identifier-based child resources.
- Keep personal identity numbers outside the schema/API until a separate KMS/envelope-encryption change exists.
- Provide optimistic concurrency, append-only evidence where appropriate, auditable state transitions and deterministic read models.
- Replace the basic Party PC page with a responsive, real-API enterprise workspace.
- Rehearse legacy-shaped data migration without claiming real-data or live-provider completion.

**Non-Goals:**

- Live business-registry, court, credit bureau, Radar crawler or WeCom integration.
- Automatic AI scoring or automatic external-profile refresh.
- Contract/rent/billing facts on Party.
- Personal identity documents, plaintext certificate identifiers, production deployment or real legacy data migration.

## Decisions

### 1. Party remains the aggregate root; enterprise data uses bounded child tables

`party_enterprise_profiles` is one-to-one with an `ORGANIZATION` Party. Relationships, credentials, tags and risk signals are separate tenant-scoped tables. Every child carries `tenant_id` and uses composite `(tenant_id, party_id)` foreign keys after adding a non-destructive unique key to `parties(tenant_id,id)`. Relationship endpoints each use composite tenant foreign keys.

This is preferred over adding many nullable columns to `parties`, because PERSON remains a valid Party type and child lifecycles/evidence differ. A separate Radar-owned company master was rejected because it would reintroduce competing customer truth.

### 2. Profile completeness is derived, bounded and explainable

Completeness is never client supplied. The read model awards: credit code 15; legal representative 10; establishment date 10; registered capital/currency 10; registration status 5; industry code/name 10; business scope 10; active REGISTERED address 10; active primary contact 10; active BUSINESS_LICENSE credential 10. The response returns the score and missing dimension codes. Updates require `lock_version`; stale writes return 409.

This fixed formula is preferred over an opaque or provider-derived score. It can be reconciled to source records and does not imply creditworthiness.

### 3. Relationship graph has explicit direction and bounded cycle rules

Relationship types are `PARENT_OF`, `INVESTED_IN`, `COMMON_CONTROL` and `BUSINESS_PARTNER`. `PARENT_OF` and `INVESTED_IN` are directional; symmetric types are stored canonically with the lower Party id as source. Active duplicate edges are prevented by a partial unique index. `PARENT_OF` rejects self-links and any edge that makes the target reach the source through active parent edges. A tenant-scoped PostgreSQL advisory transaction lock serializes hierarchy changes before the recursive cycle query. Ending an edge is a state transition, not deletion.

### 4. Organization credentials store evidence metadata, not raw identifiers

Credential types are `BUSINESS_LICENSE`, `TAX_REGISTRATION`, `ORGANIZATION_CODE`, `INDUSTRY_LICENSE` and `OTHER`. A credential references an ACTIVE attachment belonging to the same tenant and a park visible through the Party, or a tenant-level attachment for an unscoped Party. Optional organization identifiers are accepted only on create/update transport, normalized in memory, reduced to SHA-256 fingerprint plus a masked suffix, and never persisted/logged/audited in plaintext. Verification states are `UNVERIFIED`, `LOCALLY_REVIEWED`, `EXTERNALLY_VERIFIED` and `REJECTED`; only local review is available without a provider, and `EXTERNALLY_VERIFIED` cannot be set through local APIs.

Personal identity credentials and person-Party credentials are rejected. Attachment storage remains governed by the existing attachment module.

### 5. Tags and risk signals retain provenance

Tags are unique per active `(party, normalized_name, tag_type)`, include `MANUAL/MIGRATION/EXTERNAL` source, confidence in `[0,1]`, verification state and lifecycle. External/migration tags start unverified.

Risk signals are append-only facts with category, severity `LOW/MEDIUM/HIGH/CRITICAL`, occurred time, source, safe summary, optional attachment and unique source reference. Resolution appends a separate resolution record rather than mutating the signal. The current enterprise risk summary is derived from unresolved signals using max severity and counts. Existing Party `risk_status=NORMAL/BLACKLISTED` remains an independent explicit blacklist control and is shown alongside the derived summary.

### 6. Permissions separate ordinary profile, credential and risk access

`party:read` and `party:write` govern non-sensitive profile, relationship and tag operations. `party:credential_read` and `party:credential_manage` govern credential metadata and local review. `party:risk_read` and `party:risk_manage` govern full risk signals/resolutions and the existing blacklist. Search/list responses never expose raw contact phone, credential fingerprints or risk summaries without their dedicated permission. Park visibility follows the existing Party visibility graph; a relationship is visible only when both endpoints are visible.

### 7. UI is a single enterprise directory with live detail tabs

`PartiesView` becomes a directory with search, status/risk/industry filters, completeness and park indicators. Organization rows open a drawer with overview, contacts/addresses/parks, related companies, credentials, tags and risk. Mutations are permission-gated and use live APIs. Desktop uses table + drawer; narrow tablet/mobile uses cards + full-width drawer. Loading, empty, 403, 409, offline and retry are first-class states. Provider status is visibly `NOT_CONNECTED` and no refresh action implies live registry access.

### 8. Migration is synthetic until real evidence exists

The ETL accepts a versioned legacy-shaped fixture for rental tenant, enterprise profile, tag, relationship, credential metadata and risk signal records. It fingerprints/quarantines ambiguous Party matches, plaintext personal IDs, missing attachments, invalid relationships and unknown enums. Apply is transactional, idempotent by source key and supports interruption rollback, reconciliation and schema rollback. Real readiness remains blocked on authorized schema/sample and Party/park/user/attachment mappings.

## Risks / Trade-offs

- [Risk] Existing attachment rows do not have composite tenant foreign keys from every consumer → validate tenant/park in the repository and add database composite keys where the current table shape permits; keep a regression test for cross-tenant attachment ids.
- [Risk] Application cycle checks can race → serialize hierarchy changes with a tenant advisory transaction lock and verify in PostgreSQL concurrent tests.
- [Risk] SHA-256 fingerprint of a low-entropy identifier can be guessed → identifiers are organization identifiers, not personal secrets; raw values are never returned or logged. A future KMS change may replace the fingerprint scheme without schema exposure.
- [Risk] Derived risk may be mistaken for an external credit score → label it as local unresolved-signal severity, show provenance, and keep provider status explicit.
- [Risk] Profile scope can expand indefinitely → only the bounded fields in the specs are included; financial, contract, payment and AI facts stay in their contexts.

## Migration Plan

1. Add one forward Alembic revision after `s5b13d8e0f97`, including composite tenant keys, checks, partial uniques and indexes.
2. Deploy code that treats absent profiles/children as an empty valid state; no destructive backfill is required.
3. Run PG16 fresh upgrade, `head→-1→head`, metadata parity and concurrent hierarchy/tag/source-id tests.
4. Run synthetic dry/apply/interruption/reapply/reconcile/rollback and preserve reports without raw PII.
5. Roll back code first if needed; downgrade only the new revision after proving no dependent application is active. Real legacy cutover requires a separate authorized runbook execution.

## Open Questions

- Exact legacy schema names, identifier semantics and provider verification fields remain unknown until an authorized dump/sample arrives; they are migration blockers, not assumptions.
- Live external verification and key management remain separate integration/security changes.
