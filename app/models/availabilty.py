from datetime import time
from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time
from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from core import Base


class AvailabilityRuleModel(Base):
    __tablename__ = 'availability_rules'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    weekday: Mapped[int] = mapped_column(SmallInteger)      # 0 = пн ... 6 = вс
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)

    __table_args__ = (
        UniqueConstraint('user_id', 'weekday', name='uq_rule_user_weekday'),
        CheckConstraint('weekday BETWEEN 0 AND 6', name='ck_rule_weekday'),
        CheckConstraint('end_time > start_time', name='ck_rule_time_order'),
    )