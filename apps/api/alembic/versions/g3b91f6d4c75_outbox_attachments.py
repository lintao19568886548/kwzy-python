"""integration outbox and attachments

Revision ID: g3b91f6d4c75
Revises: f2a80e5c3b64
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision = "g3b91f6d4c75"
down_revision = "f2a80e5c3b64"
branch_labels = None
depends_on = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "integration_outbox",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_outbox_tenant_id", "integration_outbox", ["tenant_id"])
    op.create_index("ix_integration_outbox_channel", "integration_outbox", ["channel"])
    op.create_index(
        "ix_integration_outbox_idempotency_key", "integration_outbox", ["idempotency_key"]
    )

    op.create_table(
        "attachments",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("park_id", FK_TYPE, nullable=True),
        sa.Column("biz_type", sa.String(64), nullable=False),
        sa.Column("biz_id", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("etag", sa.String(64), nullable=False, server_default=""),
        sa.Column("uploaded_by", FK_TYPE, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["park_id"], ["parks.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "object_key", name="uk_attachment_object_key"),
    )
    op.create_index("ix_attachments_tenant_id", "attachments", ["tenant_id"])
    op.create_index("ix_attachments_biz_type", "attachments", ["biz_type"])
    op.create_index("ix_attachments_biz_id", "attachments", ["biz_id"])

    op.create_table(
        "approval_events",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("approval_id", FK_TYPE, nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_user_id", FK_TYPE, nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["approval_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_events_approval_id", "approval_events", ["approval_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_events_approval_id", table_name="approval_events")
    op.drop_table("approval_events")
    op.drop_index("ix_attachments_biz_id", table_name="attachments")
    op.drop_index("ix_attachments_biz_type", table_name="attachments")
    op.drop_index("ix_attachments_tenant_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_integration_outbox_idempotency_key", table_name="integration_outbox")
    op.drop_index("ix_integration_outbox_channel", table_name="integration_outbox")
    op.drop_index("ix_integration_outbox_tenant_id", table_name="integration_outbox")
    op.drop_table("integration_outbox")
