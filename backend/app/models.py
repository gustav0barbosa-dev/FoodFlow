import uuid
from datetime import datetime, timezone
from typing import Any, ClassVar

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    average_rating: Mapped[float] = mapped_column(Numeric(2, 1), default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    delivery_fee: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    delivery_time_min: Mapped[int] = mapped_column(Integer, default=20)
    delivery_time_max: Mapped[int] = mapped_column(Integer, default=30)
    image_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Origem do registro: catálogo próprio ("foodflow") ou descoberta no OSM.
    source: Mapped[str] = mapped_column(
        String(20), default="foodflow", server_default="foodflow"
    )
    # Identificadores e dados complementares do OpenStreetMap. O par
    # (osm_type, osm_id) é único: o mesmo estabelecimento não é duplicado.
    osm_type: Mapped[str | None] = mapped_column(String(20))
    osm_id: Mapped[int | None] = mapped_column(BigInteger)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    cuisine: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(500))
    opening_hours: Mapped[str | None] = mapped_column(String(200))
    osm_url: Mapped[str | None] = mapped_column(String(500))
    # Tags dietéticas declaradas na fonte (ex.: diet:vegan=yes no OSM).
    # Lista vazia significa "não informado", nunca "não possui".
    dietary_tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Última sincronização bem-sucedida com a fonte externa (OSM).
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    # Campos calculados em runtime (distância na busca, score na recomendação).
    # Não são colunas: servem apenas para serialização via Pydantic.
    distance_km: ClassVar[float | None] = None
    score: ClassVar[float | None] = None

    __table_args__ = (
        Index("idx_restaurants_location", "location", postgresql_using="gist"),
        Index("idx_restaurants_active", "is_active"),
        UniqueConstraint("osm_type", "osm_id", name="uq_restaurants_osm"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    dietary_preferences: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("restaurants.id"), nullable=False, index=True
    )
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    order_value: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    delivery_fee: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="Entregue")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    user = relationship("User")
    restaurant = relationship("Restaurant")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(120), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    restaurant = relationship("Restaurant")
    user = relationship("User")


class UserRestaurantInteraction(Base):
    """Comportamento do usuário em relação a um restaurante.

    A tabela é append-only: cada visualização, clique, favorito ou compra vira
    uma linha. O perfil de preferências é derivado das interações, não
    armazenado como estado mutável.
    """

    __tablename__ = "user_restaurant_interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )
    interaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    # Contexto experimental do evento. Eventos antigos (anteriores à migração
    # 0003) permanecem com grupo/versão nulos e são ignorados nas métricas.
    experiment_group: Mapped[str | None] = mapped_column(String(20), index=True)
    # Separação explícita entre o experimento oficial e o modo de demonstração.
    # Eventos de demonstração são persistidos para diagnóstico, mas excluídos
    # das métricas oficiais.
    experiment_mode: Mapped[str] = mapped_column(
        String(10), default="experiment", server_default="experiment", index=True
    )
    experiment_version: Mapped[str | None] = mapped_column(String(40))
    # Identificador da exposição/recomendação que originou o evento. Permite
    # relacionar impressão -> clique -> detalhe -> favorito -> compra.
    recommendation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    recommendation_position: Mapped[int | None] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(String(80))
    # "metadata" é reservado no Declarative do SQLAlchemy; o atributo Python
    # usa outro nome, mas a coluna mantém o nome conceitual do contrato.
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict
    )
    purchase_value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    idempotency_key: Mapped[str | None] = mapped_column(
        String(120), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    user = relationship("User")
    restaurant = relationship("Restaurant")

    __table_args__ = (
        Index("idx_interactions_user_created", "user_id", "created_at"),
        Index(
            "idx_interactions_group_type_created",
            "experiment_group",
            "interaction_type",
            "created_at",
        ),
    )


class ExperimentAssignment(Base):
    """Atribuição persistente de um usuário a um grupo experimental.

    A chave composta ``(user_id, experiment_version)`` permite iniciar uma nova
    versão do experimento sem reutilizar a atribuição anterior. O hash SHA-256
    continua sendo a fonte determinística; a tabela registra data e grupo para
    auditoria e para garantir que o usuário não mude de grupo.
    """

    __tablename__ = "experiment_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    experiment_version: Mapped[str] = mapped_column(String(40), primary_key=True)
    group_name: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str] = mapped_column(
        String(20), default="hash", server_default="hash"
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_experiment_assignments_version_group",
            "experiment_version",
            "group_name",
        ),
    )


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now()
    )

    __table_args__ = (Index("idx_events_type_created_at", "type", "created_at"),)


class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    turno: Mapped[str] = mapped_column(String(20), index=True)
    # Armazena as features do usuário e do contexto no momento da requisição
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )