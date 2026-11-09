from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import crud
from app.schemas import EventIn, EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
async def create_event(event: EventIn, session: AsyncSession = Depends(get_db)):
    allowed = {
        "restaurant_card_clicked",
        "restaurant_opened",
        "add_to_cart",
        "order_completed",
        "preferences_updated",
        "search_performed",
        "favorite_toggled",
        "order_status_updated",
        "review_submitted",
    }
    if event.type not in allowed:
        raise HTTPException(status_code=400, detail=f"Tipo de evento inválido: {event.type}")

    created = await crud.create_event(session, event.type, event.payload)
    return created
