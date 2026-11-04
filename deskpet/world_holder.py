"""Thread-safe-ish world snapshot holder (macOS replacement for perception.world.WorldState)."""
from __future__ import annotations

from .types import WorldSnapshot


class WorldHolder:
    def __init__(self) -> None:
        self._snap = WorldSnapshot()

    def update(self, snap: WorldSnapshot) -> None:
        self._snap = snap

    def read(self) -> WorldSnapshot:
        return self._snap
