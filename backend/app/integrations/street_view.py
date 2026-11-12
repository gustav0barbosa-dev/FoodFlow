"""Integração opcional com a Google Street View Metadata API.

A chave é lida apenas de ``GOOGLE_MAPS_API_KEY`` no backend. O frontend nunca
recebe a chave: consulta ``/street-view/metadata`` e, quando há panorama,
carrega a imagem pelo proxy ``/street-view/image``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"

# Status documentados pela API que indicam ausência de panorama, não falha.
EMPTY_STATUSES = {"ZERO_RESULTS", "NOT_FOUND"}
ERROR_STATUSES = {
    "OVER_QUERY_LIMIT",
    "REQUEST_DENIED",
    "INVALID_REQUEST",
    "UNKNOWN_ERROR",
}


class StreetViewError(RuntimeError):
    """Falha ao consultar a Street View API."""

    def __init__(self, status: str) -> None:
        super().__init__(f"Street View indisponível ({status})")
        self.status = status


class StreetViewClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.google_maps_api_key
        self.timeout = timeout or settings.street_view_timeout_seconds
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout, connect=min(3.0, self.timeout)),
            transport=self.transport,
        )

    async def metadata(
        self,
        lat: float,
        lon: float,
        radius: int | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            return {"available": False, "status": "NOT_CONFIGURED"}

        params = {
            "location": f"{lat},{lon}",
            "radius": radius or settings.street_view_radius_meters,
            "key": self.api_key,
        }
        try:
            async with self._client() as client:
                response = await client.get(METADATA_URL, params=params)
        except httpx.TimeoutException:
            logger.warning("Timeout ao consultar Street View metadata.")
            return {"available": False, "status": "TIMEOUT"}
        except httpx.HTTPError as exc:
            logger.warning("Falha de rede na Street View metadata: %s", exc)
            return {"available": False, "status": "NETWORK_ERROR"}

        if response.status_code in {401, 403}:
            return {"available": False, "status": "AUTH_ERROR"}
        if response.status_code == 429:
            return {"available": False, "status": "OVER_QUERY_LIMIT"}
        if response.status_code != 200:
            logger.warning(
                "Street View metadata respondeu %s: %s",
                response.status_code,
                response.text[:200],
            )
            return {"available": False, "status": "UPSTREAM_ERROR"}

        try:
            body = response.json()
        except ValueError:
            return {"available": False, "status": "INVALID_RESPONSE"}

        status = str(body.get("status", "UNKNOWN_ERROR"))
        if status == "OK":
            location = body.get("location") or {}
            return {
                "available": True,
                "status": "OK",
                "pano_id": body.get("pano_id"),
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
                "copyright": body.get("copyright"),
            }
        if status in EMPTY_STATUSES:
            return {"available": False, "status": status}
        if status in ERROR_STATUSES:
            logger.warning("Street View retornou status %s", status)
            return {"available": False, "status": status}
        return {"available": False, "status": status}

    async def image(
        self,
        lat: float,
        lon: float,
        *,
        width: int = 600,
        height: int = 400,
    ) -> tuple[bytes, str] | None:
        if not self.configured:
            return None

        params = {
            "location": f"{lat},{lon}",
            "size": f"{width}x{height}",
            "fov": 80,
            "pitch": 0,
            "key": self.api_key,
        }
        try:
            async with self._client() as client:
                response = await client.get(IMAGE_URL, params=params)
        except httpx.TimeoutException as exc:
            raise StreetViewError("TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise StreetViewError("NETWORK_ERROR") from exc

        if response.status_code in {401, 403}:
            raise StreetViewError("AUTH_ERROR")
        if response.status_code == 429:
            raise StreetViewError("OVER_QUERY_LIMIT")
        if response.status_code == 404:
            raise StreetViewError("NOT_FOUND")
        if response.status_code != 200:
            raise StreetViewError(f"UPSTREAM_{response.status_code}")

        content_type = response.headers.get("content-type", "image/jpeg")
        if not content_type.startswith("image/"):
            raise StreetViewError("INVALID_CONTENT_TYPE")
        return response.content, content_type


street_view_client = StreetViewClient()
