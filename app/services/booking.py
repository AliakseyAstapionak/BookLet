from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from fastapi import HTTPException, status
from models import UserModel, BookingModel, AnnouncementModel, BookingStatus, StatusEnum, NotificationModel
from services.announcements import AnnouncementService
from services.notifications import NotificationService
from services.slots import SlotService, SERVICE_TZ
from typing import Dict, Literal
from datetime import datetime, timedelta

MAX_BOOKING_DAYS = 31  

class BookingService:

    @staticmethod
    async def book_announcement(anc_id: int, start_at: datetime, client_id: int, client_name: str, db: AsyncSession) -> Dict:
        announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
        provider_id = announcement.user_id
        if provider_id == client_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Нельзя забронировать своё объявление')

        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=SERVICE_TZ)
        start_at = start_at.astimezone(SERVICE_TZ)

        days = (start_at.date() - datetime.now(SERVICE_TZ).date()).days + 1
        if days < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Нельзя забронировать прошедшее время')
        if days > MAX_BOOKING_DAYS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f'Бронировать можно не дальше чем на {MAX_BOOKING_DAYS} дней вперёд')

        free_slots = await SlotService.get_free_slots(anc_id=anc_id, days=days, db=db)
        if start_at not in free_slots:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Это время недоступно для записи')

        booking = BookingModel(
            announcement_id=anc_id,
            client_id=client_id,
            provider_id=provider_id,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=announcement.duration_minutes),
            status=BookingStatus.CONFIRMED,
            price=announcement.price,                         
            cancel_before_hours=announcement.cancel_before_hours,
        )
        db.add(booking)
        await db.flush()  

        await NotificationService.send_book_message(to_user_id=provider_id, sender_id=client_id, title='Новая бронь',
            msg_text=f'Пользователь {client_name} забронировал «{announcement.name}» '
                     f'на {start_at.strftime("%d.%m.%Y %H:%M")}.',
            notif_type='booking',
            booking_id=booking.id,
            commit=False, db=db,)
        await db.commit()
        await db.refresh(booking)

        return {
            'id': booking.id, 'announcement_id': booking.announcement_id, 'provider_id': booking.provider_id,
            'status': booking.status.value, 'start_at': booking.start_at, 'end_at': booking.end_at,
            'price': booking.price, 'cancel_before_hours': booking.cancel_before_hours,
            'created_at': booking.created_at,
        }



    @staticmethod
    async def get_my_bookings(status: Literal['as_client', 'as_provider'],user_id: int, status_filter: BookingStatus | None,
                            limit: int, offset: int, db: AsyncSession) -> dict:
        if status == 'as_client':
            conditions = [BookingModel.client_id == user_id]
        elif status == 'as_provider':
            conditions = [BookingModel.provider_id == user_id]
        else: 
            raise HTTPException(status_code=400, detail='Неверные данные в поиске бронирований')
        if status_filter:
            conditions.append(BookingModel.status == status_filter)
        total = (await db.execute(
            select(func.count()).select_from(BookingModel).where(*conditions))).scalar_one()
        query = (select(BookingModel.id, BookingModel.announcement_id, BookingModel.provider_id,
                        BookingModel.status, BookingModel.start_at, BookingModel.end_at,
                        BookingModel.created_at,
                        AnnouncementModel.name.label('announcement_name'), AnnouncementModel.price,
                        UserModel.username.label('provider_username'))
                .join(AnnouncementModel, AnnouncementModel.id == BookingModel.announcement_id)
                .join(UserModel, UserModel.id == BookingModel.provider_id)
                .where(*conditions)
                .order_by(BookingModel.created_at.desc(), BookingModel.id.desc())
                .limit(limit).offset(offset))
        rows = (await db.execute(query)).mappings().all()
        return {'bookings': [dict(r) for r in rows], 'total': total}