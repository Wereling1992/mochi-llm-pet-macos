"""Make overlay SpritePlayer look like mochi AnimationPlayer for Body."""
from __future__ import annotations

from typing import Any, Dict, Set


class PlayerBridge:
    def __init__(self, sprite_player: Any):
        self._sp = sprite_player
        self.clips: Dict[str, _Clip] = {}
        self._refresh_clips()

    def _refresh_clips(self) -> None:
        sp = self._sp
        clips: Dict[str, _Clip] = {}
        for name, st in getattr(sp, "_states", {}).items():
            fps = getattr(st, "fps", 10) or 10
            n = max(1, len(getattr(st, "frames", []) or [0]))
            loop = bool(getattr(st, "loop", True))
            clips[name] = _Clip(duration=n / max(1e-3, fps), loop=loop)
        for alias, target in getattr(sp, "_aliases", {}).items():
            if target in clips and alias not in clips:
                clips[alias] = clips[target]
        # canonical names Body expects
        for canon in ("idle", "walk", "run", "sit", "sleep", "look", "watch", "happy", "bored"):
            if canon not in clips and clips:
                # prefer alias target if any state exists
                clips[canon] = next(iter(clips.values()))
        self.clips = clips

    @property
    def available(self) -> Set[str]:
        return set(self.clips.keys())

    def set_state(self, name: str) -> None:
        if not name:
            return
        self._sp.play(name)

    def set_facing(self, facing: int) -> None:
        self._sp.facing = 1 if facing >= 0 else -1

    def update(self, dt: float) -> None:
        pass


class _Clip:
    __slots__ = ("duration", "loop")

    def __init__(self, duration: float, loop: bool):
        self.duration = duration
        self.loop = loop
