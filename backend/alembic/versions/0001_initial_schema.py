"""Schema inicial do FoodFlow.

Revision ID: 0001
Revises:
Create Date: 2026-11-09

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("average_rating", sa.Numeric(precision=2, scale=1), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("delivery_time_min", sa.Integer(), nullable=False),
        sa.Column("delivery_time_max", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_restaurants_location",
        "restaurants",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
    op.create_index(
        "idx_restaurants_active",
        "restaurants",
        ["is_active"],
        unique=False,
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column(
            "dietary_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "items",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("order_value", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
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
    op.create_index("ix_orders_restaurant_id", "orders", ["restaurant_id"], unique=False)
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
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
        "ix_reviews_idempotency_key",
        "reviews",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_reviews_restaurant_id",
        "reviews",
        ["restaurant_id"],
        unique=False,
    )
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_events_type_created_at",
        "events",
        ["type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_events_type_created_at", table_name="events")
    op.drop_table("events")

    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_restaurant_id", table_name="reviews")
    op.drop_index("ix_reviews_idempotency_key", table_name="reviews")
    op.drop_table("reviews")

    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_restaurant_id", table_name="orders")
    op.drop_table("orders")

    op.drop_table("users")

    op.drop_index("idx_restaurants_active", table_name="restaurants")
    op.drop_index("idx_restaurants_location", table_name="restaurants")
    op.drop_table("restaurants")
