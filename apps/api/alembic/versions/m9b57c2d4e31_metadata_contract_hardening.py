"""align timestamp nullability with the ORM contract

Revision ID: m9b57c2d4e31
Revises: l8a46b1c3e20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m9b57c2d4e31"
down_revision: Union[str, None] = "l8a46b1c3e20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATED_AT_TABLES = (
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
)


def upgrade() -> None:
    for table_name in CREATED_AT_TABLES:
        # Constants only: quoting keeps this valid for PostgreSQL and SQLite.
        op.execute(
            sa.text(
                f'UPDATE "{table_name}" '
                "SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
            )
        )
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                nullable=False,
            )


def downgrade() -> None:
    for table_name in reversed(CREATED_AT_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(),
                nullable=True,
            )
