"""Regression guards for the migration/ORM schema contract."""

from sqlalchemy import BigInteger

from app.infrastructure.database.base import Base
from app.infrastructure.database import models as _models  # noqa: F401


EXPECTED_INDEXES = {
    "audit_logs": {"ix_audit_logs_resource", "ix_audit_logs_tenant_created_at"},
    "auth_security_events": {
        "ix_auth_security_events_client_window",
        "ix_auth_security_events_subject_window",
    },
    "bill_lines": {"idx_bill_lines_bill"},
    "bills": {"idx_bills_park_status", "idx_bills_party_period"},
    "lease_change_orders": {"ix_lease_change_contract_id"},
    "lease_charge_items": {"ix_lease_charge_contract_id"},
    "lease_contract_documents": {"ix_lease_document_contract_id"},
    "lease_contract_units": {"idx_lcu_unit"},
    "lease_contract_versions": {"ix_lease_version_contract_id"},
    "lease_contracts": {"idx_lease_end_date", "idx_lease_park_status", "idx_lease_party"},
    "lease_exit_settlements": {"ix_lease_exit_contract_id"},
    "lease_performance_schedules": {"ix_lease_schedule_contract_id"},
    "lease_terms": {"idx_lease_terms_contract"},
    "parties": {
        "idx_parties_tenant_name",
        "idx_parties_tenant_risk",
        "idx_parties_tenant_status",
    },
    "party_addresses": {"uk_party_addr_primary"},
    "party_park_relations": {"uk_ppr_active"},
    "payment_allocations": {"idx_pa_bill", "idx_pa_payment"},
    "verification_codes": {"ix_verification_codes_lookup"},
}

NON_NULL_CREATED_AT_TABLES = {
    "approval_events",
    "approval_requests",
    "attachments",
    "auth_security_events",
    "collection_cases",
    "dict_items",
    "dict_types",
    "integration_outbox",
    "leads",
    "menus",
    "org_units",
    "page_access_proofs",
    "refresh_tokens",
    "system_params",
    "verification_codes",
    "work_items",
    "work_orders",
}


def test_performance_and_partial_indexes_are_part_of_orm_metadata() -> None:
    for table_name, expected_names in EXPECTED_INDEXES.items():
        actual_names = {index.name for index in Base.metadata.tables[table_name].indexes}
        assert expected_names <= actual_names, table_name


def test_created_at_nullability_matches_timestamp_mixin_contract() -> None:
    for table_name in NON_NULL_CREATED_AT_TABLES:
        assert not Base.metadata.tables[table_name].c.created_at.nullable, table_name


def test_number_sequence_uses_bigint_counter() -> None:
    next_val = Base.metadata.tables["number_sequences"].c.next_val
    assert isinstance(next_val.type, BigInteger)
