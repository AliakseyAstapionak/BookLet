
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from models import (AnnouncementModel, AvailabilityRuleModel, BookingModel, BookingStatus,
                    NotificationModel)
from services.slots import SERVICE_TZ
from services.users import UserService
from utils import hash_password

SLOTS_URL = "/BookLet/catalog/{anc_id}/slots"
BOOK_URL = "/BookLet/catalog/{anc_id}/book"
MY_BOOKINGS_URL = "/BookLet/me/my_bookings"
CLIENT_CANCEL_URL = "/BookLet/me/my_bookings/{booking_id}/cancel"
PROVIDER_BOOKED_URL = "/BookLet/me/my_announcements/booked"
PROVIDER_CANCEL_URL = "/BookLet/me/my_announcements/booked/{booking_id}/cancel"
OPERATING_MODE_URL = "/BookLet/account/me/operating_mode"
CALENDAR_URL = "/BookLet/account/me/calendar"

PASSWORD = "Str0ngPass!"


@dataclass
class Actor:
    """Пользователь + HTTP-клиент, уже авторизованный под ним."""
    id: int
    username: str
    http: AsyncClient


def now_msk() -> datetime:
    return datetime.now(SERVICE_TZ)


def at(days_ahead: int, hour: int, minute: int = 0) -> datetime:
    """Момент в московском времени: сегодня + days_ahead дней, hour:minute."""
    day = now_msk().date() + timedelta(days=days_ahead)
    return datetime.combine(day, time(hour, minute), tzinfo=SERVICE_TZ)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def create_user(db, username: str, *, active: bool = True):
    hashed = await hash_password(PASSWORD)
    await UserService.create_user(username=username, email=f"{username}@example.com", hashed_pwd=hashed, db=db)
    user = await UserService.get_user_by_username(username=username, db=db, with_settings=True)
    user.settings.two_factor_enabled = False
    user.is_active = active
    await db.commit()
    return user


async def create_announcement(db, provider, *, name="Стрижка", price=1000, duration_minutes=60,
                              cancel_before_hours=24, status="active"):
    anc = AnnouncementModel(user_id=provider.id, name=name, type="beauty", description=None, price=price,
                            status=status, duration_minutes=duration_minutes,
                            cancel_before_hours=cancel_before_hours)
    db.add(anc)
    await db.commit()
    await db.refresh(anc)
    return anc


async def set_schedule(db, provider, *, start=time(9, 0), end=time(18, 0), weekdays=range(7)):
    """Окно приёма мастера. По умолчанию каждый день 09:00–18:00."""
    for weekday in weekdays:
        db.add(AvailabilityRuleModel(user_id=provider.id, weekday=weekday, start_time=start, end_time=end))
    await db.commit()


async def insert_booking(db, anc, client, start: datetime, *, status=BookingStatus.CONFIRMED,
                         duration_minutes=None, cancel_before_hours=None, price=None):
    """Бронь напрямую в БД — чтобы получить любое время и статус (в том числе прошлое)."""
    minutes = duration_minutes if duration_minutes is not None else anc.duration_minutes
    booking = BookingModel(
        announcement_id=anc.id, client_id=getattr(client, "id", client), provider_id=anc.user_id,
        start_at=start, end_at=start + timedelta(minutes=minutes), status=status,
        price=price if price is not None else anc.price,
        cancel_before_hours=cancel_before_hours if cancel_before_hours is not None else anc.cancel_before_hours,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def booking_row(db, booking_id: int):
    """Свежие значения из БД (не из identity map сессии)."""
    row = (await db.execute(
        select(BookingModel.status, BookingModel.cancelled_by_id, BookingModel.cancelled_at,
               BookingModel.cancel_before_hours, BookingModel.price)
        .where(BookingModel.id == booking_id))).first()
    return row


async def count_bookings(db, **filters) -> int:
    rows = (await db.execute(select(BookingModel.id).filter_by(**filters))).all()
    return len(rows)


async def notifications_for(db, user_id: int):
    result = await db.execute(select(NotificationModel).where(NotificationModel.to_user_id == user_id)
                              .order_by(NotificationModel.id))
    return result.scalars().all()


async def get_slots(http: AsyncClient, anc_id: int, **params) -> list[datetime]:
    response = await http.get(SLOTS_URL.format(anc_id=anc_id), params=params)
    assert response.status_code == 200, response.text
    return [parse_dt(s) for s in response.json()["slots"]]


async def book(http: AsyncClient, anc_id: int, start: datetime):
    return await http.post(BOOK_URL.format(anc_id=anc_id), params={"start_at": start.isoformat()})
