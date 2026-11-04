"""Bridge macOS perception Snapshot -> mochi WorldSnapshot."""
from __future__ import annotations

import time
from typing import Optional, Tuple

from .types import PetState, Rect, Vec2, WindowInfo, WorldSnapshot


def _rect(r) -> Rect:
    return Rect(float(r.left), float(r.top), float(r.right), float(r.bottom))


def _guess_content(process: str, title: str):
    blob = f"{process} {title}".lower()
    if any(k in blob for k in ("youtube", "netflix", "twitch", "vimeo", "bilibili")):
        return "youtube"
    if any(k in blob for k in ("vlc", "quicktime", "iina", "mpv", "plex")):
        return "media"
    if any(k in blob for k in ("code", "xcode", "vim", "nvim", "sublime", "jetbrains")):
        return "code"
    if any(k in blob for k in ("safari", "chrome", "firefox", "edge", "arc", "brave")):
        return "web"
    return None


def _window(w) -> WindowInfo:
    process = str(getattr(w, "process", "") or "")
    title = str(getattr(w, "title", "") or "")
    guess = getattr(w, "content_guess", None) or _guess_content(process, title)
    return WindowInfo(
        handle=int(getattr(w, "handle", 0) or 0),
        process=process,
        pid=int(getattr(w, "pid", 0) or 0),
        title=title,
        rect=_rect(w.rect),
        z=int(getattr(w, "z", 0) or 0),
        is_foreground=bool(getattr(w, "is_foreground", False)),
        content_guess=guess,
    )


def to_world(
    snap,
    *,
    screen_rect: Tuple[float, float, float, float],
    pet_pos: Optional[Vec2] = None,
    pet: Optional[PetState] = None,
    monitors_rects: Optional[list] = None,
) -> WorldSnapshot:
    left, top, right, bottom = screen_rect
    if monitors_rects:
        monitors = tuple(
            Rect(float(a), float(b), float(c), float(d))
            for (a, b, c, d) in monitors_rects
        )
    else:
        monitors = (Rect(left, top, right, bottom),)
    # macOS dock as rough taskbar on primary strip (best-effort)
    taskbar = Rect(left, bottom - 80, right, bottom)

    windows = tuple(_window(w) for w in (snap.windows or []))
    fg = None
    if getattr(snap, "foreground", None) is not None:
        fg = _window(snap.foreground)
    elif windows:
        for w in windows:
            if w.is_foreground:
                fg = w
                break

    cursor = Vec2(float(snap.cursor.x), float(snap.cursor.y))
    idle = float(getattr(snap, "idle_seconds", 0) or 0)

    return WorldSnapshot(
        t=time.time(),
        cursor=cursor,
        foreground=fg,
        windows=windows,
        monitors=monitors,
        taskbar=taskbar,
        idle_s=idle,
        clipboard_hash=getattr(snap, "clipboard_hash", None),
        pet=pet or PetState(),
        pet_pos=pet_pos or Vec2(0.0, 0.0),
    )
