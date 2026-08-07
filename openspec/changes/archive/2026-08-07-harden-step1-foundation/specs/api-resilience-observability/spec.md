## ADDED Requirements

### Requirement: Uniform API error envelope
The system SHALL return errors using `{code,message,data}` for application errors, request validation errors, and unhandled server errors. Unhandled errors MUST NOT expose stack traces, SQL, or internal exception messages.

#### Scenario: Request validation failure
- **WHEN** a request fails FastAPI/Pydantic validation
- **THEN** the system returns HTTP 422 with code `VALIDATION_ERROR` and field error data

#### Scenario: Unhandled exception
- **WHEN** an unexpected exception escapes application code
- **THEN** the system returns HTTP 500 with code `INTERNAL_ERROR` and a generic message

#### Scenario: Invalid domain status
- **WHEN** a client submits an invalid Park or Unit status
- **THEN** the system returns a 400 business envelope instead of HTTP 500

### Requirement: Request correlation ID
The system SHALL accept a valid `X-Request-Id` or generate one for every HTTP request, make it available to request dependencies, and echo it in the response header.

#### Scenario: Client supplies request ID
- **WHEN** a client sends `X-Request-Id: trace-123`
- **THEN** the response contains the same request ID and business context can access it

#### Scenario: Client omits request ID
- **WHEN** a request has no X-Request-Id header
- **THEN** the system generates a non-empty request ID and returns it in the response

### Requirement: Structured business logging
The system SHALL emit JSON business logs for successful Park and Unit writes with request_id, user_id, tenant_id, park_id, module, action, and resource_id. Logs MUST NOT contain passwords or complete JWT values.

#### Scenario: Park creation log
- **WHEN** a Park is created successfully
- **THEN** one INFO business log contains the required correlation and resource fields
