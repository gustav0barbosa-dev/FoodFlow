import httpx
import pytest

from app.integrations.street_view import StreetViewClient, StreetViewError


async def test_metadata_without_key_is_not_configured() -> None:
    client = StreetViewClient(api_key="")

    result = await client.metadata(-23.55, -46.63)

    assert result == {"available": False, "status": "NOT_CONFIGURED"}


async def test_metadata_ok_returns_panorama_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["location"] == "-23.55,-46.63"
        assert request.url.params["key"] == "secret"
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "pano_id": "pano-1",
                "location": {"lat": -23.55, "lng": -46.63},
                "copyright": "© Google",
            },
        )

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    result = await client.metadata(-23.55, -46.63)

    assert result["available"] is True
    assert result["pano_id"] == "pano-1"
    assert result["copyright"] == "© Google"


@pytest.mark.parametrize("status", ["ZERO_RESULTS", "NOT_FOUND"])
async def test_metadata_empty_statuses_are_not_errors(status: str) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": status})

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    result = await client.metadata(-23.55, -46.63)

    assert result == {"available": False, "status": status}


@pytest.mark.parametrize(
    ("http_status", "expected"),
    [(401, "AUTH_ERROR"), (403, "AUTH_ERROR"), (429, "OVER_QUERY_LIMIT")],
)
async def test_metadata_maps_http_errors(
    http_status: int, expected: str
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(http_status, text="erro")

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    result = await client.metadata(-23.55, -46.63)

    assert result["available"] is False
    assert result["status"] == expected


async def test_metadata_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    result = await client.metadata(-23.55, -46.63)

    assert result == {"available": False, "status": "TIMEOUT"}


async def test_image_returns_bytes_and_content_type() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"\xff\xd8\xff",
            headers={"content-type": "image/jpeg"},
        )

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    content, content_type = await client.image(-23.55, -46.63)

    assert content == b"\xff\xd8\xff"
    assert content_type == "image/jpeg"


async def test_image_raises_when_not_configured() -> None:
    client = StreetViewClient(api_key="")

    assert await client.image(-23.55, -46.63) is None


async def test_image_raises_on_auth_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    client = StreetViewClient(
        api_key="secret", transport=httpx.MockTransport(handler)
    )

    with pytest.raises(StreetViewError) as excinfo:
        await client.image(-23.55, -46.63)

    assert excinfo.value.status == "AUTH_ERROR"
