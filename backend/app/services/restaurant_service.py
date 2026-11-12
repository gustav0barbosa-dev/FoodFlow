"""Regras de negócio da descoberta de restaurantes no OpenStreetMap."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache import restaurant_cache
from app.integrations.overpass_client import (
    OVERPASS_CATEGORY_TAGS,
    OverpassError,
    overpass_client,
)
from app.models import Restaurant

logger = logging.getLogger(__name__)

OSM_TYPES = {"node", "way", "relation"}
EARTH_RADIUS_KM = 6371.0088
MAX_RESULTS = 100
UNNAMED_RESTAURANT = "Restaurante sem nome"

# Tag ``diet:*`` no OSM -> rótulo usado pela UI. Só registramos quando o valor
# é explicitamente afirmativo ("yes", "only", "vegan", etc.). Valores como
# "no" ou "limited" não viram restrição dietética declarada.
DIETARY_TAG_MAP: dict[str, str] = {
    "diet:vegan": "Vegano",
    "diet:vegetarian": "Vegetariano",
    "diet:gluten_free": "Sem glúten",
    "diet:lactose_free": "Sem lactose",
}
_AFFIRMATIVE_VALUES = {"yes", "only", "vegan", "vegetarian", "gluten_free", "lactose_free", "true", "1"}


def _dietary_tags(tags: dict[str, Any]) -> list[str]:
    """Normaliza as tags dietéticas declaradas no OSM.

    Lista vazia significa "não informado", nunca "não possui": o OSM é editado
    por terceiros e a ausência de tag não é uma afirmação negativa.
    """
    result: list[str] = []
    for osm_key, label in DIETARY_TAG_MAP.items():
        value = tags.get(osm_key)
        if isinstance(value, str) and value.strip().casefold() in _AFFIRMATIVE_VALUES:
            result.append(label)
    return result



def _text(tags: dict[str, Any], *keys: str) -> str | None:
    """Retorna o primeiro valor textual não vazio entre as chaves."""
    for key in keys:
        value = tags.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _website(tags: dict[str, Any]) -> str | None:
    """Aceita apenas URLs http(s); o OSM é editado por terceiros."""
    website = _text(tags, "website", "contact:website", "url")
    if website is None:
        return None
    if not website.lower().startswith(("http://", "https://")):
        return None
    return website


def _coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    """Extrai coordenadas de nós ou do centro de ways/relations."""
    lat = element.get("lat")
    lon = element.get("lon")
    if (
        isinstance(lat, (int, float))
        and not isinstance(lat, bool)
        and isinstance(lon, (int, float))
        and not isinstance(lon, bool)
    ):
        return float(lat), float(lon)

    center = element.get("center")
    if isinstance(center, dict):
        center_lat = center.get("lat")
        center_lon = center.get("lon")
        if (
            isinstance(center_lat, (int, float))
            and not isinstance(center_lat, bool)
            and isinstance(center_lon, (int, float))
            and not isinstance(center_lon, bool)
        ):
            return float(center_lat), float(center_lon)

    return None


def _distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Distância em quilômetros pela fórmula de Haversine."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _address(tags: dict[str, Any]) -> dict[str, str | None] | None:
    address = {
        "street": _text(tags, "addr:street"),
        "number": _text(tags, "addr:housenumber"),
        "city": _text(tags, "addr:city", "addr:suburb"),
        "postcode": _text(tags, "addr:postcode"),
    }
    if not any(address.values()):
        return None
    return address


def _normalize_element(
    element: dict[str, Any],
    origin_lat: float,
    origin_lon: float,
) -> dict[str, Any] | None:
    osm_id = element.get("id")
    osm_type = element.get("type")
    if (
        not isinstance(osm_id, int)
        or isinstance(osm_id, bool)
        or osm_type not in OSM_TYPES
    ):
        return None

    coordinates = _coordinates(element)
    if coordinates is None:
        return None

    latitude, longitude = coordinates
    tags = element.get("tags")
    if not isinstance(tags, dict):
        tags = {}

    category = tags.get("amenity")
    if not isinstance(category, str) or not category.strip():
        category = None
    else:
        category = category.strip()

    return {
        "osm_id": osm_id,
        "osm_type": osm_type,
        "name": _text(tags, "name", "name:pt", "brand", "operator")
        or UNNAMED_RESTAURANT,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "cuisine": _text(tags, "cuisine"),
        "address": _address(tags),
        "phone": _text(tags, "phone", "contact:phone"),
        "website": _website(tags),
        "opening_hours": _text(tags, "opening_hours"),
        "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
        "dietary_tags": _dietary_tags(tags),
        "distance_km": round(
            _distance_km(origin_lat, origin_lon, latitude, longitude), 2
        ),
    }


def normalize_elements(
    elements: list[dict[str, Any]],
    origin_lat: float,
    origin_lon: float,
) -> list[dict[str, Any]]:
    """Normaliza, deduplica e ordena os elementos retornados pelo Overpass."""
    unique: dict[tuple[str, int], dict[str, Any]] = {}

    for element in elements:
        normalized = _normalize_element(element, origin_lat, origin_lon)
        if normalized is None:
            continue
        # Mantém a primeira ocorrência: o mesmo elemento pode aparecer em mais
        # de uma cláusula da consulta, mas com as mesmas tags.
        unique.setdefault(
            (normalized["osm_type"], normalized["osm_id"]), normalized
        )

    restaurants = sorted(
        unique.values(),
        key=lambda item: (item["distance_km"], item["name"].casefold()),
    )
    return restaurants[:MAX_RESULTS]


def _refresh_distances(
    restaurants: list[dict[str, Any]],
    origin_lat: float,
    origin_lon: float,
) -> list[dict[str, Any]]:
    """Recalcula distâncias ao ler do cache (a origem pode variar ~100 m)."""
    refreshed: list[dict[str, Any]] = []

    for item in restaurants:
        latitude = item.get("latitude")
        longitude = item.get("longitude")
        cached = dict(item)
        if isinstance(latitude, (int, float)) and isinstance(
            longitude, (int, float)
        ):
            cached["distance_km"] = round(
                _distance_km(
                    origin_lat, origin_lon, float(latitude), float(longitude)
                ),
                2,
            )
        refreshed.append(cached)

    refreshed.sort(
        key=lambda item: (
            item.get("distance_km") or 0.0,
            str(item.get("name", "")).casefold(),
        )
    )
    return refreshed


async def find_nearby_restaurants(
    lat: float,
    lon: float,
    radius: int,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Busca restaurantes próximos, usando Redis antes da Overpass API."""
    cache_key = restaurant_cache.build_cache_key(lat, lon, radius, category)

    cached = await restaurant_cache.get_nearby(cache_key)
    if cached is not None:
        logger.info("Cache hit OSM para %s", cache_key)
        return _refresh_distances(cached, lat, lon)

    elements = await overpass_client.search(lat, lon, radius, category)
    restaurants = normalize_elements(elements, lat, lon)
    await restaurant_cache.set_nearby(cache_key, restaurants)
    return restaurants


class OsmRestaurantNotFoundError(LookupError):
    """O elemento do OSM não existe ou não é um estabelecimento suportado."""


def format_osm_address(address: dict[str, Any] | None) -> str:
    """Formata o endereço do OSM no mesmo padrão exibido no frontend."""
    if not address:
        return ""

    street = ", ".join(
        value
        for value in (address.get("street"), address.get("number"))
        if isinstance(value, str) and value.strip()
    )
    return " · ".join(
        value
        for value in (
            street,
            address.get("city"),
            address.get("postcode"),
        )
        if isinstance(value, str) and value.strip()
    )


def build_restaurant_values(
    element: dict[str, Any],
) -> dict[str, Any] | None:
    """Converte um elemento do OSM nos campos do restaurante persistido.

    Retorna ``None`` quando o elemento não tem coordenadas ou não é uma
    categoria de alimentação suportada. Campos ausentes no OSM permanecem
    nulos ou vazios: nenhum dado é inventado.
    """
    coordinates = _coordinates(element)
    if coordinates is None:
        return None

    latitude, longitude = coordinates
    normalized = _normalize_element(element, latitude, longitude)
    if normalized is None:
        return None

    category = normalized.get("category")
    if category not in OVERPASS_CATEGORY_TAGS:
        return None

    return {
        "name": normalized["name"],
        "description": None,
        "phone": normalized["phone"],
        "address": format_osm_address(normalized["address"]),
        "location": WKTElement(
            f"POINT({longitude} {latitude})", srid=4326
        ),
        "categories": [category],
        # Valores neutros exigidos pelo schema; a UI esconde métricas de
        # avaliação/entrega para registros de origem OSM.
        "average_rating": 0.0,
        "review_count": 0,
        "delivery_fee": 0.0,
        "delivery_time_min": 20,
        "delivery_time_max": 30,
        "image_url": None,
        "is_active": True,
        "source": "osm",
        "osm_type": normalized["osm_type"],
        "osm_id": normalized["osm_id"],
        "latitude": latitude,
        "longitude": longitude,
        "cuisine": normalized["cuisine"],
        "website": normalized["website"],
        "opening_hours": normalized["opening_hours"],
        "osm_url": normalized["osm_url"],
        "dietary_tags": normalized["dietary_tags"],
        "last_synced_at": datetime.now(timezone.utc),
    }


async def upsert_osm_restaurant(
    session: AsyncSession,
    element: dict[str, Any],
) -> Restaurant | None:
    """Persiste (ou atualiza) um restaurante descoberto no OSM."""
    values = build_restaurant_values(element)
    if values is None:
        return None

    existing = await crud.get_restaurant_by_osm(
        session, values["osm_type"], values["osm_id"]
    )

    if existing is not None:
        for key, value in values.items():
            setattr(existing, key, value)
        await session.commit()
        await session.refresh(existing)
        return existing

    restaurant = Restaurant(**values)
    session.add(restaurant)

    try:
        await session.commit()
    except IntegrityError:
        # Outra requisição persistiu o mesmo elemento em paralelo.
        await session.rollback()
        existing = await crud.get_restaurant_by_osm(
            session, values["osm_type"], values["osm_id"]
        )
        if existing is None:
            raise
        return existing

    await session.refresh(restaurant)
    return restaurant


async def get_osm_restaurant_detail(
    session: AsyncSession,
    osm_type: str,
    osm_id: int,
    refresh: bool = False,
) -> Restaurant:
    """Retorna o restaurante do OSM, persistindo-o no primeiro acesso.

    Por padrão usa o registro já persistido para evitar uma consulta à
    Overpass a cada abertura de detalhes. ``refresh=True`` atualiza os dados
    a partir do OSM; se a Overpass falhar, o registro local é mantido.
    """
    existing = await crud.get_restaurant_by_osm(session, osm_type, osm_id)
    if existing is not None and not refresh:
        return existing

    try:
        element = await overpass_client.fetch_element(osm_type, osm_id)
    except OverpassError:
        if existing is not None:
            logger.warning(
                "Overpass indisponível ao atualizar %s/%s; usando cache local.",
                osm_type,
                osm_id,
            )
            return existing
        raise

    if element is None:
        if existing is not None:
            return existing
        raise OsmRestaurantNotFoundError(
            "Estabelecimento não encontrado no OpenStreetMap."
        )

    restaurant = await upsert_osm_restaurant(session, element)
    if restaurant is None:
        if existing is not None:
            return existing
        raise OsmRestaurantNotFoundError(
            "O elemento do OpenStreetMap não é um estabelecimento de "
            "alimentação suportado."
        )
    return restaurant
