"""Rastreabilidade de simulação e logs de recomendação.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-13

- ``simulation_run_id`` identifica restaurantes sintéticos e permite limpar um
  run inteiro sem tocar no catálogo real.
- ``orders`` e ``reviews`` ganham ``simulation_run_id``/``simulation_mode`` para
  auditoria e limpeza mesmo em execuções parciais.
- ``recommendation_logs`` existia no modelo, mas nunca teve migração. A tabela
  guarda as features do contexto no momento da recomendação.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turno", sa.String(length=20), nullable=False),
        sa.Column(
            "features",
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
        "ix_recommendation_logs_user_id",
        "recommendation_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_turno",
        "recommendation_logs",
        ["turno"],
        unique=False,
    )
    op.create_index(
        "ix_recommendation_logs_created_at",
        "recommendation_logs",
        ["created_at"],
        unique=False,
    )

    op.add_column(
        "restaurants",
        sa.Column("simulation_run_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_restaurants_simulation_run_id",
        "restaurants",
        ["simulation_run_id"],
        unique=False,
    )

    op.add_column(
        "orders",
        sa.Column("simulation_run_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("simulation_mode", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_orders_simulation_run_id",
        "orders",
        ["simulation_run_id"],
        unique=False,
    )

    op.add_column(
        "reviews",
        sa.Column("simulation_run_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("simulation_mode", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_reviews_simulation_run_id",
        "reviews",
        ["simulation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reviews_simulation_run_id", table_name="reviews")
    op.drop_column("reviews", "simulation_mode")
    op.drop_column("reviews", "simulation_run_id")

    op.drop_index("ix_orders_simulation_run_id", table_name="orders")
    op.drop_column("orders", "simulation_mode")
    op.drop_column("orders", "simulation_run_id")

    op.drop_index(
        "ix_restaurants_simulation_run_id", table_name="restaurants"
    )
    op.drop_column("restaurants", "simulation_run_id")

    op.drop_index(
        "ix_recommendation_logs_created_at", table_name="recommendation_logs"
    )
    op.drop_index(
        "ix_recommendation_logs_turno", table_name="recommendation_logs"
    )
    op.drop_index(
        "ix_recommendation_logs_user_id", table_name="recommendation_logs"
    )
    op.drop_table("recommendation_logs")
