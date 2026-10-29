from datetime import date, datetime, time
from typing import Literal, Optional

from pydantic import BaseModel


class CalendarItemSchema(BaseModel):
    kind: Literal['busy', 'free']
    start_at: datetime
    end_at: datetime
    start: str                    
    end: str
    booking_id: Optional[int] = None
    announcement_name: Optional[str] = None
    role: Optional[Literal['provider', 'client']] = None   
    counterpart_id: Optional[int] = None
    counterpart_username: Optional[str] = None
    status: Optional[str] = None


class CalendarDaySchema(BaseModel):
    date: date
    weekday: int                    
    window_start: Optional[time] = None
    window_end: Optional[time] = None
    items: list[CalendarItemSchema]


class CalendarResponseSchema(BaseModel):
    has_operating_mode: bool
    days: list[CalendarDaySchema]
