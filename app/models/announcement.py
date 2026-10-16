from core.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, func, Text, ForeignKey
from typing import Optional
from datetime import datetime
import enum

#TODO подумать над тем чтобы был какой то словарь из всех озможный типов и пользователь уже выбирал
class StatusEnum(str, enum.Enum):
    ACTIVE = 'active'
    ARCHIVED = 'archived'
    BOOKED = 'booked'

class AnnouncementModel(Base):
    __tablename__ = 'announcements'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id:  Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    description:  Mapped[Optional[str]] = mapped_column(Text)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StatusEnum] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),nullable=False)

    user: Mapped["UserModel"] = relationship(back_populates="announcements")
