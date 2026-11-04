"""Cursor position, system idle time, and clipboard change detection (macOS).

Cursor & idle use Quartz and need no special permissions.
Clipboard uses NSPasteboard; changeCount is always readable.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from .types import Vec2


def cursor_pos() -> Vec2:
    """Global screen coordinates (origin top-left, physical pixels)."""
    try:
        import Quartz

        # CGEventSource creates a synthetic event whose location is current cursor.
        event = Quartz.CGEventCreate(None)
        if event is None:
            return Vec2(0.0, 0.0)
        loc = Quartz.CGEventGetLocation(event)
        return Vec2(float(loc.x), float(loc.y))
    except Exception:
        return Vec2(0.0, 0.0)


def idle_seconds() -> float:
    """Seconds since any keyboard / mouse / tablet input."""
    try:
        import Quartz

        # kCGEventSourceStateHIDSystemState = 1
        # kCGAnyInputEventType = ~0 (0xFFFFFFFF)
        secs = Quartz.CGEventSourceSecondsSinceLastEventType(
            Quartz.kCGEventSourceStateHIDSystemState,
            Quartz.kCGAnyInputEventType,
        )
        return max(0.0, float(secs))
    except Exception:
        return 0.0


_last_clip_count: dict[str, int] = {"n": -1}


def clipboard_changed_hash() -> Optional[str]:
    """Return a short hash only when the pasteboard changeCount advanced.

    Never stores the actual clipboard content (privacy-friendly, same spirit
    as the original Windows prototype).
    """
    try:
        from AppKit import NSPasteboard

        pb = NSPasteboard.generalPasteboard()
        count = int(pb.changeCount())
        if count == _last_clip_count["n"]:
            return None
        _last_clip_count["n"] = count

        # Optional: hash a tiny preview of string content when present.
        # If that fails we still report the sequence number change.
        try:
            types = pb.types() or []
            if "public.utf8-plain-text" in types or "NSStringPboardType" in types:
                data = pb.stringForType_("public.utf8-plain-text")
                if data is None:
                    data = pb.stringForType_("NSStringPboardType")
                if data:
                    return hashlib.sha1(
                        str(data).encode("utf-8", "ignore")
                    ).hexdigest()[:12]
        except Exception:
            pass
        return f"seq:{count}"
    except Exception:
        return None
