"""Atribuição persistente do experimento e contexto de exposição.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11

- ``experiment_assignments`` registra a atribuição por usuário e versão do
  experimento, com data e origem. O hash SHA-256 continua determinístico; a
  tabela serve para auditoria e para impedir troca de grupo.
- ``user_restaurant_interactions`` ganha ``experiment_mode`` (separa o
  experimento oficial do modo de demonstração), ``experiment_version`` e
  ``recommendation_id`` (identificador da exposição que originou o evento).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "experiment_assignments",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("experiment_version", sa.String(length=40), nullable=False),
        sa.Column("group_name", sa.String(length=20), nullable=False),
        sa.Column(
            "source",
            sa.String(length=20),
            server_default=sa.text("'hash'"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "experiment_version"),
    )
    op.create_index(
        "ix_experiment_assignments_group_name",
        "experiment_assignments",
        ["group_name"],
        unique=False,
    )
    op.create_index(
        "idx_experiment_assignments_version_group",
        "experiment_assignments",
        ["experiment_version", "group_name"],
        unique=False,
    )

    op.add_column(
        "user_restaurant_interactions",
        sa.Column(
            "experiment_mode",
            sa.String(length=10),
            server_default=sa.text("'experiment'"),
            nullable=False,
        ),
    )
    op.add_column(
        "user_restaurant_interactions",
        sa.Column("experiment_version", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "user_restaurant_interactions",
        sa.Column("recommendation_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_user_restaurant_interactions_experiment_mode",
        "user_restaurant_interactions",
        ["experiment_mode"],
        unique=False,
    )
    op.create_index(
        "ix_user_restaurant_interactions_recommendation_id",
        "user_restaurant_interactions",
        ["recommendation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_restaurant_interactions_recommendation_id",
        table_name="user_restaurant_interactions",
    )
    op.drop_index(
        "ix_user_restaurant_interactions_experiment_mode",
        table_name="user_restaurant_interactions",
    )
    op.drop_column("user_restaurant_interactions", "recommendation_id")
    op.drop_column("user_restaurant_interactions", "experiment_version")
    op.drop_column("user_restaurant_interactions", "experiment_mode")

    op.drop_index(
        "idx_experiment_assignments_version_group",
        table_name="experiment_assignments",
    )
    op.drop_index(
        "ix_experiment_assignments_group_name",
        table_name="experiment_assignments",
    )
    op.drop_table("experiment_assignments")
