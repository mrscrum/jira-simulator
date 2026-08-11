"""Application-level coherent live-team read model."""

from dataclasses import dataclass

from app.v2.domain.scrum_state import ScrumStateSnapshot
from app.v2.domain.team_runtime import PersistedTeamAggregate


@dataclass(frozen=True)
class LiveTeamState:
    """The persisted runtime and Scrum state observed in one coherent read."""

    aggregate: PersistedTeamAggregate
    scrum: ScrumStateSnapshot
