from sqlalchemy import Column, Integer, String, Text, func, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from core import Base 

class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True, nullable=False)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), index=True, nullable=True, default=None)
    title: Mapped[str] = mapped_column(String, nullable=False)                 
    text: Mapped[str] = mapped_column(Text, nullable=False)  
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())