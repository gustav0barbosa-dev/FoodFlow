from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.cache.redis_client import track_event
from app.database import get_db
from app.schemas import EventIn, EventOut

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    event: EventIn,
    session: AsyncSession = Depends(get_db),
):
    created = await crud.create_event(session, event.type, event.payload)
    await track_event(created.type, created.payload)
    return created
