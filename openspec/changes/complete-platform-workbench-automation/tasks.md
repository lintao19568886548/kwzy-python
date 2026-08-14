## 1. Evidence and execution control

- [x] 1.1 Publish legacy Java/PC/database workspace, outbox, notification and scheduler evidence with replace/retain/block disposition
- [x] 1.2 Record current Python workbench/event/scheduler gaps without counting hard-coded projections or fixed cards as complete
- [x] 1.3 Keep roadmap, capability matrix and agent state honest about external migration, remote operations and remaining business verticals

## 2. Database contract

- [x] 2.1 Add ORM models for business events, consumer logs, automation rules/versions/executions and notifications
- [x] 2.2 Add ORM models for scheduler definitions/runs and role/user workbench layouts/widgets
- [x] 2.3 Extend work items with deep link, escalation, reassignment, event and optimistic version fields
- [x] 2.4 Add one forward Alembic revision after `o1d79e4f6a53` with FKs, checks, uniqueness and claim/query indexes
- [x] 2.5 Register metadata and verify PostgreSQL 16 fresh upgrade, current=heads, downgrade -1/re-upgrade and ORM parity

## 3. Event outbox and consumer delivery

- [x] 3.1 Define the registered event catalog, bounded payload contract and commit-free event publisher port
- [x] 3.2 Implement tenant/park-safe event and consumer repositories with skip-locked concurrent claims
- [x] 3.3 Implement idempotent dispatch, exponential bounded retry, DEAD state and generation-preserving replay
- [x] 3.4 Emit registered lifecycle events from Lease, Billing, Approval, Investment and Facility transaction boundaries
- [x] 3.5 Add scoped event/dead-letter query, dispatch and replay APIs with sanitized errors

## 4. Automation rule governance

- [x] 4.1 Add strict draft/version/condition/action/publication schemas and allow-list validation
- [x] 4.2 Implement tenant/park-safe rule repository without exposing ORM outside infrastructure
- [x] 4.3 Implement optimistic draft create/update/copy, immutable publication and retirement
- [x] 4.4 Implement deterministic scalar condition evaluation and bounded escaped interpolation
- [x] 4.5 Implement idempotent work-item/notification actions and execution evidence
- [x] 4.6 Add scoped rule/version/execution administration APIs

## 5. Notifications and work-item governance

- [x] 5.1 Implement idempotent same-tenant in-app notification delivery
- [x] 5.2 Implement recipient/park-scoped inbox list, unread count, read, bounded bulk-read and archive
- [x] 5.3 Require expected work-item version for manual transitions and reassignment
- [x] 5.4 Block ordinary manual transitions of source-owned projections and support audited override reason
- [x] 5.5 Implement idempotent escalation/reassignment metadata and registered deep-link validation

## 6. Scheduler operations

- [x] 6.1 Define allow-listed handlers for outbox dispatch, lease todo sync and approval overdue sweep
- [x] 6.2 Implement validated scheduler definition create/update/enable/disable with optimistic concurrency
- [x] 6.3 Implement PostgreSQL-safe due claims, durable runs, heartbeat, timeout recovery and next-fire calculation
- [x] 6.4 Implement idempotent manual run/retry and sanitized definition/run query APIs
- [x] 6.5 Prove restart recovery, no duplicate fire and handler failure degradation

## 7. Workbench layout and live data

- [x] 7.1 Define allow-listed widget registry, safe config schemas and permission requirements
- [x] 7.2 Implement effective user → role → server layout resolution without permission amplification
- [x] 7.3 Implement optimistic personal layout save/reset and role-default administration with grid validation
- [x] 7.4 Extend summary providers for scoped live cards, todos, notifications and automation health
- [x] 7.5 Seed automation/layout/notification/scheduler/event permissions idempotently and verify database-derived authorization

## 8. APIs and OpenAPI

- [x] 8.1 Mount workbench layout, notifications, automation rules, event operations and scheduler routes through application services
- [x] 8.2 Add permission, scope, parameter-pollution, IDOR, bounded-list and conflict error contracts
- [x] 8.3 Update canonical OpenAPI with exact schemas/enums/filters/errors/idempotency fields
- [x] 8.4 Add runtime-to-YAML drift assertions for every new or modified route/method

## 9. PC workbench and operations center

- [x] 9.1 Add typed live-API state for effective layout, widgets, todos, notifications and automation health
- [x] 9.2 Rebuild the workbench grid with role-aware live widgets, drill-down links and notification inbox
- [x] 9.3 Add personal layout edit/reset and role-default administration with permission/read-only/conflict feedback
- [x] 9.4 Add rule draft/version/publish/retire and execution detail controls
- [x] 9.5 Add scheduler definition/run/dead-letter inspection and controlled retry controls
- [x] 9.6 Add loading, empty, permission, conflict, offline/retry, keyboard and desktop/tablet/mobile states

## 10. Migration readiness

- [x] 10.1 Publish legacy field/status/route disposition for workspace logs, outbox, consume logs, notifications and jobs
- [x] 10.2 Implement schema-versioned synthetic automation ETL dry-run/apply/idempotent/reconcile/rollback with test-DB safety
- [x] 10.3 Prove interruption rollback, no fabricated recipients/events/success, no raw PII and unchanged authorization identities

## 11. Automated verification

- [x] 11.1 Add rule grammar/lifecycle, event retry/dead-letter and scheduler state-machine unit/application tests
- [x] 11.2 Add notification/work-item/layout lifecycle and effective resolution tests
- [x] 11.3 Add tenant/park/user/permission/IDOR/parameter-pollution tests for all new APIs
- [x] 11.4 Add PostgreSQL 16 concurrent event claim, rule action, work-item version and scheduler fire tests
- [x] 11.5 Add real HTTP journey for event → rule → todo/notification → schedule/retry → layout drill-down
- [x] 11.6 Add Playwright desktop/tablet/mobile multi-role workbench and operations journeys including 403/409/offline/retry
- [x] 11.7 Benchmark bounded dispatch/summary APIs and verify query/index behavior and connection recovery
- [x] 11.8 Capture and visually review key workbench/automation screenshots with no fake controls, clipping or unreadable evidence

## 12. Closure and delivery

- [x] 12.1 Run focused backend/frontend tests, Ruff, type checks, build, migration drill and strict OpenSpec validation
- [x] 12.2 Run full PostgreSQL 16 acceptance, backup/restore and update evidence, matrix, roadmap and agent state with exact results
- [ ] 12.3 Commit and normally push the vertical, re-run clean-SHA gates, sync main specs and archive without force
