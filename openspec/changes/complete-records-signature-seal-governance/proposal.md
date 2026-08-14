## Why

The rebuild has safe attachment metadata and a narrow lease-document port, but it has no governed records catalogue, retention/hold/access/disposition lifecycle, seal custody and use workflow, or truthful signature-envelope evidence. The legacy system also has no provable archive/signature/seal implementation and the blueprint explicitly identifies missing contract/archive numbering, so treating generic files or a local fake `SIGNED` flag as completion would create legal, audit and security risk.

## What Changes

- Add tenant/park-scoped record categories and deterministic archive numbers, configurable retention, confidentiality, source linkage and evidence-preserving lifecycle states.
- Add immutable record revisions backed by same-scope attachments, server-verified SHA-256 facts, filing/freeze rules and integrity verification without returning storage keys or unrestricted URLs.
- Add legal holds, access/borrow requests, manager decisions, checkout/return/expiry, disposition requests and two-person destruction confirmation with WorkItem, event and audit evidence.
- Add a physical/electronic seal registry, custody history, controlled transfer/loss/retirement and separation-of-duty rules.
- Add seal-use applications linked to exact record revisions, governed approval, authorized execution, immutable usage receipts, copy counts and reasoned cancellation.
- Add signature-provider truth records and envelope/participant/event lifecycles. Local evidence is explicitly `SANDBOX`; missing real credentials or callbacks fail closed and never make a document legally `SIGNED`.
- Harden the existing lease-document sign path so local fake execution cannot be represented as a live legal signature; route contract signing through the governed envelope boundary.
- Add live responsive PC records/seal/signature workspaces with role-aware loading, empty, 403, 409, offline and retry states; no fixture-only buttons or static success responses.
- Add exact runtime/YAML OpenAPI, PostgreSQL constraints and concurrency tests, real HTTP/browser evidence, synthetic legacy-file migration rehearsal and explicit provider/real-data blockers.
- Do not contact production storage/signature providers, migrate real files or authorize destruction without separate human approval.

## Capabilities

### New Capabilities

- `records-classification-retention`: Category, deterministic archive number, confidentiality, source linkage, retention and record lifecycle governance.
- `records-revision-integrity`: Immutable attachment-backed revisions, server-derived checksum facts, filing/freeze and repeatable integrity verification.
- `records-access-disposition`: Legal hold, access/borrow decision, checkout/return/expiry and approval-gated disposition/destruction evidence.
- `seal-registry-custody`: Physical/electronic seal master data, custodian assignment, transfer history, loss/suspension and controlled retirement.
- `seal-use-governance`: Exact-document use applications, approval, separation of duties, execution receipts and cancellation.
- `electronic-signature-envelope`: Truthful provider status, envelope/participant/event lifecycle, sandbox evidence and fail-closed live verification.
- `records-seal-api`: Strict mounted staff APIs, database-derived permissions, scope inheritance, idempotency, optimistic concurrency and exact OpenAPI.
- `records-seal-pc`: Live responsive records, seal-use and signature workspace with actionable errors and evidence drill-down.
- `records-seal-data-migration`: Versioned legacy file/document mapping, quarantine, repeat-safe rehearsal, reconciliation and real-cutover blockers.

### Modified Capabilities

- `lease-domain`: Lease document signing no longer converts a local fake result into legal `SIGNED`; it delegates to the governed signature-envelope truth model.
- `lease-api`: The contract document sign command returns a truthful pending/sandbox result and exposes linked signature evidence without claiming live verification.

## Impact

- Backend: new records/seal domain rules, SQLAlchemy models, repositories, application services, mounted FastAPI routes, WorkItem/outbox/audit integration and forward-only Alembic revisions after `z2c80e5f6a64`.
- Existing contract flow: lease document signature handling and response projection are hardened while approval/version/activation rules remain compatible.
- PC: new archive governance route/view and real HTTP Playwright journeys; navigation and permission seed data are extended.
- Contracts/data: OpenAPI additions, legacy disposition, field mapping, synthetic fixtures/drills and versioned acceptance/visual evidence.
- External systems: no production signature or object-storage endpoint is contacted. Sandbox/fail-closed adapters are delivered; legal validity, real credentials/callbacks, legacy binaries and production disposition remain `NOT_CONNECTED`/`BLOCKED_EXTERNAL_EVIDENCE` until supplied and authorized.
