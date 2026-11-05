import pytest
from datetime import time, timedelta

from models import BookingStatus

from booking_helpers import (OPERATING_MODE_URL, CALENDAR_URL, at, now_msk, parse_dt, create_announcement,
                             set_schedule, insert_booking, get_slots)

DELETE_URL = OPERATING_MODE_URL + "/{weekday}"
PUBLIC_URL = "/BookLet/user/{user_id}/operating_mode"


def rule(weekday=0, start="09:00", end="18:00"):
    return {"weekday": weekday, "start_time": start, "end_time": end}


# Режим работы
@pytest.mark.asyncio
async def test_operating_mode_initially_empty(provider):
    response = await provider.http.get(OPERATING_MODE_URL)

    assert response.status_code == 200
    assert response.json() == {"rules": []}


@pytest.mark.asyncio
async def test_set_operating_mode(provider):
    response = await provider.http.put(OPERATING_MODE_URL, json=rule(2, "10:00", "16:30"))

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["rule"]["weekday"] == 2
    assert body["rule"]["start_time"].startswith("10:00")
    assert body["rule"]["end_time"].startswith("16:30")


@pytest.mark.asyncio
async def test_operating_mode_sorted_by_weekday(provider):
    for weekday in (4, 0, 2):
        await provider.http.put(OPERATING_MODE_URL, json=rule(weekday))

    response = await provider.http.get(OPERATING_MODE_URL)

    assert [r["weekday"] for r in response.json()["rules"]] == [0, 2, 4]


@pytest.mark.asyncio
async def test_set_operating_mode_replaces_same_weekday(provider):
    await provider.http.put(OPERATING_MODE_URL, json=rule(1, "09:00", "18:00"))
    await provider.http.put(OPERATING_MODE_URL, json=rule(1, "12:00", "14:00"))
    await provider.http.put(OPERATING_MODE_URL, json=rule(3))

    rules = (await provider.http.get(OPERATING_MODE_URL)).json()["rules"]

    assert [r["weekday"] for r in rules] == [1, 3]                    # дубликатов нет, соседний день цел
    assert rules[0]["start_time"].startswith("12:00") and rules[0]["end_time"].startswith("14:00")


@pytest.mark.asyncio
async def test_operating_mode_is_per_user(provider, customer):
    await provider.http.put(OPERATING_MODE_URL, json=rule(0))

    assert (await customer.http.get(OPERATING_MODE_URL)).json() == {"rules": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    rule(weekday=7),
    rule(weekday=-1),
    rule(start="18:00", end="09:00"),            # конец раньше начала
    rule(start="10:00", end="10:00"),            # нулевое окно
    {"weekday": 1, "start_time": "09:00"},       # нет end_time
    {"weekday": 1, "end_time": "18:00"},
    {"start_time": "09:00", "end_time": "18:00"},
    rule(start="25:00"),
    rule(start="nine"),
    rule(weekday="monday"),
    {},
])
async def test_set_operating_mode_invalid(provider, payload):
    response = await provider.http.put(OPERATING_MODE_URL, json=payload)

    assert response.status_code == 422
    assert (await provider.http.get(OPERATING_MODE_URL)).json() == {"rules": []}


@pytest.mark.asyncio
async def test_delete_operating_mode(provider):
    await provider.http.put(OPERATING_MODE_URL, json=rule(1))
    await provider.http.put(OPERATING_MODE_URL, json=rule(2))

    response = await provider.http.delete(DELETE_URL.format(weekday=1))

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert [r["weekday"] for r in (await provider.http.get(OPERATING_MODE_URL)).json()["rules"]] == [2]


@pytest.mark.asyncio
async def test_delete_operating_mode_twice(provider):
    await provider.http.put(OPERATING_MODE_URL, json=rule(1))
    await provider.http.delete(DELETE_URL.format(weekday=1))

    response = await provider.http.delete(DELETE_URL.format(weekday=1))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_operating_mode_of_other_user_not_possible(provider, customer):
    await provider.http.put(OPERATING_MODE_URL, json=rule(1))

    response = await customer.http.delete(DELETE_URL.format(weekday=1))

    assert response.status_code == 404
    assert len((await provider.http.get(OPERATING_MODE_URL)).json()["rules"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("weekday", [7, -1, 100])
async def test_delete_operating_mode_invalid_weekday(provider, weekday):
    response = await provider.http.delete(DELETE_URL.format(weekday=weekday))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_operating_mode_requires_auth(ac):
    assert (await ac.get(OPERATING_MODE_URL)).status_code == 401
    assert (await ac.put(OPERATING_MODE_URL, json=rule())).status_code == 401
    assert (await ac.delete(DELETE_URL.format(weekday=1))).status_code == 401



@pytest.mark.asyncio
async def test_public_operating_mode(ac, provider):
    await provider.http.put(OPERATING_MODE_URL, json=rule(0))

    response = await ac.get(PUBLIC_URL.format(user_id=provider.id))

    assert response.status_code == 200
    assert [r["weekday"] for r in response.json()["rules"]] == [0]


@pytest.mark.asyncio
async def test_public_operating_mode_user_not_found(ac):
    response = await ac.get(PUBLIC_URL.format(user_id=999999))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_operating_mode_inactive_user(ac, make_actor):
    blocked = await make_actor("blocked", active=False)

    response = await ac.get(PUBLIC_URL.format(user_id=blocked.id))

    assert response.status_code == 404



@pytest.mark.asyncio
async def test_changing_operating_mode_changes_slots(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    weekday = at(2, 0).weekday()
    await provider.http.put(OPERATING_MODE_URL, json=rule(weekday, "09:00", "11:00"))
    day = at(2, 0).date()

    before = [s.strftime("%H:%M") for s in await get_slots(ac, anc.id, days=7) if s.date() == day]
    await provider.http.put(OPERATING_MODE_URL, json=rule(weekday, "14:00", "17:00"))
    after = [s.strftime("%H:%M") for s in await get_slots(ac, anc.id, days=7) if s.date() == day]

    assert before == ["09:00", "10:00"]
    assert after == ["14:00", "15:00", "16:00"]


@pytest.mark.asyncio
async def test_deleting_operating_mode_day_removes_its_slots(ac, db_session, provider):
    anc = await create_announcement(db_session, provider)
    weekday = at(2, 0).weekday()
    await provider.http.put(OPERATING_MODE_URL, json=rule(weekday))
    assert await get_slots(ac, anc.id, days=7)

    await provider.http.delete(DELETE_URL.format(weekday=weekday))

    assert await get_slots(ac, anc.id, days=7) == []


# Календарь
def hm(item):
    return item["kind"], item["start"], item["end"]


@pytest.mark.asyncio
async def test_calendar_without_operating_mode(provider):
    response = await provider.http.get(CALENDAR_URL, params={"days": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["has_operating_mode"] is False
    assert len(body["days"]) == 3
    assert all(d["items"] == [] and d["window_start"] is None for d in body["days"])


@pytest.mark.asyncio
async def test_calendar_free_window_without_bookings(db_session, provider):
    await set_schedule(db_session, provider, start=time(9), end=time(18))

    response = await provider.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    day = response.json()["days"][0]
    assert response.json()["has_operating_mode"] is True
    assert [hm(i) for i in day["items"]] == [("free", "09:00", "18:00")]


@pytest.mark.asyncio
async def test_calendar_splits_free_window_around_booking(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Стрижка")
    await set_schedule(db_session, provider, start=time(9), end=time(18))
    booking = await insert_booking(db_session, anc, customer, at(1, 10))

    response = await provider.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    items = response.json()["days"][0]["items"]
    assert [hm(i) for i in items] == [("free", "09:00", "10:00"), ("busy", "10:00", "11:00"),
                                      ("free", "11:00", "18:00")]
    busy = items[1]
    assert busy["booking_id"] == booking.id
    assert busy["role"] == "provider"
    assert busy["counterpart_id"] == customer.id
    assert busy["counterpart_username"] == customer.username
    assert busy["announcement_name"] == "Стрижка"
    assert busy["status"] == "confirmed"


@pytest.mark.asyncio
async def test_calendar_hides_cancelled_booking(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider, start=time(9), end=time(18))
    await insert_booking(db_session, anc, customer, at(1, 10), status=BookingStatus.CANCELLED)

    response = await provider.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    assert [hm(i) for i in response.json()["days"][0]["items"]] == [("free", "09:00", "18:00")]


@pytest.mark.asyncio
async def test_calendar_client_sees_own_booking_as_client(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10))

    response = await customer.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    items = response.json()["days"][0]["items"]
    assert [i["kind"] for i in items] == ["busy"]                 # у клиента нет режима работы — свободных окон нет
    assert items[0]["role"] == "client"
    assert items[0]["counterpart_id"] == provider.id
    assert items[0]["counterpart_username"] == provider.username


@pytest.mark.asyncio
async def test_calendar_does_not_show_foreign_bookings(db_session, make_actor, provider, customer):
    stranger = await make_actor("stranger")
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10))

    response = await stranger.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    assert response.json()["days"][0]["items"] == []


@pytest.mark.asyncio
async def test_calendar_back_to_back_bookings_leave_no_gap(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider, start=time(9), end=time(12))
    await insert_booking(db_session, anc, customer, at(1, 9))
    await insert_booking(db_session, anc, customer, at(1, 10))
    await insert_booking(db_session, anc, customer, at(1, 11))

    response = await provider.http.get(CALENDAR_URL, params={"date_from": at(1, 0).date().isoformat(), "days": 1})

    assert [i["kind"] for i in response.json()["days"][0]["items"]] == ["busy", "busy", "busy"]


@pytest.mark.asyncio
async def test_calendar_past_is_not_free(db_session, provider):
    await set_schedule(db_session, provider, start=time(0, 0), end=time(23, 59))

    response = await provider.http.get(CALENDAR_URL, params={"days": 1})

    for item in response.json()["days"][0]["items"]:
        assert item["kind"] == "free"
        assert parse_dt(item["start_at"]) >= now_msk() - timedelta(seconds=5)      # прошедшее время свободным не считаем


@pytest.mark.asyncio
async def test_calendar_default_range_is_seven_days(provider):
    response = await provider.http.get(CALENDAR_URL)

    days = response.json()["days"]
    assert len(days) == 7
    assert days[0]["date"] == now_msk().date().isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"days": 0}, {"days": 32}, {"days": "x"}, {"date_from": "not-a-date"},
                                    {"date_from": "2026-13-40"}])
async def test_calendar_invalid_params(provider, params):
    response = await provider.http.get(CALENDAR_URL, params=params)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_calendar_requires_auth(ac):
    response = await ac.get(CALENDAR_URL)

    assert response.status_code == 401
