## ADDED Requirements

### Requirement: Assignment viewing intent and channel disposition
The migration package SHALL map only evidenced legacy ownership, visit, intention and external source facts, SHALL preserve source identifiers and timestamps, and SHALL quarantine inferred approvers, ambiguous owners, invalid unit references or unknown channel mappings rather than fabricate V2 operational state.

#### Scenario: Legacy free-text visit
- **WHEN** a legacy note mentions a visit but lacks appointment time or referenced Unit
- **THEN** it may migrate as a historical Activity but MUST NOT create a completed V2 Viewing

### Requirement: Extended CRM reconciliation
The rehearsal SHALL reconcile rule/version/member counts, viewing/status/unit links, intent/version/approval links and channel inbox/source references across dry-run, interruption, apply, repeat and rollback.

#### Scenario: Repeated extended CRM apply
- **WHEN** the same approved synthetic package is applied twice
- **THEN** counts and checksums remain stable with no duplicate rules, assignments, viewings, intents, approvals, inbox events or Leads

### Requirement: Real channel and approval migration stays gated
Production readiness MUST remain blocked until authorized legacy schemas, desensitized records, approval ownership and provider source mappings are fingerprinted and reconciled.

#### Scenario: Repository-only evidence
- **WHEN** only repository SQL and synthetic fixtures are available
- **THEN** the result remains conditional synthetic readiness and no provider connection or production cutover occurs
