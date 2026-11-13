"""Cliente da Overpass API para consultar restaurantes no OpenStreetMap.

A Overpass API usa instâncias públicas compartilhadas. Por isso o cliente:

- restringe a consulta à área necessária (``around``);
- define timeout próprio;
- envia um ``User-Agent`` identificável;
- limita requisições concorrentes;
- distingue erro de rede, timeout e rate limit para o endpoint responder
  adequadamente.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Categorias expostas pelo FoodFlow -> valor da tag ``amenity`` no OSM.
OVERPASS_CATEGORY_TAGS: dict[str, str] = {
    "restaurant": "restaurant",
    "fast_food": "fast_food",
    "cafe": "cafe",
    "bar": "bar",
}

SUPPORTED_CATEGORIES = tuple(OVERPASS_CATEGORY_TAGS)
SUPPORTED_OSM_TYPES = ("node", "way", "relation")
MAX_RADIUS_METERS = 50000

# O timeout do cliente HTTP precisa ser maior que o timeout da consulta QL:
# assim a Overpass consegue responder (inclusive com erro/resultado parcial)
# antes de o cliente abortar a conexão. Em redes lentas a consulta inicial
# costuma levar mais que o timeout do QL.
HTTP_TIMEOUT_GRACE_SECONDS = 20

# A instância pública não deve receber muitas consultas simultâneas.
_request_semaphore = asyncio.Semaphore(2)

# Resiliência a indisponibilidades temporárias da Overpass. A consulta é
# somente leitura, então repetir é seguro mesmo em timeout/erro de rede.
RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})
MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 5.0
RETRY_MAX_DELAY_SECONDS = 120.0
RETRY_JITTER_RATIO = 0.25


async def _sleep(seconds: float) -> None:
    """Ponto único de espera, substituível em testes."""
    await asyncio.sleep(seconds)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Interpreta ``Retry-After`` em segundos ou como data HTTP."""
    raw_value = response.headers.get("Retry-After")
    if raw_value is None:
        return None

    value = raw_value.strip()
    if not value:
        return None

    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            logger.debug("Retry-After inválido: %r", raw_value)
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()

    if seconds < 0:
        return 0.0
    return min(seconds, RETRY_MAX_DELAY_SECONDS)


def _backoff_delay(retry_number: int) -> float:
    """Backoff exponencial com jitter para a n-ésima nova tentativa."""
    base = RETRY_BASE_DELAY_SECONDS * (2 ** (retry_number - 1))
    jitter = random.uniform(0, base * RETRY_JITTER_RATIO)
    return min(base + jitter, RETRY_MAX_DELAY_SECONDS)


class OverpassError(RuntimeError):
    """Falha ao consultar a Overpass API."""


class OverpassRateLimitError(OverpassError):
    """A Overpass API recusou a consulta por limite de uso (HTTP 429)."""


class OverpassTimeoutError(OverpassError):
    """A consulta excedeu o tempo limite na Overpass API."""


def build_overpass_query(
    lat: float,
    lon: float,
    radius: int,
    category: str | None = None,
    timeout: int | None = None,
) -> str:
    """Monta a consulta Overpass QL para restaurantes dentro de um raio."""
    if not 0 < radius <= MAX_RADIUS_METERS:
        raise ValueError(
            f"radius deve estar entre 1 e {MAX_RADIUS_METERS} metros"
        )

    if category is not None and category not in OVERPASS_CATEGORY_TAGS:
        raise ValueError(f"categoria não suportada: {category}")

    categories = (
        [category] if category is not None else list(SUPPORTED_CATEGORIES)
    )
    clauses = "\n".join(
        f'  nwr(around:{radius},{lat},{lon})["amenity"="{amenity}"];'
        for amenity in (OVERPASS_CATEGORY_TAGS[item] for item in categories)
    )

    return (
        f"[out:json][timeout:{timeout or settings.overpass_timeout_seconds}];\n"
        f"(\n{clauses}\n);\n"
        "out center tags;\n"
    )


def build_element_query(
    osm_type: str,
    osm_id: int,
    timeout: int | None = None,
) -> str:
    """Consulta um elemento específico do OSM pelo par tipo/id."""
    if osm_type not in SUPPORTED_OSM_TYPES:
        raise ValueError(f"tipo OSM não suportado: {osm_type}")
    if osm_id <= 0:
        raise ValueError("osm_id deve ser positivo")

    return (
        f"[out:json][timeout:{timeout or settings.overpass_timeout_seconds}];\n"
        f"{osm_type}({osm_id});\n"
        "out center tags;\n"
    )


# Limite de área para ingestão em lote. Regiões maiores devem ser divididas
# em tiles para não sobrecarregar a instância pública da Overpass.
MAX_BBOX_AREA_DEG2 = 1.0


def _validate_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
) -> None:
    if not (-90 <= south < north <= 90):
        raise ValueError("latitude inválida: exige -90 <= south < north <= 90")
    if not (-180 <= west < east <= 180):
        raise ValueError("longitude inválida: exige -180 <= west < east <= 180")
    area = (north - south) * (east - west)
    if area > MAX_BBOX_AREA_DEG2:
        raise ValueError(
            f"área do bbox ({area:.4f} graus²) excede o limite de "
            f"{MAX_BBOX_AREA_DEG2}; divida a região em tiles"
        )


def build_bbox_query(
    south: float,
    west: float,
    north: float,
    east: float,
    category: str | None = None,
    timeout: int | None = None,
) -> str:
    """Monta a consulta Overpass QL para uma região retangular (bbox).

    A ordem do bbox na Overpass QL é ``(south, west, north, east)``.
    """
    _validate_bbox(south, west, north, east)

    if category is not None and category not in OVERPASS_CATEGORY_TAGS:
        raise ValueError(f"categoria não suportada: {category}")

    categories = (
        [category] if category is not None else list(SUPPORTED_CATEGORIES)
    )
    bbox = f"{south},{west},{north},{east}"
    clauses = "\n".join(
        f'  nwr({bbox})["amenity"="{amenity}"];'
        for amenity in (OVERPASS_CATEGORY_TAGS[item] for item in categories)
    )

    return (
        f"[out:json][timeout:{timeout or settings.overpass_timeout_seconds}];\n"
        f"(\n{clauses}\n);\n"
        "out center tags;\n"
    )


class OverpassClient:
    """Cliente HTTP injetável (transport) para testes e uso em produção."""

    def __init__(
        self,
        *,
        url: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = url or settings.overpass_api_url
        self.timeout = timeout or settings.overpass_timeout_seconds
        self.user_agent = user_agent or settings.overpass_user_agent
        self.transport = transport

    async def search(
        self,
        lat: float,
        lon: float,
        radius: int,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Executa a consulta e devolve os elementos brutos do OSM."""
        query = build_overpass_query(
            lat, lon, radius, category, timeout=int(self.timeout)
        )
        return await self._fetch_elements(query)

    async def fetch_element(
        self,
        osm_type: str,
        osm_id: int,
    ) -> dict[str, Any] | None:
        """Busca um estabelecimento específico pelo par tipo/id do OSM."""
        query = build_element_query(
            osm_type, osm_id, timeout=int(self.timeout)
        )
        elements = await self._fetch_elements(query)
        for element in elements:
            if element.get("type") == osm_type and element.get("id") == osm_id:
                return element
        return None

    async def search_bbox(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Busca todos os restaurantes dentro de uma região retangular."""
        query = build_bbox_query(
            south,
            west,
            north,
            east,
            category,
            timeout=int(self.timeout),
        )
        return await self._fetch_elements(query)

    async def _wait_before_retry(
        self,
        attempt: int,
        *,
        response: httpx.Response | None = None,
        error: OverpassError | None = None,
    ) -> None:
        """Aguarda fora do semáforo antes de repetir a consulta."""
        total_attempts = MAX_RETRY_ATTEMPTS + 1
        retry_after = (
            _retry_after_seconds(response) if response is not None else None
        )
        delay = (
            retry_after
            if retry_after is not None
            else _backoff_delay(attempt)
        )

        if response is not None:
            logger.warning(
                "Overpass API respondeu %s (tentativa %s/%s); "
                "nova tentativa em %.1fs%s",
                response.status_code,
                attempt,
                total_attempts,
                delay,
                " (Retry-After)" if retry_after is not None else "",
            )
        else:
            logger.warning(
                "%s (tentativa %s/%s); nova tentativa em %.1fs",
                error,
                attempt,
                total_attempts,
                delay,
            )

        # O semáforo já foi liberado ao sair do ``async with`` acima; a espera
        # não pode bloquear outras consultas.
        await _sleep(delay)

    async def _fetch_elements(self, query: str) -> list[dict[str, Any]]:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

        timeout = httpx.Timeout(
            self.timeout + HTTP_TIMEOUT_GRACE_SECONDS, connect=10.0
        )
        total_attempts = MAX_RETRY_ATTEMPTS + 1

        for attempt in range(1, total_attempts + 1):
            try:
                async with _request_semaphore:
                    async with httpx.AsyncClient(
                        timeout=timeout, transport=self.transport
                    ) as client:
                        response = await client.post(
                            self.url, data={"data": query}, headers=headers
                        )
            except httpx.TimeoutException as exc:
                error = OverpassTimeoutError(
                    "Tempo esgotado ao consultar a Overpass API"
                )
                if attempt < total_attempts:
                    await self._wait_before_retry(attempt, error=error)
                    continue
                raise error from exc
            except httpx.HTTPError as exc:
                error = OverpassError(
                    "Falha de rede ao consultar a Overpass API"
                )
                # Só falhas de transporte (conexão, leitura, protocolo) são
                # potencialmente transitórias; erros de configuração/redirect
                # não devem ser repetidos.
                if (
                    attempt < total_attempts
                    and isinstance(exc, httpx.TransportError)
                ):
                    await self._wait_before_retry(attempt, error=error)
                    continue
                raise error from exc

            if (
                response.status_code in RETRYABLE_STATUS_CODES
                and attempt < total_attempts
            ):
                await self._wait_before_retry(attempt, response=response)
                continue

            if response.status_code == 429:
                raise OverpassRateLimitError(
                    "Overpass API limitou as requisições (HTTP 429) "
                    f"após {attempt} tentativa(s)"
                )
            if response.status_code == 504:
                raise OverpassTimeoutError(
                    "Overpass API excedeu o tempo limite (HTTP 504) "
                    f"após {attempt} tentativa(s)"
                )
            if response.status_code != 200:
                logger.warning(
                    "Overpass API respondeu %s: %s",
                    response.status_code,
                    response.text[:200],
                )
                raise OverpassError(
                    f"Overpass API respondeu {response.status_code} "
                    f"após {attempt} tentativa(s)"
                )

            break

        try:
            body = response.json()
        except ValueError as exc:
            raise OverpassError("Resposta inválida da Overpass API") from exc

        if not isinstance(body, dict):
            raise OverpassError("Resposta inesperada da Overpass API")

        elements = body.get("elements", [])
        remark = body.get("remark")
        if remark and not elements:
            logger.warning("Overpass API retornou erro: %s", remark)
            raise OverpassError(f"Overpass API retornou erro: {remark}")
        if not isinstance(elements, list):
            raise OverpassError("Resposta inesperada da Overpass API")

        return [element for element in elements if isinstance(element, dict)]


overpass_client = OverpassClient()
