from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum, DateTime, Boolean, func, ForeignKey
from typing import Optional
from datetime import datetime
from core.database import Base
from typing import List
from models.tables import user_liked_announcements
#TODO добавить какую нибуль связвнную таблицу с отщывами и рейтинг пользователя
class UserModel(Base):
    __tablename__ = 'users' 

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=False, index=True)
    hashed_pwd: Mapped[str] = mapped_column(String(255), nullable=False)
    _2fa: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    announcements: Mapped[List["AnnouncementModel"]] = relationship(back_populates="user")
    liked_announcements: Mapped[List["AnnouncementModel"]] = relationship(
        secondary=user_liked_announcements,
        back_populates="liked_by_users"
    )