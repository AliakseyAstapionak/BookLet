from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import aliased
from fastapi import HTTPException, status
from models import UserModel, BookingModel, AnnouncementModel, BookingStatus, StatusEnum, NotificationModel
from services.announcements import AnnouncementService
from services.notifications import NotificationService
from services.slots import SlotService, SERVICE_TZ, ACTIVE_STATUSES
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
        Provider, Client = aliased(UserModel), aliased(UserModel)
        query = (select(BookingModel.id, BookingModel.announcement_id, BookingModel.provider_id,
                        BookingModel.client_id, BookingModel.cancel_before_hours,
                        BookingModel.status, BookingModel.start_at, BookingModel.end_at,
                        BookingModel.created_at,
                        AnnouncementModel.name.label('announcement_name'), AnnouncementModel.price,
                        Provider.username.label('provider_username'),
                        Client.username.label('client_username'))
                .join(AnnouncementModel, AnnouncementModel.id == BookingModel.announcement_id)
                .join(Provider, Provider.id == BookingModel.provider_id)
                .join(Client, Client.id == BookingModel.client_id)
                .where(*conditions)
                .order_by(BookingModel.created_at.desc(), BookingModel.id.desc())
                .limit(limit).offset(offset))
        rows = (await db.execute(query)).mappings().all()
        role = 'client' if status == 'as_client' else 'provider'
        now = datetime.now(SERVICE_TZ)
        bookings = []
        for r in rows:
            item = dict(r)
            item['can_cancel'] = BookingService._can_cancel(
                role=role, booking_status=r['status'], start_at=r['start_at'],
                cancel_before_hours=r['cancel_before_hours'], now=now)
            bookings.append(item)
        return {'bookings': bookings, 'total': total}

    @staticmethod
    def _can_cancel(role: Literal['client', 'provider'], booking_status: BookingStatus,
                    start_at: datetime, cancel_before_hours: int, now: datetime) -> bool:
        """Правила отмены. Клиент — не позднее чем за cancel_before_hours до начала.
        Мастер — в любой момент до начала услуги."""
        if booking_status not in ACTIVE_STATUSES or start_at is None or start_at <= now:
            return False
        if role == 'client':
            return now <= start_at - timedelta(hours=cancel_before_hours)
        return True

    @staticmethod
    async def cancel_booking(booking_id: int, user_id: int, username: str,
                             role: Literal['client', 'provider'], db: AsyncSession) -> dict:
        owner_col = BookingModel.client_id if role == 'client' else BookingModel.provider_id
        row = (await db.execute(
            select(BookingModel, AnnouncementModel.name)
            .join(AnnouncementModel, AnnouncementModel.id == BookingModel.announcement_id)
            .where(BookingModel.id == booking_id, owner_col == user_id)
        )).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Бронь не найдена')
        booking, anc_name = row

        if booking.status == BookingStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Бронь уже отменена')
        if booking.status == BookingStatus.COMPLETED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Услуга уже оказана, бронь отменить нельзя')
        now = datetime.now(SERVICE_TZ)
        if booking.start_at <= now:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Услуга уже началась, бронь отменить нельзя')
        if role == 'client':
            deadline = booking.start_at - timedelta(hours=booking.cancel_before_hours)
            if now > deadline:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f'Отменить бронь можно не позднее чем за {booking.cancel_before_hours} ч до начала '
                           f'(до {deadline.astimezone(SERVICE_TZ).strftime("%d.%m.%Y %H:%M")}). '
                           f'Свяжитесь с мастером.')

        # Условный UPDATE: защита от двойной отмены и гонки с другой стороной
        result = await db.execute(
            update(BookingModel)
            .where(BookingModel.id == booking_id, BookingModel.status.in_(ACTIVE_STATUSES))
            .values(status=BookingStatus.CANCELLED, cancelled_by_id=user_id, cancelled_at=now))
        if result.rowcount == 0:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Бронь уже отменена')

        when = booking.start_at.astimezone(SERVICE_TZ).strftime('%d.%m.%Y %H:%M')
        if role == 'client':
            to_user_id, text = booking.provider_id, f'Пользователь {username} отменил бронь «{anc_name}» на {when}. Время снова свободно.'
        else:
            to_user_id, text = booking.client_id, f'Мастер {username} отменил вашу бронь «{anc_name}» на {when}.'
        await NotificationService.send_book_message(
            to_user_id=to_user_id, sender_id=user_id, title='Бронь отменена', msg_text=text,
            notif_type='booking_cancelled', booking_id=booking_id, commit=False, db=db)
        await db.commit()
        return {'id': booking_id, 'status': BookingStatus.CANCELLED.value, 'cancelled_at': now}