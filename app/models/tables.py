from sqlalchemy import Table, Column, ForeignKey, DateTime, func
from core import Base


user_liked_announcements = Table(
    "user_liked_announcements",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("announcement_id", ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()) 
)