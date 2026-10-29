from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from models import BookingStatus
from schemas import (CreateAnnouncementSchema, AnnouncementsResponseSchema,
                     AnnouncementResponseSchema, MyAnnouncementFiltersSchema, BookingsResponseSchema)
from services import AnnouncementService, BookingService
from core import get_db
from utils import get_current_user
from ..tags import TAG_MY_ANNOUNCEMENTS

router = APIRouter(prefix='/BookLet/me/my_announcements', tags=[TAG_MY_ANNOUNCEMENTS])

_NOT_FOUND = {404: {'description': 'Объявление не найдено'}}
_UNAUTHORIZED = {401: {'description': 'Не авторизован'}}


@router.post(
    '/create',
    summary='Создать объявление',
    responses=_UNAUTHORIZED,
)
async def create_announcement(anc: CreateAnnouncementSchema, db=Depends(get_db), current_data=Depends(get_current_user)):
    user_id = current_data['uid']
    new_announcement = await AnnouncementService.create_announcement(user_id=current_data['uid'], name=anc.name, status=anc.status, type=anc.type,
                                                                    price=anc.price, description=anc.description,
                                                                    duration_minutes=anc.duration_minutes, cancel_before_hours=anc.cancel_before_hours, db=db)
    return {'success': True, 'new_announcement': new_announcement}

@router.get(
    '/active',
    response_model=AnnouncementsResponseSchema,
    summary='Список моих активных объявлений',
    description='Поддерживает фильтры, сортировку и пагинацию.',
    responses=_UNAUTHORIZED,
)
async def my_active_announcements(filters: Annotated[MyAnnouncementFiltersSchema, Query()], db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='active', filters=filters, db=db)
    return {'announcements': announcements}


@router.get(
    '/active/{anc_id}',
    response_model=AnnouncementResponseSchema,
    summary='Моё активное объявление по id',
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def my_active_announcement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='active', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}


@router.get(
    '/booked',
    response_model=BookingsResponseSchema,
    summary='Список моих забронированных объявлений',
    description='Объявления, которые у меня как у продавца забронировали клиенты.',
    responses=_UNAUTHORIZED,
)
async def get_my_bookings(status_filter: Optional[BookingStatus] = Query(default=None, alias='status'), limit: int = Query(default=20, ge=1, le=150),
                          offset: int = Query(default=0, ge=0),
                          db: AsyncSession = Depends(get_db),
                          current_user=Depends(get_current_user)):
    return await BookingService.get_my_bookings(status='as_provider', user_id=current_user['uid'], status_filter=status_filter, limit=limit, offset=offset, db=db)


@router.post(
    '/booked/{booking_id}/cancel',
    summary='Отменить запись клиента',
    description='Мастер может отменить запись клиента в любой момент до начала услуги. Клиенту придёт уведомление.',
    responses={**_UNAUTHORIZED,
               404: {'description': 'Бронь не найдена'},
               409: {'description': 'Бронь уже отменена или услуга началась'}},
)
async def cancel_client_booking(booking_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    await BookingService.cancel_booking(booking_id=booking_id, user_id=current_user['uid'],
                                        username=current_user['username'], role='provider', db=db)
    return {'success': True, 'msg': 'Запись отменена'}


@router.get(
    '/archived',
    response_model=AnnouncementsResponseSchema,
    summary='Список моих архивных объявлений',
    responses=_UNAUTHORIZED,
)
async def my_archived_announcements(filters: Annotated[MyAnnouncementFiltersSchema, Query()], db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='archived', filters=filters, db=db)
    return {'announcements': announcements}


@router.get(
    '/archived/{anc_id}',
    response_model=AnnouncementResponseSchema,
    summary='Моё архивное объявление по id',
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def my_archived_announcement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='archived', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}

@router.post(
    '/{anc_id}/unarchive',
    summary='Разархивировать объявление по id',
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def unarchive_announcement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.unarchive_announcement(user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail='Объявление не найдено в архиве или у вас нет прав'
        )
    return {'success': True, 'msg': 'Объявление удалено из архива'}


@router.post(
    '/{anc_id}/archive',
    summary='Отправить объявление в архив',
    description='Забронированное или уже архивированное объявление в архив отправить нельзя.',
    responses={**_UNAUTHORIZED, **_NOT_FOUND,
               409: {'description': 'Объявление забронировано или уже в архиве'}},
)
async def archive_announcement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    anc_user = await AnnouncementService.get_announcement_user(id=anc_id, db=db)
    if anc_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    if user_id != anc_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    if not await AnnouncementService.delete_announcement(id=anc_id, db=db):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail='Нельзя удалить забронированное или уже архивированное объявление')
    return {'success': True, 'msg': 'Объявление занесено в архив'}
