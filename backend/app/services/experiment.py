"""Atribuição estável, contabilização e análise do experimento A/B.

Princípios:

- a unidade experimental é o **usuário**, não a sessão;
- o grupo é derivado por SHA-256 com a versão do experimento e persistido em
  ``experiment_assignments`` (data e origem incluídas);
- o modo ``demo`` permite escolher a estratégia manualmente, mas seus eventos
  são excluídos das métricas oficiais;
- as métricas vêm de ``user_restaurant_interactions``; contadores Redis são
  apenas diagnóstico operacional;
- ``ready`` significa "há volume mínimo para leitura descritiva", **não**
  significância estatística. Testes só rodam na fase ``statistical_analysis``.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    ExperimentAssignment,
    Restaurant,
    UserRestaurantInteraction,
)

EXPERIMENT_BASELINE = "baseline"
EXPERIMENT_PERSONALIZED = "personalized"
EXPERIMENT_DISTANCE = "distance"
EXPERIMENT_GROUPS: tuple[str, ...] = (
    EXPERIMENT_BASELINE,
    EXPERIMENT_PERSONALIZED,
    EXPERIMENT_DISTANCE,
)

EXPERIMENT_MODE_EXPERIMENT = "experiment"
EXPERIMENT_MODE_DEMO = "demo"
EXPERIMENT_MODES: tuple[str, ...] = (
    EXPERIMENT_MODE_EXPERIMENT,
    EXPERIMENT_MODE_DEMO,
)

# Mantido por compatibilidade com imports existentes.
MIN_IMPRESSIONS_FOR_READING = settings.experiment_min_impressions

_GROUP_LABELS = {
    EXPERIMENT_BASELINE: "Baseline (popularidade)",
    EXPERIMENT_PERSONALIZED: "Personalizado (ML)",
    EXPERIMENT_DISTANCE: "Por distância",
}

_EVENT_KEYS = {
    "IMPRESSION": "impressions",
    "CLICK": "clicks",
    # ``VIEW`` é o evento legado; ``VIEW_DETAILS`` é o sinal atual de abertura
    # da tela. Contamos separadamente para não inflar ``detail_rate``.
    "VIEW": "views",
    "VIEW_DETAILS": "view_details",
    "FAVORITE": "favorites",
    "PURCHASE": "purchases",
    "DISMISS": "dismissals",
}


def assign_experiment_group(
    user_id: UUID, experiment_version: str | None = None
) -> str:
    """Atribui o usuário a um grupo de forma determinística.

    A versão entra no hash: mudar a versão do experimento é uma decisão
    explícita e produz uma nova atribuição, documentada no relatório.
    """
    version = experiment_version or settings.experiment_version
    digest = int.from_bytes(
        hashlib.sha256(f"{version}:{user_id}".encode("utf-8")).digest()[:8],
        "big",
    )
    return EXPERIMENT_GROUPS[digest % len(EXPERIMENT_GROUPS)]


def resolve_experiment_group(
    experiment: str | None,
    user_id: UUID,
    experiment_version: str | None = None,
) -> str:
    """Resolve o grupo para chamadas internas/demonstração.

    O endpoint de recomendações **não** usa esta função no modo oficial: lá a
    atribuição vem de ``get_or_create_assignment``. Este helper permanece para
    compatibilidade e para o modo demo explícito.
    """
    if experiment in EXPERIMENT_GROUPS:
        return str(experiment)
    return assign_experiment_group(user_id, experiment_version)


async def get_or_create_assignment(
    session: AsyncSession,
    user_id: UUID,
    experiment_version: str | None = None,
) -> ExperimentAssignment:
    """Lê ou cria a atribuição persistente do usuário para a versão atual."""
    version = experiment_version or settings.experiment_version
    existing = (
        await session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_version == version,
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing

    group = assign_experiment_group(user_id, version)
    statement = (
        pg_insert(ExperimentAssignment)
        .values(
            user_id=user_id,
            experiment_version=version,
            group_name=group,
            source="hash",
        )
        .on_conflict_do_nothing(
            index_elements=[
                ExperimentAssignment.user_id,
                ExperimentAssignment.experiment_version,
            ]
        )
    )
    await session.execute(statement)
    await session.commit()

    assignment = (
        await session.execute(
            select(ExperimentAssignment).where(
                ExperimentAssignment.user_id == user_id,
                ExperimentAssignment.experiment_version == version,
            )
        )
    ).scalars().first()
    if assignment is None:  # pragma: no cover - proteção contra corrida extrema
        raise RuntimeError("Não foi possível persistir a atribuição experimental.")
    return assignment


def _empty_group() -> dict[str, Any]:
    return {
        "users": 0,
        "impressions": 0,
        "clicks": 0,
        "views": 0,
        "view_details": 0,
        "favorites": 0,
        "purchases": 0,
        "dismissals": 0,
        "distinct_restaurants": 0,
        "ctr": 0.0,
        "conversion_rate": 0.0,
        "detail_rate": 0.0,
        "favorite_rate": 0.0,
        "dismiss_rate": 0.0,
        "detail_per_click": 0.0,
        "impressions_per_user": 0.0,
        "clicks_per_user": 0.0,
        "purchases_per_user": 0.0,
        "model_versions": [],
        "confidence_intervals": {},
        "readable": False,
        "conversion_readable": False,
    }


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _wilson_interval(
    successes: int, total: int, z: float = 1.959963984540054
) -> dict[str, float] | None:
    """Intervalo de confiança de Wilson para uma proporção (95% por padrão)."""
    if total <= 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
        / denominator
    )
    return {
        "low": round(max(0.0, center - margin), 4),
        "high": round(min(1.0, center + margin), 4),
    }


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _two_proportion_p_value(
    successes_a: int,
    total_a: int,
    successes_b: int,
    total_b: int,
) -> float | None:
    """Teste z de duas proporções (bilateral), sem dependência de scipy."""
    if total_a <= 0 or total_b <= 0:
        return None
    pooled = (successes_a + successes_b) / (total_a + total_b)
    if pooled <= 0.0 or pooled >= 1.0:
        return None
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if standard_error == 0:
        return None
    z_score = (successes_a / total_a - successes_b / total_b) / standard_error
    return round(2 * (1 - _normal_cdf(abs(z_score))), 6)


def _build_timeline(
    timeline_rows: Iterable[Sequence[Any]],
) -> list[dict[str, Any]]:
    days: dict[str, dict[str, dict[str, int]]] = {}
    for row in timeline_rows:
        day, group, event_type, count = row[0], row[1], row[2], int(row[3] or 0)
        key = _EVENT_KEYS.get(str(event_type).upper())
        if key is None or group not in EXPERIMENT_GROUPS:
            continue
        day_key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        bucket = days.setdefault(day_key, {})
        group_bucket = bucket.setdefault(
            group, {"impressions": 0, "clicks": 0, "purchases": 0}
        )
        if key in group_bucket:
            group_bucket[key] += count

    timeline: list[dict[str, Any]] = []
    for day in sorted(days):
        groups = days[day]
        timeline.append(
            {
                "date": day,
                "groups": {
                    group: {
                        **values,
                        "ctr": _ratio(values["clicks"], values["impressions"]),
                        "conversion_rate": _ratio(
                            values["purchases"], values["impressions"]
                        ),
                    }
                    for group, values in groups.items()
                },
            }
        )
    return timeline


def summarize_experiment(
    count_rows: Iterable[Sequence[Any]],
    user_rows: Iterable[Sequence[Any]] = (),
    model_rows: Iterable[Sequence[Any]] = (),
    *,
    now: datetime | None = None,
    demo_events: int = 0,
    contaminated_users: int = 0,
    timeline_rows: Iterable[Sequence[Any]] = (),
    diversity_rows: Iterable[Sequence[Any]] = (),
    total_catalog_restaurants: int = 0,
    unique_users: int | None = None,
    assignment_counts: dict[str, int] | None = None,
    min_impressions: int | None = None,
    min_users_per_group: int | None = None,
    min_clicks_per_group: int | None = None,
    min_purchases_per_group: int | None = None,
    statistical_min_impressions: int | None = None,
    statistical_min_users_per_group: int | None = None,
    alpha: float | None = None,
) -> dict[str, Any]:
    """Agrega eventos oficiais em métricas por estratégia.

    ``count_rows`` deve conter apenas eventos com ``experiment_mode='experiment'``.
    Eventos de demonstração entram em ``demo_events`` e nunca no denominador.
    """
    min_impressions = (
        settings.experiment_min_impressions
        if min_impressions is None
        else min_impressions
    )
    min_users_per_group = (
        settings.experiment_min_users_per_group
        if min_users_per_group is None
        else min_users_per_group
    )
    min_clicks_per_group = (
        settings.experiment_min_clicks_per_group
        if min_clicks_per_group is None
        else min_clicks_per_group
    )
    min_purchases_per_group = (
        settings.experiment_min_purchases_per_group
        if min_purchases_per_group is None
        else min_purchases_per_group
    )
    statistical_min_impressions = (
        settings.experiment_statistical_min_impressions
        if statistical_min_impressions is None
        else statistical_min_impressions
    )
    statistical_min_users_per_group = (
        settings.experiment_statistical_min_users_per_group
        if statistical_min_users_per_group is None
        else statistical_min_users_per_group
    )
    alpha = settings.experiment_statistical_alpha if alpha is None else alpha

    groups = {group: _empty_group() for group in EXPERIMENT_GROUPS}
    periods: dict[str, dict[str, datetime | None]] = {
        group: {"first_event_at": None, "last_event_at": None}
        for group in EXPERIMENT_GROUPS
    }
    untagged_events = 0

    for row in count_rows:
        group, event_type, count = row[0], row[1], int(row[2] or 0)
        if group is None or group not in groups:
            untagged_events += count
            continue
        key = _EVENT_KEYS.get(str(event_type).upper())
        if key is None:
            continue
        groups[group][key] += count
        if len(row) > 3:
            first_event, last_event = row[3], row[4]
            period = periods[group]
            if first_event is not None and (
                period["first_event_at"] is None
                or first_event < period["first_event_at"]
            ):
                period["first_event_at"] = first_event
            if last_event is not None and (
                period["last_event_at"] is None
                or last_event > period["last_event_at"]
            ):
                period["last_event_at"] = last_event

    for row in user_rows:
        group, count = row[0], int(row[1] or 0)
        if group in groups:
            groups[group]["users"] = count

    versions: dict[str, set[str]] = {group: set() for group in EXPERIMENT_GROUPS}
    for row in model_rows:
        group, version = row[0], row[1]
        if group in groups and version:
            versions[group].add(str(version))

    diversity: dict[str, int] = {}
    for row in diversity_rows:
        group, count = row[0], int(row[1] or 0)
        if group in groups:
            diversity[group] = count

    for group, values in groups.items():
        impressions = values["impressions"]
        values["ctr"] = _ratio(values["clicks"], impressions)
        values["conversion_rate"] = _ratio(values["purchases"], impressions)
        values["detail_rate"] = _ratio(values["view_details"], impressions)
        values["favorite_rate"] = _ratio(values["favorites"], impressions)
        values["dismiss_rate"] = _ratio(values["dismissals"], impressions)
        values["detail_per_click"] = _ratio(
            values["view_details"], values["clicks"]
        )
        values["impressions_per_user"] = _ratio(impressions, values["users"])
        values["clicks_per_user"] = _ratio(values["clicks"], values["users"])
        values["purchases_per_user"] = _ratio(
            values["purchases"], values["users"]
        )
        values["distinct_restaurants"] = diversity.get(group, 0)
        values["catalog_diversity"] = (
            _ratio(values["distinct_restaurants"], total_catalog_restaurants)
            if total_catalog_restaurants
            else 0.0
        )
        values["model_versions"] = sorted(versions[group])
        values["label"] = _GROUP_LABELS[group]
        values["confidence_intervals"] = {
            "ctr": _wilson_interval(values["clicks"], impressions),
            "detail_rate": _wilson_interval(values["view_details"], impressions),
            "conversion_rate": _wilson_interval(
                values["purchases"], impressions
            ),
        }
        values["readable"] = (
            impressions >= min_impressions
            and values["users"] >= min_users_per_group
            and values["clicks"] >= min_clicks_per_group
        )
        values["conversion_readable"] = (
            values["readable"]
            and values["purchases"] >= min_purchases_per_group
        )

    total_impressions = sum(values["impressions"] for values in groups.values())
    total_purchases = sum(values["purchases"] for values in groups.values())
    total_clicks = sum(values["clicks"] for values in groups.values())
    exposed_users = sum(values["users"] for values in groups.values())
    groups_with_impressions = [
        group for group, values in groups.items() if values["impressions"] > 0
    ]

    statistical_ready = (
        total_impressions >= statistical_min_impressions
        and len(groups_with_impressions) >= 2
        and all(
            groups[group]["impressions"] >= min_impressions
            and groups[group]["users"] >= statistical_min_users_per_group
            for group in groups_with_impressions
        )
    )
    descriptive_ready = (
        total_impressions >= min_impressions
        and len(groups_with_impressions) >= 2
        and all(groups[group]["readable"] for group in groups_with_impressions)
    )

    if total_impressions == 0:
        phase = "collecting"
        message = (
            "Ainda não há impressões oficiais registradas. Abra a Home com o "
            "backend disponível e mantenha o modo experimental (não o modo de "
            "demonstração) para contabilizar as recomendações exibidas."
        )
    elif not descriptive_ready:
        phase = "insufficient_data"
        message = (
            f"Há {total_impressions} impressões oficiais. O mínimo descritivo "
            f"configurado é {min_impressions} impressões, {min_users_per_group} "
            f"usuários e {min_clicks_per_group} cliques por grupo. Os números "
            "abaixo são descritivos e não permitem conclusão."
        )
    elif not statistical_ready:
        phase = "ready"
        message = (
            "Volume mínimo para leitura descritiva atingido. Isso não é "
            "significância estatística; a análise inferencial ainda não foi "
            "liberada."
        )
    else:
        phase = "statistical_analysis"
        message = (
            "Volume mínimo para análise estatística atingido. Os testes são "
            "aplicados com correção para múltiplas comparações; significância "
            "não é declarada apenas por diferença percentual."
        )

    comparison: dict[str, Any] = {
        "best_ctr": None,
        "best_conversion": None,
        "winner_declared": False,
        "note": (
            "Comparação descritiva. Nenhuma estratégia é declarada vencedora "
            "sem teste estatístico válido."
        ),
    }
    if descriptive_ready and groups_with_impressions:
        comparison["best_ctr"] = max(
            groups_with_impressions, key=lambda group: groups[group]["ctr"]
        )
        comparison["best_conversion"] = max(
            groups_with_impressions,
            key=lambda group: groups[group]["conversion_rate"],
        )

    statistical_analysis: dict[str, Any] = {
        "available": False,
        "reason": (
            "Amostra insuficiente para inferência. "
            f"Requer ao menos {statistical_min_impressions} impressões totais "
            f"e {statistical_min_users_per_group} usuários por grupo."
        ),
    }
    if statistical_ready:
        comparisons: list[dict[str, Any]] = []
        # Comparações planejadas: 2 métricas x (grupos - baseline). A correção
        # de Bonferroni usa o número total de comparações, não apenas duas.
        comparisons_planned = 2 * max(len(groups_with_impressions) - 1, 1)
        corrected_alpha = alpha / comparisons_planned
        for metric, successes_key, total_key in (
            ("ctr", "clicks", "impressions"),
            ("conversion_rate", "purchases", "impressions"),
        ):
            baseline = groups[EXPERIMENT_BASELINE]
            for group in (EXPERIMENT_PERSONALIZED, EXPERIMENT_DISTANCE):
                candidate = groups[group]
                if candidate[total_key] <= 0 or baseline[total_key] <= 0:
                    continue
                p_value = _two_proportion_p_value(
                    candidate[successes_key],
                    candidate[total_key],
                    baseline[successes_key],
                    baseline[total_key],
                )
                absolute = round(candidate[metric] - baseline[metric], 4)
                relative = (
                    round(absolute / baseline[metric], 4)
                    if baseline[metric]
                    else None
                )
                significant = (
                    p_value is not None and p_value < corrected_alpha
                )
                comparisons.append(
                    {
                        "metric": metric,
                        "group": group,
                        "baseline": EXPERIMENT_BASELINE,
                        "absolute_difference": absolute,
                        "relative_lift": relative,
                        "p_value": p_value,
                        "significant": significant,
                    }
                )
        statistical_analysis = {
            "available": True,
            "method": (
                "Intervalo de Wilson (95%) para taxas e teste z bilateral de "
                "duas proporções contra o baseline, com correção de Bonferroni "
                f"(alpha={alpha}, alpha_corrigido={corrected_alpha})."
            ),
            "alpha": alpha,
            "corrected_alpha": corrected_alpha,
            "comparisons": comparisons,
        }
        comparison["winner_declared"] = any(
            item["significant"] and item["absolute_difference"] > 0
            for item in comparisons
        )

    return {
        "source": "database",
        "phase": phase,
        "message": message,
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "has_data": total_impressions > 0,
        "experiment_version": settings.experiment_version,
        "unit": "user",
        "minimum_impressions_for_reading": min_impressions,
        "thresholds": {
            "min_impressions": min_impressions,
            "min_users_per_group": min_users_per_group,
            "min_clicks_per_group": min_clicks_per_group,
            "min_purchases_per_group": min_purchases_per_group,
            "statistical_min_impressions": statistical_min_impressions,
            "statistical_min_users_per_group": statistical_min_users_per_group,
        },
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_purchases": total_purchases,
        # ``exposed_users`` soma usuários por grupo (pode contar a mesma pessoa
        # duas vezes se houver contaminação); ``unique_users`` é a contagem
        # distinta real quando o chamador a fornece.
        "exposed_users": exposed_users,
        "unique_users": unique_users
        if unique_users is not None
        else max((values["users"] for values in groups.values()), default=0),
        "assignment_counts": assignment_counts or {},
        "untagged_events": untagged_events,
        "demo_events": demo_events,
        "contaminated_users": contaminated_users,
        "contamination_detected": contaminated_users > 0,
        "groups": groups,
        "comparison": comparison,
        "statistical_analysis": statistical_analysis,
        "periods": periods,
        "timeline": _build_timeline(timeline_rows),
        "coverage_definition": (
            "catalog_diversity = restaurantes distintos com impressão no grupo "
            "/ total de restaurantes do catálogo. Não confundir com cobertura "
            "de ranking do treino."
        ),
    }


async def get_experiment_metrics(session: AsyncSession) -> dict[str, Any]:
    """Consulta o banco e devolve as métricas oficiais do experimento A/B."""
    interaction = UserRestaurantInteraction

    count_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                interaction.interaction_type,
                func.count(interaction.id),
                func.min(interaction.created_at),
                func.max(interaction.created_at),
            )
            .where(interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT)
            .group_by(interaction.experiment_group, interaction.interaction_type)
        )
    ).all()

    user_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                func.count(func.distinct(interaction.user_id)),
            )
            .where(
                interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                interaction.experiment_group.is_not(None),
                interaction.interaction_type == "IMPRESSION",
            )
            .group_by(interaction.experiment_group)
        )
    ).all()

    model_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                interaction.model_version,
                func.count(interaction.id),
            )
            .where(
                interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                interaction.experiment_group.is_not(None),
                interaction.model_version.is_not(None),
            )
            .group_by(interaction.experiment_group, interaction.model_version)
        )
    ).all()

    demo_events = int(
        (
            await session.execute(
                select(func.count(interaction.id)).where(
                    interaction.experiment_mode == EXPERIMENT_MODE_DEMO
                )
            )
        ).scalar_one()
        or 0
    )

    unique_users = int(
        (
            await session.execute(
                select(func.count(func.distinct(interaction.user_id))).where(
                    interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                    interaction.experiment_group.is_not(None),
                )
            )
        ).scalar_one()
        or 0
    )

    assignment_rows = (
        await session.execute(
            select(ExperimentAssignment.group_name, func.count())
            .where(
                ExperimentAssignment.experiment_version
                == settings.experiment_version
            )
            .group_by(ExperimentAssignment.group_name)
        )
    ).all()
    assignment_counts = {
        str(group): int(count) for group, count in assignment_rows if group
    }

    # Contaminação em duas frentes: (1) o mesmo usuário aparece em mais de um
    # grupo nos eventos oficiais; (2) o evento foi gravado com grupo diferente
    # da atribuição persistente para a versão atual.
    event_contamination = set(
        (
            await session.execute(
                select(interaction.user_id)
                .where(
                    interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                    interaction.experiment_group.is_not(None),
                )
                .group_by(interaction.user_id)
                .having(
                    func.count(func.distinct(interaction.experiment_group)) > 1
                )
            )
        )
        .scalars()
        .all()
    )
    assignment_mismatch = set(
        (
            await session.execute(
                select(interaction.user_id)
                .join(
                    ExperimentAssignment,
                    and_(
                        ExperimentAssignment.user_id == interaction.user_id,
                        ExperimentAssignment.experiment_version
                        == interaction.experiment_version,
                    ),
                )
                .where(
                    interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                    interaction.experiment_group.is_not(None),
                    interaction.experiment_group
                    != ExperimentAssignment.group_name,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    contaminated_users = len(event_contamination | assignment_mismatch)

    timeline_rows = (
        await session.execute(
            select(
                func.date(interaction.created_at),
                interaction.experiment_group,
                interaction.interaction_type,
                func.count(interaction.id),
            )
            .where(
                interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                interaction.experiment_group.is_not(None),
            )
            .group_by(
                func.date(interaction.created_at),
                interaction.experiment_group,
                interaction.interaction_type,
            )
            .order_by(func.date(interaction.created_at))
        )
    ).all()

    diversity_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                func.count(func.distinct(interaction.restaurant_id)),
            )
            .where(
                interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
                interaction.experiment_group.is_not(None),
                interaction.interaction_type == "IMPRESSION",
            )
            .group_by(interaction.experiment_group)
        )
    ).all()

    total_catalog_restaurants = int(
        (await session.execute(select(func.count(Restaurant.id)))).scalar_one()
        or 0
    )
    return summarize_experiment(
        count_rows,
        user_rows,
        model_rows,
        demo_events=demo_events,
        contaminated_users=contaminated_users,
        timeline_rows=timeline_rows,
        diversity_rows=diversity_rows,
        total_catalog_restaurants=total_catalog_restaurants,
        unique_users=unique_users,
        assignment_counts=assignment_counts,
    )
