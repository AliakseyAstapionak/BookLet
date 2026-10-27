from fastapi import APIRouter, Depends, HTTPException, status

from schemas import MyNotificationsResponseSchema, NotificationResponseSchema
from services import NotificationService
from core import get_db
from utils import get_current_user
from ..tags import TAG_NOTIFICATIONS

router = APIRouter(prefix='/BookLet/me/my_notifications', tags=[TAG_NOTIFICATIONS])

_UNAUTHORIZED = {401: {'description': 'Не авторизован'}}


#TODO добавить фильтры для всех видов my_notifications/*
@router.get(
    '',
    response_model=MyNotificationsResponseSchema,
    summary='Все мои уведомления',
    description='Входящие и отправленные вместе.',
    responses=_UNAUTHORIZED,
)
async def get_my_all_notifications(db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_all_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}


@router.get(
    '/incoming',
    response_model=MyNotificationsResponseSchema,
    summary='Входящие уведомления',
    responses=_UNAUTHORIZED,
)
async def get_my_incoming_notifications(db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_encoming_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}


@router.get(
    '/incoming/{not_id}',
    response_model=NotificationResponseSchema,
    summary='Входящее уведомление по id',
    responses={**_UNAUTHORIZED, 404: {'description': 'Входящее уведомление не найдено'}},
)
async def get_incoming_notification_data(not_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    client_id = current_user['uid']
    notification = await NotificationService.get_my_incoming_notification(not_id=not_id, client_id=client_id, db=db)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Входящее уведомление не найдено')
    return {'notification': notification}


@router.get(
    '/sent',
    response_model=MyNotificationsResponseSchema,
    summary='Отправленные уведомления',
    responses=_UNAUTHORIZED,
)
async def get_my_sent_notifications(db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_sent_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}


@router.get(
    '/sent/{not_id}',
    response_model=NotificationResponseSchema,
    summary='Отправленное уведомление по id',
    responses={**_UNAUTHORIZED, 404: {'description': 'Отправленное уведомление не найдено'}},
)
async def get_sent_notification_data(not_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    client_id = current_user['uid']
    notification = await NotificationService.get_my_sent_notification(not_id=not_id, client_id=client_id, db=db)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Отправленное уведомление не найдено')
    return {'notification': notification}
