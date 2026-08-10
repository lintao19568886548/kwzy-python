"""party master tables

Revision ID: c3a91b2e4f10
Revises: 9f17fd2e9180
Create Date: 2026-08-10

Party master, roles, park relations, contacts, addresses, risk events.
PostgreSQL 16 authoritative; SQLite compatible for local/unit tests.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3a91b2e4f10"
down_revision: Union[str, None] = "9f17fd2e9180"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "parties",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("credit_code", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_status", sa.String(length=32), nullable=False),
        sa.Column("blacklist_reason", sa.String(length=512), nullable=True),
        sa.Column("blacklisted_at", sa.DateTime(), nullable=True),
        sa.Column("blacklisted_by", FK_TYPE, nullable=True),
        sa.Column("blacklist_removed_at", sa.DateTime(), nullable=True),
        sa.Column("blacklist_removed_by", FK_TYPE, nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "credit_code", name="uk_parties_tenant_credit"),
    )
    op.create_index("ix_parties_tenant_id", "parties", ["tenant_id"])
    op.create_index("idx_parties_tenant_status", "parties", ["tenant_id", "status"])
    op.create_index("idx_parties_tenant_risk", "parties", ["tenant_id", "risk_status"])
    op.create_index("idx_parties_tenant_name", "parties", ["tenant_id", "name"])

    op.create_table(
        "party_roles",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "party_id", "role_code", name="uk_party_role_code"),
    )
    op.create_index("ix_party_roles_tenant_id", "party_roles", ["tenant_id"])

    op.create_table(
        "party_park_relations",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("party_role_id", FK_TYPE, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["party_role_id"], ["party_roles.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_park_relations_tenant_id", "party_park_relations", ["tenant_id"])
    op.create_index(
        "uk_ppr_active",
        "party_park_relations",
        ["tenant_id", "party_id", "park_id", "party_role_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE' AND deleted_at IS NULL"),
        sqlite_where=sa.text("status = 'ACTIVE' AND deleted_at IS NULL"),
    )

    op.create_table(
        "party_risk_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("previous_risk_status", sa.String(length=32), nullable=False),
        sa.Column("new_risk_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("operator_user_id", FK_TYPE, nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_risk_events_tenant_id", "party_risk_events", ["tenant_id"])

    op.create_table(
        "party_contacts",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("role_label", sa.String(length=64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("linked_person_party_id", FK_TYPE, nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_contacts_tenant_id", "party_contacts", ["tenant_id"])

    op.create_table(
        "party_addresses",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("party_id", FK_TYPE, nullable=False),
        sa.Column("address_type", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("province", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("district", sa.String(length=64), nullable=True),
        sa.Column("street", sa.String(length=128), nullable=True),
        sa.Column("detail", sa.String(length=255), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_addresses_tenant_id", "party_addresses", ["tenant_id"])
    op.create_index(
        "uk_party_addr_primary",
        "party_addresses",
        ["tenant_id", "party_id", "address_type"],
        unique=True,
        postgresql_where=sa.text(
            "is_primary = true AND deleted_at IS NULL AND status = 'ACTIVE'"
        ),
        sqlite_where=sa.text(
            "is_primary = 1 AND deleted_at IS NULL AND status = 'ACTIVE'"
        ),
    )


def downgrade() -> None:
    op.drop_index("uk_party_addr_primary", table_name="party_addresses")
    op.drop_index("ix_party_addresses_tenant_id", table_name="party_addresses")
    op.drop_table("party_addresses")
    op.drop_index("ix_party_contacts_tenant_id", table_name="party_contacts")
    op.drop_table("party_contacts")
    op.drop_index("ix_party_risk_events_tenant_id", table_name="party_risk_events")
    op.drop_table("party_risk_events")
    op.drop_index("uk_ppr_active", table_name="party_park_relations")
    op.drop_index("ix_party_park_relations_tenant_id", table_name="party_park_relations")
    op.drop_table("party_park_relations")
    op.drop_index("ix_party_roles_tenant_id", table_name="party_roles")
    op.drop_table("party_roles")
    op.drop_index("idx_parties_tenant_name", table_name="parties")
    op.drop_index("idx_parties_tenant_risk", table_name="parties")
    op.drop_index("idx_parties_tenant_status", table_name="parties")
    op.drop_index("ix_parties_tenant_id", table_name="parties")
    op.drop_table("parties")
