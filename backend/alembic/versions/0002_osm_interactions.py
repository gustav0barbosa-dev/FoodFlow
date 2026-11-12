"""Persistência de restaurantes do OpenStreetMap e interações do usuário.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="foodflow",
            nullable=False,
        ),
    )
    op.add_column(
        "restaurants", sa.Column("osm_type", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "restaurants", sa.Column("osm_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "restaurants", sa.Column("latitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "restaurants", sa.Column("longitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "restaurants", sa.Column("cuisine", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "restaurants", sa.Column("website", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "restaurants",
        sa.Column("opening_hours", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "restaurants", sa.Column("osm_url", sa.String(length=500), nullable=True)
    )
    # Vários restaurantes do catálogo têm osm_type/osm_id nulos; no PostgreSQL
    # valores NULL não colidem, então a constraint só vale para registros OSM.
    op.create_unique_constraint(
        "uq_restaurants_osm", "restaurants", ["osm_type", "osm_id"]
    )

    op.create_table(
        "user_restaurant_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "restaurant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("interaction_type", sa.String(length=20), nullable=False),
        sa.Column("purchase_value", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_restaurant_interactions_user_id",
        "user_restaurant_interactions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_restaurant_interactions_restaurant_id",
        "user_restaurant_interactions",
        ["restaurant_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_restaurant_interactions_interaction_type",
        "user_restaurant_interactions",
        ["interaction_type"],
        unique=False,
    )
    op.create_index(
        "ix_user_restaurant_interactions_idempotency_key",
        "user_restaurant_interactions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_interactions_user_created",
        "user_restaurant_interactions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_interactions_user_created",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_idempotency_key",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_interaction_type",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_restaurant_id",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_user_id",
        table_name="user_restaurant_interactions",
    )
    op.drop_table("user_restaurant_interactions")

    op.drop_constraint("uq_restaurants_osm", "restaurants", type_="unique")
    op.drop_column("restaurants", "osm_url")
    op.drop_column("restaurants", "opening_hours")
    op.drop_column("restaurants", "website")
    op.drop_column("restaurants", "cuisine")
    op.drop_column("restaurants", "longitude")
    op.drop_column("restaurants", "latitude")
    op.drop_column("restaurants", "osm_id")
    op.drop_column("restaurants", "osm_type")
    op.drop_column("restaurants", "source")
