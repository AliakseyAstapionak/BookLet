from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models import AnnouncementModel, AvailabilityRuleModel, BookingModel, BookingStatus, UserModel
from services.slots import SERVICE_TZ

# Отменённые брони в календаре не показываем: время по ним свободно
CALENDAR_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.COMPLETED)


def _hm(dt: datetime) -> str:
    return dt.astimezone(SERVICE_TZ).strftime('%H:%M')


class CalendarService:

    @staticmethod
    async def get_calendar(user_id: int, date_from: date | None, days: int, db: AsyncSession) -> dict:
        now = datetime.now(SERVICE_TZ)
        first = date_from or now.date()
        range_start = datetime.combine(first, time.min, tzinfo=SERVICE_TZ)
        range_end = datetime.combine(first + timedelta(days=days), time.min, tzinfo=SERVICE_TZ)

        rules = (await db.execute(
            select(AvailabilityRuleModel).where(AvailabilityRuleModel.user_id == user_id)
        )).scalars().all()
        windows = {r.weekday: (r.start_time, r.end_time) for r in rules}

        Client, Provider = aliased(UserModel), aliased(UserModel)
        rows = (await db.execute(
            select(BookingModel.id, BookingModel.start_at, BookingModel.end_at, BookingModel.status,
                   BookingModel.client_id, BookingModel.provider_id,
                   AnnouncementModel.name.label('announcement_name'),
                   Client.username.label('client_username'), Provider.username.label('provider_username'))
            .join(AnnouncementModel, AnnouncementModel.id == BookingModel.announcement_id)
            .join(Client, Client.id == BookingModel.client_id)
            .join(Provider, Provider.id == BookingModel.provider_id)
            .where(or_(BookingModel.provider_id == user_id, BookingModel.client_id == user_id),
                   BookingModel.status.in_(CALENDAR_STATUSES),
                   BookingModel.end_at > range_start, BookingModel.start_at < range_end)
            .order_by(BookingModel.start_at)
        )).mappings().all()

        by_day: dict[date, list] = {}
        for r in rows:
            by_day.setdefault(r['start_at'].astimezone(SERVICE_TZ).date(), []).append(r)

        result = []
        for offset in range(days):
            day = first + timedelta(days=offset)
            window = windows.get(day.weekday())
            day_rows = by_day.get(day, [])
            items = []

            for r in day_rows:
                as_provider = r['provider_id'] == user_id
                items.append({
                    'kind': 'busy',
                    'start_at': r['start_at'].astimezone(SERVICE_TZ), 'end_at': r['end_at'].astimezone(SERVICE_TZ),
                    'start': _hm(r['start_at']), 'end': _hm(r['end_at']),
                    'booking_id': r['id'], 'announcement_name': r['announcement_name'],
                    'role': 'provider' if as_provider else 'client',
                    'counterpart_id': r['client_id'] if as_provider else r['provider_id'],
                    'counterpart_username': r['client_username'] if as_provider else r['provider_username'],
                    'status': r['status'].value,
                })

            if window:
                w_start = datetime.combine(day, window[0], tzinfo=SERVICE_TZ)
                w_end = datetime.combine(day, window[1], tzinfo=SERVICE_TZ)
                # Свободные окна считаем только по записям ко мне, как и SlotService:
                # так календарь совпадает с тем, что реально видят клиенты.
                busy = [(r['start_at'], r['end_at']) for r in rows if r['provider_id'] == user_id]
                cursor = max(w_start, now)      # прошлое свободным не считаем
                for b_start, b_end in busy:
                    if b_end <= cursor:
                        continue
                    if b_start >= w_end:
                        break
                    if b_start > cursor:
                        items.append(CalendarService._free(cursor, b_start))
                    cursor = max(cursor, b_end)
                if cursor < w_end:
                    items.append(CalendarService._free(cursor, w_end))

            items.sort(key=lambda i: i['start_at'])
            result.append({
                'date': day, 'weekday': day.weekday(),
                'window_start': window[0] if window else None,
                'window_end': window[1] if window else None,
                'items': items,
            })
        return {'has_operating_mode': bool(windows), 'days': result}

    @staticmethod
    def _free(start: datetime, end: datetime) -> dict:
        return {'kind': 'free', 'start_at': start, 'end_at': end, 'start': _hm(start), 'end': _hm(end)}
