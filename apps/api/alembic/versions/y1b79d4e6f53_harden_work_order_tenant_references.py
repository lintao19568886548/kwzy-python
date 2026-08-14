"""harden work-order tenant and park references

Revision ID: y1b79d4e6f53
Revises: x0a68c3d5e42
"""

from collections.abc import Sequence

from alembic import op

revision: str = "y1b79d4e6f53"
down_revision: str | None = "x0a68c3d5e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHILD_ORDER_FKS = (
    ("work_order_events", "fk_work_order_event_order"),
    ("work_order_quotes", "fk_work_order_quote_order"),
    ("work_order_cost_entries", "fk_work_order_cost_order"),
    ("work_order_acceptances", "fk_work_order_acceptance_order"),
    ("work_order_ratings", "fk_work_order_rating_order"),
)


def upgrade() -> None:
    with op.batch_alter_table("party_contacts") as batch:
        batch.create_unique_constraint(
            "uk_party_contacts_tenant_party_id",
            ["tenant_id", "party_id", "id"],
        )

    with op.batch_alter_table("work_orders") as batch:
        batch.create_unique_constraint(
            "uk_work_orders_tenant_park_id",
            ["tenant_id", "park_id", "id"],
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_reporter_v2",
            "users",
            ["tenant_id", "reporter_user_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_party_contact_v2",
            "party_contacts",
            ["tenant_id", "party_id", "contact_id"],
            ["tenant_id", "party_id", "id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_work_orders_tenant_unit_v2",
            "units",
            ["tenant_id", "unit_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )

    for table_name, constraint_name in CHILD_ORDER_FKS:
        with op.batch_alter_table(table_name) as batch:
            batch.drop_constraint(constraint_name, type_="foreignkey")
            batch.create_foreign_key(
                constraint_name,
                "work_orders",
                ["tenant_id", "park_id", "work_order_id"],
                ["tenant_id", "park_id", "id"],
                ondelete="RESTRICT" if table_name == "work_order_events" else None,
            )


def downgrade() -> None:
    for table_name, constraint_name in reversed(CHILD_ORDER_FKS):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_constraint(constraint_name, type_="foreignkey")
            batch.create_foreign_key(
                constraint_name,
                "work_orders",
                ["tenant_id", "work_order_id"],
                ["tenant_id", "id"],
                ondelete="RESTRICT" if table_name == "work_order_events" else None,
            )

    with op.batch_alter_table("work_orders") as batch:
        batch.drop_constraint("fk_work_orders_tenant_unit_v2", type_="foreignkey")
        batch.drop_constraint(
            "fk_work_orders_tenant_party_contact_v2",
            type_="foreignkey",
        )
        batch.drop_constraint("fk_work_orders_tenant_reporter_v2", type_="foreignkey")
        batch.drop_constraint("uk_work_orders_tenant_park_id", type_="unique")

    with op.batch_alter_table("party_contacts") as batch:
        batch.drop_constraint("uk_party_contacts_tenant_party_id", type_="unique")
