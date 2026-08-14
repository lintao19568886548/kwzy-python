## ADDED Requirements

### Requirement: Viewing facts drive the activity pipeline
The activity timeline SHALL distinguish scheduled viewing metadata from completed VISIT facts, and only a completed viewing SHALL advance an eligible Lead stage or satisfy a visit milestone.

#### Scenario: Scheduled viewing is not a completed visit
- **WHEN** an owner schedules or confirms a viewing
- **THEN** the appointment is visible but no VISIT activity or VISITING stage transition is recorded

#### Scenario: Completed viewing reconciles
- **WHEN** a confirmed viewing is completed with outcome and next follow-up
- **THEN** exactly one VISIT activity references the viewing, Lead projections update and the appointment/activity/board counts reconcile
