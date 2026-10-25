from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from models import BookingModel, AnnouncementModel
from services.announcements import AnnouncementService
from typing import Dict

class BookingService:

    @staticmethod
    async def book_announcement(anc_id: int, client_id: int, db: AsyncSession) -> Dict:
        stmt = (select(AnnouncementModel, BookingModel).outerjoin(BookingModel, 
                        (BookingModel.announcement_id == AnnouncementModel.id) & (BookingModel.client_id == client_id))
                    .where(AnnouncementModel.id == anc_id))
        result = await db.execute(stmt)
        row = result.first()
        if not row or not row[0]: 
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Объявление не найдено')
    
        announcement = row[0]
        provider_id = announcement.user_id
        existing_booking = row[1]
        if announcement.status == 'booked':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Данное обьявление уже забронировано')
        if announcement.user_id == client_id: 
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Нельзя забронировать свое объявление')
        if existing_booking:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Вы уже подали заявку на бронирование этого объявления')
        new_booking = BookingModel(announcement_id=anc_id, client_id=client_id)
        db.add(new_booking)
        await db.commit()
        await db.refresh(new_booking)
        return {'provider_id': provider_id, 'client_id': new_booking} 