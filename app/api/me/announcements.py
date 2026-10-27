from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query

from schemas import (CreateAnnouncementSchema, AnnouncementsResponseSchema,
                     AnnouncementResponseSchema, MyAnnouncementFiltersSchema)
from services import AnnouncementService
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
    response_model=AnnouncementsResponseSchema,
    summary='Список моих забронированных объявлений',
    description='Объявления, которые у меня как у продавца забронировали клиенты.',
    responses=_UNAUTHORIZED,
)
async def my_booked_announcements(filters: Annotated[MyAnnouncementFiltersSchema, Query()], db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='booked', filters=filters, db=db)
    return {'announcements': announcements}


@router.get(
    '/booked/{anc_id}',
    response_model=AnnouncementResponseSchema,
    summary='Моё забронированное объявление по id',
    responses={**_UNAUTHORIZED, **_NOT_FOUND},
)
async def my_booked_announcement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='booked', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}


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


#TODO подумать а можно ли удалять вообщще забронированные(пока что нельзя)
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
