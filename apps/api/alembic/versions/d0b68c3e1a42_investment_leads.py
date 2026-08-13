"""investment leads

Revision ID: d0b68c3e1a42
Revises: c9a57b2d0f31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "d0b68c3e1a42"
down_revision = "c9a57b2d0f31"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("contact_phone", sa.String(32), nullable=False),
        sa.Column("contact_name", sa.String(64), nullable=True),
        sa.Column("agent_name", sa.String(64), nullable=True),
        sa.Column("intent_level", sa.String(16), nullable=True),
        sa.Column("intent_area", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("owner_user_id", FK_TYPE, nullable=True),
        sa.Column("party_id", FK_TYPE, nullable=True),
        sa.Column("lease_id", FK_TYPE, nullable=True),
        sa.Column("converted_at", sa.DateTime(), nullable=True),
        sa.Column("lost_reason", sa.String(255), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"]),
        sa.ForeignKeyConstraint(["lease_id"], ["lease_contracts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])
    op.create_index("ix_leads_park_id", "leads", ["park_id"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_owner_user_id", "leads", ["owner_user_id"])
    op.create_index("ix_leads_party_id", "leads", ["party_id"])
    op.create_index("ix_leads_lease_id", "leads", ["lease_id"])


def downgrade() -> None:
    op.drop_index("ix_leads_lease_id", table_name="leads")
    op.drop_index("ix_leads_party_id", table_name="leads")
    op.drop_index("ix_leads_owner_user_id", table_name="leads")
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_index("ix_leads_park_id", table_name="leads")
    op.drop_index("ix_leads_tenant_id", table_name="leads")
    op.drop_table("leads")
