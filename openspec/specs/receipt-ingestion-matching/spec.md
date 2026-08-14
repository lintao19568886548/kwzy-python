# receipt-ingestion-matching Specification

## Purpose
TBD - created by archiving change complete-receivables-collection-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Incoming receipts enter a governed pending pool
Finance import and locally supported offline channels SHALL create tenant/park-scoped receipt transactions with positive amount, currency, received time, bounded payer/reference data, masked account value and unique source identity. A receipt is not a confirmed Payment.

#### Scenario: Duplicate statement row
- **WHEN** the same source provider and source reference are imported twice
- **THEN** one receipt exists and the repeat returns the original row or a deterministic conflict

### Requirement: Disconnected provider channels fail closed
Bank-enterprise, payment-link, WeChat, Alipay and aggregate-payment channels SHALL expose truthful capability state. Ingestion that claims an unconfigured live adapter SHALL be rejected and SHALL NOT create a fake success receipt.

#### Scenario: Unconfigured bank callback
- **WHEN** a local caller submits a BANK_API receipt while that adapter is not configured
- **THEN** the API rejects it with provider-not-connected and creates no receipt

### Requirement: Matching candidates are deterministic and explainable
Matching SHALL use bounded rules based on exact Bill reference, scoped Party, amount/open amount and due order. Candidate score, rank, proposed amount and rule codes SHALL be persisted and returned; arbitrary client scores are forbidden.

#### Scenario: Exact Bill reference
- **WHEN** a pending receipt reference exactly equals one visible issued Bill number
- **THEN** the candidate identifies that Bill with the exact-reference rule and a deterministic proposed allocation

### Requirement: Automatic matching requires finance confirmation
Matching SHALL never create Payment or change Bill paid amount. A `payment:review` user SHALL explicitly confirm allocations under row locks; confirmation creates one Payment, immutable allocation rows and a receipt link atomically.

#### Scenario: Suggested candidate not confirmed
- **WHEN** a match run produces a high score but no reviewer confirms it
- **THEN** the receipt remains unconfirmed and every Bill paid amount is unchanged

### Requirement: Exceptions and disputes use separated review
Finance MAY mark an exception with a bounded reason. A business dispute SHALL enter `DISPUTED` and require `payment:dispute_review` resolution before finance can rematch/confirm or reject it.

#### Scenario: Finance cannot self-resolve manager dispute without permission
- **WHEN** a finance reviewer lacking dispute-review permission tries to resolve a disputed receipt
- **THEN** the request is denied and the dispute state remains unchanged
