import pytest
import pytest_asyncio
from datetime import timedelta

from models import BookingStatus

from booking_helpers import (MY_BOOKINGS_URL, PROVIDER_BOOKED_URL, at, now_msk, parse_dt, create_announcement,
                             set_schedule, insert_booking, book)


@pytest.mark.asyncio
async def test_my_bookings_empty(customer):
    response = await customer.http.get(MY_BOOKINGS_URL)

    assert response.status_code == 200
    assert response.json() == {"bookings": [], "total": 0}


@pytest.mark.asyncio
async def test_my_bookings_item_fields(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Стрижка", price=1500, cancel_before_hours=24)
    start = now_msk() + timedelta(days=3)
    booking = await insert_booking(db_session, anc, customer, start)

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["bookings"][0]
    assert item["id"] == booking.id
    assert item["announcement_id"] == anc.id
    assert item["announcement_name"] == "Стрижка"
    assert item["price"] == 1500
    assert item["provider_id"] == provider.id
    assert item["provider_username"] == provider.username
    assert item["client_id"] == customer.id
    assert item["client_username"] == customer.username
    assert item["status"] == "confirmed"
    assert parse_dt(item["start_at"]) == start
    assert parse_dt(item["end_at"]) == start + timedelta(minutes=60)
    assert item["cancel_before_hours"] == 24
    assert item["can_cancel"] is True
    assert item["created_at"]


@pytest.mark.asyncio
async def test_my_bookings_only_own(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    mine = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    await insert_booking(db_session, anc, other_customer, now_msk() + timedelta(days=4))

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert [b["id"] for b in response.json()["bookings"]] == [mine.id]
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_my_bookings_as_client_does_not_include_provider_side(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider.http.get(MY_BOOKINGS_URL)      # мастер не бронировал ничего сам

    assert response.json() == {"bookings": [], "total": 0}


@pytest.mark.asyncio
async def test_my_bookings_newest_first(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    ids = []
    for hour in (12, 9, 15):                      # порядок создания, а не порядок времени услуги
        response = await book(customer.http, anc.id, at(2, hour))
        ids.append(response.json()["booking"]["id"])

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert [b["id"] for b in response.json()["bookings"]] == ids[::-1]


@pytest.mark.asyncio
async def test_my_bookings_after_booking_via_api(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await set_schedule(db_session, provider)
    created = await book(customer.http, anc.id, at(1, 10))

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert response.json()["bookings"][0]["id"] == created.json()["booking"]["id"]


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="get_my_bookings берёт price из объявления, а не из брони: "
                                       "после смены цены у старых броней показывается новая цена")
async def test_my_bookings_price_is_snapshot_of_booking(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, price=1000)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    anc.price = 5000
    await db_session.commit()

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert response.json()["bookings"][0]["price"] == 5000



@pytest.mark.asyncio
@pytest.mark.parametrize("status, start_delta, expected", [
    (BookingStatus.CONFIRMED, timedelta(days=3), True),
    (BookingStatus.PENDING, timedelta(days=3), True),
    (BookingStatus.CONFIRMED, timedelta(hours=5), False),        # дедлайн (24 ч) уже прошёл
    (BookingStatus.CONFIRMED, timedelta(hours=-3), False),       # услуга уже началась
    (BookingStatus.CANCELLED, timedelta(days=3), False),
    (BookingStatus.COMPLETED, timedelta(days=-3), False),
])
async def test_my_bookings_can_cancel_flag(db_session, provider, customer, status, start_delta, expected):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    await insert_booking(db_session, anc, customer, now_msk() + start_delta, status=status)

    response = await customer.http.get(MY_BOOKINGS_URL)

    assert response.json()["bookings"][0]["can_cancel"] is expected


@pytest.mark.asyncio
async def test_my_bookings_can_cancel_matches_cancel_endpoint(db_session, provider, customer):
    """Флаг в списке не должен расходиться с реальным поведением ручки отмены."""
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    early = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    late = await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=5))

    flags = {b["id"]: b["can_cancel"] for b in (await customer.http.get(MY_BOOKINGS_URL)).json()["bookings"]}

    assert flags == {early.id: True, late.id: False}
    assert (await customer.http.post(f"/BookLet/me/my_bookings/{early.id}/cancel")).status_code == 200
    assert (await customer.http.post(f"/BookLet/me/my_bookings/{late.id}/cancel")).status_code == 409



@pytest.mark.asyncio
async def test_my_bookings_status_filter(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    base = now_msk() + timedelta(days=3)
    confirmed = await insert_booking(db_session, anc, customer, base)
    cancelled = await insert_booking(db_session, anc, customer, base + timedelta(hours=2),
                                     status=BookingStatus.CANCELLED)
    completed = await insert_booking(db_session, anc, customer, base + timedelta(hours=4),
                                     status=BookingStatus.COMPLETED)

    for status, expected in [("confirmed", confirmed), ("cancelled", cancelled), ("completed", completed)]:
        response = await customer.http.get(MY_BOOKINGS_URL, params={"status": status})
        body = response.json()
        assert [b["id"] for b in body["bookings"]] == [expected.id]
        assert body["total"] == 1

    assert (await customer.http.get(MY_BOOKINGS_URL)).json()["total"] == 3


@pytest.mark.asyncio
async def test_my_bookings_status_filter_no_matches(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await customer.http.get(MY_BOOKINGS_URL, params={"status": "pending"})

    assert response.json() == {"bookings": [], "total": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["bogus", "CONFIRMED", "", "1"])
async def test_my_bookings_invalid_status(customer, status):
    response = await customer.http.get(MY_BOOKINGS_URL, params={"status": status})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_bookings_cancelled_after_cancel_endpoint(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    await customer.http.post(f"/BookLet/me/my_bookings/{booking.id}/cancel")

    response = await customer.http.get(MY_BOOKINGS_URL, params={"status": "cancelled"})

    item = response.json()["bookings"][0]
    assert item["id"] == booking.id
    assert item["status"] == "cancelled"
    assert item["can_cancel"] is False



@pytest_asyncio.fixture
async def five_bookings(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    base = now_msk() + timedelta(days=3)
    return [await insert_booking(db_session, anc, customer, base + timedelta(hours=2 * i)) for i in range(5)]


@pytest.mark.asyncio
async def test_my_bookings_pagination(customer, five_bookings):
    ids_newest_first = [b.id for b in reversed(five_bookings)]

    first = (await customer.http.get(MY_BOOKINGS_URL, params={"limit": 2, "offset": 0})).json()
    second = (await customer.http.get(MY_BOOKINGS_URL, params={"limit": 2, "offset": 2})).json()
    last = (await customer.http.get(MY_BOOKINGS_URL, params={"limit": 2, "offset": 4})).json()

    assert [b["id"] for b in first["bookings"]] == ids_newest_first[0:2]
    assert [b["id"] for b in second["bookings"]] == ids_newest_first[2:4]
    assert [b["id"] for b in last["bookings"]] == ids_newest_first[4:5]
    assert first["total"] == second["total"] == last["total"] == 5     # total — всего, а не на странице


@pytest.mark.asyncio
async def test_my_bookings_offset_beyond_total(customer, five_bookings):
    response = await customer.http.get(MY_BOOKINGS_URL, params={"offset": 100})

    assert response.json() == {"bookings": [], "total": 5}


@pytest.mark.asyncio
async def test_my_bookings_max_limit(customer, five_bookings):
    response = await customer.http.get(MY_BOOKINGS_URL, params={"limit": 150})

    assert response.status_code == 200
    assert len(response.json()["bookings"]) == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": -1}, {"limit": 151}, {"offset": -1}, {"limit": "x"}])
async def test_my_bookings_invalid_pagination(customer, params):
    response = await customer.http.get(MY_BOOKINGS_URL, params=params)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_bookings_pagination_with_status_filter(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    base = now_msk() + timedelta(days=3)
    for i in range(3):
        await insert_booking(db_session, anc, customer, base + timedelta(hours=2 * i))
    await insert_booking(db_session, anc, customer, base + timedelta(hours=10), status=BookingStatus.CANCELLED)

    response = await customer.http.get(MY_BOOKINGS_URL, params={"status": "confirmed", "limit": 2})

    body = response.json()
    assert len(body["bookings"]) == 2
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_my_bookings_without_auth(ac):
    response = await ac.get(MY_BOOKINGS_URL)

    assert response.status_code == 401



@pytest.mark.asyncio
async def test_provider_sees_bookings_of_his_announcements(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, name="Стрижка")
    booking = await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await provider.http.get(PROVIDER_BOOKED_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["bookings"][0]
    assert item["id"] == booking.id
    assert item["client_username"] == customer.username
    assert item["provider_username"] == provider.username
    assert item["announcement_name"] == "Стрижка"


@pytest.mark.asyncio
async def test_client_does_not_see_provider_list(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await customer.http.get(PROVIDER_BOOKED_URL)

    assert response.json() == {"bookings": [], "total": 0}


@pytest.mark.asyncio
async def test_other_provider_does_not_see_foreign_bookings(db_session, make_actor, provider, customer):
    stranger = await make_actor("master2")
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))

    response = await stranger.http.get(PROVIDER_BOOKED_URL)

    assert response.json() == {"bookings": [], "total": 0}


@pytest.mark.asyncio
async def test_provider_can_cancel_flag_ignores_client_deadline(db_session, provider, customer):
    anc = await create_announcement(db_session, provider, cancel_before_hours=24)
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(hours=2))
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=3))
    await insert_booking(db_session, anc, customer, now_msk() + timedelta(days=5), status=BookingStatus.CANCELLED)

    items = (await provider.http.get(PROVIDER_BOOKED_URL)).json()["bookings"]

    assert sorted(b["can_cancel"] for b in items) == [False, True, True]
    # а клиенту в тот же момент часть из этого недоступна
    client_items = (await customer.http.get(MY_BOOKINGS_URL)).json()["bookings"]
    assert sum(b["can_cancel"] for b in client_items) == 1


@pytest.mark.asyncio
async def test_provider_list_status_filter_and_pagination(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    base = now_msk() + timedelta(days=3)
    for i in range(3):
        await insert_booking(db_session, anc, customer, base + timedelta(hours=2 * i))
    await insert_booking(db_session, anc, customer, base + timedelta(hours=10), status=BookingStatus.CANCELLED)

    cancelled = (await provider.http.get(PROVIDER_BOOKED_URL, params={"status": "cancelled"})).json()
    paged = (await provider.http.get(PROVIDER_BOOKED_URL, params={"limit": 2, "offset": 1})).json()

    assert cancelled["total"] == 1
    assert len(paged["bookings"]) == 2 and paged["total"] == 4
    assert (await provider.http.get(PROVIDER_BOOKED_URL, params={"status": "bogus"})).status_code == 422
    assert (await provider.http.get(PROVIDER_BOOKED_URL, params={"limit": 0})).status_code == 422


@pytest.mark.asyncio
async def test_provider_list_without_auth(ac):
    response = await ac.get(PROVIDER_BOOKED_URL)

    assert response.status_code == 401
test_my_bookings_price_is_snapshot_of_booking