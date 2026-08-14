"""Harden seal-use execution separation and idempotency.

Revision ID: b4ea2c7d8f86
Revises: a3d91f6a7b75
Create Date: 2026-08-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b4ea2c7d8f86"
down_revision = "a3d91f6a7b75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "seal_use_receipts",
        sa.Column("command_fingerprint", sa.String(length=64), nullable=True),
    )
    # Pre-existing receipts cannot be reconstructed because the original expected
    # version was not persisted. A sentinel makes retries fail closed instead of
    # incorrectly replaying a changed command; no extension or secret is required.
    op.execute(
        "UPDATE seal_use_receipts SET command_fingerprint = repeat('0', 64) "
        "WHERE command_fingerprint IS NULL"
    )
    op.alter_column("seal_use_receipts", "command_fingerprint", nullable=False)


def downgrade() -> None:
    op.drop_column("seal_use_receipts", "command_fingerprint")
