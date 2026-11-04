"""Enumerate on-screen windows via Quartz CGWindowListCopyWindowInfo.

Requires no special entitlement for basic bounds + owner name, but
window *titles* (kCGWindowName) are often empty unless the process has
Screen Recording permission (System Settings → Privacy & Security →
Screen Recording). The prototype still works without it — titles just
come back blank.
"""

from __future__ import annotations

from typing import Optional

from .types import Rect, WindowInfo


# Layers we usually care about:
#   0  = normal application windows
#  25  = menu bar / status items (often filtered)
# higher = overlays, screen savers, etc.
_DEFAULT_MAX_LAYER = 0


def enumerate_windows(
    *,
    on_screen_only: bool = True,
    exclude_desktop: bool = True,
    max_layer: int = _DEFAULT_MAX_LAYER,
    min_size: float = 32.0,
    require_title: bool = False,
) -> list[WindowInfo]:
    """Return front-to-back list of interesting windows.

    Front-most window is index 0 (z=0).
    """
    try:
        import Quartz
    except ImportError as e:
        raise RuntimeError(
            "pyobjc Quartz not installed. On macOS run:\n"
            "  pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa"
        ) from e

    options = 0
    if on_screen_only:
        options |= Quartz.kCGWindowListOptionOnScreenOnly
    if exclude_desktop:
        options |= Quartz.kCGWindowListExcludeDesktopElements

    raw = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
    if not raw:
        return []

    # Front-most app PID (best-effort; does not require Accessibility).
    front_pid: Optional[int] = None
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is not None:
            front_pid = int(app.processIdentifier())
    except Exception:
        pass

    results: list[WindowInfo] = []
    z = 0
    for win in raw:
        try:
            layer = int(win.get("kCGWindowLayer", 0) or 0)
            if layer > max_layer:
                continue

            bounds = win.get("kCGWindowBounds") or {}
            left = float(bounds.get("X", 0))
            top = float(bounds.get("Y", 0))
            width = float(bounds.get("Width", 0))
            height = float(bounds.get("Height", 0))
            if width < min_size or height < min_size:
                continue

            owner = (win.get("kCGWindowOwnerName") or "").strip()
            title = (win.get("kCGWindowName") or "").strip()
            if require_title and not title:
                continue
            # Skip nameless system chrome that still passes size filter
            if not owner and not title:
                continue

            pid = int(win.get("kCGWindowOwnerPID", 0) or 0)
            number = int(win.get("kCGWindowNumber", 0) or 0)
            alpha = float(win.get("kCGWindowAlpha", 1.0) or 1.0)
            if alpha < 0.05:
                continue

            is_fg = (front_pid is not None and pid == front_pid and z == 0) or (
                front_pid is not None and pid == front_pid and not any(r.is_foreground for r in results)
            )
            # Prefer the first (top-most) window belonging to the front app.
            if front_pid is not None and pid == front_pid:
                is_fg = not any(r.is_foreground for r in results)

            results.append(
                WindowInfo(
                    handle=number,
                    process=owner or f"pid:{pid}",
                    pid=pid,
                    title=title,
                    rect=Rect(left, top, left + width, top + height),
                    z=z,
                    is_foreground=is_fg,
                    layer=layer,
                    alpha=alpha,
                )
            )
            z += 1
        except Exception:
            continue

    return results


def foreground_window(windows: Optional[list[WindowInfo]] = None) -> Optional[WindowInfo]:
    wins = windows if windows is not None else enumerate_windows()
    for w in wins:
        if w.is_foreground:
            return w
    return wins[0] if wins else None
