from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import (
    get_scores,
    increment_ab_test_metrics,
    increment_metrics,
    set_scores,
)
from app.core.config import settings
from app.core.constants import Turno
from app.database import get_db
from app.ml.features import (
    affinity_scores,
    blend_with_affinity,
    build_user_features,
    has_turno_history,
)
from app.ml.reranker import reranker
from app.ml.recommender import popularity_scores, recommender
from app.schemas import RecommendationOut, RestaurantSearchParams
from app.services.experiment import (
    EXPERIMENT_BASELINE,
    EXPERIMENT_DISTANCE,
    EXPERIMENT_GROUPS,
    EXPERIMENT_MODE_DEMO,
    EXPERIMENT_MODE_EXPERIMENT,
    EXPERIMENT_PERSONALIZED,
    get_or_create_assignment,
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


async def _resolve_group(
    session: AsyncSession,
    user_id: UUID,
    mode: str,
    experiment: str | None,
) -> str:
    """Resolve o grupo conforme o modo.

    - ``experiment``: ignora seleção manual e usa a atribuição persistente.
    - ``demo``: usa a estratégia escolhida (ou baseline) para demonstração.
    """
    if mode == EXPERIMENT_MODE_DEMO:
        return experiment if experiment in EXPERIMENT_GROUPS else EXPERIMENT_BASELINE

    assignment = await get_or_create_assignment(session, user_id)
    return assignment.group_name


def _model_version() -> str:
    version = recommender.metadata.get("model_version")
    return str(version) if version else "unavailable"


@router.get("", response_model=list[RecommendationOut])
async def recommendations(
    response: Response,
    user_id: UUID = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: Turno = Query("tarde"),
    experiment: str | None = Query(
        None,
        description="Estratégia para o modo demo: 'baseline', 'personalized' "
        "ou 'distance'. No modo experimental este parâmetro é ignorado.",
    ),
    mode: str = Query(
        EXPERIMENT_MODE_EXPERIMENT,
        pattern="^(experiment|demo)$",
        description="'experiment' usa atribuição persistente; 'demo' permite "
        "escolher a estratégia e não conta nas métricas oficiais.",
    ),
    session: AsyncSession = Depends(get_db),
):
    group = await _resolve_group(session, user_id, mode, experiment)
    await increment_ab_test_metrics(group)
    params = RestaurantSearchParams(
        lat=lat,
        lon=lon,
        radius_km=10,
        limit=50,
        offset=0,
    )
    nearby = await crud.search_restaurants(session, params)

    # O frontend usa estes headers para associar impressões/cliques ao grupo,
    # à versão do modelo e à exposição que gerou o ranking.
    model_version = _model_version()
    recommendation_id = str(uuid4())
    response.headers["X-Experiment-Group"] = group
    response.headers["X-Experiment-Mode"] = mode
    response.headers["X-Experiment-Version"] = settings.experiment_version
    response.headers["X-Model-Version"] = model_version
    response.headers["X-Recommendation-Id"] = recommendation_id
    if not nearby:
        response.headers["X-Recommendation-Strategy"] = "empty"
        return []

    user = await crud.get_user(session, user_id)
    orders = await crud.get_user_orders(session, user_id) if user else []
    interactions = (
        await crud.get_user_interactions(session, user_id) if user else []
    )
    interaction_restaurants = await crud.get_restaurants_by_ids(
        session, {interaction.restaurant_id for interaction in interactions}
    )
    restaurant_lookup = {restaurant.id: restaurant for restaurant in nearby}
    for restaurant in interaction_restaurants:
        restaurant_lookup.setdefault(restaurant.id, restaurant)

    user_features = (
        build_user_features(
            orders,
            user,
            interactions=interactions,
            restaurants=restaurant_lookup,
        )
        if user
        else {}
    )

    scores = await get_scores(str(user_id), turno, group)
    strategy_used = "cache_hit"

    if scores is None:
        if group == EXPERIMENT_DISTANCE:
            # Grupo C: apenas proximidade geográfica, sem modelo de ML.
            scores = {
                str(restaurant.id): 1.0
                / (1.0 + float(restaurant.distance_km or 0.0))
                for restaurant in nearby
            }
            await increment_metrics(
                "requests",
                "cache_misses",
                "distance_scores",
            )
            strategy_used = "distance"
        elif group == EXPERIMENT_BASELINE:
            # Grupo A: estratégia padrão do backend (popularidade documentada),
            # usada como referência contra a personalização.
            scores = popularity_scores(nearby)
            await increment_metrics(
                "requests",
                "cache_misses",
                "popularity_scores",
            )
            strategy_used = "baseline_popularity"
        elif (
            recommender.model is not None
            and orders
            and user is not None
            and has_turno_history(orders, turno)
        ):
            lightgbm_scores = recommender.predict_scores(user_features, nearby, turno)
            # Re-ranking com LoRA (ou fallback determinístico).
            scores = reranker.rerank(
                user_features, nearby, lightgbm_scores, turno
            )
            await increment_metrics("requests", "cache_misses", "model_scores")
            strategy_used = "lightgbm+rerank"
        else:
            # Cold start (sem histórico no turno): popularidade documentada.
            scores = popularity_scores(nearby)
            await increment_metrics("requests", "cache_misses", "popularity_scores")
            strategy_used = "popularity"

        await set_scores(str(user_id), turno, scores, group)
    else:
        await increment_metrics("requests", "cache_hits")

    # Somente o grupo personalizado usa o histórico recente para reordenar o
    # resultado. Baseline e distância permanecem estratégias puras.
    if group == EXPERIMENT_PERSONALIZED:
        affinity = affinity_scores(user_features, nearby)
        if any(value > 0 for value in affinity.values()):
            scores = blend_with_affinity(scores, affinity)
            strategy_used = f"{strategy_used}+affinity"

    response.headers["X-Recommendation-Strategy"] = strategy_used

    for restaurant in nearby:
        restaurant.score = round(
            float(scores.get(str(restaurant.id), 0.0)),
            4,
        )

    return sorted(
        nearby, key=lambda restaurant: restaurant.score or 0.0, reverse=True
    )


@router.post("/train", status_code=202)
async def train_model():
    """Sinaliza que o treino é offline; nunca bloqueia uma requisição HTTP."""
    return {
        "status": "accepted",
        "detail": (
            "O treino do LightGBM é uma operação offline. Execute "
            "`python -m app.ml.train --source db` (ou `--source seed`) no "
            "diretório backend e reinicie a API para carregar o novo artefato."
        ),
    }


@router.post("/train-lora", status_code=202)
async def train_lora_model():
    """Sinaliza que o treino LoRA é uma operação offline.

    Treinar o adapter dentro de uma requisição HTTP bloquearia o event loop
    e exigiria GPU/dependências pesadas no processo da API. O endpoint
    permanece para descoberta, mas delega a execução ao comando dedicado.
    """
    return {
        "status": "accepted",
        "detail": (
            "O treino LoRA é uma operação offline. Execute "
            "`python scripts/train_lora.py` no diretório backend "
            "(requer requirements-llmops.txt) e reinicie a API para carregar "
            "o adapter."
        ),
    }


@router.post("/rerank")
async def rerank_endpoint(
    user_id: UUID = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    turno: Turno = Query("tarde"),
    experiment: str | None = Query(None),
    mode: str = Query(
        EXPERIMENT_MODE_EXPERIMENT,
        pattern="^(experiment|demo)$",
    ),
    session: AsyncSession = Depends(get_db),
):
    """Re-executa o re-ranking (LoRA) sobre os scores já em cache para um usuário/turno."""
    group = await _resolve_group(session, user_id, mode, experiment)
    scores = await get_scores(str(user_id), turno, group)
    if scores is None:
        raise HTTPException(
            status_code=404,
            detail="Nenhum score em cache para este usuário/turno/grupo. "
            "Chame /recommendations primeiro.",
        )

    user = await crud.get_user(session, user_id)
    orders = await crud.get_user_orders(session, user_id) if user else []
    interactions = (
        await crud.get_user_interactions(session, user_id) if user else []
    )
    interaction_restaurants = await crud.get_restaurants_by_ids(
        session, {interaction.restaurant_id for interaction in interactions}
    )
    restaurant_lookup = {
        restaurant.id: restaurant
        for restaurant in interaction_restaurants
    }
    user_features = (
        build_user_features(
            orders,
            user,
            interactions=interactions,
            restaurants=restaurant_lookup,
        )
        if user
        else {}
    )

    nearby = await crud.search_restaurants(
        session,
        RestaurantSearchParams(lat=lat, lon=lon, radius_km=10, limit=50, offset=0),
    )
    if not nearby:
        return []

    adjusted = reranker.rerank(user_features, nearby, scores, turno)

    for restaurant in nearby:
        restaurant.score = round(float(adjusted.get(str(restaurant.id), 0.0)), 4)

    return sorted(
        nearby, key=lambda restaurant: restaurant.score or 0.0, reverse=True
    )