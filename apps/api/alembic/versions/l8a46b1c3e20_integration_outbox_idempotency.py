"""integration outbox idempotency uniqueness

Revision ID: l8a46b1c3e20
Revises: k7f35a0b2d19
"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8a46b1c3e20"
down_revision: Union[str, None] = "k7f35a0b2d19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = "uk_integration_outbox_tenant_channel_key"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, tenant_id, channel, idempotency_key "
            "FROM integration_outbox ORDER BY tenant_id, channel, idempotency_key, id"
        )
    ).mappings()
    seen: set[tuple[int, str, str]] = set()
    for row in rows:
        key = (int(row["tenant_id"]), str(row["channel"]), str(row["idempotency_key"]))
        if key in seen:
            digest = hashlib.sha256(
                f"{key[0]}:{key[1]}:{key[2]}:{row['id']}".encode("utf-8")
            ).hexdigest()
            bind.execute(
                sa.text(
                    "UPDATE integration_outbox SET idempotency_key = :replacement WHERE id = :id"
                ),
                {"replacement": f"legacy-{digest}", "id": row["id"]},
            )
        else:
            seen.add(key)
    with op.batch_alter_table("integration_outbox") as batch_op:
        batch_op.create_unique_constraint(
            CONSTRAINT_NAME,
            ["tenant_id", "channel", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("integration_outbox") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
