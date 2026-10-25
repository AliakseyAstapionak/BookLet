from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from models import BookingModel, AnnouncementModel, BookingStatus, StatusEnum, NotificationModel
from services.announcements import AnnouncementService
from typing import Dict

class BookingService:

    @staticmethod
    async def book_announcement(anc_id: int, client_id: int, client_name: str, db: AsyncSession) -> Dict:
        announcement = (await db.execute(select(AnnouncementModel).where(AnnouncementModel.id == anc_id))).scalar()
        if not announcement:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
        if announcement.status == StatusEnum.ARCHIVED:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Объявление недоступно')
        if announcement.user_id == client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Нельзя забронировать своё объявление')
        active = (await db.execute(select(BookingModel).where(BookingModel.announcement_id == anc_id,
                    BookingModel.status == BookingStatus.CONFIRMED))).scalars().first()
        if active:
            if active.client_id == client_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Вы уже забронировали это объявление')
            raise HTTPException(status.HTTP_409_CONFLICT, detail='Объявление уже забронировано')
        
        booking = BookingModel(announcement_id=anc_id, client_id=client_id, provider_id=announcement.user_id)
        db.add(booking)
        announcement.status = StatusEnum.BOOKED
        db.add(NotificationModel(
            to_user_id=announcement.user_id, sender_id=client_id, type='booking_created', booking_id=booking.id,
            title='🔔 Новое бронирование',
            text=f'Пользователь @{client_name} забронировал «{announcement.name}».'))
        await db.commit()
        await db.refresh(booking)
        return booking

