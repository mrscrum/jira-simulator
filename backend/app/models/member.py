from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.team import Team


class Member(TimestampMixin, Base):
    __tablename__ = "members"

    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    daily_capacity_hours: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    max_concurrent_wip: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="members")
