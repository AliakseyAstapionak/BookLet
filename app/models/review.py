from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core import Base


class ReviewModel(Base):
    __tablename__ = 'reviews'

    id: Mapped[int] = mapped_column(primary_key=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey('announcements.id'), index=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey('bookings.id'))
    author_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    rating: Mapped[int]
    text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('booking_id', name='uq_review_booking'),
        CheckConstraint('rating BETWEEN 1 AND 5', name='ck_review_rating_range'),
    )
