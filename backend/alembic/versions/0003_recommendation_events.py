"""Eventos de recomendação, contexto experimental e sincronização OSM.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11

A tabela ``user_restaurant_interactions`` já era append-only e cobre o
comportamento do usuário. Em vez de criar uma tabela ``recommendation_events``
duplicada, esta migração a amplia com o contexto necessário para medir o
experimento A/B (grupo, posição e versão do modelo) e para registrar
impressões/descarte.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_restaurant_interactions",
        sa.Column("experiment_group", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "user_restaurant_interactions",
        sa.Column("recommendation_position", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_restaurant_interactions",
        sa.Column("model_version", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "user_restaurant_interactions",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_restaurant_interactions_experiment_group",
        "user_restaurant_interactions",
        ["experiment_group"],
        unique=False,
    )
    op.create_index(
        "idx_interactions_group_type_created",
        "user_restaurant_interactions",
        ["experiment_group", "interaction_type", "created_at"],
        unique=False,
    )

    op.add_column(
        "restaurants",
        sa.Column(
            "dietary_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "restaurants",
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("restaurants", "last_synced_at")
    op.drop_column("restaurants", "dietary_tags")

    op.drop_index(
        "idx_interactions_group_type_created",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_experiment_group",
        table_name="user_restaurant_interactions",
    )
    op.drop_column("user_restaurant_interactions", "metadata")
    op.drop_column("user_restaurant_interactions", "model_version")
    op.drop_column("user_restaurant_interactions", "recommendation_position")
    op.drop_column("user_restaurant_interactions", "experiment_group")
