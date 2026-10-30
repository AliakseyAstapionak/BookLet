from typing import Annotated

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from core import get_db
from services import AnnouncementService, UserService, BookingService, SlotService
from utils import get_current_user
from schemas import AnnouncementFiltersSchema
from .tags import TAG_CATALOG

router = APIRouter(prefix='/BookLet', tags=[TAG_CATALOG])

_UNAUTHORIZED = {401: {'description': 'Не авторизован'}}

#TODO добавить в фильтры время на которое заказать хочешь и покажет активные
@router.get(
    '/catalog',
    summary='Каталог объявлений',
    description='Поиск по объявлениям: фильтры по продавцу, названию, типу и цене, сортировка и пагинация.',
)
async def catalog(filters: Annotated[AnnouncementFiltersSchema, Query()], db=Depends(get_db)):
    result = await AnnouncementService.get_catalog(filters=filters, db=db)
    return {'announcements': result}


@router.get(
    '/catalog/{anc_id}',
    summary='Карточка объявления',
    description='Возвращает объявление по id. Архивные и забронированные объявления недоступны.',
    responses={400: {'description': 'Объявление недоступно'},
               404: {'description': 'Объявление не найдено'}},
)
async def announcement(anc_id: int, db=Depends(get_db)):
    result = await AnnouncementService.get_announcement(id=anc_id, db=db)
    return {'success': True, 'announcement': result}

@router.post(
    '/catalog/{anc_id}/like',
    summary='Добавить в избранное / убрать из избранного',
    description='Переключатель: повторный вызов убирает объявление из избранного. '
                'Свои объявления лайкать нельзя. Список избранного — в разделе «Избранное».',
    responses={**_UNAUTHORIZED,
               404: {'description': 'Объявление не найдено'},
               409: {'description': 'Нельзя лайкать свои объявления'}},
)
async def like_anc(anc_id: int, db: AsyncSession = Depends(get_db), current_data=Depends(get_current_user)):
    announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
    if announcement.user_id == current_data['uid']:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Нельзя лайкать свои сообщения')
    result = await UserService.like_announcement(uid=current_data['uid'], anc_id=anc_id, db=db)
    return result

@router.get('/catalog/{anc_id}/slots', summary='Свободные слоты',
            description='Свободное время для записи. По умолчанию ближайшие 7 дней, максимум 31 день.')
async def free_slots(anc_id: int, days: int = Query(default=7, ge=1, le=31), db=Depends(get_db)):
    return {'slots': await SlotService.get_free_slots(anc_id=anc_id, days=days, db=db)}

@router.post(
    '/catalog/{anc_id}/book',
    summary='Забронировать объявление',
    description='Бронирует объявление за текущим пользователем. Продавцу приходит уведомление. '
                'Свои брони — в разделе «Мои брони».',
    responses=_UNAUTHORIZED,
)
async def book_announcement(anc_id: int, start_at: datetime, db: AsyncSession = Depends(get_db), current_data=Depends(get_current_user)):
    client_name = current_data['username']
    client_id = current_data['uid']
    booking = await BookingService.book_announcement(start_at=start_at, anc_id=anc_id, client_id=client_id, client_name=client_name, db=db)

    return {"success": True, "booking": booking}
