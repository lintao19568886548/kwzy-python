## Context

`work_items` currently provides scoped CRUD and source-key idempotency, and Lease, Billing, Facility, Investment and Approval call it directly from application services. `GET /workbench/summary` performs live counts and the PC page renders five fixed cards. There is no durable generic event boundary, configurable rule/version model, notification inbox, schedule registry/run history or user layout. Old Java contains Kafka outbox dispatch, Rabbit notification routing/retries, station notifications and XXL-Job handlers, but it is over-fragmented and not safe to translate package-for-package. The V2 blueprint explicitly recommends a clear event bus plus state machines and few environment switches.

The implementation must remain Python 3.10 compatible, preserve FastAPI/SQLAlchemy/PostgreSQL 16 and the single Alembic chain, keep Router-to-ORM and cross-tenant access prohibited, and never execute user-authored code or contact production/external providers during acceptance.

## Goals / Non-Goals

**Goals:**

- Turn committed domain events into idempotent, observable work-item and in-app notification projections.
- Provide publishable constrained rules and allow-listed schedules with durable execution/recovery state.
- Deliver role defaults plus user-owned workbench layouts and a live PC operations experience.
- Prove tenant/park/user isolation, optimistic concurrency, concurrent claims, retries/dead letters, performance, migration and recovery on PostgreSQL 16 and real HTTP/browser stacks.

**Non-Goals:**

- Run arbitrary Python, JavaScript, SQL, URLs or templates supplied by administrators.
- Introduce Kafka, RabbitMQ, Redis, Celery or another external service before measured volume requires it.
- Guess legacy business event history, notification recipients or layout ownership without an authorized schema/snapshot.
- Replace Approval tasks or business aggregates as sources of truth; work items and notifications remain projections.
- Operate remote staging/production schedules or providers without separate credentials and authorization.

## Decisions

### 1. Use a transactional database outbox with explicit dispatch commands

`BusinessEvent` is appended in the same transaction as the originating business change and carries only a registered type, source key, park, occurred time, schema version and bounded JSON payload. `EventConsumerLog` uniquely identifies `(tenant, event, consumer)` and owns PENDING/RUNNING/SUCCEEDED/RETRY/DEAD states. A protected dispatcher command claims rows with PostgreSQL `FOR UPDATE SKIP LOCKED`, which is simpler and locally recoverable than introducing an unproven broker. The dispatcher is also exposed as an allow-listed scheduler handler.

### 2. Evaluate a constrained rule grammar

Each immutable published `AutomationRuleVersion` contains an event type, priority, optional park restriction, AND-combined comparisons over allow-listed payload fields, and ordered allow-listed actions. Supported comparisons are `EQ`, `NE`, `IN`, `GT`, `GTE`, `LT`, `LTE` over scalar JSON values. Actions are `CREATE_WORK_ITEM` and `CREATE_NOTIFICATION`; values use fixed fields plus a small `${payload.field}` interpolation with escaping and maximum lengths. Dynamic SQL, expressions, URLs and executable code are rejected at validation/publication.

### 3. Separate rule identity from immutable versions and execution evidence

`AutomationRule` owns code/status and optimistic lock; `AutomationRuleVersion` owns the immutable draft/published document. Publication validates uniqueness and creates a new immutable active pointer. `AutomationExecution` records event, rule version, matched status, action result and sanitized error. A unique event/rule-version key prevents repeated delivery from duplicating actions.

### 4. Keep projections source-owned and concurrency-safe

Work items gain `deep_link`, `escalation_level`, `reassigned_from_user_id`, `lock_version` and `last_event_id`. Source-created work items cannot be manually completed/cancelled/reopened unless the actor has the override permission; owning events or registered jobs transition them. Update commands require `expected_version` and return 409 on stale writes. Existing callers use commit-free service methods and keep their aggregate transaction boundary.

### 5. Model notifications as user-scoped durable records

`InAppNotification` has a recipient user, optional park, category, safe title/content/deep link, unread/read/archived status and an idempotency key. Repository queries always combine tenant, current recipient and park visibility. Bulk read uses bounded explicit ids and rejects inaccessible ids atomically. No external push is claimed.

### 6. Register scheduler handlers in code and persist only safe parameters

`SchedulerDefinition` stores a registered handler key, cadence in seconds, enablement, safe JSON parameters, concurrency policy and next run time. It cannot contain command lines, modules or URLs. `SchedulerRun` records claim token, start/heartbeat/end, outcome, attempt and sanitized result/error. Claims are unique and stale RUNNING rows can be recovered. Manual run/retry uses idempotency keys and the same handler registry.

### 7. Store role defaults and user overrides as validated widget rows

`WorkbenchLayout` owns either a role default or one user's active layout, with optimistic version. `WorkbenchWidget` stores an allow-listed widget key, grid coordinates, dimensions, visibility and safe configuration. Effective layout resolution chooses user override, then highest-priority active role default, then a server default. Widgets obtain data from registered summary providers; the client cannot name URLs or submit SQL. Saving a layout validates overlap/bounds/permission visibility and never changes role permissions.

### 8. Keep a single workbench PC surface with an operations drawer

The workbench renders the effective layout, live metrics/todos/notifications and drill-down links. Users with configuration permission can rearrange/enable allow-listed widgets and reset to role defaults. Administrators see rule versioning, schedules, run/dead-letter details and controlled retry in a separate tab/drawer. Every control calls a live API and has 403/409/offline/retry feedback.

## Risks / Trade-offs

- [Risk] Database polling can increase write/query load. → Indexed claim queries, bounded batches, skip-locked claims, retention fields and measured acceptance thresholds.
- [Risk] Rule actions can create notification/todo storms. → Per-version action caps, unique idempotency keys, event batch caps and disabled-by-default rules.
- [Risk] Replaying dead letters could repeat side effects. → Consumer and action idempotency constraints plus explicit audited replay generation.
- [Risk] Layout JSON/config could become an ungoverned client API. → Normalized widgets, allow-listed keys, schema validation and server-provided data only.
- [Risk] Local dispatcher endpoints could be exposed operationally. → Separate permissions, no anonymous/internal bypass, bounded commands and Runbook guidance for network restriction.
- [Trade-off] A constrained condition grammar lacks arbitrary boolean graphs. → Determinism, auditability and security are more important; advanced orchestration requires a separately approved design.

## Migration Plan

1. Add one forward Alembic revision after `o1d79e4f6a53`; create new tables, append nullable/defaulted work-item columns, constraints and claim/query indexes.
2. Seed permissions idempotently; migrate no implicit production rules or enabled schedules. Existing work items become `lock_version=1` and remain readable.
3. Deploy backward-compatible APIs, register built-in events/handlers/widgets and then enable PC configuration and operations tabs.
4. Verify PG16 fresh upgrade, current=heads, downgrade/re-upgrade, metadata parity, concurrent claims/updates and restart recovery.
5. Run synthetic dry/apply/interruption/idempotent/reconcile/rollback for layouts/rules/schedules/notifications without fabricating users or business history.
6. Roll back UI/routes first; drain or disable dispatch; production database downgrade or schedule enablement remains a separately authorized operation.

## Open Questions

- Real legacy outbox/notification data ownership and reliable recipient mappings remain blocked until an authorized schema dump and desensitized snapshot exist.
- Remote scheduler cadence, retention and alert thresholds require the SRE owner and staging telemetry; local acceptance records safe defaults only.
- External delivery channels (WeChat/SMS/email) remain separate adapter capabilities and are not represented as successful delivery here.
