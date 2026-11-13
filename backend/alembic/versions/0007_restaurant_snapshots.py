"""Snapshots históricos de atributos de restaurantes.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-13

- ``restaurant_snapshots`` registra o estado mutável (rating, nº de avaliações,
  frete, tempo de entrega) de um restaurante em um instante, permitindo
  avaliações temporalmente consistentes sem vazamento.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "restaurant_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("average_rating", sa.Numeric(2, 1), server_default="0", nullable=False),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivery_fee", sa.Numeric(4, 2), server_default="0", nullable=False),
        sa.Column("delivery_time_min", sa.Integer(), server_default="20", nullable=False),
        sa.Column("delivery_time_max", sa.Integer(), server_default="30", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="current", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_restaurant_snapshots_restaurant_valid_from",
        "restaurant_snapshots",
        ["restaurant_id", "valid_from"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_restaurant_snapshots_restaurant_valid_from",
        table_name="restaurant_snapshots",
    )
    op.drop_table("restaurant_snapshots")