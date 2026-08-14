# notification-inbox Specification

## Purpose

Define recipient-scoped, idempotent in-app notifications without false external-delivery claims.

## Requirements

### Requirement: Idempotent in-app delivery
The system SHALL create at most one notification per tenant and idempotency key for an active same-tenant recipient, with bounded safe content and optional visible park/deep link.

#### Scenario: Duplicate action delivery
- **WHEN** the same notification action is retried
- **THEN** the original notification is returned and no duplicate row is created

### Requirement: Recipient-scoped inbox lifecycle
The system SHALL list only the current recipient's park-visible notifications and SHALL support unread, read and archived states with unread counts.

#### Scenario: Read own notification
- **WHEN** a recipient marks an unread visible notification as read
- **THEN** read time is recorded and the unread count decreases once

#### Scenario: Other recipient id
- **WHEN** a user attempts to read or archive another user's notification
- **THEN** the system returns not found and does not mutate the row

### Requirement: Atomic bounded bulk read
The system SHALL accept a bounded unique id list for bulk read and SHALL fail the whole command if any id is inaccessible or malformed.

#### Scenario: Mixed accessible and inaccessible ids
- **WHEN** a bulk request includes one notification owned by another recipient
- **THEN** no notification in the request changes state

### Requirement: No false external delivery claim
The system SHALL label these records as in-app delivery only and SHALL not report WeChat, SMS or email success without a separately verified provider result.

#### Scenario: In-app notification created
- **WHEN** a rule creates an in-app notification
- **THEN** its channel is IN_APP and no external delivery status is fabricated
