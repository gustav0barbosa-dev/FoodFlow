from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class RestaurantOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    phone: str | None
    address: str
    distance_km: float | None = None
    categories: list[str]
    average_rating: float
    review_count: int
    delivery_fee: float
    delivery_time_min: int
    delivery_time_max: int
    image_url: str | None

    class Config:
        from_attributes = True


class RestaurantSearchParams(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=5, gt=0, le=50)
    limit: int = Field(default=20, gt=0, le=100)
    offset: int = Field(default=0, ge=0)


class EventIn(BaseModel):
    type: str = Field(max_length=60)
    payload: dict[str, Any] = {}


class EventOut(BaseModel):
    id: UUID
    type: str
    payload: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True
