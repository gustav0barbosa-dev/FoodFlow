from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.models import Review, User
from app.schemas import ReviewCreate, ReviewOut, ReviewUpdate

router = APIRouter(prefix="/reviews", tags=["reviews"])


def _to_out(review: Review, user: User) -> ReviewOut:
    return ReviewOut.model_validate(review).model_copy(
        update={"user_name": user.name}
    )


@router.post("", response_model=ReviewOut, status_code=201)
async def create_review(
    payload: ReviewCreate,
    response: Response,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=120,
    ),
    session: AsyncSession = Depends(get_db),
):
    restaurant = await crud.get_restaurant(session, payload.restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurante não encontrado")

    user = await crud.get_user(session, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    key = idempotency_key.strip() if idempotency_key else None
    review, created = await crud.create_review(
        session=session,
        restaurant=restaurant,
        user=user,
        rating=payload.rating,
        comment=payload.comment,
        idempotency_key=key or None,
    )

    if not created:
        same_request = (
            review.user_id == user.id
            and review.restaurant_id == restaurant.id
            and review.rating == payload.rating
            and review.comment == payload.comment
        )
        if not same_request:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key reutilizada com um payload diferente.",
            )
        response.status_code = 200

    return _to_out(review, user)


@router.put("/{review_id}", response_model=ReviewOut)
async def update_review(
    review_id: UUID,
    payload: ReviewUpdate,
    session: AsyncSession = Depends(get_db),
):
    """Atualiza uma avaliação existente do próprio usuário."""
    review = await crud.get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    if review.user_id != payload.user_id:
        raise HTTPException(
            status_code=403,
            detail="A avaliação pertence a outro usuário",
        )

    user = await crud.get_user(session, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    updated = await crud.update_review(
        session=session,
        review=review,
        rating=payload.rating,
        comment=payload.comment,
    )
    return _to_out(updated, user)


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    review_id: UUID,
    user_id: UUID = Query(...),
    session: AsyncSession = Depends(get_db),
):
    """Remove uma avaliação existente do próprio usuário."""
    review = await crud.get_review(session, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    if review.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="A avaliação pertence a outro usuário",
        )

    await crud.delete_review(session, review)
    return Response(status_code=204)
