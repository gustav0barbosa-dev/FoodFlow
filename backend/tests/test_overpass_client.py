from urllib.parse import parse_qs

import httpx
import pytest

from app.integrations import overpass_client as op


@pytest.fixture(autouse=True)
def retry_delays(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Captura as esperas de retry sem tornar a suíte lenta."""
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr(op, "_sleep", fake_sleep)
    return delays


def test_build_query_includes_all_categories_by_default() -> None:
    query = op.build_overpass_query(-23.5505, -46.6333, 3000)

    assert "[out:json]" in query
    for amenity in ("restaurant", "fast_food", "cafe", "bar"):
        assert (
            f'nwr(around:3000,-23.5505,-46.6333)["amenity"="{amenity}"]'
            in query
        )
    assert query.rstrip().endswith("out center tags;")


def test_build_query_filters_specific_category() -> None:
    query = op.build_overpass_query(-23.5, -46.6, 1500, "cafe")

    assert '["amenity"="cafe"]' in query
    assert '["amenity"="restaurant"]' not in query


@pytest.mark.parametrize("radius", [0, -1, 50001])
def test_build_query_rejects_invalid_radius(radius: int) -> None:
    with pytest.raises(ValueError):
        op.build_overpass_query(0, 0, radius)


def test_build_query_rejects_unknown_category() -> None:
    with pytest.raises(ValueError):
        op.build_overpass_query(0, 0, 1000, "sushi")


def test_build_element_query_uses_type_and_id() -> None:
    query = op.build_element_query("way", 12345, timeout=15)

    assert "[out:json][timeout:15]" in query
    assert "way(12345);" in query
    assert query.rstrip().endswith("out center tags;")


@pytest.mark.parametrize("osm_type", ["invalid", "Node", ""])
def test_build_element_query_rejects_unknown_type(osm_type: str) -> None:
    with pytest.raises(ValueError):
        op.build_element_query(osm_type, 1)


@pytest.mark.parametrize("osm_id", [0, -1])
def test_build_element_query_rejects_invalid_id(osm_id: int) -> None:
    with pytest.raises(ValueError):
        op.build_element_query("node", osm_id)


async def test_fetch_element_returns_matching_element() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["data"] = parse_qs(request.content.decode())["data"][0]
        return httpx.Response(
            200,
            json={
                "elements": [
                    {"type": "node", "id": 7, "tags": {"amenity": "cafe"}}
                ]
            },
        )

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    element = await client.fetch_element("node", 7)

    assert "node(7);" in captured["data"]
    assert element == {
        "type": "node",
        "id": 7,
        "tags": {"amenity": "cafe"},
    }


async def test_fetch_element_returns_none_when_absent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"elements": []})

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    assert await client.fetch_element("node", 7) is None


async def test_search_posts_query_and_returns_elements() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["user_agent"] = request.headers.get("User-Agent", "")
        captured["data"] = parse_qs(request.content.decode())["data"][0]
        return httpx.Response(
            200,
            json={"elements": [{"type": "node", "id": 1}]},
        )

    client = op.OverpassClient(
        url="https://overpass.test/api",
        timeout=42,
        user_agent="FoodFlow/test",
        transport=httpx.MockTransport(handler),
    )

    elements = await client.search(-23.55, -46.63, 3000, "restaurant")

    assert captured["url"] == "https://overpass.test/api"
    assert captured["user_agent"] == "FoodFlow/test"
    assert "[timeout:42]" in captured["data"]
    assert '["amenity"="restaurant"]' in captured["data"]
    assert "around:3000,-23.55,-46.63" in captured["data"]
    assert elements == [{"type": "node", "id": 1}]


@pytest.mark.parametrize(
    ("status", "error_cls"),
    [
        (429, op.OverpassRateLimitError),
        (504, op.OverpassTimeoutError),
        (500, op.OverpassError),
    ],
)
async def test_search_maps_upstream_http_errors(
    status: int, error_cls: type[Exception]
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="erro")

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(error_cls):
        await client.search(-23.55, -46.63, 3000)


async def test_search_maps_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassError, match="rede"):
        await client.search(-23.55, -46.63, 3000)


async def test_search_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassTimeoutError):
        await client.search(-23.55, -46.63, 3000)


@pytest.mark.parametrize("status", [429, 502, 503])
async def test_search_retries_transient_http_errors(
    status: int, retry_delays: list[float]
) -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(status, text="indisponível")
        return httpx.Response(
            200, json={"elements": [{"type": "node", "id": 1}]}
        )

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    elements = await client.search(-23.55, -46.63, 3000)

    assert elements == [{"type": "node", "id": 1}]
    assert calls["count"] == 2
    assert len(retry_delays) == 1
    assert retry_delays[0] >= op.RETRY_BASE_DELAY_SECONDS
    assert retry_delays[0] <= op.RETRY_BASE_DELAY_SECONDS * (
        1 + op.RETRY_JITTER_RATIO
    )


async def test_search_exhausts_retries_for_504(
    retry_delays: list[float],
) -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(504, text="gateway timeout")

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassTimeoutError, match="504"):
        await client.search(-23.55, -46.63, 3000)

    assert calls["count"] == op.MAX_RETRY_ATTEMPTS + 1
    assert len(retry_delays) == op.MAX_RETRY_ATTEMPTS
    assert retry_delays[0] >= 5.0
    assert retry_delays[1] >= 10.0
    assert retry_delays[2] >= 20.0


async def test_search_does_not_retry_permanent_http_errors(
    retry_delays: list[float],
) -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, text="consulta inválida")

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassError, match="400"):
        await client.search(-23.55, -46.63, 3000)

    assert calls["count"] == 1
    assert retry_delays == []


async def test_search_respects_retry_after_header(
    retry_delays: list[float],
) -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                429, headers={"Retry-After": "7"}, text="limite de uso"
            )
        return httpx.Response(200, json={"elements": []})

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    await client.search(-23.55, -46.63, 3000)

    assert calls["count"] == 2
    assert retry_delays == [7.0]


async def test_search_ignores_invalid_retry_after_header(
    retry_delays: list[float],
) -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                503, headers={"Retry-After": "em breve"}, text="indisponível"
            )
        return httpx.Response(200, json={"elements": []})

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    await client.search(-23.55, -46.63, 3000)

    assert calls["count"] == 2
    assert len(retry_delays) == 1
    assert retry_delays[0] >= op.RETRY_BASE_DELAY_SECONDS


async def test_search_retries_network_error_then_succeeds(
    retry_delays: list[float],
) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("sem rede", request=request)
        return httpx.Response(
            200, json={"elements": [{"type": "node", "id": 2}]}
        )

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    elements = await client.search(-23.55, -46.63, 3000)

    assert elements == [{"type": "node", "id": 2}]
    assert calls["count"] == 2
    assert len(retry_delays) == 1


async def test_retry_wait_releases_request_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_semaphore_values: list[int] = []

    async def fake_sleep(_seconds: float) -> None:
        observed_semaphore_values.append(op._request_semaphore._value)

    monkeypatch.setattr(op, "_sleep", fake_sleep)

    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json={"elements": []})

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    await client.search(-23.55, -46.63, 3000)

    assert observed_semaphore_values == [2]


async def test_search_raises_when_overpass_reports_runtime_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "elements": [],
                "remark": "runtime error: Query timed out",
            },
        )

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassError, match="runtime error"):
        await client.search(-23.55, -46.63, 3000)


async def test_search_rejects_invalid_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="não é json")

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    with pytest.raises(op.OverpassError, match="inválida"):
        await client.search(-23.55, -46.63, 3000)


def test_build_bbox_query_uses_south_west_north_east_order() -> None:
    query = op.build_bbox_query(-23.6, -46.7, -23.5, -46.6, "cafe")

    assert "nwr(-23.6,-46.7,-23.5,-46.6)" in query
    assert '["amenity"="cafe"]' in query
    assert '["amenity"="restaurant"]' not in query


@pytest.mark.parametrize(
    "bbox",
    [
        (-23.5, -46.7, -24.0, -46.6),  # south > north
        (-23.6, -46.5, -23.5, -46.6),  # west > east
        (-91.0, -46.7, -23.5, -46.6),  # latitude fora do intervalo
    ],
)
def test_build_bbox_query_rejects_invalid_bounds(bbox) -> None:
    with pytest.raises(ValueError):
        op.build_bbox_query(*bbox)


def test_build_bbox_query_rejects_region_too_large() -> None:
    with pytest.raises(ValueError, match="excede"):
        op.build_bbox_query(-24.0, -47.0, -22.0, -45.0)


async def test_search_bbox_posts_bbox_query() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["data"] = parse_qs(request.content.decode())["data"][0]
        return httpx.Response(
            200,
            json={"elements": [{"type": "way", "id": 9, "center": {"lat": 0, "lon": 0}}]},
        )

    client = op.OverpassClient(transport=httpx.MockTransport(handler))

    elements = await client.search_bbox(-23.6, -46.7, -23.5, -46.6)

    assert "nwr(-23.6,-46.7,-23.5,-46.6)" in captured["data"]
    assert elements[0]["id"] == 9
