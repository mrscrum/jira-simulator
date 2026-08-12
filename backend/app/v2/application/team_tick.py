"""Application orchestration for one atomically committed Scrum tick."""

from app.v2.domain.authoritative_slice import CommittedAuthoritativeTickSlice
from app.v2.domain.draw_source import SeededDrawSource
from app.v2.domain.scrum_tick import TickRequest, calculate_scrum_tick
from app.v2.persistence.live_team_store import LiveTeamStore
from app.v2.persistence.unit_of_work import StaleRuntimeVersion, V2UnitOfWork


class TeamTickService:
    """Loads, calculates, and atomically commits one team tick attempt."""

    def __init__(self, store: LiveTeamStore, unit_of_work: V2UnitOfWork) -> None:
        self._store = store
        self._unit_of_work = unit_of_work

    def advance(self, request: TickRequest) -> CommittedAuthoritativeTickSlice:
        """Retry one stale runtime race exactly once with a fresh coherent load."""
        for attempt in range(2):
            state = self._store.load(request.team_id)
            command = calculate_scrum_tick(state, request, SeededDrawSource(state.aggregate))
            try:
                return self._unit_of_work.commit_authoritative_slice(command)
            except StaleRuntimeVersion:
                if attempt == 1:
                    raise
        raise RuntimeError("unreachable tick retry state")
