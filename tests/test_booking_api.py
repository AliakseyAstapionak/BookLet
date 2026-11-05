import jwt
import pytest
from datetime import datetime, time, timedelta, timezone

from models import BookingStatus
from services.slots import SlotService
from settings import jwtsettings

from booking_helpers import (BOOK_URL, at, now_msk, parse_dt, create_announcement, set_schedule, insert_booking,
                             booking_row, count_bookings, notifications_for, book)


@pytest.mark.asyncio
async def test_book_success(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, price=2500, duration_minutes=90, cancel_before_hours=48)
    await set_schedule(db_session, provider)
    start = at(1, 10, 30)         

    response = await book(customer.http, anc.id, start)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    booking = body["booking"]
    assert booking["announcement_id"] == anc.id
    assert booking["provider_id"] == provider.id
    assert booking["status"] == "confirmed"
    assert booking["price"] == 2500
    assert booking["cancel_before_hours"] == 48
    assert parse_dt(booking["start_at"]) == start
    assert parse_dt(booking["end_at"]) == start + timedelta(minutes=90)
    row = await booking_row(db_session, booking["id"])
    assert row.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_book_notifies_provider_only(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Маникюр")
    await set_schedule(db_session, provider)
    start = at(1, 10)

    response = await book(customer.http, anc.id, start)
    booking_id = response.json()["booking"]["id"]

    notes = await notifications_for(db_session, provider.id)
    assert len(notes) == 1
    note = notes[0]
    assert note.type == "booking"
    assert note.title == "Новая бронь"
    assert note.sender_id == customer.id
    assert note.booking_id == booking_id
    assert note.is_read is False
    assert customer.username in note.text
    assert "Маникюр" in note.text
    assert start.strftime("%d.%m.%Y %H:%M") in note.text
    assert await notifications_for(db_session, customer.id) == []


@pytest.mark.asyncio
async def test_book_two_adjacent_slots_by_different_clients(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    first = await book(customer.http, anc.id, at(1, 10))
    second = await book(other_customer.http, anc.id, at(1, 11))   # начинается ровно в конце первой

    assert first.status_code == 200
    assert second.status_code == 200
    assert await count_bookings(db_session, provider_id=provider.id) == 2


@pytest.mark.asyncio
async def test_book_same_client_several_slots(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    for hour in (9, 12, 15):
        assert (await book(customer.http, anc.id, at(2, hour))).status_code == 200

    assert await count_bookings(db_session, client_id=customer.id) == 3


@pytest.mark.asyncio
async def test_book_price_and_cancel_hours_are_snapshotted(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, price=1000, cancel_before_hours=24)
    await set_schedule(db_session, provider)
    response = await book(customer.http, anc.id, at(1, 10))
    booking_id = response.json()["booking"]["id"]

    anc.price = 9999
    anc.cancel_before_hours = 120
    await db_session.commit()

    row = await booking_row(db_session, booking_id)
    assert row.price == 1000
    assert row.cancel_before_hours == 24


@pytest.mark.asyncio
async def test_book_at_boundary_of_horizon(db_session, provider, customer):
    """Сегодня + 30 дней — последний допустимый день (всего 31 день включая сегодня)."""
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(30, 10))

    assert response.status_code == 200



@pytest.mark.asyncio
async def test_book_naive_datetime_is_moscow_time(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    naive = at(1, 10).replace(tzinfo=None)

    response = await customer.http.post(BOOK_URL.format(anc_id=anc.id), params={"start_at": naive.isoformat()})

    assert response.status_code == 200
    assert parse_dt(response.json()["booking"]["start_at"]) == at(1, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize("tz", [timezone.utc, timezone(timedelta(hours=5)), timezone(timedelta(hours=-8))])
async def test_book_with_other_timezone_same_instant(db_session, provider, customer, tz):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    start = at(1, 10)

    response = await book(customer.http, anc.id, start.astimezone(tz))

    assert response.status_code == 200
    assert parse_dt(response.json()["booking"]["start_at"]) == start


@pytest.mark.asyncio
async def test_book_utc_time_is_not_mistaken_for_moscow(db_session, provider, customer):
    """«10:00 UTC» — это 13:00 по Москве, т.е. вне окна 09:00–12:00. Часовой пояс нельзя отбрасывать."""
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider, start=time(9), end=time(12))
    ten_utc = at(1, 13).astimezone(timezone.utc)            # 13:00 MSK == 10:00 UTC
    assert ten_utc.hour == 10

    response = await book(customer.http, anc.id, ten_utc)

    assert response.status_code == 409
    assert await count_bookings(db_session) == 0



@pytest.mark.asyncio
async def test_book_same_slot_twice_by_different_clients(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    assert (await book(customer.http, anc.id, at(1, 10))).status_code == 200

    response = await book(other_customer.http, anc.id, at(1, 10))

    assert response.status_code == 409
    assert response.json()["detail"] == "Это время недоступно для записи"
    assert await count_bookings(db_session, provider_id=provider.id) == 1
    assert len(await notifications_for(db_session, provider.id)) == 1      # уведомление только за первую


@pytest.mark.asyncio
async def test_book_same_slot_twice_by_same_client(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    await book(customer.http, anc.id, at(1, 10))

    response = await book(customer.http, anc.id, at(1, 10))

    assert response.status_code == 409
    assert await count_bookings(db_session, client_id=customer.id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("hour, minute", [
    (10, 30),     # не попадает в сетку шага 60 минут
    (10, 1),
    (8, 0),       # до начала окна приёма
    (18, 0),      # после конца окна
    (17, 30),     # сетка не совпадает, хоть и внутри окна
    (3, 0),       # ночью
])
async def test_book_time_not_in_free_slots(db_session, provider, customer, hour, minute):
    anc = await create_announcement(db_session, provider, duration_minutes=60)
    await set_schedule(db_session, provider, start=time(9), end=time(18))

    response = await book(customer.http, anc.id, at(1, hour, minute))

    assert response.status_code == 409
    assert response.json()["detail"] == "Это время недоступно для записи"
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
async def test_book_with_seconds_is_not_a_slot(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(1, 10) + timedelta(seconds=30))

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_book_day_without_operating_mode(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    off_weekday = at(1, 0).weekday()
    await set_schedule(db_session, provider, weekdays=[d for d in range(7) if d != off_weekday])

    response = await book(customer.http, anc.id, at(1, 10))

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_book_provider_without_operating_mode(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)

    response = await book(customer.http, anc.id, at(1, 10))

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_book_slot_overlapping_other_announcement_booking(db_session, provider, customer, other_customer):
    hour = await create_announcement(db_session, provider, name="Час", duration_minutes=60)
    half = await create_announcement(db_session, provider, name="Полчаса", duration_minutes=30)
    await set_schedule(db_session, provider)
    assert (await book(customer.http, half.id, at(1, 9, 30))).status_code == 200      # 09:30–10:00

    overlapping = await book(other_customer.http, hour.id, at(1, 9))                     # 09:00–10:00
    adjacent = await book(other_customer.http, hour.id, at(1, 10))                       # 10:00–11:00

    assert overlapping.status_code == 409
    assert adjacent.status_code == 200


@pytest.mark.asyncio
async def test_book_slot_race_is_caught_by_db_constraint(db_session, monkeypatch, provider, customer, other_customer):
    """Слот «ещё свободен» по версии SlotService, но кто-то успел занять его раньше:
    запись должна отклонить ограничение ex_provider_no_overlap, а клиент получить 409, а не 500."""
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    start = at(1, 10)
    await insert_booking(db_session, anc, other_customer, start)

    async def stale_slots(anc_id, days, db):
        return [start]
    monkeypatch.setattr(SlotService, "get_free_slots", stale_slots)

    response = await book(customer.http, anc.id, start)

    assert response.status_code == 409
    assert response.json()["detail"] == "Это время недоступно для записи"
    assert await count_bookings(db_session, provider_id=provider.id) == 1
    assert await notifications_for(db_session, provider.id) == []


@pytest.mark.asyncio
async def test_book_slot_freed_by_cancel_can_be_rebooked(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    first = await book(customer.http, anc.id, at(2, 10))
    booking_id = first.json()["booking"]["id"]
    cancel = await customer.http.post(f"/BookLet/me/my_bookings/{booking_id}/cancel")
    assert cancel.status_code == 200

    second = await book(other_customer.http, anc.id, at(2, 10))

    assert second.status_code == 200
    assert second.json()["booking"]["id"] != booking_id


@pytest.mark.asyncio
async def test_book_same_slot_again_after_own_cancel(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    first = await book(customer.http, anc.id, at(2, 10))
    await customer.http.post(f"/BookLet/me/my_bookings/{first.json()['booking']['id']}/cancel")

    again = await book(customer.http, anc.id, at(2, 10))

    assert again.status_code == 200



@pytest.mark.asyncio
async def test_book_yesterday(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(-1, 10))

    assert response.status_code == 400
    assert response.json()["detail"] == "Нельзя забронировать прошедшее время"


@pytest.mark.asyncio
async def test_book_earlier_today(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider, start=time(0, 0), end=time(23, 59))
    past = (now_msk() - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    response = await book(customer.http, anc.id, past)

    # если час назад был ещё вчерашний день, сервис отвечает 400, иначе слота нет — 409
    assert response.status_code == (400 if past.date() < now_msk().date() else 409)
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
async def test_book_beyond_horizon(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(31, 10))

    assert response.status_code == 400
    assert "31" in response.json()["detail"]


@pytest.mark.asyncio
async def test_book_far_future(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(365, 10))

    assert response.status_code == 400



@pytest.mark.asyncio
async def test_book_own_announcement(db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(provider.http, anc.id, at(1, 10))

    assert response.status_code == 409
    assert response.json()["detail"] == "Нельзя забронировать своё объявление"
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("anc_id", [999999, 0, -5])
async def test_book_announcement_not_found(customer, anc_id):
    response = await book(customer.http, anc_id, at(1, 10))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_book_archived_announcement(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, status="archived")
    await set_schedule(db_session, provider)

    response = await book(customer.http, anc.id, at(1, 10))

    assert response.status_code == 400
    assert await count_bookings(db_session) == 0



@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["not-a-date", "2026-13-45T10:00:00", "", "10:00", "tomorrow"])
async def test_book_invalid_start_at(db_session, provider, customer, value):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await customer.http.post(BOOK_URL.format(anc_id=anc.id), params={"start_at": value})

    assert response.status_code == 422
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
async def test_book_missing_start_at(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)

    response = await customer.http.post(BOOK_URL.format(anc_id=anc.id))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_book_start_at_in_body_is_not_accepted(db_session, provider, customer):
    """start_at — query-параметр, в теле JSON он игнорируется."""
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await customer.http.post(BOOK_URL.format(anc_id=anc.id), json={"start_at": at(1, 10).isoformat()})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_book_invalid_announcement_id(customer):
    response = await customer.http.post("/BookLet/catalog/abc/book", params={"start_at": at(1, 10).isoformat()})

    assert response.status_code == 422



@pytest.mark.asyncio
async def test_book_without_auth(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
async def test_book_with_garbage_token(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    ac.cookies.set("access_token", "definitely.not.jwt")

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_book_with_expired_token(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    expired = jwt.encode({"uid": customer.id, "username": customer.username, "type": "access",
                          "exp": datetime.now(tz=timezone.utc) - timedelta(minutes=1)},
                         jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)
    ac.cookies.set("access_token", expired)

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_book_with_token_of_wrong_type(ac, db_session, provider, customer):
    """Токен 2FA нельзя использовать как access_token."""
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    wrong = jwt.encode({"uid": customer.id, "username": customer.username, "type": "2fa",
                        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=5)},
                       jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)
    ac.cookies.set("access_token", wrong)

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_book_with_token_signed_by_other_key(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    forged = jwt.encode({"uid": customer.id, "username": customer.username, "type": "access",
                         "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=5)},
                        "some-other-secret-key-0123456789abcdef", algorithm=jwtsettings.JWT_ALGORITHM)
    ac.cookies.set("access_token", forged)

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_book_inactive_account(db_session, make_actor, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    blocked = await make_actor("blocked", active=False)

    response = await book(blocked.http, anc.id, at(1, 10))

    assert response.status_code == 401
    assert response.json()["detail"] == "Аккаунт неактивен"
    assert await count_bookings(db_session) == 0


@pytest.mark.asyncio
async def test_book_token_of_nonexistent_user(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    ghost = jwt.encode({"uid": 424242, "username": "ghost", "type": "access",
                        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=5)},
                       jwtsettings.JWT_SECRET_KEY, algorithm=jwtsettings.JWT_ALGORITHM)
    ac.cookies.set("access_token", ghost)

    response = await book(ac, anc.id, at(1, 10))

    assert response.status_code == 401
