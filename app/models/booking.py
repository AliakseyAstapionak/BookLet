"""models/booking.py - простая версия"""
import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from core import Base


class BookingStatus(str, enum.Enum):
    PENDING = 'pending'          # ждёт подтверждения провайдера
    CONFIRMED = 'confirmed'      # подтверждена
    CANCELLED = 'cancelled'      # отменена
    COMPLETED = 'completed'      # услуга оказана


class BookingModel(Base):
    __tablename__ = 'bookings'

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey('announcements.id'), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[BookingStatus] = mapped_column(default=BookingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint('end_at > start_at', name='ck_booking_time_order'),)