from app.cache import restaurant_cache
from app.services import restaurant_service

import pytest
from uuid import uuid4

from app.models import Restaurant


def _node(
    osm_id: int,
    tags: dict[str, str],
    lat: float = -23.5505,
    lon: float = -46.6333,
) -> dict:
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": tags}


ELEMENTS = [
    _node(
        1,
        {
            "amenity": "restaurant",
            "name": "Cantina da Praça",
            "cuisine": "italian",
            "addr:street": "Rua Teste",
            "addr:housenumber": "100",
            "addr:city": "Mogi das Cruzes",
            "phone": "+55 11 99999-0000",
            "website": "https://exemplo.test",
            "opening_hours": "Mo-Su 11:00-23:00",
        },
    ),
    {
        "type": "way",
        "id": 2,
        "center": {"lat": -23.551, "lon": -46.634},
        "tags": {
            "amenity": "fast_food",
            "name": "Lanchonete",
            "cuisine": "burger",
        },
    },
    {
        "type": "relation",
        "id": 3,
        "center": {"lat": -23.553, "lon": -46.636},
        "tags": {"amenity": "cafe", "name": "Café Central"},
    },
    # Duplicata do mesmo elemento: deve ser descartada.
    _node(1, {"amenity": "restaurant", "name": "Cantina da Praça"}),
    # Sem coordenadas: deve ser descartado.
    {"type": "node", "id": 4, "tags": {"amenity": "bar", "name": "Bar"}},
]


def test_normalize_elements_extracts_fields_and_dedups() -> None:
    restaurants = restaurant_service.normalize_elements(
        ELEMENTS, -23.5505, -46.6333
    )

    assert len(restaurants) == 3
    assert {item["osm_id"] for item in restaurants} == {1, 2, 3}

    first = restaurants[0]
    assert first["osm_id"] == 1
    assert first["osm_type"] == "node"
    assert first["name"] == "Cantina da Praça"
    assert first["category"] == "restaurant"
    assert first["cuisine"] == "italian"
    assert first["address"] == {
        "street": "Rua Teste",
        "number": "100",
        "city": "Mogi das Cruzes",
        "postcode": None,
    }
    assert first["phone"] == "+55 11 99999-0000"
    assert first["website"] == "https://exemplo.test"
    assert first["opening_hours"] == "Mo-Su 11:00-23:00"
    assert first["osm_url"] == "https://www.openstreetmap.org/node/1"
    assert first["distance_km"] == 0.0

    distances = [item["distance_km"] for item in restaurants]
    assert distances == sorted(distances)

    way = next(item for item in restaurants if item["osm_id"] == 2)
    assert way["osm_type"] == "way"
    assert way["latitude"] == -23.551
    assert way["address"] is None


def test_normalize_elements_handles_missing_fields() -> None:
    restaurants = restaurant_service.normalize_elements(
        [_node(99, {"amenity": "bar"})], -23.5505, -46.6333
    )

    assert restaurants == [
        {
            "osm_id": 99,
            "osm_type": "node",
            "name": restaurant_service.UNNAMED_RESTAURANT,
            "latitude": -23.5505,
            "longitude": -46.6333,
            "category": "bar",
            "cuisine": None,
            "address": None,
            "phone": None,
            "website": None,
            "opening_hours": None,
            "osm_url": "https://www.openstreetmap.org/node/99",
            "dietary_tags": [],
            "distance_km": 0.0,
        }
    ]


def test_normalize_elements_ignores_unsafe_website_scheme() -> None:
    restaurants = restaurant_service.normalize_elements(
        [
            _node(
                50,
                {
                    "amenity": "restaurant",
                    "name": "Suspeito",
                    "website": "javascript:alert(1)",
                },
            ),
            _node(
                51,
                {
                    "amenity": "cafe",
                    "name": "Seguro",
                    "contact:website": "https://seguro.test",
                },
            ),
        ],
        -23.5505,
        -46.6333,
    )

    by_id = {item["osm_id"]: item for item in restaurants}
    assert by_id[50]["website"] is None
    assert by_id[51]["website"] == "https://seguro.test"


def test_normalize_elements_maps_dietary_tags() -> None:
    restaurants = restaurant_service.normalize_elements(
        [
            _node(
                70,
                {
                    "amenity": "restaurant",
                    "name": "Verde",
                    "diet:vegan": "yes",
                    "diet:vegetarian": "only",
                    "diet:gluten_free": "no",
                },
            )
        ],
        -23.5505,
        -46.6333,
    )

    assert restaurants[0]["dietary_tags"] == ["Vegano", "Vegetariano"]


def test_normalize_elements_keeps_dietary_tags_empty_when_absent() -> None:
    restaurants = restaurant_service.normalize_elements(
        [_node(71, {"amenity": "restaurant"})], -23.5505, -46.6333
    )

    assert restaurants[0]["dietary_tags"] == []



async def test_find_nearby_uses_cache_before_overpass(monkeypatch) -> None:
    cached = [
        {
            "osm_id": 7,
            "osm_type": "node",
            "name": "Do Cache",
            "latitude": -23.5505,
            "longitude": -46.6333,
            "distance_km": 9.0,
        }
    ]
    called = False

    async def fake_get(_key):
        return cached

    async def fake_search(*_args, **_kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(
        restaurant_service.restaurant_cache, "get_nearby", fake_get
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "search", fake_search
    )

    restaurants = await restaurant_service.find_nearby_restaurants(
        -23.5505, -46.6333, 3000, "cafe"
    )

    assert called is False
    assert restaurants[0]["osm_id"] == 7
    # A distância é recalculada para a origem da requisição atual.
    assert restaurants[0]["distance_km"] == 0.0


async def test_find_nearby_fetches_and_stores_on_cache_miss(monkeypatch) -> None:
    calls: list[tuple] = []
    saved: dict = {}

    async def fake_get(_key):
        return None

    async def fake_search(lat, lon, radius, category):
        calls.append((lat, lon, radius, category))
        return ELEMENTS

    async def fake_set(key, restaurants):
        saved["key"] = key
        saved["restaurants"] = restaurants
        return True

    monkeypatch.setattr(
        restaurant_service.restaurant_cache, "get_nearby", fake_get
    )
    monkeypatch.setattr(
        restaurant_service.restaurant_cache, "set_nearby", fake_set
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "search", fake_search
    )

    restaurants = await restaurant_service.find_nearby_restaurants(
        -23.5505, -46.6333, 3000, "restaurant"
    )

    assert calls == [(-23.5505, -46.6333, 3000, "restaurant")]
    assert len(restaurants) == 3
    assert saved["key"] == restaurant_cache.build_cache_key(
        -23.5505, -46.6333, 3000, "restaurant"
    )
    assert saved["restaurants"] == restaurants


def test_build_restaurant_values_keeps_missing_fields_empty() -> None:
    values = restaurant_service.build_restaurant_values(ELEMENTS[1])

    assert values is not None
    assert values["source"] == "osm"
    assert values["osm_type"] == "way"
    assert values["osm_id"] == 2
    assert values["name"] == "Lanchonete"
    assert values["address"] == ""
    assert values["phone"] is None
    assert values["website"] is None
    assert values["opening_hours"] is None
    assert values["cuisine"] == "burger"
    assert values["average_rating"] == 0.0
    assert values["review_count"] == 0


def test_build_restaurant_values_rejects_unsupported_amenity() -> None:
    element = _node(80, {"amenity": "pharmacy", "name": "Farmácia"})

    assert restaurant_service.build_restaurant_values(element) is None


async def test_osm_detail_uses_persisted_record_without_refresh(monkeypatch) -> None:
    restaurant = Restaurant(
        id=uuid4(),
        name="Cantina",
        address="Rua Teste, 1",
        categories=["restaurant"],
        source="osm",
        osm_type="node",
        osm_id=1,
    )
    called = False

    async def fake_get_by_osm(*_args, **_kwargs):
        return restaurant

    async def fake_fetch(*_args, **_kwargs):
        nonlocal called
        called = True
        return ELEMENTS[0]

    monkeypatch.setattr(
        restaurant_service.crud, "get_restaurant_by_osm", fake_get_by_osm
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "fetch_element", fake_fetch
    )

    result = await restaurant_service.get_osm_restaurant_detail(
        object(), "node", 1
    )

    assert result is restaurant
    assert called is False


async def test_osm_detail_persists_on_first_access(monkeypatch) -> None:
    restaurant = Restaurant(
        id=uuid4(),
        name="Cantina",
        address="Rua Teste, 1",
        categories=["restaurant"],
        source="osm",
        osm_type="node",
        osm_id=1,
    )

    async def fake_get_by_osm(*_args, **_kwargs):
        return None

    async def fake_fetch(osm_type, osm_id):
        assert (osm_type, osm_id) == ("node", 1)
        return ELEMENTS[0]

    async def fake_upsert(_session, element):
        assert element is ELEMENTS[0]
        return restaurant

    monkeypatch.setattr(
        restaurant_service.crud, "get_restaurant_by_osm", fake_get_by_osm
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "fetch_element", fake_fetch
    )
    monkeypatch.setattr(
        restaurant_service, "upsert_osm_restaurant", fake_upsert
    )

    result = await restaurant_service.get_osm_restaurant_detail(
        object(), "node", 1
    )

    assert result is restaurant


async def test_osm_detail_keeps_local_record_when_overpass_fails(
    monkeypatch,
) -> None:
    restaurant = Restaurant(
        id=uuid4(),
        name="Cantina",
        address="Rua Teste, 1",
        categories=["restaurant"],
        source="osm",
        osm_type="node",
        osm_id=1,
    )

    async def fake_get_by_osm(*_args, **_kwargs):
        return restaurant

    async def fake_fetch(*_args, **_kwargs):
        raise restaurant_service.OverpassError("indisponível")

    monkeypatch.setattr(
        restaurant_service.crud, "get_restaurant_by_osm", fake_get_by_osm
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "fetch_element", fake_fetch
    )

    result = await restaurant_service.get_osm_restaurant_detail(
        object(), "node", 1, refresh=True
    )

    assert result is restaurant


async def test_osm_detail_raises_when_missing_everywhere(monkeypatch) -> None:
    async def fake_get_by_osm(*_args, **_kwargs):
        return None

    async def fake_fetch(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        restaurant_service.crud, "get_restaurant_by_osm", fake_get_by_osm
    )
    monkeypatch.setattr(
        restaurant_service.overpass_client, "fetch_element", fake_fetch
    )

    with pytest.raises(restaurant_service.OsmRestaurantNotFoundError):
        await restaurant_service.get_osm_restaurant_detail(
            object(), "node", 999
        )
