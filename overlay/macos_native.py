"""macOS-native helpers for the pet overlay window.

Toggle NSWindow.ignoresMouseEvents for click-through (like WS_EX_TRANSPARENT).
Critical: setHidesOnDeactivate_(False) so the pet stays visible when another
app is focused (otherwise Qt Tool windows vanish on deactivate).
"""

from __future__ import annotations

import sys
from typing import Any, Optional


def _ns_window_for_widget(widget) -> Optional[Any]:
    """Resolve the Cocoa NSWindow backing a QWidget (best-effort on M1/Intel)."""
    if sys.platform != "darwin":
        return None

    # Method 1: winId → NSView → window (standard PyQt path)
    try:
        import objc
        from ctypes import c_void_p

        for wid_src in (
            lambda: int(widget.winId()),
            lambda: int(widget.windowHandle().winId()) if widget.windowHandle() else 0,
        ):
            try:
                wid = wid_src()
            except Exception:
                wid = 0
            if not wid:
                continue
            view = objc.objc_object(c_void_p=wid)
            if view is None:
                continue
            # Some builds expose window() on NSView; others need objc msg
            nsw = None
            if hasattr(view, "window"):
                try:
                    nsw = view.window()
                except Exception:
                    nsw = None
            if nsw is None:
                try:
                    nsw = view.performSelector_("window")
                except Exception:
                    nsw = None
            if nsw is not None:
                return nsw
    except Exception as e:
        print(f"[native] winId path failed: {e}")

    # Method 2: match among NSApp windows by frame (single-pet apps: best candidate)
    try:
        from AppKit import NSApp

        try:
            fg = widget.frameGeometry()
            qx, qy, qw, qh = fg.x(), fg.y(), fg.width(), fg.height()
        except Exception:
            qx = qy = qw = qh = 0

        best = None
        best_score = 1e18
        for nsw in list(NSApp.windows() or []):
            if nsw is None:
                continue
            try:
                if not nsw.isVisible():
                    continue
                fr = nsw.frame()
                # Cocoa y is flipped vs Qt; compare size more than origin
                score = abs(fr.size.width - qw) + abs(fr.size.height - qh)
                if score < best_score:
                    best_score = score
                    best = nsw
            except Exception:
                continue
        if best is not None and best_score < 80:
            return best
        # last resort: any visible non-main-menu window
        for nsw in list(NSApp.windows() or []):
            if nsw is None:
                continue
            try:
                if nsw.isVisible() and nsw.frame().size.width > 32:
                    return nsw
            except Exception:
                continue
    except Exception as e:
        print(f"[native] NSApp.windows path failed: {e}")

    return None


def set_ignores_mouse_events(widget, enabled: bool) -> bool:
    """enabled=True → clicks pass through to apps beneath."""
    if sys.platform != "darwin":
        return False
    try:
        nsw = _ns_window_for_widget(widget)
        if nsw is None:
            return False
        nsw.setIgnoresMouseEvents_(bool(enabled))
        return True
    except Exception as e:
        print(f"[native] setIgnoresMouseEvents failed: {e}")
        return False


def apply_overlay_style(widget, *, start_click_through: bool = False) -> bool:
    """Polish after show(). Returns True if NSWindow was found.

    Always tries to keep the window visible when the app is not frontmost.
    """
    if sys.platform != "darwin":
        return False
    try:
        nsw = _ns_window_for_widget(widget)
        if nsw is None:
            print("[native] could not resolve NSWindow — pet may hide when you focus other apps")
            print("[native] tip: keep Terminal/Python in the Dock; retry after window is fully shown")
            return False

        try:
            from AppKit import NSFloatingWindowLevel, NSStatusWindowLevel

            # Status level stays above most windows; floating is also OK
            try:
                nsw.setLevel_(NSStatusWindowLevel)
            except Exception:
                nsw.setLevel_(NSFloatingWindowLevel)
        except Exception:
            try:
                nsw.setLevel_(25)  # typical status level
            except Exception:
                nsw.setLevel_(3)

        for call in (
            lambda: nsw.setHasShadow_(False),
            # KEY: do not hide when Terminal loses focus / you click Safari
            lambda: nsw.setHidesOnDeactivate_(False),
            lambda: nsw.setCollectionBehavior_(
                # Can join all spaces + stationary (less likely to vanish on space switch)
                (1 << 0) | (1 << 4)  # NSWindowCollectionBehaviorCanJoinAllSpaces | FullScreenAuxiliary-ish
            ),
            lambda: nsw.setIgnoresMouseEvents_(bool(start_click_through)),
        ):
            try:
                call()
            except Exception:
                pass

        # Re-assert after a moment (Qt sometimes resets)
        try:
            nsw.setHidesOnDeactivate_(False)
        except Exception:
            pass

        print(f"[native] NSWindow OK  hidesOnDeactivate=False  click_through={start_click_through}")
        return True
    except Exception as e:
        print(f"[native] apply_overlay_style failed: {e}")
        return False
