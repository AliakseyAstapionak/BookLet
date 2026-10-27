from fastapi import APIRouter, Depends, HTTPException, status

from core import get_db
from services import UserService, AnnouncementService
from schemas import AccountDataResponseSchema
from .tags import TAG_USER_PROFILES

router = APIRouter(prefix='/BookLet/user/{user_id}', tags=[TAG_USER_PROFILES])


@router.get(
    '/profile',
    response_model=AccountDataResponseSchema,
    summary='Профиль пользователя',
    responses={404: {'description': 'Аккаунт не найден'}},
)
async def get_profile(user_id: int, db=Depends(get_db)):
    data = await UserService.get_user_by_id(id=user_id, with_settings=True, db=db)
    if not data or data.is_active == False:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    if not data.settings.show_email:
        data.email = 'Недоступен к просмотру'
    return {'user': data}


@router.get(
    '/announcements',
    summary='Объявления пользователя',
)
async def get_announcements(user_id: int, db=Depends(get_db)):
    announcements = await AnnouncementService.get_user_announcements(user_id=user_id, db=db)
    return {'announcements': announcements}


@router.get(
    '/announcements/{anc_id}',
    summary='Активное объявление пользователя по id',
    responses={404: {'description': 'Объявление не найдено'}},
)
async def get_announcement(user_id: int, anc_id: int, db=Depends(get_db)):
    announcement = await AnnouncementService.get_my_announcement(anc_id=anc_id, user_id=user_id, status='active', db=db)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объявление не найдено")
    return announcement
