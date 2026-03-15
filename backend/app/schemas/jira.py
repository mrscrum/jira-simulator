from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class JiraStatus(BaseModel):
    name: str
    category: str


class BootstrapStatusResponse(BaseModel):
    bootstrapped: bool
    warnings: list[str]
    board_id: int | None
    custom_field_ids: dict[str, str]
    last_run: datetime | None


class JiraHealthResponse(BaseModel):
    status: Literal["ONLINE", "OFFLINE", "RECOVERING"]
    last_checked: datetime | None
    last_online: datetime | None
    consecutive_failures: int
    outage_start: datetime | None


class QueueStatusResponse(BaseModel):
    pending: int
    in_flight: int
    done: int
    failed: int
    skipped: int
    total: int
