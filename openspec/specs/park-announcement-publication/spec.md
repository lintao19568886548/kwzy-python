# Park Announcement Publication

## Purpose

Define governed announcement publication, frozen audiences, truthful fan-out, and receipt evidence.

## Requirements

### Requirement: Versioned approved announcement publication
The system SHALL preserve editable drafts and immutable approved announcement versions with title, sanitized content, attachments, priority, pin window, publish time, expiry time, and withdrawal evidence.

#### Scenario: Scheduled publication
- **WHEN** an approved announcement reaches its scheduled publish time
- **THEN** the exact approved version becomes visible once and an auditable publication event is appended

### Requirement: Frozen tenant and park audience
The system SHALL define a bounded role, park, Party, user, and tenant-principal audience and SHALL freeze the resolved target snapshot for each publication.

#### Scenario: Audience changes after publication
- **WHEN** a user's park grant changes after an announcement was published
- **THEN** historical delivery retains the original target snapshot while current visibility follows the documented audience and grant rules

### Requirement: Idempotent in-app fan-out with truthful channels
Publication SHALL append a transactional registered event and idempotently create at most one in-app notification and delivery ledger row per resolved recipient.

#### Scenario: Fan-out retry
- **WHEN** the announcement consumer retries after partial processing
- **THEN** completed recipients are not duplicated, pending recipients can continue, and no SMS, WeChat, or email success is fabricated

### Requirement: Read, expiry, and withdrawal evidence
The system SHALL record one read acknowledgement per recipient/version, exclude expired or withdrawn announcements from new active lists, and retain historical publication, delivery, read, and withdrawal evidence.

#### Scenario: Read withdrawn announcement from history
- **WHEN** an authorized recipient opens a previously delivered withdrawn announcement from history
- **THEN** the exact historical version and withdrawn state are visible without returning it as currently active
