## 1. Database and Bootstrap

- [x] 1.1 Add RBAC and AuditLog ORM models with relationships and metadata imports
- [x] 1.2 Add Alembic migration for permissions, role/user mappings, role park scopes, and audit_logs
- [x] 1.3 Make local/test default tenant bootstrap idempotently seed ADMIN role and explicit `*` permission

## 2. Identity Authorization

- [x] 2.1 Add AuthorizationRepository and AuthService for tenant-aware login and database-derived claims
- [x] 2.2 Add optional tenant_code to login schema and refactor Identity interface to call AuthService
- [x] 2.3 Add reusable permission dependencies and protect Park/Unit read and write routes

## 3. API Resilience and Observability

- [x] 3.1 Add request ID middleware/context propagation and JSON logging configuration
- [x] 3.2 Add validation/unhandled exception envelope handlers and map invalid Park/Unit states to AppError
- [x] 3.3 Add production Settings validation for JWT secret and CORS origins

## 4. Transactional Audit

- [x] 4.1 Add AuditRecorder and write structured Park/Unit success logs
- [x] 4.2 Record Park/Unit create, update, status-change, and delete audits in the business transaction

## 5. Verification and Documentation

- [x] 5.1 Add tenant login, RBAC, permission rejection, and production authentication/configuration tests
- [x] 5.2 Add error envelope, request ID, invalid status, soft-delete, and audit transaction tests
- [x] 5.3 Update Step1 documentation and run the full isolated test suite
