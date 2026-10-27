from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core import get_db
from services import UserService, AnnouncementService
from schemas import AccountDataResponseSchema
from typing import Annotated


router = APIRouter(prefix='/BookLet/user/{user_id}', tags=['Просмотр аккаунта другого пользователя'])

@router.get('/profile', response_model=AccountDataResponseSchema)
async def get_profile(user_id: int, db=Depends(get_db)):
    data = await UserService.get_user_by_id(id=user_id, db=db)
    if not data or data.is_active == False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    return {'user' : data}

@router.get('/announcements')
async def get_announcements(user_id: int, db=Depends(get_db)):
    announcements = await AnnouncementService.get_user_announcements(user_id=user_id, db=db)
    return {'announcements': announcements}

@router.get("/announcements/{anc_id}")
async def get_announcement(user_id: int, anc_id: int, db=Depends(get_db)):
    announcement = await AnnouncementService.get_my_announcement(id=anc_id, user_id=user_id, status='active', db=db)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    return announcement