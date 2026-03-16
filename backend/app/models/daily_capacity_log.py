from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailyCapacityLog(TimestampMixin, Base):
    __tablename__ = "daily_capacity_log"

    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_hours: Mapped[float] = mapped_column(Float, nullable=False)
    consumed_hours: Mapped[float] = mapped_column(Float, nullable=False)
    active_wip_count: Mapped[int] = mapped_column(Integer, nullable=False)
