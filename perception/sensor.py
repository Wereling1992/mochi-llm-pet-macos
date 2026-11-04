"""High-level sensor facade — closest analogue to mochi's Sensors class.

Call `tick()` on a timer (e.g. 2–10 Hz). Cheap path refreshes only the
cursor; medium path rebuilds the full window list + idle + clipboard.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Optional

from . import macos_input, macos_windows
from .types import Snapshot, Vec2, WindowInfo


class MacSensors:
    def __init__(
        self,
        *,
        fast_ms: float = 50.0,    # cursor only
        medium_ms: float = 400.0, # full rebuild
        min_window_size: float = 32.0,
    ):
        self.fast_ms = fast_ms
        self.medium_ms = medium_ms
        self.min_window_size = min_window_size
        self._t_fast = 0.0
        self._t_medium = 0.0
        self._snap = Snapshot(cursor=Vec2(0, 0), idle_seconds=0.0)

    @property
    def snapshot(self) -> Snapshot:
        return self._snap

    def tick(self, now: Optional[float] = None) -> Snapshot:
        now = time.monotonic() if now is None else now

        if (now - self._t_medium) * 1000.0 >= self.medium_ms:
            self._t_medium = now
            self._t_fast = now
            self._rebuild()
        elif (now - self._t_fast) * 1000.0 >= self.fast_ms:
            self._t_fast = now
            self._patch_cursor()

        return self._snap

    def _patch_cursor(self) -> None:
        try:
            cur = macos_input.cursor_pos()
            self._snap = replace(self._snap, cursor=cur, error=None)
        except Exception as e:
            self._snap = replace(self._snap, error=f"cursor: {e}")

    def _rebuild(self) -> None:
        err: Optional[str] = None
        windows: list[WindowInfo] = []
        try:
            windows = macos_windows.enumerate_windows(
                min_size=self.min_window_size,
            )
        except Exception as e:
            err = f"windows: {e}"

        try:
            cursor = macos_input.cursor_pos()
        except Exception as e:
            cursor = self._snap.cursor
            err = (err + "; " if err else "") + f"cursor: {e}"

        try:
            idle = macos_input.idle_seconds()
        except Exception as e:
            idle = 0.0
            err = (err + "; " if err else "") + f"idle: {e}"

        clip_hash = None
        try:
            clip_hash = macos_input.clipboard_changed_hash()
        except Exception:
            pass

        fg = next((w for w in windows if w.is_foreground), None)
        if fg is None and windows:
            fg = windows[0]

        self._snap = Snapshot(
            cursor=cursor,
            idle_seconds=idle,
            windows=windows,
            foreground=fg,
            clipboard_hash=clip_hash,
            error=err,
        )
