from core import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

class UserSettingsModel(Base):
    __tablename__ = 'user_settings'
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    two_factor_enabled: Mapped[bool] = mapped_column(default=False, server_default='false')
    show_email: Mapped[bool] = mapped_column(default=False, server_default='false')

    user: Mapped['UserModel'] = relationship(back_populates='settings')