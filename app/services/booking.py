from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from fastapi import HTTPException, status
from models import UserModel, BookingModel, AnnouncementModel, BookingStatus, StatusEnum, NotificationModel
from services.announcements import AnnouncementService
from typing import Dict, Literal

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



    @staticmethod
    async def cancel_my_booking(anc_id: int, client_id: int, client_name: str, db: AsyncSession) -> None:
        query = (select(BookingModel, AnnouncementModel).join(AnnouncementModel, AnnouncementModel.id == BookingModel.announcement_id)
        .where(BookingModel.announcement_id == anc_id,
                BookingModel.client_id == client_id,
                BookingModel.status == BookingStatus.CONFIRMED))
        row = (await db.execute(query)).first()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail='У вас нет активной брони на это объявление')
        booking, announcement = row
        res = await db.execute(update(BookingModel).where(BookingModel.id == booking.id, BookingModel.status == BookingStatus.CONFIRMED)
                .values(status=BookingStatus.CANCELLED, cancelled_by_id=client_id))
        if res.rowcount == 0:
            await db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail='Бронь уже отменена')

        await db.execute(update(AnnouncementModel).where(AnnouncementModel.id == anc_id, AnnouncementModel.status == StatusEnum.BOOKED)
                .values(status=StatusEnum.ACTIVE))
                
        
        db.add(NotificationModel(
            to_user_id=booking.provider_id, sender_id=client_id, type='booking_cancelled', booking_id=booking.id,
            title='❌ Бронь отменена',
            text=f'Пользователь @{client_name} отменил бронь «{announcement.name}». Объявление снова доступно в каталоге.'))
        
        await db.commit()
        return True