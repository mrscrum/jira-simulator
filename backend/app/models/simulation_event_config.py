from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SimulationEventConfig(TimestampMixin, Base):
    __tablename__ = "simulation_event_config"

    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    params: Mapped[str] = mapped_column(String, nullable=False, default="{}")
