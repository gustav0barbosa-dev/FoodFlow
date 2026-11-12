"""Pipeline de ingestão de restaurantes do OpenStreetMap por região.

A ingestão é uma operação de manutenção, executada por CLI/script — nunca por
um endpoint HTTP. Ela:

1. consulta a Overpass API para um bbox (região retangular);
2. normaliza os elementos (nome, endereço, cozinha, dietas, coordenadas);
3. deduplica por ``(osm_type, osm_id)``;
4. valida que o elemento é um estabelecimento de alimentação suportado;
5. faz upsert no PostgreSQL, atualizando ``last_synced_at``;
6. devolve um resumo (criados, atualizados, ignorados e erros).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.integrations.overpass_client import overpass_client
from app.services.restaurant_service import build_restaurant_values

logger = logging.getLogger(__name__)


@dataclass
class IngestionSummary:
    region: dict[str, float]
    fetched: int = 0
    deduplicated: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "fetched": self.fetched,
            "deduplicated": self.deduplicated,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "error_count": len(self.errors),
            "errors": self.errors[:20],
        }


def _deduplicate(
    elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove duplicatas do mesmo elemento mantendo a primeira ocorrência."""
    unique: dict[tuple[str, int], dict[str, Any]] = {}
    for element in elements:
        osm_type = element.get("type")
        osm_id = element.get("id")
        if not isinstance(osm_id, int) or isinstance(osm_id, bool):
            continue
        if osm_type not in {"node", "way", "relation"}:
            continue
        unique.setdefault((str(osm_type), osm_id), element)
    return list(unique.values())


async def ingest_region(
    session: AsyncSession,
    *,
    south: float,
    west: float,
    north: float,
    east: float,
    category: str | None = None,
    client=None,
) -> IngestionSummary:
    """Executa a ingestão de um bbox e devolve o resumo da operação."""
    overpass = client or overpass_client
    summary = IngestionSummary(
        region={
            "south": south,
            "west": west,
            "north": north,
            "east": east,
        }
    )

    elements = await overpass.search_bbox(
        south, west, north, east, category=category
    )
    summary.fetched = len(elements)

    deduplicated = _deduplicate(elements)
    summary.deduplicated = len(deduplicated)

    for element in deduplicated:
        values = build_restaurant_values(element)
        if values is None:
            summary.skipped += 1
            continue

        osm_type = values["osm_type"]
        osm_id = values["osm_id"]
        try:
            existing = await crud.get_restaurant_by_osm(
                session, osm_type, osm_id
            )
            is_new = existing is None
            if is_new:
                from app.models import Restaurant

                session.add(Restaurant(**values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
            await session.commit()
            if is_new:
                summary.created += 1
            else:
                summary.updated += 1
        except Exception as exc:  # noqa: BLE001 - uma linha ruim não aborta o lote
            await session.rollback()
            summary.errors.append(f"{osm_type}/{osm_id}: {exc}")
            logger.warning(
                "Falha ao ingerir %s/%s: %s", osm_type, osm_id, exc
            )

    return summary
