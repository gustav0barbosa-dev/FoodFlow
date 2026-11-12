from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import EventType


def _none_to_list(value: object) -> object:
    return [] if value is None else value


def _none_to_dict(value: object) -> object:
    return {} if value is None else value


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    phone: str | None = None
    address: str
    distance_km: float | None = None
    categories: list[str]
    average_rating: float
    review_count: int
    delivery_fee: float
    delivery_time_min: int
    delivery_time_max: int
    image_url: str | None = None
    # Origem e dados complementares do OpenStreetMap. Registros do catálogo
    # próprio mantêm source="foodflow" e os campos osm_* nulos.
    source: str | None = None
    osm_type: str | None = None
    osm_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    cuisine: str | None = None
    website: str | None = None
    opening_hours: str | None = None
    osm_url: str | None = None
    dietary_tags: list[str] = Field(default_factory=list)
    last_synced_at: datetime | None = None

    @field_validator("dietary_tags", mode="before")
    @classmethod
    def _dietary_tags_default(cls, value: object) -> object:
        return _none_to_list(value)


class NearbyCategory(str, Enum):
    """Categorias do OpenStreetMap suportadas pela busca por proximidade."""

    restaurant = "restaurant"
    fast_food = "fast_food"
    cafe = "cafe"
    bar = "bar"


class OsmAddressOut(BaseModel):
    street: str | None = None
    number: str | None = None
    city: str | None = None
    postcode: str | None = None


class OsmRestaurantOut(BaseModel):
    """Estabelecimento descoberto no OpenStreetMap via Overpass API.

    Não representa um restaurante do catálogo do FoodFlow: cardápio, taxa e
    tempo de entrega não fazem parte deste contrato. Campos ausentes no OSM
    são retornados como ``null``.
    """

    osm_id: int
    osm_type: str
    name: str
    latitude: float
    longitude: float
    category: str | None = None
    cuisine: str | None = None
    address: OsmAddressOut | None = None
    phone: str | None = None
    website: str | None = None
    opening_hours: str | None = None
    osm_url: str | None = None
    dietary_tags: list[str] = Field(default_factory=list)
    distance_km: float | None = None


class NearbyRestaurantsOut(BaseModel):
    source: str = "OpenStreetMap"
    count: int
    restaurants: list[OsmRestaurantOut]


class InteractionType(str, Enum):
    """Tipos de comportamento registrados para o recomendador."""

    impression = "IMPRESSION"
    view = "VIEW"
    view_details = "VIEW_DETAILS"
    click = "CLICK"
    favorite = "FAVORITE"
    purchase = "PURCHASE"
    dismiss = "DISMISS"


class InteractionIn(BaseModel):
    user_id: UUID
    restaurant_id: UUID
    interaction_type: InteractionType
    purchase_value: float | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, max_length=120)
    experiment_group: str | None = Field(default=None, max_length=20)
    experiment_mode: str = Field(default="experiment", pattern="^(experiment|demo)$")
    experiment_version: str | None = Field(default=None, max_length=40)
    recommendation_id: str | None = Field(default=None, max_length=64)
    recommendation_position: int | None = Field(default=None, ge=0)
    model_version: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    restaurant_id: UUID
    interaction_type: str
    purchase_value: float | None = None
    experiment_group: str | None = None
    # ``None`` é aceito para linhas antigas; o banco preenche o default.
    experiment_mode: str | None = "experiment"
    experiment_version: str | None = None
    recommendation_id: str | None = None
    recommendation_position: int | None = None
    model_version: str | None = None
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("event_metadata", mode="before")
    @classmethod
    def _event_metadata_default(cls, value: object) -> object:
        return _none_to_dict(value)


class PreferenceItemOut(BaseModel):
    name: str
    score: float


class PreferenceRestaurantOut(BaseModel):
    restaurant_id: UUID
    name: str
    score: float
    purchases: int


class UserPreferenceProfileOut(BaseModel):
    user_id: UUID
    total_interactions: int
    views: int
    clicks: int
    favorites: int
    purchases: int
    impressions: int = 0
    dismissals: int = 0
    total_spent: float
    average_purchase_value: float
    top_categories: list[PreferenceItemOut] = Field(default_factory=list)
    top_cuisines: list[PreferenceItemOut] = Field(default_factory=list)
    top_restaurants: list[PreferenceRestaurantOut] = Field(default_factory=list)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    restaurant_id: UUID
    user_id: UUID
    user_name: str | None = None
    rating: int
    comment: str | None = None
    created_at: datetime


class RestaurantDetailOut(RestaurantOut):
    reviews: list[ReviewOut] = Field(default_factory=list)


class RecommendationOut(RestaurantOut):
    score: float = 0.0


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    dietary_preferences: list[str] = Field(default_factory=list)
    created_at: datetime


class RestaurantSearchParams(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=5, gt=0, le=50)
    limit: int = Field(default=20, gt=0, le=100)
    offset: int = Field(default=0, ge=0)


class ReviewCreate(BaseModel):
    restaurant_id: UUID
    user_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(BaseModel):
    user_id: UUID
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class EventIn(BaseModel):
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    payload: dict[str, Any]
    created_at: datetime
