"""Sprite sheet player compatible with mochi-llm-pet anim_manifest.yaml."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


@dataclass
class AnimState:
    name: str
    frames: List[int]
    fps: float
    loop: bool


def _alpha_bounds(pm) -> Tuple[int, int, int, int]:
    """Tight bbox of non-transparent pixels in a QPixmap: (x, y, w, h).

    Returns full frame if empty / failure.
    """
    from PyQt6.QtGui import QImage

    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return (0, 0, max(1, w), max(1, h))

    min_x, min_y = w, h
    max_x, max_y = -1, -1
    # Sample every pixel — 32x32 is tiny
    for y in range(h):
        for x in range(w):
            if (img.pixel(x, y) >> 24) & 0xFF > 8:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if max_x < min_x:
        return (0, 0, w, h)
    return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


class SpritePlayer:
    def __init__(self, scale: int = 3):
        self.scale = max(1, scale)
        self.frame_w = 32
        self.frame_h = 32
        self.columns = 1
        self._frames = []  # QPixmap list
        self._bounds = []  # per-frame alpha (x,y,w,h) in source pixels
        self._states: Dict[str, AnimState] = {}
        self._aliases: Dict[str, str] = {}
        self._state_name = "idle"
        self._frame_i = 0
        self._t_frame = time.monotonic()
        self._facing = 1
        self._loaded = False
        self._sheet_path: Optional[Path] = None

    @property
    def loaded(self) -> bool:
        return self._loaded and bool(self._frames)

    @property
    def state(self) -> str:
        return self._state_name

    @property
    def facing(self) -> int:
        return self._facing

    @facing.setter
    def facing(self, v: int) -> None:
        if v != 0:
            self._facing = 1 if v > 0 else -1

    def load_manifest(self, manifest_path: Path) -> None:
        if yaml is None:
            raise RuntimeError("PyYAML required: pip install PyYAML")
        manifest_path = Path(manifest_path)
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        sheet_rel = data.get("sheet") or data.get("sheet_rel")
        if not sheet_rel:
            raise ValueError("manifest missing 'sheet'")
        sheet_path = (manifest_path.parent / sheet_rel).resolve()
        if not sheet_path.is_file():
            raise FileNotFoundError(f"sprite sheet not found: {sheet_path}")

        fw, fh = data.get("frame_size") or [32, 32]
        self.frame_w, self.frame_h = int(fw), int(fh)
        self.columns = int(data.get("columns") or 10)
        default_fps = float(data.get("default_fps") or 10)

        from PyQt6.QtGui import QPixmap

        sheet = QPixmap(str(sheet_path))
        if sheet.isNull():
            raise RuntimeError(f"failed to load image: {sheet_path}")

        cols = self.columns
        cols_from_w = max(1, sheet.width() // self.frame_w)
        cols = min(cols, cols_from_w)
        rows = max(1, sheet.height() // self.frame_h)

        frames = []
        bounds = []
        for idx in range(rows * cols):
            row = idx // cols
            col = idx % cols
            x, y = col * self.frame_w, row * self.frame_h
            if x + self.frame_w > sheet.width() or y + self.frame_h > sheet.height():
                break
            cell = sheet.copy(x, y, self.frame_w, self.frame_h)
            frames.append(cell)
            bounds.append(_alpha_bounds(cell))

        states: Dict[str, AnimState] = {}
        for name, spec in (data.get("states") or {}).items():
            if not isinstance(spec, dict):
                continue
            fps = float(spec.get("fps") or default_fps)
            loop = bool(spec.get("loop", True))
            if "frames" in spec:
                fl = [int(i) for i in spec["frames"]]
            else:
                a = int(spec.get("from", 0))
                b = int(spec.get("to", a))
                fl = list(range(a, b + 1))
            fl = [i for i in fl if 0 <= i < len(frames)]
            if not fl:
                continue
            states[name] = AnimState(name=name, frames=fl, fps=fps, loop=loop)

        aliases = {str(k): str(v) for k, v in (data.get("aliases") or {}).items()}

        self._frames = frames
        self._bounds = bounds
        self._states = states
        self._aliases = aliases
        self._sheet_path = sheet_path
        self._loaded = True
        self.play("idle")

    def play(self, name: str, *, force: bool = False) -> None:
        resolved = self._aliases.get(name, name)
        if resolved not in self._states:
            for key in ("idle", "Idle_1"):
                resolved = self._aliases.get(key, key)
                if resolved in self._states:
                    break
            else:
                return
        if not force and self._state_name == resolved:
            return
        self._state_name = resolved
        self._frame_i = 0
        self._t_frame = time.monotonic()

    def tick(self, now: Optional[float] = None) -> None:
        if not self._loaded:
            return
        st = self._states.get(self._state_name)
        if not st or not st.frames:
            return
        now = time.monotonic() if now is None else now
        interval = 1.0 / max(1e-3, st.fps)
        if now - self._t_frame < interval:
            return
        self._t_frame = now
        self._frame_i += 1
        if self._frame_i >= len(st.frames):
            if st.loop:
                self._frame_i = 0
            else:
                self._frame_i = len(st.frames) - 1

    def _current_frame_index(self) -> int:
        st = self._states.get(self._state_name)
        if not st or not st.frames:
            return 0
        return st.frames[min(self._frame_i, len(st.frames) - 1)]

    def current_pixmap(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap, QTransform

        if not self._frames:
            return QPixmap()
        idx = self._current_frame_index()
        pm = self._frames[idx] if idx < len(self._frames) else self._frames[0]
        w = self.frame_w * self.scale
        h = self.frame_h * self.scale
        scaled = pm.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        if self._facing < 0:
            scaled = scaled.transformed(QTransform().scale(-1, 1))
        return scaled

    def content_rect_local(self, sprite_x: int, sprite_y: int) -> Tuple[int, int, int, int]:
        """Drawable content rect in widget coords (tight alpha bounds, scaled).

        Returns (x, y, w, h) relative to the widget.
        """
        if not self._frames or not self._bounds:
            return (sprite_x, sprite_y, self.frame_w * self.scale, self.frame_h * self.scale)

        idx = self._current_frame_index()
        if idx >= len(self._bounds):
            idx = 0
        bx, by, bw, bh = self._bounds[idx]
        s = self.scale
        # scale bounds
        x = sprite_x + bx * s
        y = sprite_y + by * s
        w = max(1, bw * s)
        h = max(1, bh * s)

        # mirror when facing left (frame is flipped around vertical center)
        if self._facing < 0:
            frame_w = self.frame_w * s
            # distance from left of frame -> distance from right
            x = sprite_x + (frame_w - (bx * s + bw * s))
        return (x, y, w, h)

    def logical_size(self) -> Tuple[int, int]:
        return (self.frame_w * self.scale, self.frame_h * self.scale)
