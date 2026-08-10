## ADDED Requirements

### Requirement: Application environment is normalized and fail-closed
The system SHALL normalize APP_ENV case-insensitively to one of local, test, staging, or production. Unrecognized environment values SHALL cause startup configuration failure.

#### Scenario: Production case variants require JWT
- **WHEN** APP_ENV is production, Production, or PRODUCTION and a request lacks Bearer token
- **THEN** the API returns 401 UNAUTHORIZED

#### Scenario: Staging requires JWT
- **WHEN** APP_ENV is staging and a request lacks Bearer token
- **THEN** the API returns 401

#### Scenario: Anonymous dev is explicit
- **WHEN** APP_ENV is local and ALLOW_ANON_DEV is not true
- **THEN** requests without Bearer return 401

#### Scenario: Explicit local anonymous allowed
- **WHEN** APP_ENV is local and ALLOW_ANON_DEV is true and no Bearer is provided
- **THEN** the request may proceed with the documented local development identity
