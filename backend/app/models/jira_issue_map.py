from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JiraIssueMap(Base):
    __tablename__ = "jira_issue_map"

    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id"), primary_key=True
    )
    jira_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    jira_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
