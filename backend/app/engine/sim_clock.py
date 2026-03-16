"""Virtual clock for simulation time acceleration.

Default behaviour is real-time (speed=1.0).  Set speed > 1 to accelerate
for one-off testing.  For example speed=60 means 1 wall-clock minute equals
1 simulated hour.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class SimClock:
    def __init__(self, speed_multiplier: float = 1.0) -> None:
        self._multiplier = speed_multiplier
        self._real_start = datetime.now(UTC)
        self._sim_start = datetime.now(UTC)

    # -- public API --

    def now(self) -> datetime:
        """Return the current simulated time."""
        elapsed = datetime.now(UTC) - self._real_start
        return self._sim_start + timedelta(
            seconds=elapsed.total_seconds() * self._multiplier,
        )

    @property
    def speed(self) -> float:
        return self._multiplier

    @speed.setter
    def speed(self, value: float) -> None:
        # Anchor sim time at current point before changing rate.
        self._sim_start = self.now()
        self._real_start = datetime.now(UTC)
        self._multiplier = value
