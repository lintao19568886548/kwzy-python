## Context

Current attachments are tenant/park scoped and validate filename, MIME and magic bytes, but `biz_type/biz_id` are caller supplied and there is no record classification, archive number, retention, legal hold, borrow or disposition aggregate. Lease documents are append-only versions, yet local/test environments call `LocalFakeSignatureAdapter` and append a document whose status is `SIGNED` even though `live_verified=false`. There is no seal register, custody history or approval-gated use record.

The legacy evidence has no archive/signature/seal controller, page or DDL family. Its rental tenant table has neither contract nor archive numbering, and the blueprint records this as a real gap. This change therefore designs the required business controls from authoritative operational rules rather than copying an absent or unsafe legacy implementation.

## Goals / Non-Goals

**Goals:**

- Deliver tenant/park-scoped records classification, immutable revisions, retention/hold, governed access and disposition.
- Deliver seal master/custody/use evidence with approval and separation of duties.
- Deliver truthful signature envelopes whose local evidence is visibly sandbox and whose live path fails closed.
- Reuse attachments, platform approvals, WorkItems, outbox and audit without weakening their isolation or transaction rules.
- Provide PostgreSQL, API, browser and synthetic migration evidence suitable for independent acceptance.

**Non-Goals:**

- Asserting legal validity for a sandbox signature or connecting a real certificate authority/signature provider without contracts and credentials.
- Deleting production files or executing irreversible archive destruction; local tests use synthetic records only.
- Implementing OCR, full-text search, WORM hardware, HSM/key custody or qualified trust-service certification.
- Replacing the independent employee mobile app or tenant mini-program with a responsive PC page.

## Decisions

### Records are governed metadata over immutable attachment evidence

`RecordFile` owns tenant, optional park, deterministic `record_no`, category, title, confidentiality, source linkage, status, retention date and lock version. `RecordRevision` references an ACTIVE attachment with the same tenant/park/business owner and stores server-derived SHA-256, size, MIME, version and creator. Filing requires at least one revision, freezes its revision set and changes require a new record/revision rather than editing evidence. Generic attachments remain a storage boundary; a caller-supplied attachment alone is never an archive record.

Alternative considered: add archive flags directly to `attachments`. Rejected because one binary may be transient business evidence while archive classification, retention, access and disposition are separate governed facts.

### Archive numbers and retention are deterministic and database protected

Categories have tenant-unique codes and retention modes `YEARS/PERMANENT`. Record numbers use a tenant/category/year sequence protected by a unique constraint and row lock. Filing snapshots the category policy so later category edits do not rewrite old obligations. `retention_until` is derived by the server and cannot be shortened by normal edits.

### Holds, access and disposition are append-only control flows

Legal holds have ACTIVE/RELEASED events and block disposition. Access requests capture scope, purpose and requested expiry; approval is a native platform approval keyed by stable business id. Checkout/return updates the request with expected version and does not unlock the underlying file URL. Disposition requires expired retention, no active hold/loan/signature/use dependency, an approved platform application and two distinct confirmations; the operation marks records/revisions disposed and writes a cryptographic manifest but never physically deletes object storage in this change.

### Seal custody and use are separate aggregates

`SealAsset` stores a tenant-unique code, kind, status, park scope and current custodian. Every assignment/transfer/accept/loss/restore/retire action appends `SealCustodyEvent`. A pending transfer does not change custody until accepted. `SealUseApplication` references an exact record revision, copy count, purpose and seal; submission creates one platform approval. Only an approved application may be executed by the current custodian, and applicant/approver/executor separation is enforced for high-risk seal kinds. Execution appends one immutable receipt containing revision checksum, operator, timestamp, copies and evidence attachment.

Alternative considered: store `seal_id` on a generic approval. Rejected because custody, document checksum and immutable receipt are legal/audit evidence beyond a workflow task.

### Signature provider truth is independent of business status

`SignatureProvider` status is `NOT_CONNECTED/SANDBOX/CONNECTED/DEGRADED` and stores only an environment credential reference. `SignatureEnvelope` references an exact record revision and has `DRAFT/PENDING/SANDBOX_COMPLETED/COMPLETED/DECLINED/VOID/FAILED`; `live_verified` may be true only for `COMPLETED` after a verified provider event. Participants and provider events are append-only. Exact provider event replay returns the existing event; changed payload with the same source id is rejected.

The lease sign command creates or returns a governed envelope. In local/test it records `SANDBOX_COMPLETED` and leaves the lease document at `APPROVED`; production without a configured CONNECTED provider returns 503. Only a verified live completion may append a lease document status `SIGNED`.

### Cross-domain approvals are queried, not duplicated

Records and seal applications call the existing `ApprovalService` with dedicated native definitions and store `approval_id`. Execution reads the authoritative approval status under tenant/park scope. Direct business-table approval flags are not accepted. WorkItems deep-link to the application and approval center; outbox and audit writes share the same transaction.

### APIs are strict and scope inherited from parent aggregates

All request models reject unknown fields and duplicate query parameters. Child records are loaded through tenant/park-scoped parents and cross-scope ids return 404. Permissions are split across `records:read/manage/access/approve/dispose`, `seal:read/manage/custody/use/approve/execute`, and `signature:read/manage/dispatch/ingest`; JWT claims do not grant permissions absent from the database.

## Risks / Trade-offs

- [Object storage cannot provide certified WORM locally] → retain checksums/manifests and explicit provider truth; certification remains external evidence.
- [Approval decision and domain execution can race] → lock the domain aggregate and authoritative approval row, require expected versions and make execution idempotent.
- [Two users can allocate the same archive number] → lock a category/year counter and enforce tenant-unique record numbers.
- [A held record could be disposed by stale pre-read] → lock record, active holds and loans inside the final disposition transaction.
- [Seal custody transfer can leave ambiguous owners] → one pending transfer per seal, acceptance under row lock, immutable history and no silent reassignment.
- [Provider callback replay or spoofing] → no public generic callback; sandbox ingestion requires database permission, future live adapters require signature verification and unique source-event hashes.
- [Existing clients expect local lease `SIGNED`] → return an explicit sandbox envelope and keep document APPROVED; tests/UI display the truthful distinction.

## Migration Plan

1. Add forward-only revisions after `z2c80e5f6a64`; do not edit applied history.
2. Upgrade empty PostgreSQL 16, assert unique head/current, metadata parity and one-step downgrade/upgrade.
3. Seed permissions and native approval definitions without enabling a live signature provider.
4. Deploy records/seal routes and PC navigation; lease local sign becomes sandbox-truthful.
5. Run synthetic legacy file/document dry-run, injected interruption, apply, reapply, reconcile and schema rollback. Unknown owners, missing binaries/checksums and raw identity material are quarantined.
6. Real migration requires authorized schema/dictionaries, desensitized metadata/binaries, checksums, category/owner maps and signed counts. Production disposition and provider activation require separate approval.
7. If rollback is required before new writes, downgrade the newest revision. After evidence exists, use forward repair/export; do not erase records, receipts or provider events.

## Open Questions

- Which qualified electronic-signature provider, certificate policy, callback signature and legal verification report are authorized?
- Which records are permanent, which retention periods apply, and who owns category/disposition approval in production?
- Which physical/electronic seals exist, who are their custodians and which seal kinds require three-way separation of duties?
- No authorized legacy archive/file inventory, checksum manifest or object-store export has been supplied; real migration remains blocked.
