# iot-alarm-lifecycle Specification

## Purpose
TBD - created by archiving change complete-facility-device-inspection-iot. Update Purpose after archive.
## Requirements
### Requirement: Alarm ingestion is authenticated and replay safe
Alarm ingestion SHALL require database-derived `iot:ingest` authority, an active provider/binding, bounded source event id, source time and strict payload. The provider/source event id SHALL be unique and exact replay SHALL return the original event without another side effect.

#### Scenario: Replay one provider event
- **WHEN** the same authorized provider event is submitted twice with identical content
- **THEN** one source event exists and the second response identifies the same correlated alarm

### Requirement: Severity and correlation are deterministic
Provider values SHALL map through an explicit canonical INFO/WARNING/HIGH/CRITICAL policy. Events for the same binding and alarm type inside the configured window SHALL update one active alarm occurrence count and monotonically raise severity; events outside the window SHALL open a new alarm.

#### Scenario: Warning followed by critical event
- **WHEN** a correlated CRITICAL event follows a WARNING event inside the window
- **THEN** the same alarm records two occurrences and projects CRITICAL severity

### Requirement: Alarm lifecycle is governed and versioned
OPEN, ACKNOWLEDGED, RESOLVED and CLOSED transitions SHALL require permission, expected version, actor, bounded reason and allowed state transition. Concurrent conflicting decisions SHALL have exactly one winner and immutable alarm events SHALL never be deleted.

#### Scenario: Concurrent acknowledge and resolve
- **WHEN** two operators act on the same OPEN alarm version concurrently
- **THEN** exactly one transition commits and the other receives a version conflict

### Requirement: Escalation and WorkOrder linkage are repeat safe
Escalation levels SHALL be uniquely recorded per alarm. Policy-qualified HIGH/CRITICAL alarms SHALL atomically create or reuse one linked WorkOrder and WorkItem using a stable alarm source id; lower severity SHALL not fabricate remediation.

#### Scenario: Critical alarm replay and sweep
- **WHEN** a critical event is replayed and escalation sweep runs repeatedly
- **THEN** one linked WorkOrder and at most one event for each escalation level exist
