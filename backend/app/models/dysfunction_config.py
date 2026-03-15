from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.team import Team


class DysfunctionConfig(TimestampMixin, Base):
    __tablename__ = "dysfunction_configs"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), unique=True, nullable=False
    )
    low_quality_probability: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    scope_creep_probability: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    blocking_dependency_probability: Mapped[float] = mapped_column(
        Float, default=0.12, nullable=False
    )
    dark_teammate_probability: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    re_estimation_probability: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)
    bug_injection_probability: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)
    cross_team_block_probability: Mapped[float] = mapped_column(
        Float, default=0.08, nullable=False
    )
    cross_team_handoff_lag_probability: Mapped[float] = mapped_column(
        Float, default=0.10, nullable=False
    )
    cross_team_bug_probability: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)

    team: Mapped["Team"] = relationship(back_populates="dysfunction_config")
