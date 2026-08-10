## ADDED Requirements

### Requirement: Legacy adapter without write redirects
Legacy /rental/tenant* endpoints, if retained, SHALL call Party application services via a compatibility adapter. Write operations SHALL NOT use HTTP 301 or 302 redirects.

#### Scenario: Legacy create maps to party service
- **WHEN** a deprecated create call is received
- **THEN** the adapter invokes Party application create and returns a legacy-compatible body

### Requirement: Deprecation headers and metrics
Legacy endpoints SHALL emit Deprecation and Sunset plan information, record call counts, caller identity when available, request_id, and path, without logging passwords, tokens, or other sensitive request bodies. New features SHALL only be added to /api/v1/parties*.

#### Scenario: Deprecation signal present
- **WHEN** a legacy endpoint responds
- **THEN** deprecation related signalling is present per design

### Requirement: Removal target version is v2.0.0 with gate status NOT_READY
Design SHALL record removal_target_version as v2.0.0 and removal_gate_status as NOT_READY. Reaching API v2.0.0 alone SHALL NOT authorize unconditional deletion of legacy endpoints.

#### Scenario: Version alone insufficient
- **WHEN** product version is v2.0.0 but gates are unmet
- **THEN** the compatibility layer remains

### Requirement: Removal gates before shutdown
Legacy removal SHALL require a separate OpenSpec change only after: deprecation notice at least 90 days; all callers registered; PC, App, mini-program and external integrations migrated; 30 consecutive days of zero legacy traffic; new Party APIs stable for at least two formal release cycles; field mapping and migration guide published; production regression passed; and human approval granted. This Party design change SHALL NOT delete legacy endpoints.

#### Scenario: Gate incomplete blocks removal
- **WHEN** any removal gate is unmet
- **THEN** legacy endpoints must not be removed
