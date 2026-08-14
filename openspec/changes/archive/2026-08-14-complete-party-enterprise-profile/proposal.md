## Why

The rebuilt Party context currently stops at a name, contact, address, role and binary blacklist. It cannot replace the legacy enterprise-profile and rental-tenant user journeys because operators cannot maintain a governed company profile, related-company graph, organization credentials, tags or an explainable risk view from real Party records.

## What Changes

- Add one tenant-scoped enterprise profile for each `ORGANIZATION` Party, with validated registration, industry, scale and business fields plus a server-derived completeness result.
- Add temporal related-enterprise edges with bounded relationship types, optional ownership percentage, source/evidence metadata and cycle/self-link protection where the relationship is hierarchical.
- Add organization credential records that reference protected attachments, expose only masked identifiers/fingerprints, track validity and verification state, and never introduce personal identity-number storage.
- Add append-only enterprise risk signals and derived current risk summaries without weakening the existing dedicated blacklist workflow; manual resolution is separately audited.
- Add governed enterprise tags with source, confidence and active/inactive lifecycle; externally sourced claims remain `UNVERIFIED` until locally reviewed.
- Replace the current basic Party page with a live API-backed enterprise directory and detail drawer covering profile, contacts, parks, relationships, credentials, tags, risk and completeness on desktop/tablet/mobile.
- Add a synthetic legacy-profile migration rehearsal with dry-run, interruption rollback, idempotent reapply, quarantine, reconciliation and rollback. Real legacy migration remains blocked until an authorized schema dump and desensitized sample are supplied.
- Add strict OpenAPI, tenant/park/field-permission, IDOR, parameter-pollution, concurrency, real HTTP and browser regression coverage.
- Keep external business-registry/Radar providers `NOT_CONNECTED`; no refresh button or local fixture may claim live verification.

## Capabilities

### New Capabilities

- `party-enterprise-profile`: Governed organization profile fields, normalization, optimistic concurrency and derived completeness.
- `party-enterprise-relationships`: Tenant-safe temporal related-company graph and hierarchy invariants.
- `party-enterprise-credentials`: Attachment-backed organization credential metadata with masking and verification boundaries.
- `party-enterprise-tags`: Traceable enterprise tags, confidence and lifecycle.
- `party-enterprise-risk-profile`: Append-only risk signals, resolution and deterministic summary alongside blacklist state.
- `party-enterprise-pc`: Responsive enterprise directory and live detail workspace.
- `party-enterprise-data-migration`: Synthetic legacy enterprise-profile/tag migration and real-data readiness gates.

### Modified Capabilities

- `party-api`: Add strict enterprise profile, relationship, credential, tag and risk subresources.
- `party-data-isolation`: Extend tenant, park and dedicated field-permission enforcement to the new Party graph.

## Impact

- Backend: Party domain/application/repository/interface, shared attachment lookup, permission seeds, audit/event publication and OpenAPI.
- Persistence: one forward Alembic revision after `s5b13d8e0f97`; existing migrations remain immutable.
- Frontend: Party API client, route/navigation and `PartiesView` replacement; no local JSON or provider simulation.
- Operations: local PostgreSQL 16 acceptance, synthetic ETL evidence, backup/restore and performance coverage expand to the enterprise profile slice.
- External systems: legacy MySQL, business-registry/Radar and object-storage production providers are not contacted and remain explicit external blockers.
