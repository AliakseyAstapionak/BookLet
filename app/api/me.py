from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from utils import verify_password, hash_password
from schemas import (ChangePasswordSchema, CreateAnnouncementSchema, 
                    AnnouncementsResponseSchema, MyAnnouncementFiltersSchema, Change2FASchema,
                    MyNotificationsResponseSchema, MyBookingsResponseSchema, NotificationResponseSchema,
                    AnnouncementResponseSchema, AccountDataResponseSchema)
from services import UserService, AnnouncementService, NotificationService, BookingService, BookingStatus, NotificationService
from core import get_db
from utils import get_current_user
from typing import Annotated, Optional

router = APIRouter(prefix='/BookLet/me', tags=['Функции моего аккаунта'])

async def check_password(data: Change2FASchema, userdata: dict=Depends(get_current_user), db: AsyncSession=Depends(get_db)):
    hash_password = await UserService.get_password_by_username(username=userdata['username'], db=db)
    if not hash_password:
        return False
    return await verify_password(password=data.password ,hashed_password=hash_password)

@router.post('/account/settings/security/2fa', response_model=None)
async def change_2fa(data: Change2FASchema, request: Request, db=Depends(get_db), current_data=Depends(get_current_user), check_pass=Depends(check_password)):
    if not check_pass:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль')  
    result = await UserService.change_2fa(user_id=current_data['uid'], db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Не удалось поменять значение 2fa')
    return {'success': True, 'msg': 'Данные изменены успешно'}

@router.post('/account/settings/security/change_password')
async def change_password(data: ChangePasswordSchema, db=Depends(get_db), current_data=Depends(get_current_user)):
    if not await check_password(data, current_data, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Неверный пароль') 
    new_hash_password = await hash_password(data.new_password)
    result = await UserService.change_password(user_id=current_data['uid'], new_hash_password=new_hash_password, db=db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Не удалось поменять пароль")
    return {'success': True, 'msg': 'Пароль успешно изменен'}

#TODO нужно подумать как разбединит ьпоказ данных для пользователя другого и своего аккаунта потому что что бы на своем акке почта показывалась всегда а на другом только если пользователь открыт
@router.get('', response_model=AccountDataResponseSchema)
async def get_my_data(db=Depends(get_db), current_data=Depends(get_current_user)):
    data = await UserService.get_user_by_id(id=current_data['uid'], db=db)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Аккаунт не найден')
    return {'user' : data}

#TODO добавить фильтры для всех видов my_notifications/*
@router.get('/my_notifications', response_model=MyNotificationsResponseSchema)
async def get_my_all_notifications(request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_all_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}

@router.get('/my_notifications/incoming', response_model=MyNotificationsResponseSchema)
async def get_my_incoming_notifications(request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_encoming_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}

@router.get('/my_notifications/incoming/{not_id}', response_model=NotificationResponseSchema)
async def get_incoming_notification_data(not_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    client_id = current_user['uid']
    notification = await NotificationService.get_my_incoming_notification(not_id=not_id, client_id=client_id, db=db)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Входящее уведомление не найдено')
    return {'notification': notification}

@router.get('/my_notifications/sent', response_model=MyNotificationsResponseSchema)
async def get_my_sent_notifications(request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    notifications = await NotificationService.get_my_sent_notifications(user_id=current_user['uid'], db=db)
    return {'notifications': notifications}

@router.get('/my_notifications/sent/{not_id}', response_model=NotificationResponseSchema)
async def get_sent_notification_data(not_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    client_id = current_user['uid']
    notification = await NotificationService.get_my_sent_notification(not_id=not_id, client_id=client_id, db=db)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Отправленное уведомление не найдено')
    return {'notification': notification}

@router.post('/my_announcements/create')
async def create_announcement(anc: CreateAnnouncementSchema, db=Depends(get_db), current_data=Depends(get_current_user)):
    user_id = current_data['uid']
    new_announcement = await AnnouncementService.create_announcement(user_id=current_data['uid'], name=anc.name, status=anc.status, type=anc.type,
                                                                    price=anc.price, description=anc.description, db=db)
    return {'success': True, 'new_announcement': new_announcement}

@router.get('/my_announcements/active', response_model=AnnouncementsResponseSchema, )
async def my_activeannouncemets(filters: Annotated[MyAnnouncementFiltersSchema, Query()], request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='active', filters=filters,  db=db)
    return {'announcements': announcements}

@router.get('/my_announcements/active/{anc_id}', response_model=AnnouncementResponseSchema)
async def my_active_announcemet(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='active', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}

#TODO подумать а можно ли удалять вообщще забронированные(пока что нельзя)
@router.post('/my_announcements/{anc_id}/archive')
async def delete_annoncement(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    anc_user = await AnnouncementService.get_announcement_user(id=anc_id, db=db)
    if anc_user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    if user_id != anc_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')   # см. ниже
    if not await AnnouncementService.delete_announcement(id=anc_id, db=db):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail='Нельзя удалить забронированное или уже архивированное объявление')
    return {'success': True, 'msg': 'Объявление занесено в архив'}


@router.get('/my_announcements/archived', response_model=AnnouncementsResponseSchema, )
async def my_archive_dannouncemets(filters: Annotated[MyAnnouncementFiltersSchema, Query()], request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='archived', filters=filters,  db=db)
    return {'announcements': announcements}


@router.get('/my_announcements/archived/{anc_id}', response_model=AnnouncementResponseSchema)
async def my_active_announcemet(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='archived', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}

@router.get('/my_announcements/booked', response_model=AnnouncementsResponseSchema, )
async def my_booked_announcemets(filters: Annotated[MyAnnouncementFiltersSchema, Query()], request: Request, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcements = await AnnouncementService.get_my_announcements(user_id=user_id, status='booked', filters=filters,  db=db)
    return {'announcements': announcements}

@router.get('/my_announcements/booked/{anc_id}', response_model=AnnouncementResponseSchema)
async def my_active_announcemet(anc_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    user_id = current_user['uid']
    announcement = await AnnouncementService.get_my_announcement(status='booked', user_id=user_id, anc_id=anc_id, db=db)
    if not announcement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    return {'announcement': announcement}


@router.get('/my_favourites')
async def my_favourites(filters: Annotated[MyAnnouncementFiltersSchema, Query()], current_data=Depends(get_current_user), db=Depends(get_db)):
    announcements = await AnnouncementService.get_liked_user_announcements(filters=filters, uid=current_data['uid'], db=db)
    return {'announcements': announcements, 'total': len(announcements)}


@router.get('/my_bookings', response_model=MyBookingsResponseSchema)
async def get_my_bookings(status_filter: Optional[BookingStatus] = Query(default=None, alias='status'), limit: int = Query(default=20, ge=1, le=150),
        offset: int = Query(default=0, ge=0),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user)):
    return await BookingService.get_my_bookings_as_client(client_id=current_user['uid'], status_filter=status_filter, limit=limit, offset=offset, db=db)


#TODO сказать что нельзя отменить бронь если уже за определенное время до начала услуги, если нет то бронь отменить нельзя или только по заявке
@router.post('/my_bookings/{anc_id}/cancel')
async def cancel_my_booking(anc_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    if await BookingService.cancel_my_booking(anc_id=anc_id, client_id=current_user['uid'], client_name=current_user['username'], db=db):
        return {'success': True, 'msg': 'Бронь отменена'}
    else:
        return {'success': False, 'msg': 'Бронь не отменена, произошла ошибка'}