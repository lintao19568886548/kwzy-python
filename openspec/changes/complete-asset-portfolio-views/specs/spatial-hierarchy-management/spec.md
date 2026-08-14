## ADDED Requirements

### Requirement: Versioned spatial geometry
An active spatial node MAY store validated provider-neutral geometry, coordinate reference and a positive geometry version. Geometry updates SHALL require the expected version and SHALL preserve hierarchy, tenant and park invariants.

#### Scenario: Concurrent geometry update
- **WHEN** two clients save geometry using the same expected geometry version
- **THEN** one succeeds and the stale command receives 409 without lost update
