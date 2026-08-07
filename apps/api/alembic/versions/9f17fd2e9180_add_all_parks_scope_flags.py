"""add_all_parks_scope_flags

Revision ID: 9f17fd2e9180
Revises: 8c2f4aa10b7d
Create Date: 2026-08-07

Separates action super-permission (*) from all-parks data scope.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9f17fd2e9180"
down_revision: Union[str, None] = "8c2f4aa10b7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("roles") as batch:
        batch.add_column(
            sa.Column("all_parks", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("all_parks", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    # Existing ADMIN roles that historically relied on * for all-parks
    op.execute("UPDATE roles SET all_parks = 1 WHERE code = 'ADMIN'")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("all_parks")
    with op.batch_alter_table("roles") as batch:
        batch.drop_column("all_parks")
