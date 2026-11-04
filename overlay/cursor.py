"""Global cursor position in Qt logical coordinates (origin top-left).

Prefer QCursor so hit-testing matches widget.mapToGlobal() exactly.
Falls back to Quartz (converted to top-left) if Qt is unavailable.
"""

from __future__ import annotations

from typing import Tuple


def cursor_pos() -> Tuple[float, float]:
    """Return (x, y) in the same space as QWidget.mapToGlobal / QCursor.pos."""
    try:
        from PyQt6.QtGui import QCursor

        p = QCursor.pos()
        return (float(p.x()), float(p.y()))
    except Exception:
        pass

    # Fallback: Quartz (origin is bottom-left of main display)
    try:
        import Quartz
        from AppKit import NSScreen

        event = Quartz.CGEventCreate(None)
        if event is None:
            return (0.0, 0.0)
        loc = Quartz.CGEventGetLocation(event)
        x = float(loc.x)
        y_bottom = float(loc.y)
        # Convert bottom-left → top-left using main screen height
        h = float(NSScreen.mainScreen().frame().size.height)
        y = h - y_bottom
        return (x, y)
    except Exception:
        return (0.0, 0.0)
