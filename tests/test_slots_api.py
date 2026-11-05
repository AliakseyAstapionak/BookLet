import pytest
from datetime import time, timedelta
from models import BookingStatus

from booking_helpers import (SLOTS_URL, at, now_msk, create_announcement, set_schedule, insert_booking,
                             get_slots, book)


@pytest.mark.asyncio
async def test_slots_without_operating_mode_empty(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)

    assert await get_slots(ac, anc.id) == []


@pytest.mark.asyncio
async def test_slots_are_public_and_sorted(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    slots = await get_slots(ac, anc.id, days=3)   # без авторизации

    assert slots
    assert slots == sorted(slots)
    assert len(slots) == len(set(slots))


@pytest.mark.asyncio
async def test_slots_follow_window_and_duration(ac, db_session, provider):
    anc = await create_announcement(db_session, provider, duration_minutes=60)
    await set_schedule(db_session, provider, start=time(9), end=time(12))

    slots = await get_slots(ac, anc.id, days=7)
    tomorrow = [s for s in slots if s.date() == at(1, 0).date()]

    assert [s.strftime("%H:%M") for s in tomorrow] == ["09:00", "10:00", "11:00"]


@pytest.mark.asyncio
@pytest.mark.parametrize("duration, window_end, expected", [
    (90, time(12), ["09:00", "10:30"]),                       # последний слот ровно упирается в конец окна
    (45, time(12), ["09:00", "09:45", "10:30", "11:15"]),
    (120, time(12), ["09:00"]),                               # остаток 60 минут уже не влезает
    (30, time(10), ["09:00", "09:30"]),
])
async def test_slot_step_equals_duration(ac, db_session, provider, duration, window_end, expected):
    anc = await create_announcement(db_session, provider, duration_minutes=duration)
    await set_schedule(db_session, provider, start=time(9), end=window_end)

    slots = await get_slots(ac, anc.id, days=7)
    tomorrow = [s.strftime("%H:%M") for s in slots if s.date() == at(1, 0).date()]

    assert tomorrow == expected


@pytest.mark.asyncio
async def test_slots_window_shorter_than_duration(ac, db_session, provider):
    anc = await create_announcement(db_session, provider, duration_minutes=120)
    await set_schedule(db_session, provider, start=time(9), end=time(10))

    assert await get_slots(ac, anc.id, days=7) == []


@pytest.mark.asyncio
async def test_slots_only_on_days_with_rule(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    working_weekday = at(2, 0).weekday()
    await set_schedule(db_session, provider, weekdays=[working_weekday])

    slots = await get_slots(ac, anc.id, days=14)

    assert slots
    assert {s.weekday() for s in slots} == {working_weekday}


@pytest.mark.asyncio
async def test_slots_never_in_the_past(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider, start=time(0, 0), end=time(23, 59))

    slots = await get_slots(ac, anc.id, days=1)

    assert all(s > now_msk() for s in slots)
    assert all(s.date() == now_msk().date() for s in slots)


@pytest.mark.asyncio
async def test_slots_default_is_seven_days(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    slots = await get_slots(ac, anc.id)

    assert max(s.date() for s in slots) <= now_msk().date() + timedelta(days=6)
    assert any(s.date() == at(6, 0).date() for s in slots)


@pytest.mark.asyncio
async def test_slots_max_days_boundary(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)

    slots = await get_slots(ac, anc.id, days=31)
    dates = {s.date() for s in slots}

    assert at(30, 0).date() in dates
    assert at(31, 0).date() not in dates


@pytest.mark.asyncio
async def test_booked_slot_disappears(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    assert at(1, 10) in await get_slots(ac, anc.id)

    response = await book(customer.http, anc.id, at(1, 10))
    assert response.status_code == 200

    slots = await get_slots(ac, anc.id)
    assert at(1, 10) not in slots
    assert at(1, 9) in slots and at(1, 11) in slots


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [BookingStatus.PENDING, BookingStatus.CONFIRMED])
async def test_active_booking_blocks_slot(ac, db_session, provider, customer, status):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10), status=status)

    assert at(1, 10) not in await get_slots(ac, anc.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [BookingStatus.CANCELLED, BookingStatus.COMPLETED])
async def test_inactive_booking_does_not_block_slot(ac, db_session, provider, customer, status):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10), status=status)

    assert at(1, 10) in await get_slots(ac, anc.id)


@pytest.mark.asyncio
async def test_slot_is_free_again_after_cancel(ac, db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, at(3, 10))
    assert at(3, 10) not in await get_slots(ac, anc.id, days=7)

    response = await customer.http.post(f"/BookLet/me/my_bookings/{booking.id}/cancel")
    assert response.status_code == 200

    assert at(3, 10) in await get_slots(ac, anc.id, days=7)


@pytest.mark.asyncio
async def test_booking_of_other_announcement_blocks_slot_for_same_provider(ac, db_session, provider, customer):
    """Календарь у мастера один на все его объявления."""
    haircut = await create_announcement(db_session, provider, name="Стрижка")
    coloring = await create_announcement(db_session, provider, name="Окрашивание")
    await set_schedule(db_session, provider)
    await insert_booking(db_session, haircut, customer, at(1, 10))

    assert at(1, 10) not in await get_slots(ac, coloring.id)


@pytest.mark.asyncio
async def test_booking_of_other_provider_does_not_block_slot(ac, db_session, make_actor, provider, customer):
    other_provider = await make_actor("master2")
    anc = await create_announcement(db_session, provider)
    other_anc = await create_announcement(db_session, other_provider)
    await set_schedule(db_session, provider)
    await set_schedule(db_session, other_provider)
    await insert_booking(db_session, other_anc, customer, at(1, 10))

    assert at(1, 10) in await get_slots(ac, anc.id)


@pytest.mark.asyncio
async def test_partial_overlap_with_different_duration(ac, db_session, provider, customer):
    """Бронь на 30 минут блокирует только пересекающиеся часовые слоты."""
    hour = await create_announcement(db_session, provider, name="Час", duration_minutes=60)
    half = await create_announcement(db_session, provider, name="Полчаса", duration_minutes=30)
    await set_schedule(db_session, provider)
    await insert_booking(db_session, half, customer, at(1, 9, 30))      # 09:30–10:00

    slots = await get_slots(ac, hour.id)

    assert at(1, 9) not in slots        # пересекается
    assert at(1, 10) in slots           # впритык, свободно
    assert at(1, 8) not in slots        # вне окна приёма


@pytest.mark.asyncio
async def test_long_booking_blocks_several_slots(ac, db_session, provider, customer):
    half = await create_announcement(db_session, provider, name="Полчаса", duration_minutes=30)
    long = await create_announcement(db_session, provider, name="Долго", duration_minutes=120)
    await set_schedule(db_session, provider)
    await insert_booking(db_session, long, customer, at(1, 10))         # 10:00–12:00

    slots = await get_slots(ac, half.id)

    blocked = {at(1, 10), at(1, 10, 30), at(1, 11), at(1, 11, 30)}
    assert blocked.isdisjoint(slots)
    assert at(1, 9, 30) in slots and at(1, 12) in slots


@pytest.mark.asyncio
async def test_slots_announcement_not_found(ac):
    response = await ac.get(SLOTS_URL.format(anc_id=999999))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_slots_archived_announcement(ac, db_session, provider):
    anc = await create_announcement(db_session, provider, status="archived")
    await set_schedule(db_session, provider)

    response = await ac.get(SLOTS_URL.format(anc_id=anc.id))

    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [0, -1, 32, 100, "abc"])
async def test_slots_invalid_days(ac, db_session, provider, days):
    anc = await create_announcement(db_session, provider)

    response = await ac.get(SLOTS_URL.format(anc_id=anc.id), params={"days": days})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_slots_invalid_announcement_id(ac):
    response = await ac.get("/BookLet/catalog/abc/slots")

    assert response.status_code == 422
