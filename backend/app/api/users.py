from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db
from app.schemas import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """Retorna o perfil público de um usuário.

    Não há autenticação neste MVP; o endpoint existe para o app mobile e o
    frontend web exibirem o perfil sem depender de dados mock.
    """
    user = await crud.get_user(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return user
