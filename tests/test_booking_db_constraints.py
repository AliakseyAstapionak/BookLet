"""Защита целостности на уровне БД: именно она спасает от гонок, когда два клиента
одновременно успели пройти проверку слотов в сервисе."""
import pytest
from datetime import timedelta
from sqlalchemy.exc import IntegrityError

from models import BookingModel, BookingStatus

from booking_helpers import at, create_announcement, insert_booking


async def expect_integrity_error(db, coro, constraint: str):
    with pytest.raises(IntegrityError) as exc:
        await coro
    await db.rollback()
    assert constraint in str(exc.value.orig)


@pytest.mark.asyncio
async def test_overlapping_bookings_of_same_provider_rejected(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10))                       # 10:00–11:00

    await expect_integrity_error(db_session, insert_booking(db_session, anc, other_customer, at(1, 10, 30)),
                                 "ex_provider_no_overlap")


@pytest.mark.asyncio
async def test_identical_time_rejected(db_session, provider, customer, other_customer):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10))

    await expect_integrity_error(db_session, insert_booking(db_session, anc, other_customer, at(1, 10)),
                                 "ex_provider_no_overlap")


@pytest.mark.asyncio
async def test_booking_inside_longer_booking_rejected(db_session, provider, customer, other_customer):
    long = await create_announcement(db_session, provider, name="Долго", duration_minutes=240)
    short = await create_announcement(db_session, provider, name="Коротко", duration_minutes=30)
    await insert_booking(db_session, long, customer, at(1, 10))                      # 10:00–14:00

    await expect_integrity_error(db_session, insert_booking(db_session, short, other_customer, at(1, 12)),
                                 "ex_provider_no_overlap")


@pytest.mark.asyncio
async def test_adjacent_bookings_allowed(db_session, provider, customer):
    """Интервал полуоткрытый [start, end): конец одной брони = начало следующей — не пересечение."""
    anc = await create_announcement(db_session, provider)

    await insert_booking(db_session, anc, customer, at(1, 10))
    await insert_booking(db_session, anc, customer, at(1, 11))
    await insert_booking(db_session, anc, customer, at(1, 9))


@pytest.mark.asyncio
async def test_overlap_of_different_providers_allowed(db_session, make_actor, provider, customer):
    other_provider = await make_actor("master2")
    anc = await create_announcement(db_session, provider)
    other_anc = await create_announcement(db_session, other_provider)

    await insert_booking(db_session, anc, customer, at(1, 10))
    await insert_booking(db_session, other_anc, customer, at(1, 10))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [BookingStatus.CANCELLED, BookingStatus.COMPLETED])
async def test_overlap_with_inactive_booking_allowed(db_session, provider, customer, other_customer, status):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10), status=status)

    await insert_booking(db_session, anc, other_customer, at(1, 10))


@pytest.mark.asyncio
@pytest.mark.parametrize("first, second", [
    (BookingStatus.PENDING, BookingStatus.CONFIRMED),
    (BookingStatus.CONFIRMED, BookingStatus.PENDING),
    (BookingStatus.PENDING, BookingStatus.PENDING),
])
async def test_pending_and_confirmed_both_block(db_session, provider, customer, other_customer, first, second):
    anc = await create_announcement(db_session, provider)
    await insert_booking(db_session, anc, customer, at(1, 10), status=first)

    await expect_integrity_error(db_session, insert_booking(db_session, anc, other_customer, at(1, 10), status=second),
                                 "ex_provider_no_overlap")


@pytest.mark.asyncio
async def test_cannot_restore_cancelled_booking_over_new_one(db_session, provider, customer, other_customer):
    """Если слот после отмены уже занят другим, вернуть отменённую бронь в «confirmed» нельзя."""
    anc = await create_announcement(db_session, provider)
    cancelled = await insert_booking(db_session, anc, customer, at(1, 10), status=BookingStatus.CANCELLED)
    await insert_booking(db_session, anc, other_customer, at(1, 10))

    cancelled.status = BookingStatus.CONFIRMED

    await expect_integrity_error(db_session, db_session.commit(), "ex_provider_no_overlap")


@pytest.mark.asyncio
@pytest.mark.parametrize("minutes", [0, -30])
async def test_end_must_be_after_start(db_session, provider, customer, minutes):
    anc = await create_announcement(db_session, provider)
    start = at(1, 10)
    db_session.add(BookingModel(announcement_id=anc.id, client_id=customer.id, provider_id=provider.id,
                                start_at=start, end_at=start + timedelta(minutes=minutes),
                                status=BookingStatus.CONFIRMED, price=100, cancel_before_hours=24))

    await expect_integrity_error(db_session, db_session.commit(), "ck_booking_time_order")


@pytest.mark.asyncio
async def test_booking_requires_existing_announcement(db_session, provider, customer):
    start = at(1, 10)
    db_session.add(BookingModel(announcement_id=424242, client_id=customer.id, provider_id=provider.id,
                                start_at=start, end_at=start + timedelta(hours=1),
                                status=BookingStatus.CONFIRMED, price=100, cancel_before_hours=24))

    await expect_integrity_error(db_session, db_session.commit(), "foreign key")


@pytest.mark.asyncio
async def test_booking_requires_existing_client(db_session, provider):
    anc = await create_announcement(db_session, provider)
    start = at(1, 10)
    db_session.add(BookingModel(announcement_id=anc.id, client_id=424242, provider_id=provider.id,
                                start_at=start, end_at=start + timedelta(hours=1),
                                status=BookingStatus.CONFIRMED, price=100, cancel_before_hours=24))

    await expect_integrity_error(db_session, db_session.commit(), "foreign key")


@pytest.mark.asyncio
async def test_default_status_is_confirmed(db_session, provider, customer):
    anc = await create_announcement(db_session, provider)
    start = at(1, 10)
    booking = BookingModel(announcement_id=anc.id, client_id=customer.id, provider_id=provider.id,
                           start_at=start, end_at=start + timedelta(hours=1), price=100, cancel_before_hours=24)
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)

    assert booking.status == BookingStatus.CONFIRMED
    assert booking.cancelled_by_id is None and booking.cancelled_at is None
    assert booking.created_at is not None
