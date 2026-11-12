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
import random
from datetime import datetime, timezone
from statistics import NormalDist
from typing import Any, Iterable, Sequence
from uuid import UUID

from sqlalchemy import and_, case, func, select
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

# Reamostragens do bootstrap agrupado por usuário.
BOOTSTRAP_RESAMPLES = 1000
# Efeito relativo mínimo usado no dimensionamento ilustrativo da amostra.
DEFAULT_MINIMUM_DETECTABLE_EFFECT = 0.20
DEFAULT_POWER = 0.80

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


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[int(position)]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _bootstrap_interval(
    values: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: str = "interval",
) -> dict[str, float] | None:
    """IC 95% da média por reamostragem (unidade já agregada por usuário)."""
    if len(values) < 2 or resamples <= 0:
        return None
    rng = random.Random(seed)
    means = [
        sum(rng.choice(values) for _ in values) / len(values)
        for _ in range(resamples)
    ]
    return {
        "low": round(_percentile(means, 0.025), 4),
        "high": round(_percentile(means, 0.975), 4),
        "resamples": resamples,
        "unit": "user",
    }


def _bootstrap_difference(
    candidate: Sequence[float],
    baseline: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: str = "difference",
) -> dict[str, Any]:
    """Bootstrap agrupado por usuário para a diferença de médias.

    Cada grupo é reamostrado com reposição **por usuário**, preservando a
    dependência entre impressões do mesmo usuário. O IC 95% vem da
    distribuição bootstrap da diferença observada.

    O p-valor usa uma distribuição nula construída explicitamente: as duas
    amostras são centralizadas na média conjunta e reamostradas sob a hipótese
    de que ambos os grupos vêm da mesma distribuição. Isso é diferente de usar
    a proporção de diferenças positivas/negativas da distribuição observada,
    que não é um teste formal sob H0.
    """
    if len(candidate) < 2 or len(baseline) < 2 or resamples <= 0:
        return {
            "p_value": None,
            "confidence_interval": None,
            "observed_difference": None,
            "method": None,
        }
    rng = random.Random(seed)
    differences: list[float] = []
    for _ in range(resamples):
        candidate_mean = sum(rng.choice(candidate) for _ in candidate) / len(
            candidate
        )
        baseline_mean = sum(rng.choice(baseline) for _ in baseline) / len(baseline)
        differences.append(candidate_mean - baseline_mean)

    observed = sum(candidate) / len(candidate) - sum(baseline) / len(baseline)

    pooled = list(candidate) + list(baseline)
    pooled_mean = sum(pooled) / len(pooled)
    centered = [value - pooled_mean for value in pooled]
    extreme = 0
    for _ in range(resamples):
        null_candidate = sum(rng.choice(centered) for _ in candidate) / len(
            candidate
        )
        null_baseline = sum(rng.choice(centered) for _ in baseline) / len(
            baseline
        )
        if abs(null_candidate - null_baseline) >= abs(observed):
            extreme += 1
    # Correção de continuidade: nunca reportar p=0 com um número finito de
    # reamostragens.
    p_value = round((extreme + 1) / (resamples + 1), 6)

    return {
        "p_value": p_value,
        "confidence_interval": {
            "low": round(_percentile(differences, 0.025), 4),
            "high": round(_percentile(differences, 0.975), 4),
        },
        "observed_difference": round(observed, 4),
        "method": "bootstrap_null_distribution_by_user",
    }


def required_sample_size(
    baseline_rate: float,
    expected_rate: float,
    *,
    alpha: float = 0.05,
    power: float = DEFAULT_POWER,
) -> int | None:
    """Aproximação de tamanho de amostra por grupo (duas proporções).

    ``n ≈ 2 (z_{1-alpha/2} + z_{power})² p̄ (1-p̄) / (p1-p0)²``.
    É uma aproximação para proporções independentes; com unidade usuário e
    múltiplas comparações, o número deve ser tratado como piso, não garantia.
    """
    if not (0.0 < baseline_rate < 1.0) or not (0.0 < expected_rate < 1.0):
        return None
    difference = abs(expected_rate - baseline_rate)
    if difference <= 0.0:
        return None
    average = (baseline_rate + expected_rate) / 2
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    size = (
        2
        * (z_alpha + z_power) ** 2
        * average
        * (1 - average)
        / (difference**2)
    )
    return max(1, math.ceil(size))


def _user_metric_values(
    user_metric_rows: Iterable[Sequence[Any]],
) -> dict[str, dict[str, list[float]]]:
    """Agrega métricas por usuário para inferência agrupada.

    ``user_metric_rows`` = ``(grupo, user_id, impressões, cliques, compras)``.
    Usuários sem impressão são ignorados nas taxas (não têm denominador).
    """
    result: dict[str, dict[str, list[float]]] = {
        group: {
            "ctr": [],
            "conversion_rate": [],
            "conversion_per_user": [],
            "users": [],
        }
        for group in EXPERIMENT_GROUPS
    }
    for row in user_metric_rows:
        group = row[0]
        if group not in result:
            continue
        impressions = int(row[2] or 0)
        clicks = int(row[3] or 0)
        purchases = int(row[4] or 0)
        if impressions <= 0:
            continue
        result[group]["users"].append(1.0)
        result[group]["ctr"].append(clicks / impressions)
        result[group]["conversion_rate"].append(purchases / impressions)
        result[group]["conversion_per_user"].append(1.0 if purchases > 0 else 0.0)
    return result


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


def _aggregate_valid_groups(
    count_rows: Iterable[Sequence[Any]],
    user_rows: Iterable[Sequence[Any]],
    user_metric_rows: Iterable[Sequence[Any]],
    *,
    diversity_rows: Iterable[Sequence[Any]] = (),
    total_catalog_restaurants: int,
    min_impressions: int,
    min_users_per_group: int,
    min_clicks_per_group: int,
    bootstrap_resamples: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, list[float]]]]:
    """Métricas da coorte válida (usuários sem contaminação).

    As taxas por impressão continuam descritivas. A inferência usa as médias
    por usuário e o bootstrap agrupado.
    """
    groups = {group: _empty_group() for group in EXPERIMENT_GROUPS}
    for row in count_rows:
        group, event_type, count = row[0], row[1], int(row[2] or 0)
        if group not in groups:
            continue
        key = _EVENT_KEYS.get(str(event_type).upper())
        if key is not None:
            groups[group][key] += count
    for row in user_rows:
        group, count = row[0], int(row[1] or 0)
        if group in groups:
            groups[group]["users"] = count

    user_values = _user_metric_values(user_metric_rows)
    distinct_restaurants: dict[str, int] = {}
    for row in diversity_rows:
        group, count = row[0], int(row[1] or 0)
        if group in groups:
            distinct_restaurants[group] = count
    for group, values in groups.items():
        impressions = values["impressions"]
        values["distinct_restaurants"] = distinct_restaurants.get(group, 0)
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

        metrics = user_values[group]
        values["users_with_impressions"] = len(metrics["ctr"])
        values["user_ctr"] = (
            round(sum(metrics["ctr"]) / len(metrics["ctr"]), 4)
            if metrics["ctr"]
            else 0.0
        )
        values["user_conversion_rate"] = (
            round(
                sum(metrics["conversion_rate"])
                / len(metrics["conversion_rate"]),
                4,
            )
            if metrics["conversion_rate"]
            else 0.0
        )
        values["conversion_per_user"] = (
            round(
                sum(metrics["conversion_per_user"])
                / len(metrics["conversion_per_user"]),
                4,
            )
            if metrics["conversion_per_user"]
            else 0.0
        )
        values["user_confidence_intervals"] = {
            "ctr": _bootstrap_interval(
                metrics["ctr"],
                resamples=bootstrap_resamples,
                seed=f"ctr:{group}",
            ),
            "conversion_rate": _bootstrap_interval(
                metrics["conversion_rate"],
                resamples=bootstrap_resamples,
                seed=f"conversion:{group}",
            ),
            "conversion_per_user": _bootstrap_interval(
                metrics["conversion_per_user"],
                resamples=bootstrap_resamples,
                seed=f"conversion_user:{group}",
            ),
        }
        values["catalog_diversity"] = (
            _ratio(values["distinct_restaurants"], total_catalog_restaurants)
            if total_catalog_restaurants
            else 0.0
        )
        values["label"] = _GROUP_LABELS[group]
    return groups, user_values


def _sample_size_plan(
    groups: dict[str, dict[str, Any]],
    user_values: dict[str, dict[str, list[float]]],
    *,
    alpha: float,
    planned_comparisons: int,
    power: float = DEFAULT_POWER,
    minimum_detectable_effect: float = DEFAULT_MINIMUM_DETECTABLE_EFFECT,
) -> dict[str, Any]:
    """Dimensionamento ilustrativo por grupo, com correção de comparações.

    Usa a taxa do baseline da coorte válida e um efeito relativo mínimo. É um
    piso aproximado (duas proporções independentes), não uma garantia de poder:
    a unidade real é o usuário e a variância agrupada pode ser maior.
    """
    del user_values  # mantido na assinatura para evolução futura
    corrected_alpha = alpha / max(planned_comparisons, 1)
    baseline = groups[EXPERIMENT_BASELINE]
    impressions_per_user = float(baseline.get("impressions_per_user") or 0.0)
    plans: list[dict[str, Any]] = []
    for metric in ("conversion_rate", "ctr"):
        baseline_rate = float(baseline.get(metric) or 0.0)
        entry: dict[str, Any] = {
            "metric": metric,
            "baseline_rate": round(baseline_rate, 4),
            "expected_rate": None,
            "required_users_per_group": None,
            "required_impressions_per_group": None,
            "reason": None,
        }
        if not (0.0 < baseline_rate < 1.0):
            entry["reason"] = (
                "Taxa do baseline ausente ou em 0/1 na coorte válida; não é "
                "possível dimensionar sem uma taxa de referência observada."
            )
            plans.append(entry)
            continue
        expected_rate = min(
            baseline_rate * (1 + minimum_detectable_effect), 0.999
        )
        entry["expected_rate"] = round(expected_rate, 4)
        required_users = required_sample_size(
            baseline_rate, expected_rate, alpha=corrected_alpha, power=power
        )
        entry["required_users_per_group"] = required_users
        if required_users is not None and impressions_per_user > 0:
            entry["required_impressions_per_group"] = math.ceil(
                required_users * impressions_per_user
            )
        plans.append(entry)
    return {
        "primary_metric": "conversion_rate",
        "unit": "user",
        "alpha": alpha,
        "corrected_alpha": round(corrected_alpha, 6),
        "power": power,
        "planned_comparisons": planned_comparisons,
        "minimum_detectable_effect_relative": minimum_detectable_effect,
        "baseline_impressions_per_user": round(impressions_per_user, 4),
        "plans": plans,
        "note": (
            "Aproximação para duas proporções independentes, com alpha "
            "corrigido por Bonferroni. Trate o resultado como piso: a unidade "
            "real é o usuário e a variância agrupada pode ser maior."
        ),
    }


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
    valid_count_rows: Iterable[Sequence[Any]] | None = None,
    valid_user_rows: Iterable[Sequence[Any]] | None = None,
    valid_diversity_rows: Iterable[Sequence[Any]] | None = None,
    user_metric_rows: Iterable[Sequence[Any]] = (),
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, Any]:
    """Agrega eventos oficiais em métricas por estratégia.

    ``count_rows`` deve conter apenas eventos com ``experiment_mode='experiment'``.
    Eventos de demonstração entram em ``demo_events`` e nunca no denominador.

    Há duas visões deliberadamente separadas:

    - ``groups``: todos os eventos oficiais, para auditoria;
    - ``valid_groups``: apenas usuários sem contaminação, usada para leitura e
      inferência.

    Quando ``valid_count_rows``/``valid_user_rows`` não são fornecidos, a
    coorte válida coincide com a bruta (compatibilidade com chamadas antigas).
    """
    # Materializa uma vez: os mesmos iteráveis alimentam as visões bruta e
    # válida, e um gerador só pode ser consumido uma vez.
    count_rows = list(count_rows)
    user_rows = list(user_rows)
    model_rows = list(model_rows)
    timeline_rows = list(timeline_rows)
    diversity_rows = list(diversity_rows)
    user_metric_rows = list(user_metric_rows)
    valid_count_rows = (
        count_rows if valid_count_rows is None else list(valid_count_rows)
    )
    valid_user_rows = (
        user_rows if valid_user_rows is None else list(valid_user_rows)
    )
    valid_diversity_rows = (
        diversity_rows
        if valid_diversity_rows is None
        else list(valid_diversity_rows)
    )
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

    valid_groups, user_values = _aggregate_valid_groups(
        valid_count_rows,
        valid_user_rows,
        user_metric_rows,
        diversity_rows=valid_diversity_rows,
        total_catalog_restaurants=total_catalog_restaurants,
        min_impressions=min_impressions,
        min_users_per_group=min_users_per_group,
        min_clicks_per_group=min_clicks_per_group,
        bootstrap_resamples=bootstrap_resamples,
    )

    total_impressions = sum(values["impressions"] for values in groups.values())
    total_purchases = sum(values["purchases"] for values in groups.values())
    total_clicks = sum(values["clicks"] for values in groups.values())
    exposed_users = sum(values["users"] for values in groups.values())

    valid_total_impressions = sum(
        values["impressions"] for values in valid_groups.values()
    )
    valid_total_clicks = sum(
        values["clicks"] for values in valid_groups.values()
    )
    valid_total_purchases = sum(
        values["purchases"] for values in valid_groups.values()
    )
    valid_exposed_users = sum(
        values["users"] for values in valid_groups.values()
    )
    valid_groups_with_impressions = [
        group
        for group, values in valid_groups.items()
        if values["impressions"] > 0
    ]
    # A inferência é sempre contra o baseline. Sem baseline com volume, não há
    # comparação válida — mesmo que dois grupos variantes tenham dados.
    comparison_groups = [
        group
        for group in (EXPERIMENT_PERSONALIZED, EXPERIMENT_DISTANCE)
        if valid_groups[group]["impressions"] > 0
    ]
    baseline_valid = valid_groups[EXPERIMENT_BASELINE]
    baseline_ready = (
        baseline_valid["impressions"] >= min_impressions
        and baseline_valid["users"] >= statistical_min_users_per_group
    )
    ready_comparison_groups = [
        group
        for group in comparison_groups
        if valid_groups[group]["impressions"] >= min_impressions
        and valid_groups[group]["users"] >= statistical_min_users_per_group
    ]

    resolved_unique_users = (
        unique_users if unique_users is not None else exposed_users
    )
    contamination_rate = (
        round(contaminated_users / resolved_unique_users, 4)
        if resolved_unique_users
        else 0.0
    )

    statistical_ready = (
        valid_total_impressions >= statistical_min_impressions
        and baseline_ready
        and bool(ready_comparison_groups)
    )
    descriptive_ready = (
        valid_total_impressions >= min_impressions
        and len(valid_groups_with_impressions) >= 2
        and all(
            valid_groups[group]["readable"]
            for group in valid_groups_with_impressions
        )
    )

    contamination_note = (
        f" {contaminated_users} usuário(s) contaminado(s) foram excluídos da "
        f"coorte válida ({contamination_rate:.1%} dos usuários)."
        if contaminated_users
        else ""
    )

    if valid_total_impressions == 0:
        phase = "collecting"
        message = (
            "Ainda não há impressões oficiais na coorte válida. Abra a Home com "
            "o backend disponível e mantenha o modo experimental (não o modo de "
            "demonstração) para contabilizar as recomendações exibidas."
            + contamination_note
        )
    elif not descriptive_ready:
        phase = "insufficient_data"
        message = (
            f"A coorte válida tem {valid_total_impressions} impressões "
            f"oficiais. O mínimo descritivo configurado é {min_impressions} "
            f"impressões, {min_users_per_group} usuários e "
            f"{min_clicks_per_group} cliques por grupo. Os números abaixo são "
            "descritivos e não permitem conclusão."
            + contamination_note
        )
    elif not statistical_ready:
        phase = "ready"
        if not baseline_ready:
            message = (
                "Volume mínimo descritivo atingido, mas o grupo baseline não "
                "tem impressões/usuários suficientes na coorte válida. Sem "
                "baseline não há comparação inferencial válida; a análise "
                "estatística permanece bloqueada."
                + contamination_note
            )
        else:
            message = (
                "Volume mínimo para leitura descritiva atingido na coorte "
                "válida. Isso não é significância estatística; a análise "
                "inferencial ainda não foi liberada."
                + contamination_note
            )
    else:
        phase = "statistical_analysis"
        message = (
            "Volume mínimo para análise estatística atingido na coorte válida. "
            "Os testes usam bootstrap agrupado por usuário e correção para "
            "múltiplas comparações; significância não é declarada apenas por "
            "diferença percentual."
            + contamination_note
        )

    comparison: dict[str, Any] = {
        "best_ctr": None,
        "best_conversion": None,
        "winner_declared": False,
        "note": (
            "Comparação descritiva sobre a coorte válida. Nenhuma estratégia é "
            "declarada vencedora sem teste estatístico válido."
        ),
    }
    if descriptive_ready and valid_groups_with_impressions:
        comparison["best_ctr"] = max(
            valid_groups_with_impressions,
            key=lambda group: valid_groups[group]["ctr"],
        )
        comparison["best_conversion"] = max(
            valid_groups_with_impressions,
            key=lambda group: valid_groups[group]["conversion_rate"],
        )

    planned_comparisons = 2 * max(len(ready_comparison_groups), 1)
    corrected_alpha = alpha / planned_comparisons
    statistical_analysis: dict[str, Any] = {
        "available": False,
        "reason": (
            (
                "O grupo baseline não tem impressões/usuários suficientes na "
                "coorte válida; não há comparação inferencial válida. "
            )
            if not baseline_ready
            else (
                "Amostra insuficiente para inferência na coorte válida. "
                f"Requer ao menos {statistical_min_impressions} impressões "
                f"totais e {statistical_min_users_per_group} usuários por "
                "grupo comparado (incluindo o baseline). "
            )
        ),
        "planned_comparisons": planned_comparisons,
        "alpha": alpha,
        "corrected_alpha": round(corrected_alpha, 6),
        "unit": "user",
        "baseline_ready": baseline_ready,
        "comparison_groups": comparison_groups,
        "ready_comparison_groups": ready_comparison_groups,
    }
    if statistical_ready:
        comparisons: list[dict[str, Any]] = []
        for metric, successes_key in (
            ("ctr", "clicks"),
            ("conversion_rate", "purchases"),
        ):
            baseline = valid_groups[EXPERIMENT_BASELINE]
            baseline_values = user_values[EXPERIMENT_BASELINE][metric]
            for group in ready_comparison_groups:
                candidate = valid_groups[group]
                if (
                    candidate["impressions"] <= 0
                    or baseline["impressions"] <= 0
                ):
                    continue
                candidate_values = user_values[group][metric]
                bootstrap = _bootstrap_difference(
                    candidate_values,
                    baseline_values,
                    resamples=bootstrap_resamples,
                    seed=f"{metric}:{group}",
                )
                p_value = bootstrap["p_value"]
                method = bootstrap.get("method") or "bootstrap_by_user"
                confidence_interval = bootstrap["confidence_interval"]
                if p_value is None:
                    # Menos de dois usuários válidos por grupo: o bootstrap não
                    # é identificável. O teste por impressão é apenas fallback
                    # e herda a limitação de tratar impressões como
                    # independentes.
                    p_value = _two_proportion_p_value(
                        candidate[successes_key],
                        candidate["impressions"],
                        baseline[successes_key],
                        baseline["impressions"],
                    )
                    method = "z_test_by_impression_fallback"
                    confidence_interval = None
                ci_excludes_zero = bool(
                    confidence_interval
                    and (
                        confidence_interval["low"] > 0
                        or confidence_interval["high"] < 0
                    )
                )
                # A evidência principal é o IC da diferença. O p-valor só
                # declara significância quando o IC também exclui zero; no
                # fallback z (sem IC bootstrap), usa-se apenas o p-valor.
                significant = (
                    p_value is not None
                    and p_value < corrected_alpha
                    and (
                        ci_excludes_zero
                        if confidence_interval is not None
                        else True
                    )
                )
                absolute = round(candidate[metric] - baseline[metric], 4)
                relative = (
                    round(absolute / baseline[metric], 4)
                    if baseline[metric]
                    else None
                )
                candidate_mean = (
                    round(sum(candidate_values) / len(candidate_values), 4)
                    if candidate_values
                    else None
                )
                baseline_mean = (
                    round(sum(baseline_values) / len(baseline_values), 4)
                    if baseline_values
                    else None
                )
                comparisons.append(
                    {
                        "metric": metric,
                        "group": group,
                        "baseline": EXPERIMENT_BASELINE,
                        "absolute_difference": absolute,
                        "relative_lift": relative,
                        "user_level": {
                            "candidate_mean": candidate_mean,
                            "baseline_mean": baseline_mean,
                            "absolute_difference": (
                                round(candidate_mean - baseline_mean, 4)
                                if candidate_mean is not None
                                and baseline_mean is not None
                                else None
                            ),
                        },
                        "p_value": p_value,
                        "confidence_interval": confidence_interval,
                        "confidence_interval_excludes_zero": ci_excludes_zero,
                        "method": method,
                        "significant": significant,
                    }
                )
        statistical_analysis = {
            "available": True,
            "method": (
                "Bootstrap agrupado por usuário: IC 95% da diferença de médias "
                "por usuário e p-valor de uma distribuição nula construída "
                "explicitamente (amostras centralizadas na média conjunta), "
                "com correção de Bonferroni. A evidência principal é o IC da "
                "diferença; quando ele exclui zero e p < alpha corrigido, a "
                "diferença é marcada como significante. Com menos de dois "
                "usuários válidos por grupo, usa-se teste z por impressão como "
                "fallback explícito, sem IC bootstrap."
            ),
            "alpha": alpha,
            "corrected_alpha": round(corrected_alpha, 6),
            "planned_comparisons": planned_comparisons,
            "unit": "user",
            "bootstrap_resamples": bootstrap_resamples,
            "baseline_ready": baseline_ready,
            "comparison_groups": comparison_groups,
            "ready_comparison_groups": ready_comparison_groups,
            "comparisons": comparisons,
            "notes": [
                "CTR e conversão por impressão continuam descritivos; a "
                "inferência principal usa a média por usuário.",
                "O p-valor bootstrap vem de uma distribuição nula construída "
                "sob H0; não é a proporção de diferenças positivas da "
                "distribuição observada.",
                "O IC 95% da diferença é o critério principal de evidência; "
                "significância exige IC excluindo zero e p < alpha corrigido.",
            ],
        }
        comparison["winner_declared"] = any(
            item["significant"] and item["absolute_difference"] > 0
            for item in comparisons
        )

    plan = _sample_size_plan(
        valid_groups,
        user_values,
        alpha=alpha,
        planned_comparisons=planned_comparisons,
    )

    return {
        "source": "database",
        "phase": phase,
        "message": message,
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "has_data": total_impressions > 0,
        "has_valid_data": valid_total_impressions > 0,
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
        # Totais brutos (todos os eventos oficiais), para auditoria.
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_purchases": total_purchases,
        # Totais da coorte válida, usados na leitura e na inferência.
        "valid_total_impressions": valid_total_impressions,
        "valid_total_clicks": valid_total_clicks,
        "valid_total_purchases": valid_total_purchases,
        # ``exposed_users`` soma usuários por grupo (pode contar a mesma pessoa
        # duas vezes se houver contaminação); ``unique_users`` é a contagem
        # distinta real quando o chamador a fornece.
        "exposed_users": exposed_users,
        "valid_exposed_users": valid_exposed_users,
        "baseline_ready": baseline_ready,
        "comparison_groups": comparison_groups,
        "unique_users": (
            unique_users
            if unique_users is not None
            else max(
                (values["users"] for values in groups.values()), default=0
            )
        ),
        "assignment_counts": assignment_counts or {},
        "untagged_events": untagged_events,
        "demo_events": demo_events,
        "contaminated_users": contaminated_users,
        "contamination_rate": contamination_rate,
        "contamination_detected": contaminated_users > 0,
        "valid_cohort": {
            "excluded_users": contaminated_users,
            "contamination_rate": contamination_rate,
            "users": valid_exposed_users,
            "raw_users": exposed_users,
            "impressions": valid_total_impressions,
            "raw_impressions": total_impressions,
            "note": (
                "Métricas brutas incluem todos os eventos oficiais; a coorte "
                "válida exclui usuários contaminados e é a base da inferência."
            ),
        },
        "groups": groups,
        "valid_groups": valid_groups,
        "comparison": comparison,
        "statistical_analysis": statistical_analysis,
        "plan": plan,
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
    contaminated = event_contamination | assignment_mismatch
    contaminated_users = len(contaminated)

    # Coorte válida: mesmos eventos oficiais, sem usuários contaminados. A
    # visão bruta continua no relatório para auditoria.
    valid_conditions = [
        interaction.experiment_mode == EXPERIMENT_MODE_EXPERIMENT,
        interaction.experiment_group.is_not(None),
    ]
    if contaminated:
        valid_conditions.append(interaction.user_id.notin_(contaminated))

    valid_count_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                interaction.interaction_type,
                func.count(interaction.id),
                func.min(interaction.created_at),
                func.max(interaction.created_at),
            )
            .where(*valid_conditions)
            .group_by(interaction.experiment_group, interaction.interaction_type)
        )
    ).all()

    valid_user_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                func.count(func.distinct(interaction.user_id)),
            )
            .where(
                *valid_conditions,
                interaction.interaction_type == "IMPRESSION",
            )
            .group_by(interaction.experiment_group)
        )
    ).all()

    valid_diversity_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                func.count(func.distinct(interaction.restaurant_id)),
            )
            .where(
                *valid_conditions,
                interaction.interaction_type == "IMPRESSION",
            )
            .group_by(interaction.experiment_group)
        )
    ).all()

    # Métricas por usuário para bootstrap agrupado. A unidade é o usuário:
    # reamostrar impressões individuais subestimaria a variância.
    user_metric_rows = (
        await session.execute(
            select(
                interaction.experiment_group,
                interaction.user_id,
                func.sum(
                    case(
                        (interaction.interaction_type == "IMPRESSION", 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case((interaction.interaction_type == "CLICK", 1), else_=0)
                ),
                func.sum(
                    case(
                        (interaction.interaction_type == "PURCHASE", 1),
                        else_=0,
                    )
                ),
            )
            .where(*valid_conditions)
            .group_by(interaction.experiment_group, interaction.user_id)
        )
    ).all()

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
        valid_count_rows=valid_count_rows,
        valid_user_rows=valid_user_rows,
        valid_diversity_rows=valid_diversity_rows,
        user_metric_rows=user_metric_rows,
        total_catalog_restaurants=total_catalog_restaurants,
        unique_users=unique_users,
        assignment_counts=assignment_counts,
    )
