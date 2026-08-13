"""identity security events

Revision ID: h4c02d7e9a86
Revises: g3b91f6d4c75
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h4c02d7e9a86"
down_revision: Union[str, None] = "g3b91f6d4c75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
FK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "auth_security_events",
        sa.Column("tenant_id", FK_TYPE, nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("client_digest", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False, server_default=""),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_security_events_tenant_id",
        "auth_security_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_auth_security_events_event_type",
        "auth_security_events",
        ["event_type"],
    )
    op.create_index(
        "ix_auth_security_events_subject_digest",
        "auth_security_events",
        ["subject_digest"],
    )
    op.create_index(
        "ix_auth_security_events_client_digest",
        "auth_security_events",
        ["client_digest"],
    )
    op.create_index(
        "ix_auth_security_events_subject_window",
        "auth_security_events",
        ["subject_digest", "event_type", "created_at"],
    )
    op.create_index(
        "ix_auth_security_events_client_window",
        "auth_security_events",
        ["client_digest", "event_type", "created_at"],
    )
    op.create_table(
        "verification_codes",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("recipient_digest", sa.String(64), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_codes_tenant_id",
        "verification_codes",
        ["tenant_id"],
    )
    op.create_index(
        "ix_verification_codes_user_id",
        "verification_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_verification_codes_purpose",
        "verification_codes",
        ["purpose"],
    )
    op.create_index(
        "ix_verification_codes_lookup",
        "verification_codes",
        ["tenant_id", "user_id", "purpose", "created_at"],
    )
    op.create_table(
        "page_access_proofs",
        sa.Column("tenant_id", FK_TYPE, nullable=False),
        sa.Column("user_id", FK_TYPE, nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("proof_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("id", PK_TYPE, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proof_hash", name="uk_page_access_proof_hash"),
    )
    op.create_index(
        "ix_page_access_proofs_tenant_id",
        "page_access_proofs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_page_access_proofs_user_id",
        "page_access_proofs",
        ["user_id"],
    )
    op.create_index(
        "ix_page_access_proofs_purpose",
        "page_access_proofs",
        ["purpose"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_page_access_proofs_purpose",
        table_name="page_access_proofs",
    )
    op.drop_index(
        "ix_page_access_proofs_user_id",
        table_name="page_access_proofs",
    )
    op.drop_index(
        "ix_page_access_proofs_tenant_id",
        table_name="page_access_proofs",
    )
    op.drop_table("page_access_proofs")
    op.drop_index(
        "ix_verification_codes_lookup",
        table_name="verification_codes",
    )
    op.drop_index(
        "ix_verification_codes_purpose",
        table_name="verification_codes",
    )
    op.drop_index(
        "ix_verification_codes_user_id",
        table_name="verification_codes",
    )
    op.drop_index(
        "ix_verification_codes_tenant_id",
        table_name="verification_codes",
    )
    op.drop_table("verification_codes")
    op.drop_index(
        "ix_auth_security_events_client_window",
        table_name="auth_security_events",
    )
    op.drop_index(
        "ix_auth_security_events_subject_window",
        table_name="auth_security_events",
    )
    op.drop_index(
        "ix_auth_security_events_client_digest",
        table_name="auth_security_events",
    )
    op.drop_index(
        "ix_auth_security_events_subject_digest",
        table_name="auth_security_events",
    )
    op.drop_index(
        "ix_auth_security_events_event_type",
        table_name="auth_security_events",
    )
    op.drop_index(
        "ix_auth_security_events_tenant_id",
        table_name="auth_security_events",
    )
    op.drop_table("auth_security_events")
