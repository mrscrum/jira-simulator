"""Decision-draw source used by live simulator operations."""

from typing import Protocol

from app.v2.domain.deterministic_rng import (
    DecisionOccurrence,
    DeterministicRandomStream,
    UniformDraw,
)
from app.v2.domain.team_runtime import PersistedTeamAggregate


class DrawSource(Protocol):
    """Provides an authenticated deterministic draw for a decision coordinate."""

    def draw(self, decision: DecisionOccurrence, draw_index: int = 0) -> UniformDraw:
        """Return the deterministic draw for one semantic decision."""


class SeededDrawSource:
    """Adapter over the persisted blueprint seed and active runtime identity."""

    def __init__(self, aggregate: PersistedTeamAggregate):
        self._stream = DeterministicRandomStream(
            aggregate.blueprint.seed,
            aggregate.team.id,
            aggregate.runtime.run_id,
        )

    def draw(self, decision: DecisionOccurrence, draw_index: int = 0) -> UniformDraw:
        """Delegate authenticated Task 3 HMAC-U53 draws to the stream."""
        return self._stream.draw(decision, draw_index)
