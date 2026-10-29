from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AvailabilityRuleModel, BookingModel, BookingStatus
from services.announcements import AnnouncementService

# TODO: вынести в settings (а позже хранить пояс у каждого мастера).
SERVICE_TZ = ZoneInfo('Europe/Moscow')
ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED)


class SlotService:

    @staticmethod
    async def get_free_slots(anc_id: int, db: AsyncSession, days: int = 7,
                             ) -> list[datetime]:
        announcement = await AnnouncementService.get_announcement(id=anc_id, db=db)
        provider_id = announcement.user_id
        step = timedelta(minutes=announcement.duration_minutes)

        now = (datetime.now(SERVICE_TZ)).astimezone(SERVICE_TZ)
        today = now.date()
        range_end = datetime.combine(today + timedelta(days=days), time.min, tzinfo=SERVICE_TZ)

        rules = (await db.execute(
            select(AvailabilityRuleModel).where(AvailabilityRuleModel.user_id == provider_id)
        )).scalars().all()
        windows = {r.weekday: (r.start_time, r.end_time) for r in rules}
        if not windows:
            return []

        busy = (await db.execute(
            select(BookingModel.start_at, BookingModel.end_at).where(
                BookingModel.provider_id == provider_id,
                BookingModel.status.in_(ACTIVE_STATUSES),
                BookingModel.end_at > now,
                BookingModel.start_at < range_end,
            ).order_by(BookingModel.start_at)
        )).all()

        slots: list[datetime] = []
        for offset in range(days):
            day: date = today + timedelta(days=offset)
            window = windows.get(day.weekday())        
            if not window:
                continue
            cursor = datetime.combine(day, window[0], tzinfo=SERVICE_TZ)
            window_end = datetime.combine(day, window[1], tzinfo=SERVICE_TZ)
            while cursor + step <= window_end:
                slot_end = cursor + step
                if cursor > now and not any(b_start < slot_end and b_end > cursor for b_start, b_end in busy):
                    slots.append(cursor)
                cursor = slot_end
        return slots