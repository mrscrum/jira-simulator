from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JiraIssueLink(Base):
    __tablename__ = "jira_issue_links"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    from_issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id"), nullable=False
    )
    to_issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(String, nullable=False)
    jira_link_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="PENDING"
    )
