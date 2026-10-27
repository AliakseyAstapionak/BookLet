from core.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, func, Text, ForeignKey
from typing import Optional, List
from datetime import datetime
import enum
from models.tables import user_liked_announcements

#TODO подумать над тем чтобы был какой то словарь из всех озможный типов и пользователь уже выбирал
class StatusEnum(str, enum.Enum):
    ACTIVE = 'active'
    ARCHIVED = 'archived'
    BOOKED = 'booked'

#TODO подумать над временем и бронированием 
class AnnouncementModel(Base):
    __tablename__ = 'announcements'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id:  Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    description:  Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StatusEnum] = mapped_column(nullable=False, default='active')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),nullable=False)

    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default='60')
    cancel_before_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24, server_default='24')

    user: Mapped["UserModel"] = relationship(back_populates="announcements")
    liked_by_users: Mapped[List["UserModel"]] = relationship(
        secondary=user_liked_announcements,
        back_populates="liked_announcements"
    )
