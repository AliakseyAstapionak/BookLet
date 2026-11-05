import pytest
from datetime import timedelta

from models import BookingStatus
from services import BookingService

from booking_helpers import (CLIENT_CANCEL_URL, PROVIDER_CANCEL_URL, at, now_msk, create_announcement, set_schedule,
                             insert_booking, booking_row, notifications_for, get_slots, book)

NOT_FOUND = "Бронь не найдена"
ALREADY_CANCELLED = "Бронь уже отменена"


def client_cancel(http, booking_id):
    return http.post(CLIENT_CANCEL_URL.format(booking_id=booking_id))


def provider_cancel(http, booking_id):
    return http.post(PROVIDER_CANCEL_URL.format(booking_id=booking_id))


# Отмена клиентом

@pytest.mark.asyncio
async def test_client_cancel_success(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 200
    assert response.json() == {"success": True, "msg": "Бронь отменена"}
    row = await booking_row(db_session, booking.id)
    assert row.status == BookingStatus.CANCELLED
    assert row.cancelled_by_id == customer.id
    assert abs(row.cancelled_at - now_msk()) < timedelta(seconds=30)


@pytest.mark.asyncio
async def test_client_cancel_notifies_provider(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Стрижка")
    start = now_msk() + timedelta(days=3)
    booking = await insert_booking(db_session, anc, customer, start)

    await client_cancel(customer.http, booking.id)

    notes = await notifications_for(db_session, provider.id)
    assert len(notes) == 1
    note = notes[0]
    assert note.type == "booking_cancelled"
    assert note.title == "Бронь отменена"
    assert note.sender_id == customer.id
    assert note.booking_id == booking.id
    assert customer.username in note.text and "Стрижка" in note.text
    assert start.strftime("%d.%m.%Y %H:%M") in note.text
    assert await notifications_for(db_session, customer.id) == []


@pytest.mark.asyncio
async def test_client_cancel_frees_slot_for_others(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    first = await book(customer.http, anc.id, at(2, 10))
    assert at(2, 10) not in await get_slots(other_customer.http, anc.id, days=7)

    await client_cancel(customer.http, first.json()["booking"]["id"])

    assert at(2, 10) in await get_slots(other_customer.http, anc.id, days=7)
    assert (await book(other_customer.http, anc.id, at(2, 10))).status_code == 200


@pytest.mark.asyncio
async def test_client_cancel_pending_booking(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3),
                                   status=BookingStatus.PENDING)

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 200
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CANCELLED


@pytest.mark.asyncio
async def test_client_cancel_does_not_touch_other_bookings(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    target = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    other = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=4))

    await client_cancel(customer.http, target.id)

    assert (await booking_row(db_session, other.id)).status == BookingStatus.CONFIRMED



@pytest.mark.asyncio
async def test_client_cancel_just_before_deadline(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=24, minutes=2))

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_client_cancel_just_after_deadline(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=23, minutes=58))

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409
    assert "не позднее чем за 24 ч" in response.json()["detail"]
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED
    assert await notifications_for(db_session, provider.id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_before_hours", [12, 24, 48, 120])
async def test_client_cancel_deadline_uses_booking_value(db_session, provider, customer, cancel_before_hours):
    anc = await create_announcement(db_session, provider, cancel_before_hours=cancel_before_hours)
    too_late = await insert_booking(db_session, anc, customer,
                                    now_msk() + timedelta(hours=cancel_before_hours - 1))
    in_time = await insert_booking(db_session, anc, customer,
                                   now_msk() + timedelta(hours=cancel_before_hours + 1))

    assert (await client_cancel(customer.http, too_late.id)).status_code == 409
    assert (await client_cancel(customer.http, in_time.id)).status_code == 200


@pytest.mark.asyncio
async def test_client_cancel_deadline_is_snapshotted(db_session, provider, customer):
    """Мастер потом поменял срок отмены в объявлении — для старой брони действует срок из момента записи."""
    anc = await create_announcement(db_session, provider, cancel_before_hours=12)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=20))
    anc.cancel_before_hours = 120
    await db_session.commit()

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_client_cancel_message_contains_deadline_time(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    start = now_msk() + timedelta(hours=10)
    booking = await insert_booking(db_session, anc, customer, start)

    response = await client_cancel(customer.http, booking.id)

    deadline = (start - timedelta(hours=24)).strftime("%d.%m.%Y %H:%M")
    assert response.status_code == 409
    assert deadline in response.json()["detail"]



@pytest.mark.asyncio
async def test_client_cancel_twice(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    assert (await client_cancel(customer.http, booking.id)).status_code == 200

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409
    assert response.json()["detail"] == ALREADY_CANCELLED
    assert len(await notifications_for(db_session, provider.id)) == 1      # повторного уведомления нет


@pytest.mark.asyncio
async def test_client_cancel_already_cancelled_by_provider(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    await provider_cancel(provider.http, booking.id)

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409
    assert response.json()["detail"] == ALREADY_CANCELLED


@pytest.mark.asyncio
async def test_client_cancel_completed(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3),
                                   status=BookingStatus.COMPLETED)

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409
    assert "уже оказана" in response.json()["detail"]
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.COMPLETED


@pytest.mark.asyncio
async def test_client_cancel_started(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, duration_minutes=60)
    booking = await insert_booking(db_session, anc, customer, now_msk() - timedelta(minutes=10))

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409
    assert "уже началась" in response.json()["detail"]
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_client_cancel_long_past(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() - timedelta(days=10))

    response = await client_cancel(customer.http, booking.id)

    assert response.status_code == 409



@pytest.mark.asyncio
@pytest.mark.parametrize("booking_id", [999999, 0, -1])
async def test_client_cancel_not_found(customer, booking_id):
    response = await client_cancel(customer.http, booking_id)

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND


@pytest.mark.asyncio
async def test_client_cannot_cancel_foreign_booking(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await client_cancel(other_customer.http, booking.id)

    assert response.status_code == 404           # существование чужой брони не раскрываем
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED
    assert await notifications_for(db_session, provider.id) == []


@pytest.mark.asyncio
async def test_provider_cannot_use_client_cancel_endpoint(db_session, provider, customer):
    """Ручка клиента ищет бронь по client_id — у мастера своей клиентской брони нет."""
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await client_cancel(provider.http, booking.id)

    assert response.status_code == 404
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_client_cancel_invalid_id(customer):
    response = await customer.http.post("/BookLet/me/my_bookings/abc/cancel")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_client_cancel_without_auth(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await client_cancel(ac, booking.id)

    assert response.status_code == 401
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_client_cancel_inactive_account(db_session, make_actor, provider):
    blocked = await make_actor("blocked", active=False)
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, blocked, now_msk() + timedelta(days=3))

    response = await client_cancel(blocked.http, booking.id)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cancel_is_not_available_via_get(db_session, provider, customer):
    """Отмена меняет состояние, поэтому GET её вызывать не должен (что именно вернётся — 404 из catch-all
    или 405 — не важно)."""
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await customer.http.get(CLIENT_CANCEL_URL.format(booking_id=booking.id))

    assert response.status_code in (404, 405)
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


# Отмена мастером

@pytest.mark.asyncio
async def test_provider_cancel_success(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider_cancel(provider.http, booking.id)

    assert response.status_code == 200
    assert response.json() == {"success": True, "msg": "Запись отменена"}
    row = await booking_row(db_session, booking.id)
    assert row.status == BookingStatus.CANCELLED
    assert row.cancelled_by_id == provider.id
    assert row.cancelled_at is not None


@pytest.mark.asyncio
async def test_provider_cancel_notifies_client(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Массаж")
    start = now_msk() + timedelta(days=3)
    booking = await insert_booking(db_session, anc, customer, start)

    await provider_cancel(provider.http, booking.id)

    notes = await notifications_for(db_session, customer.id)
    assert len(notes) == 1
    note = notes[0]
    assert note.type == "booking_cancelled"
    assert note.sender_id == provider.id
    assert note.booking_id == booking.id
    assert provider.username in note.text and "Массаж" in note.text
    assert start.strftime("%d.%m.%Y %H:%M") in note.text
    assert await notifications_for(db_session, provider.id) == []


@pytest.mark.asyncio
async def test_provider_can_cancel_inside_client_deadline(db_session, provider, customer):
    """Для мастера срок cancel_before_hours не действует: клиенту за 2 часа уже нельзя, мастеру можно."""
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=2))
    assert (await client_cancel(customer.http, booking.id)).status_code == 409

    response = await provider_cancel(provider.http, booking.id)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_provider_cancel_frees_slot(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    first = await book(customer.http, anc.id, at(2, 10))
    booking_id = first.json()["booking"]["id"]

    await provider_cancel(provider.http, booking_id)

    assert (await book(other_customer.http, anc.id, at(2, 10))).status_code == 200


@pytest.mark.asyncio
async def test_provider_cancel_twice(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    await provider_cancel(provider.http, booking.id)

    response = await provider_cancel(provider.http, booking.id)

    assert response.status_code == 409
    assert response.json()["detail"] == ALREADY_CANCELLED
    assert len(await notifications_for(db_session, customer.id)) == 1


@pytest.mark.asyncio
async def test_provider_cancel_completed(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=1),
                                   status=BookingStatus.COMPLETED)

    response = await provider_cancel(provider.http, booking.id)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_provider_cancel_started(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() - timedelta(minutes=5))

    response = await provider_cancel(provider.http, booking.id)

    assert response.status_code == 409
    assert "уже началась" in response.json()["detail"]


@pytest.mark.asyncio
async def test_provider_cancel_not_found(provider):
    response = await provider_cancel(provider.http, 999999)

    assert response.status_code == 404
    assert response.json()["detail"] == NOT_FOUND


@pytest.mark.asyncio
async def test_other_provider_cannot_cancel(db_session, make_actor, provider, customer):
    stranger = await make_actor("master2")
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider_cancel(stranger.http, booking.id)

    assert response.status_code == 404
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_client_cannot_use_provider_cancel_endpoint(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider_cancel(customer.http, booking.id)

    assert response.status_code == 404
    assert (await booking_row(db_session, booking.id)).status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_provider_cancel_without_auth(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider_cancel(ac, booking.id)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_provider_cancel_invalid_id(provider):
    response = await provider.http.post("/BookLet/me/my_announcements/booked/abc/cancel")

    assert response.status_code == 422


# Правила can_cancel 
NOW = now_msk()
@pytest.mark.parametrize("role, booking_status, start_delta, cancel_hours, expected", [
    # клиент: только до дедлайна
    ("client", BookingStatus.CONFIRMED, timedelta(hours=48), 24, True),
    ("client", BookingStatus.PENDING, timedelta(hours=48), 24, True),
    ("client", BookingStatus.CONFIRMED, timedelta(hours=24, seconds=1), 24, True),
    ("client", BookingStatus.CONFIRMED, timedelta(hours=24), 24, True),            # ровно дедлайн — ещё можно
    ("client", BookingStatus.CONFIRMED, timedelta(hours=23, minutes=59), 24, False),
    ("client", BookingStatus.CONFIRMED, timedelta(hours=1), 24, False),
    # мастер: в любой момент до начала
    ("provider", BookingStatus.CONFIRMED, timedelta(hours=48), 24, True),
    ("provider", BookingStatus.CONFIRMED, timedelta(minutes=1), 24, True),
    ("provider", BookingStatus.PENDING, timedelta(hours=1), 120, True),
    # после начала — никому
    ("client", BookingStatus.CONFIRMED, timedelta(minutes=-1), 12, False),
    ("provider", BookingStatus.CONFIRMED, timedelta(minutes=-1), 12, False),
    ("provider", BookingStatus.CONFIRMED, timedelta(0), 12, False),                 # начало ровно сейчас
    # неактивные статусы — никому
    ("client", BookingStatus.CANCELLED, timedelta(days=5), 24, False),
    ("provider", BookingStatus.CANCELLED, timedelta(days=5), 24, False),
    ("client", BookingStatus.COMPLETED, timedelta(days=5), 24, False),
    ("provider", BookingStatus.COMPLETED, timedelta(days=5), 24, False),
])
def test_can_cancel_rules(role, booking_status, start_delta, cancel_hours, expected):
    result = BookingService._can_cancel(role=role, booking_status=booking_status, start_at=NOW + start_delta,
                                        cancel_before_hours=cancel_hours, now=NOW)

    assert result is expected


def test_can_cancel_without_start_time():
    assert BookingService._can_cancel(role="provider", booking_status=BookingStatus.CONFIRMED, start_at=None,
                                      cancel_before_hours=24, now=NOW) is False
