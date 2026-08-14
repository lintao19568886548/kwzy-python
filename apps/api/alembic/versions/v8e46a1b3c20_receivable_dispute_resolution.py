"""add approval-gated receivable dispute resolution type

Revision ID: v8e46a1b3c20
Revises: u7d35f0a2b19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "v8e46a1b3c20"
down_revision: str | None = "u7d35f0a2b19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("receivable_adjustments") as batch:
        batch.drop_constraint("ck_receivable_adjustment_type", type_="check")
        batch.create_check_constraint(
            "ck_receivable_adjustment_type",
            "adjustment_type IN "
            "('WAIVER','EXTENSION','BAD_DEBT','DISPUTE','DISPUTE_RESOLUTION')",
        )


def downgrade() -> None:
    with op.batch_alter_table("receivable_adjustments") as batch:
        batch.drop_constraint("ck_receivable_adjustment_type", type_="check")
        batch.create_check_constraint(
            "ck_receivable_adjustment_type",
            "adjustment_type IN ('WAIVER','EXTENSION','BAD_DEBT','DISPUTE')",
        )
