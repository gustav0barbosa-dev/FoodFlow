"""Endpoints de interações do usuário e perfil de preferências."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    InteractionIn,
    InteractionOut,
    UserPreferenceProfileOut,
)
from app.services import interactions as interaction_service

router = APIRouter(tags=["interactions"])


@router.post(
    "/interactions",
    response_model=InteractionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_interaction(
    payload: InteractionIn,
    response: Response,
    session: AsyncSession = Depends(get_db),
):
    """Registra visualização, clique, favorito ou compra confirmada.

    ``idempotency_key`` evita duplicar a mesma compra quando o frontend repete
    a requisição. Interações repetidas sem chave são registradas normalmente
    (cada visualização conta no histórico).
    """
    try:
        interaction, created = await interaction_service.record_interaction(
            session,
            user_id=payload.user_id,
            restaurant_id=payload.restaurant_id,
            interaction_type=payload.interaction_type.value,
            purchase_value=payload.purchase_value,
            idempotency_key=payload.idempotency_key,
            experiment_group=payload.experiment_group,
            experiment_mode=payload.experiment_mode,
            experiment_version=payload.experiment_version,
            recommendation_id=payload.recommendation_id,
            recommendation_position=payload.recommendation_position,
            model_version=payload.model_version,
            event_metadata=payload.metadata,
        )
    except interaction_service.InteractionUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except interaction_service.InteractionRestaurantNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except interaction_service.InvalidInteractionTypeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except interaction_service.InvalidExperimentGroupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not created:
        # Compra repetida: devolve a interação já existente com 200.
        response.status_code = status.HTTP_200_OK
    return InteractionOut.model_validate(interaction)


@router.get(
    "/users/{user_id}/preferences",
    response_model=UserPreferenceProfileOut,
)
async def get_user_preferences(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Perfil derivado do histórico: categorias, cozinhas e restaurantes."""
    profile = await interaction_service.get_user_preference_profile(
        session, user_id
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return profile
