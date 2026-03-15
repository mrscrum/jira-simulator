from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.dysfunction_config import DysfunctionConfig
    from app.models.issue import Issue
    from app.models.member import Member
    from app.models.organization import Organization
    from app.models.sprint import Sprint
    from app.models.workflow import Workflow


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    jira_project_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    jira_board_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="teams")
    members: Mapped[list["Member"]] = relationship(back_populates="team")
    workflow: Mapped["Workflow | None"] = relationship(back_populates="team", uselist=False)
    dysfunction_config: Mapped["DysfunctionConfig | None"] = relationship(
        back_populates="team", uselist=False
    )
    sprints: Mapped[list["Sprint"]] = relationship(back_populates="team")
    issues: Mapped[list["Issue"]] = relationship(back_populates="team")
