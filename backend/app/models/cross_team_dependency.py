from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.team import Team


class CrossTeamDependency(TimestampMixin, Base):
    __tablename__ = "cross_team_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "source_team_id",
            "target_team_id",
            "dependency_type",
            name="uq_dependency_source_target_type",
        ),
    )

    source_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    target_team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    dependency_type: Mapped[str] = mapped_column(String, nullable=False)

    source_team: Mapped["Team"] = relationship(
        foreign_keys=[source_team_id],
    )
    target_team: Mapped["Team"] = relationship(
        foreign_keys=[target_team_id],
    )
