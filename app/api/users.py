from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core import get_db
from services import UserService
from schemas import AccountDataResponseSchema



router = APIRouter(prefix='/BookLet/user/{user_id}', tags=['Просмотр аккаунта другого пользователя'])

@router.get('/profile', response_model=AccountDataResponseSchema)
async def get_profile(user_id: int, db=Depends(get_db)):
    data = await UserService.get_user_by_id(id=user_id, db=db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    return {'user' : data}