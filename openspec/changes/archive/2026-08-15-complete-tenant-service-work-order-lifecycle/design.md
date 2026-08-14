## Context

V2 already has a tenant/park-scoped WorkOrder, WorkItem projection, transactional business events, Party/PartyContact and immutable attachment metadata. The existing aggregate lacks tenant Party ownership, robust states, version checks and operational evidence. Legacy `repair_order` exposes source, tenant/factory labels, repair type, images, assignee, processing images/remark and accept/finish/confirm timestamps. Its PC code models `待接单 → 处理中 → 待验收 → 已完成` plus return/cancel, but the inspected backend only provides list/detail/CRUD and states that creation does not dispatch or notify. The redesign keeps the recognizable journey while rejecting mutable wide-row and physical-delete semantics.

## Goals / Non-Goals

**Goals:** close local tenant service from authenticated Party-bound intake through deterministic dispatch, quote decision, execution evidence, tenant acceptance/rework and rating; preserve tenant/Party/park scope, exact money, append-only evidence, idempotency and PostgreSQL concurrency; make SLA state and disconnected providers truthful.

**Non-goals:** tenant WeChat mini-program UI, employee mobile application, live SMS/WeCom push, production object storage, vendor procurement/inventory decrement, IoT/inspection origin, real legacy migration or production deployment. Those remain separate matrix capabilities or external blockers.

## Decisions

### 1. Tenant-facing identity is database-bound, not client-declared

`tenant_service_principals` binds an active platform User to exactly one organization Party and one or more permitted parks inside the same SaaS tenant. Tenant-facing endpoints derive `party_id` and visible parks from this record and ignore no client-supplied identity override. Staff may create on behalf of a visible Party only with `work_order:intake`; principal grants require `tenant_service:principal_manage` and same-tenant/same-park validation.

### 2. WorkOrder remains the aggregate root with optimistic concurrency

Existing rows are backfilled with stable order numbers, `MANUAL` source, safe SLA defaults and `lock_version=1`. Mutations require `expected_version`; repository updates or locked transitions reject stale writes with 409. Physical DELETE is not exposed. `work_order_events` is append-only and records state, actor kind, bounded reason, SLA/assignment/quote evidence and idempotency key.

### 3. Assignment is deterministic and still supports governed override

Published assignment rules are tenant/park/category/priority scoped, ordered by specificity then explicit order and id. A request transaction chooses one active rule, records the rule version, assignee, response/resolution deadlines and creates the assignee WorkItem. If no rule matches, the order stays `SUBMITTED` with an unassigned triage WorkItem. Manual dispatch/reassignment requires `work_order:dispatch`, a reason and current version; it never erases prior assignments.

### 4. SLA is derived from immutable timestamps

First response is recorded once when an assignee accepts. Response and resolution deadlines come from the applied rule snapshot. Status views derive `ON_TRACK`, `RESPONSE_BREACHED`, `RESOLUTION_BREACHED`, `COMPLETED_ON_TIME` or `COMPLETED_LATE`; a repeat-safe sweep appends one breach/escalation event per boundary and raises/updates a WorkItem. Waiting for an accepted tenant quote pauses no clock unless an explicit future policy says so; this avoids silently improving performance metrics.

### 5. Quote is versioned financial intent, not actual cost

Quotes have immutable submitted versions and Decimal lines of `LABOR`, `MATERIAL`, `OUTSOURCE` or `OTHER`. Server-calculated line and header totals must equal quantity × unit price and sum of active lines. A new draft supersedes no submitted evidence. Tenant acceptance/rejection is Party-bound and idempotent; accepted versions cannot be edited. When `quote_required=true`, execution beyond initial diagnosis is blocked until one version is accepted.

### 6. Fulfillment evidence is append-only and completion means waiting for tenant

Actual labor/material/outsource entries are append-only; a correction is a reversing entry with a reason and reference, not an update/delete. Submitting completion requires processing summary and at least one evidence item or explicit no-material/no-photo reason. It moves to `WAITING_ACCEPTANCE`, closes the field-task WorkItem and opens a tenant acceptance WorkItem; it does not mark the order completed.

### 7. Acceptance, rework and rating are separate tenant decisions

The Party-bound principal may accept or request rework. Acceptance appends an attempt and moves to `COMPLETED`; rework requires a reason, appends an attempt and returns to `IN_PROGRESS_AFTER_QUOTE` or `IN_PROGRESS` while preserving quote and prior completion evidence. One rating of 1–5 may be submitted after completion by the same Party; it is immutable except for an explicit future moderation process.

### 8. Scope, permission and sensitive fields fail closed

Every Party, park, User, unit, quote, event and cost id is resolved through tenant and park scope. `work_order.*` and `tenant_service.*` permissions are database-derived high-risk grants. Phone values are accepted only through controlled contact references or stored masked; timeline/audit payloads never retain raw phone, attachment content or external secrets. Duplicate query names and unknown body fields fail.

### 9. PC uses live server truth and does not impersonate missing apps

The staff workspace exposes queue/SLA filters, intake/dispatch drawer, quote builder, cost/evidence timeline and acceptance status. A tenant-principal role view exposes only its own requests, quote decisions, acceptance/rework and rating. Responsive screenshots prove the browser rendering but are not evidence that employee mobile or WeChat mini-program exists.

### 10. Migration remains synthetic until authorized evidence exists

The ETL maps legacy order/source/tenant/park/factory/type/status/priority/assignee/process/timestamps and bounded image references. Phone is masked; ambiguous tenant labels, missing Party/park mapping, impossible state/timestamp combinations and raw binary/image payloads are quarantined. Dry-run/apply/interruption/reapply/reconcile/rollback prove tooling readiness only.

## Migration Plan

1. Add forward revision(s) after `w9f57b2c4d31` with WorkOrder columns, principal/rule/event/quote/line/cost/acceptance/rating tables, bounded checks, composite tenant foreign keys, partial uniques and query indexes.
2. Backfill existing WorkOrders to stable identifiers, version 1 and conservative workflow/source defaults without rewriting audit history.
3. Deploy APIs/UI and run PG16 base-to-head, `head -> -1 -> head`, metadata parity and concurrent transition/decision tests.
4. Run synthetic repair-order ETL and preserve redacted reconciliation/quarantine evidence.
5. Real legacy execution, external provider enablement and production deployment require separate authorization.

## Risks / Trade-offs

- A Party-bound User model adds administration work but prevents tenant users from enumerating arbitrary Party ids.
- Deterministic rules may leave unusual requests unassigned; explicit triage is safer than silently choosing a wrong worker.
- SLA clocks continue while quotes wait, which may make metrics look worse but preserves transparent customer elapsed time.
- Legacy phone/image fields may contain raw PII or untrusted URLs; migration masks/quarantines rather than copying them blindly.
- Inventory decrement and supplier settlement are deliberately outside this slice; actual material entries are service evidence, not stock truth.
