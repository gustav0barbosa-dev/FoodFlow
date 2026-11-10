from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import EventType


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
