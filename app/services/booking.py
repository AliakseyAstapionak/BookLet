from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from fastapi import HTTPException, status
from models import UserModel, BookingModel, AnnouncementModel, BookingStatus, StatusEnum, NotificationModel
from services.announcements import AnnouncementService
from typing import Dict, Literal

class BookingService:

    @staticmethod
    async def book_announcement(anc_id: int, client_id: int, client_name: str, db: AsyncSession) -> Dict:
        ...



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

