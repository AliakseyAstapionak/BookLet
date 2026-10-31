from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MyBookingOut(BaseModel):
    id: int
    announcement_id: int
    announcement_name: str
    price: int = Field(ge=0, le=100_000_000)
    provider_id: int
    provider_username: str
    client_id: int
    client_username: str
    status: str
    start_at: Optional[datetime] = None   
    end_at: Optional[datetime] = None
    cancel_before_hours: int = Field(ge=12, le=120)
    can_cancel: bool = False   
    created_at: datetime


class MyBookingsResponseSchema(BaseModel):
    bookings: list[MyBookingOut]
    total: int

class BookingsResponseSchema(MyBookingsResponseSchema):
    pass