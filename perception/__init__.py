"""Independent macOS perception prototype for mochi-llm-pet.

Public surface:
    from perception import MacSensors, Snapshot, WindowInfo, Vec2, Rect
"""

from .sensor import MacSensors
from .types import Rect, Snapshot, Vec2, WindowInfo

__all__ = ["MacSensors", "Snapshot", "WindowInfo", "Vec2", "Rect"]
