# observability-contract-hardening Specification

## Purpose
TBD - created by archiving change close-step1-acceptance-gaps. Update Purpose after archive.
## Requirements
### Requirement: Canonical log field name module
Business log records SHALL use the field name `module` for the bounded-context/module identifier required by the engineering logging standard.

#### Scenario: Success business log includes module
- **WHEN** a successful Park create log is emitted
- **THEN** the structured extra/fields include `module` with value identifying the park module

### Requirement: Transition compatibility for legacy field name
During a single transition period, the logging configuration SHALL dual-write the same module identifier to both `module` and `business_module` so existing collectors keep working while the canonical field is `module`. After the transition period ends, new log emitters SHALL stop requiring `business_module`.

#### Scenario: Dual-write during transition
- **WHEN** dual-write mode is enabled for the transition period
- **THEN** both `module` and `business_module` carry the same module identifier

### Requirement: OpenAPI 3.1 strict schema validation
The repository's `docs/04-api/openapi-v1-core.yaml` SHALL be validated with an OpenAPI 3.1-capable schema validator in the verification tasks of this change.

#### Scenario: Validator passes
- **WHEN** OpenAPI strict validation runs against `openapi-v1-core.yaml`
- **THEN** validation succeeds without schema errors

### Requirement: Runtime routes align with documented Step1 API surface
Verification SHALL compare FastAPI registered routes for Identity and Park/Unit with the corresponding paths in `openapi-v1-core.yaml` and record gaps without adding Party APIs.

#### Scenario: Step1 paths documented or listed as known gaps
- **WHEN** route consistency check runs
- **THEN** each runtime Step1 business route is either present in the OpenAPI document or explicitly listed as a documented gap to fix in this change's tasks
- **AND** no Party API is introduced

