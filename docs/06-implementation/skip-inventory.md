# 原 15/16 skip 清单与清除结果

| 测试 | 原原因 | 清除方式 | 结果 |
| --- | --- | --- | --- |
| test_psycopg_importable | 无 | 本地已装 psycopg | PASS |
| test_postgres_connect_and_version | 无 TEST_DATABASE_URL | Docker PG16 + URL | PASS |
| test_postgres_transaction_commit_rollback | 同上 | 同上 | PASS |
| test_postgres_url_safety_shape | 同上 | 同上 | PASS |
| test_postgres_party_tables_and_partial_indexes | 同上 + 需 alembic | upgrade head | PASS |
| test_pg_lease_tables_exist | 同上 | 同上 | PASS |
| test_pg_credit_code_unique_conflict | 同上 | 同上 | PASS |
| test_pg_address_primary_partial_unique | 同上 | 同上 | PASS |
| test_pg_risk_event_same_transaction_with_audit | 同上 | 同上 | PASS |
| test_pg_person_preseeded_address_not_readable_via_service | 同上 | 同上 | PASS |
| test_pg_concurrent_allocate_same_bill | 同上 | 同上 | PASS |
| test_pg_concurrent_reverse_not_double_deduct | 同上 | 同上 | PASS |
| test_pg_concurrent_number_sequence_unique | 同上 | 同上 | PASS |
| test_pg_integrity_tables_exist | 同上 | 同上 | PASS |
| test_pg_concurrent_same_idempotency_key_one_payment | 同上 | 同上 | PASS |
| test_pg_concurrent_same_key_different_body_conflict | 同上 | 同上 | PASS |

运行命令：

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://kwzy_party_test:kwzy_test_local_only@127.0.0.1:55432/kwzy_party_test'
$env:POSTGRES_TEST_URL=$env:TEST_DATABASE_URL
pytest -m pg
```

Alembic：`DATABASE_URL` 指向同上库，`upgrade head` / `downgrade -1` / `upgrade head` 已验证。
