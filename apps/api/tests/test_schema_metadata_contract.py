"""Regression guards for the migration/ORM schema contract."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
)

from app.infrastructure.database import models as _models  # noqa: F401
from app.infrastructure.database.base import Base

EXPECTED_INDEXES = {
    "asset_templates": {"ix_asset_templates_category", "ix_asset_templates_tenant_id"},
    "asset_template_versions": {
        "ix_asset_template_versions_template_id",
        "ix_asset_template_versions_tenant_id",
        "uk_asset_template_one_draft",
    },
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
    "party_enterprise_credentials": {
        "ix_party_enterprise_credentials_expiry",
        "uk_party_enterprise_credential_active_attachment",
    },
    "party_enterprise_profiles": {
        "ix_party_enterprise_profiles_tenant_industry",
        "ix_party_enterprise_profiles_tenant_registration",
    },
    "party_enterprise_relationships": {
        "ix_party_enterprise_relationship_target",
        "uk_party_enterprise_relationship_active",
    },
    "party_enterprise_risk_signals": {
        "ix_party_enterprise_risk_open",
        "uk_party_enterprise_risk_source",
    },
    "party_enterprise_tags": {"uk_party_enterprise_tag_active"},
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
    "party_enterprise_credentials",
    "party_enterprise_profiles",
    "party_enterprise_relationships",
    "party_enterprise_risk_resolutions",
    "party_enterprise_risk_signals",
    "party_enterprise_tags",
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


def test_asset_template_schema_has_boolean_keys_and_database_invariants() -> None:
    templates = Base.metadata.tables["asset_templates"]
    versions = Base.metadata.tables["asset_template_versions"]
    units = Base.metadata.tables["units"]
    buildings = Base.metadata.tables["buildings"]

    assert isinstance(templates.c.is_builtin.type, Boolean)
    assert not templates.c.is_builtin.nullable
    assert not buildings.c.geometry_version.nullable
    assert {
        constraint.name
        for constraint in templates.constraints
        if isinstance(constraint, (CheckConstraint, UniqueConstraint))
    } >= {
        "uk_asset_template_code",
        "uk_asset_template_tenant_id_id",
        "ck_asset_template_status",
        "ck_asset_template_current_version",
        "ck_asset_template_lock_version",
    }
    assert {
        constraint.name
        for constraint in versions.constraints
        if isinstance(constraint, (CheckConstraint, UniqueConstraint))
    } >= {
        "uk_asset_template_version",
        "uk_asset_template_version_tenant_id_id",
        "ck_asset_template_version_status",
        "ck_asset_template_version_positive",
    }
    assert {
        foreign_key.target_fullname
        for foreign_key in units.c.asset_template_version_id.foreign_keys
    } == {"asset_template_versions.id"}
    assert {
        constraint.name
        for constraint in versions.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    } >= {"fk_asset_template_versions_tenant_template"}
    assert {
        constraint.name
        for constraint in units.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    } >= {"fk_units_tenant_asset_template_version"}


def test_party_enterprise_schema_has_tenant_composite_references_and_checks() -> None:
    profiles = Base.metadata.tables["party_enterprise_profiles"]
    relationships = Base.metadata.tables["party_enterprise_relationships"]
    credentials = Base.metadata.tables["party_enterprise_credentials"]
    tags = Base.metadata.tables["party_enterprise_tags"]
    signals = Base.metadata.tables["party_enterprise_risk_signals"]
    resolutions = Base.metadata.tables["party_enterprise_risk_resolutions"]

    expected_constraints = {
        profiles: {
            "fk_party_enterprise_profile_tenant_party",
            "ck_party_enterprise_profile_lock_version",
        },
        relationships: {
            "fk_party_enterprise_relationship_tenant_source",
            "fk_party_enterprise_relationship_tenant_target",
            "ck_party_enterprise_relationship_self",
        },
        credentials: {
            "fk_party_enterprise_credential_tenant_party",
            "fk_party_enterprise_credential_tenant_attachment",
            "ck_party_enterprise_credential_dates",
        },
        tags: {
            "fk_party_enterprise_tag_tenant_party",
            "ck_party_enterprise_tag_confidence",
        },
        signals: {
            "fk_party_enterprise_risk_tenant_party",
            "fk_party_enterprise_risk_tenant_attachment",
        },
        resolutions: {
            "fk_party_enterprise_resolution_tenant_party",
            "fk_party_enterprise_resolution_tenant_signal",
        },
    }
    for table, expected in expected_constraints.items():
        actual = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, (CheckConstraint, ForeignKeyConstraint))
        }
        assert expected <= actual, table.name

    assert isinstance(profiles.c.lock_version.type, Integer)
    assert isinstance(credentials.c.lock_version.type, Integer)
