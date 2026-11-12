"""Endpoints de Street View (metadata + proxy de imagem).

A chave da Google Maps API permanece exclusivamente no backend. O frontend
consulta a metadata para decidir se exibe o componente e, quando há panorama,
carrega a imagem pelo proxy para nunca receber a chave.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Response

from app.integrations.street_view import StreetViewError, street_view_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/street-view", tags=["street-view"])

MAX_IMAGE_SIZE = 640
MIN_IMAGE_SIZE = 100
# A imagem de um panorama é estável por muito tempo; cacheável no navegador.
IMAGE_CACHE_SECONDS = 86400


@router.get("/metadata")
async def street_view_metadata(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(50, ge=1, le=500),
) -> dict:
    """Informa se há panorama disponível nas coordenadas.

    Nunca levanta erro para ausência de cobertura: ``available=False`` com o
    status correspondente é a resposta esperada e permite ao frontend ocultar
    o componente sem quebrar a tela.
    """
    return await street_view_client.metadata(lat, lon, radius)


@router.get("/image")
async def street_view_image(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    width: int = Query(600, ge=MIN_IMAGE_SIZE, le=MAX_IMAGE_SIZE),
    height: int = Query(400, ge=MIN_IMAGE_SIZE, le=MAX_IMAGE_SIZE),
) -> Response:
    """Faz proxy da imagem do Street View sem expor a chave da API."""
    try:
        result = await street_view_client.image(lat, lon, width=width, height=height)
    except StreetViewError as exc:
        # Não vazamos detalhes internos da chave; o status basta ao frontend.
        status_code = {
            "AUTH_ERROR": 502,
            "OVER_QUERY_LIMIT": 429,
            "TIMEOUT": 504,
            "NOT_FOUND": 404,
        }.get(exc.status, 502)
        raise HTTPException(
            status_code=status_code,
            detail=f"Street View indisponível ({exc.status}).",
        ) from exc

    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Street View não configurado no servidor.",
        )

    content, content_type = result
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": f"public, max-age={IMAGE_CACHE_SECONDS}",
            "X-Street-View-Proxy": "foodflow",
        },
    )
