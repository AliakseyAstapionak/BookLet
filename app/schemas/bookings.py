from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MyBookingOut(BaseModel):
    id: int
    announcement_id: int
    announcement_name: str
    price: int
    provider_id: int
    provider_username: str
    status: str
    start_at: Optional[datetime] = None   # пока времени нет, будет None
    end_at: Optional[datetime] = None
    created_at: datetime


class MyBookingsResponseSchema(BaseModel):
    bookings: list[MyBookingOut]
    total: int

class BookingsResponseSchema(MyBookingsResponseSchema):
    pass