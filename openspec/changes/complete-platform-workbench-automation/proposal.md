## Why

The current V2 workbench is a narrow summary plus manually mutable work items, with only a few hard-coded Lease, Billing and Approval projections. It has no role-aware layout, durable event consumption, governed rules, user notification inbox, observable schedules, retry/dead-letter recovery or replay evidence, while the blueprint and legacy source explicitly require a daily multi-role workbench backed by Outbox, notifications and night-time jobs.

## What Changes

- Add an explicit transactional business-event outbox and idempotent consumer log for registered internal events; failed delivery uses bounded retry, dead-letter and administrator-controlled replay without executing arbitrary code.
- Add versioned, publishable automation rules with a constrained condition grammar and allow-listed `CREATE_WORK_ITEM` / `CREATE_NOTIFICATION` actions; published versions are immutable and all execution is traceable.
- Add a tenant/user/park-scoped in-app notification inbox with unread counts, idempotent delivery and read/archive lifecycle.
- Add governed scheduler definitions and durable run records for allow-listed handlers, including lease-todo sync, approval-overdue sweep and outbox dispatch; concurrent claims, timeout recovery and manual retry are observable and idempotent.
- Upgrade work items with deep links, version conflicts, automatic escalation/reassignment metadata and safe source-owned completion semantics.
- Replace the fixed PC workbench with server-owned role defaults and per-user widget configuration, live drill-down cards, notification inbox and automation operations center with loading/empty/permission/conflict/offline/retry states.
- Add exact OpenAPI contracts, PostgreSQL concurrency tests, real HTTP and browser journeys, screenshots, performance/recovery evidence and a reversible synthetic migration drill.
- Do not connect production, invoke real external providers, accept executable scripts/dynamic SQL, or claim real legacy events/notifications migrated without an authorized schema and desensitized snapshot.

## Capabilities

### New Capabilities

- `event-outbox-delivery`: Transactional business-event capture, allow-listed dispatch, consumption idempotency, retry, dead-letter and replay.
- `automation-rule-governance`: Versioned constrained rules, publication controls, deterministic matching and traceable actions.
- `notification-inbox`: Tenant/user/park-scoped in-app notifications, unread counts and read/archive lifecycle.
- `scheduler-operations`: Governed allow-listed job definitions, concurrent claims, durable runs, recovery and retry.
- `workbench-layout-pc`: Role-aware server defaults, per-user widget configuration and live PC operational workbench.
- `workbench-automation-migration`: Legacy disposition and reversible synthetic migration/reconciliation evidence for layouts, rules, schedules and notifications.

### Modified Capabilities

- `workbench-ops`: Extend source-owned work items with deep links, optimistic updates, escalation/reassignment and rule/event projections.
- `identity-authorization`: Add database-derived workbench configuration, automation administration, scheduler operation and notification permissions.

## Impact

- Adds one forward Alembic revision after `o1d79e4f6a53` with event, consumer, rule/version/execution, notification, scheduler/run and workbench-layout tables plus backward-compatible work-item columns and indexes.
- Extends `modules/workbench` into explicit application, infrastructure and interface boundaries and adds commit-free event emission ports for business contexts.
- Adds `/workbench/layout`, `/notifications`, `/automation-rules`, `/business-events` and `/scheduler` APIs under `/api/v1`, while preserving existing work-item and summary routes.
- Rebuilds the PC workbench and adds live automation configuration/operations views without local JSON or placeholder actions.
- Adds PostgreSQL 16 migration/concurrency/recovery verification, runtime-to-YAML OpenAPI checks, real HTTP/Playwright journeys, synthetic migration tooling and acceptance evidence.
