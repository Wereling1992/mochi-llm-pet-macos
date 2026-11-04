"""Minimal types aligned with mochi-llm-pet deskpet.types so this prototype
can later drop into the real perception layer with little glue.

Compatible with Python 3.8+ (no dataclass slots=).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    def contains(self, p: Vec2) -> bool:
        return self.left <= p.x <= self.right and self.top <= p.y <= self.bottom


@dataclass(frozen=True)
class WindowInfo:
    """One on-screen window, roughly matching mochi's WindowInfo."""

    handle: int          # CGWindowNumber
    process: str         # owner name (e.g. "Code", "Safari")
    pid: int
    title: str
    rect: Rect           # physical pixels, global screen space
    z: int               # 0 = front-most among returned windows
    is_foreground: bool
    layer: int = 0
    alpha: float = 1.0


@dataclass
class Snapshot:
    """What the sensors produce each tick."""

    cursor: Vec2
    idle_seconds: float
    windows: List[WindowInfo] = field(default_factory=list)
    foreground: Optional[WindowInfo] = None
    clipboard_hash: Optional[str] = None  # only set when clipboard changed
    error: Optional[str] = None           # human-readable permission / API failure
