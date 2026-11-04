"""Transparent, always-on-top pet window (macOS-first).

Supports real sprite sheets via SpritePlayer (mochi anim_manifest.yaml),
with a drawn placeholder fallback if no sheet is loaded.
"""

from __future__ import annotations

import math
import time
from collections import deque
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPolygonF
from PyQt6.QtWidgets import QWidget

from . import cursor as cursor_mod
from . import macos_native
from .sprite_player import SpritePlayer
from .speech_bubble import SpeechBubble


# Default drawn size when no sprite sheet (logical px)
FALLBACK_SPRITE = 96


class PetWindow(QWidget):
    def __init__(
        self,
        scale: int = 3,
        *,
        click_through: bool = True,
        debug: bool = False,
        manifest: Optional[Path] = None,
    ):
        super().__init__(None)
        self.scale = max(1, scale)
        self._want_click_through = click_through
        self._debug = debug

        self.player = SpritePlayer(scale=self.scale)
        if manifest is not None:
            self.player.load_manifest(Path(manifest))

        if self.player.loaded:
            self.sprite_px = self.player.logical_size()[0]
        else:
            self.sprite_px = FALLBACK_SPRITE

        # Extra headroom above the sprite for the speech bubble (mochi-style)
        self._bubble_room = 72
        self.canvas_w = max(self.sprite_px + 24, 280)
        self.canvas_h = self.sprite_px + 40 + self._bubble_room
        self.sprite_x = (self.canvas_w - self.sprite_px) // 2
        self.sprite_y = self.canvas_h - self.sprite_px - 8

        self.bubble = SpeechBubble()
        self.setFixedSize(self.canvas_w, self.canvas_h)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._dragging = False
        self._click_through = False
        self._press_t = 0.0
        self._moved = False
        self._drag_offset_x = 0.0
        self._drag_offset_y = 0.0

        self._stroke_times: deque = deque(maxlen=8)
        self._stroke_last_x = None
        self._stroke_dir = 0
        self._last_pet_t = 0.0

        self._status = ""
        self._status_until = 0.0
        self._bob_t0 = time.monotonic()
        self._facing = 1
        self._native_ok = False
        self._last_debug = 0.0
        self._over = False
        self._external_control = True
        self._drag_samples = []  # (t, x, y) for throw velocity
        self._pending_throw = None  # (vx, vy) or None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    # ---- sprites ----------------------------------------------------------- #
    def load_manifest(self, path: Path) -> None:
        self.player.load_manifest(Path(path))
        if self.player.loaded:
            self.sprite_px = self.player.logical_size()[0]
            self._bubble_room = getattr(self, "_bubble_room", 72)
            self.canvas_w = max(self.sprite_px + 24, 280)
            self.canvas_h = self.sprite_px + 40 + self._bubble_room
            self.sprite_x = (self.canvas_w - self.sprite_px) // 2
            self.sprite_y = self.canvas_h - self.sprite_px - 8
            self.setFixedSize(self.canvas_w, self.canvas_h)
            self._flash("sprite OK")

    def play_anim(self, name: str, *, force: bool = False) -> None:
        self.player.play(name, force=force)

    # ---- public API for combined body -------------------------------------- #
    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def sprite_anchor_offset(self):
        return (
            self.sprite_x + self.sprite_px / 2,
            self.sprite_y + self.sprite_px / 2,
        )

    def set_world_pos(self, x: float, y: float, *, facing=None) -> None:
        if self._dragging or not self._external_control:
            return
        ax, ay = self.sprite_anchor_offset
        nx, ny = int(x - ax), int(y - ay)
        if nx != self.x() or ny != self.y():
            self.move(nx, ny)
        if facing is not None and facing != 0:
            self._facing = 1 if facing > 0 else -1
            self.player.facing = self._facing

    def flash(self, text: str) -> None:
        self._flash(text)

    def say(self, text: str, duration: float | None = None) -> None:
        """Show a speech bubble above the cat (mochi Intent.say)."""
        if not text:
            return
        self.bubble.show(text, duration)
        self.update()

    def consume_throw(self):
        """Return (vx, vy) once after a fling release, else None."""
        v = self._pending_throw
        self._pending_throw = None
        return v

    # ---- lifecycle --------------------------------------------------------- #
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # winId / NSWindow often not ready at 0ms — retry a few times
        self._native_tries = 0
        QTimer.singleShot(50, self._setup_native)

    def _setup_native(self) -> None:
        self._native_tries = getattr(self, "_native_tries", 0) + 1
        ok = macos_native.apply_overlay_style(
            self, start_click_through=False
        )
        self._click_through = False
        if ok:
            self._native_ok = True
            if self._native_tries <= 1:
                self._flash("ready — drag me")
            return
        # Retry: common on M1 when the Cocoa window is not mapped yet
        if self._native_tries < 8:
            QTimer.singleShot(100, self._setup_native)
            return
        self._native_ok = False
        self._flash("native partial — still interactive")
        print("[native] still no NSWindow after retries — "
              "window may hide when you click other apps")

    def _content_rect_local(self) -> QRect:
        """Tight rect around visible cat pixels (not full 32x32 cell)."""
        if self.player.loaded:
            x, y, w, h = self.player.content_rect_local(self.sprite_x, self.sprite_y)
            return QRect(x, y, w, h)
        return QRect(self.sprite_x, self.sprite_y, self.sprite_px, self.sprite_px)

    def _sprite_rect_global(self) -> QRect:
        local = self._content_rect_local()
        top_left = self.mapToGlobal(local.topLeft())
        return QRect(top_left.x(), top_left.y(), local.width(), local.height())

    def _cursor_over_sprite(self) -> bool:
        cx, cy = cursor_mod.cursor_pos()
        r = self._sprite_rect_global().adjusted(-10, -10, 10, 10)
        return r.contains(int(cx), int(cy))

    def _on_tick(self) -> None:
        now = time.monotonic()
        self.player.tick(now)
        self.player.facing = self._facing

        over = self._cursor_over_sprite()
        self._over = over

        if self._want_click_through and self._native_ok and not self._dragging:
            want_through = not over
            if want_through != self._click_through:
                ok = macos_native.set_ignores_mouse_events(self, want_through)
                if ok:
                    self._click_through = want_through

        if self._debug and now - self._last_debug > 0.5:
            self._last_debug = now
            cx, cy = cursor_mod.cursor_pos()
            r = self._sprite_rect_global()
            print(
                f"[debug] cursor=({cx:.0f},{cy:.0f}) sprite=({r.x()},{r.y()}) "
                f"over={over} anim={self.player.state} loaded={self.player.loaded}"
            )

        self.update()
        if self._status and now > self._status_until:
            self._status = ""

    # ---- painting ---------------------------------------------------------- #
    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, not self.player.loaded)
        p.fillRect(self.rect(), QColor(0, 0, 0, 1))

        if self.player.loaded:
            pm = self.player.current_pixmap()
            if not pm.isNull():
                p.drawPixmap(self.sprite_x, self.sprite_y, pm)
        else:
            self._paint_fallback_cat(p)

        # Speech bubble (LLM / rules say) — above the sprite
        if getattr(self, "bubble", None) is not None and self.bubble.active:
            self.bubble.paint(p, self.canvas_w, anchor_y=self.sprite_y)

        if self._status:
            p.setPen(QColor(255, 255, 255, 230))
            p.setFont(QFont("Menlo", 11))
            p.drawText(
                QRectF(0, 2, self.canvas_w, 18),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                self._status,
            )

        # Hitbox outline only in --debug
        if self._debug and (not self._click_through or self._over):
            color = QColor(80, 220, 120, 180) if self._over else QColor(200, 200, 200, 80)
            p.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            cr = self._content_rect_local()
            p.drawRect(cr)

        p.end()

    def _paint_fallback_cat(self, p: QPainter) -> None:
        bob = int(2 * math.sin((time.monotonic() - self._bob_t0) * 2.2))
        cx = self.sprite_x + self.sprite_px / 2
        cy = self.sprite_y + self.sprite_px / 2 + bob
        r = self.sprite_px * 0.42
        p.setBrush(QColor(0, 0, 0, 50))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - r + 2, cy - r + 4, r * 2, r * 2))
        p.setBrush(QColor(255, 168, 90))
        p.setPen(QPen(QColor(180, 100, 40), 2))
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))
        ear = r * 0.45
        for sign in (-1, 1):
            ex = cx + sign * r * 0.55 * self._facing
            ey = cy - r * 0.75
            p.drawPolygon(
                QPolygonF(
                    [
                        QPointF(ex, ey - ear),
                        QPointF(ex - ear * 0.55, ey + ear * 0.2),
                        QPointF(ex + ear * 0.55, ey + ear * 0.2),
                    ]
                )
            )
        for sign in (-1, 1):
            ex = cx + sign * r * 0.28 * self._facing
            p.setBrush(QColor(40, 30, 20))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(ex - 4, cy - r * 0.15 - 5, 8, 10))
        p.setBrush(QColor(220, 90, 90))
        p.drawEllipse(QRectF(cx - 3, cy + 4, 6, 5))

    # ---- mouse ------------------------------------------------------------- #
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._click_through:
            macos_native.set_ignores_mouse_events(self, False)
            self._click_through = False
        self._dragging = True
        self._press_t = time.monotonic()
        self._moved = False
        self._pending_throw = None
        self._drag_samples = []
        g = event.globalPosition()
        self._drag_offset_x = g.x() - self.x()
        self._drag_offset_y = g.y() - self.y()
        self._drag_samples.append((time.monotonic(), g.x(), g.y()))
        self.play_anim("idle")
        self._flash("grab")

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            g = event.globalPosition()
            nx = int(g.x() - self._drag_offset_x)
            ny = int(g.y() - self._drag_offset_y)
            if abs(nx - self.x()) > 2 or abs(ny - self.y()) > 2:
                self._moved = True
            self.move(nx, ny)
            now = time.monotonic()
            self._drag_samples.append((now, g.x(), g.y()))
            if len(self._drag_samples) > 12:
                self._drag_samples = self._drag_samples[-12:]
            self._facing = 1 if event.position().x() > self.sprite_x + self.sprite_px / 2 else -1
            self.player.facing = self._facing
            return
        self._detect_stroke(event.globalPosition().x())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._dragging:
            return
        self._dragging = False
        held = time.monotonic() - self._press_t
        # Estimate throw velocity from last ~80ms of drag samples
        self._pending_throw = None
        if self._moved and len(self._drag_samples) >= 2:
            t1, x1, y1 = self._drag_samples[-1]
            # find sample ~60-100ms earlier
            t0, x0, y0 = self._drag_samples[0]
            for s in reversed(self._drag_samples[:-1]):
                if t1 - s[0] >= 0.05:
                    t0, x0, y0 = s
                    break
            dt = max(1e-3, t1 - t0)
            vx = (x1 - x0) / dt
            vy = (y1 - y0) / dt
            if abs(vx) > 80 or abs(vy) > 80:
                self._pending_throw = (vx, vy)
                self.play_anim("fall", force=True)
                self._flash("put")
            else:
                self._flash("ok")
        elif not self._moved and held < 0.3:
            self.play_anim("pounce", force=True)
            self._flash("poke!")
        else:
            self._flash("put" if self._moved else "release")

    def leaveEvent(self, _event) -> None:  # noqa: N802
        self._stroke_last_x = None
        self._stroke_dir = 0
        self._stroke_times.clear()

    def _detect_stroke(self, x: float) -> None:
        now = time.monotonic()
        if self._stroke_last_x is not None:
            dx = x - self._stroke_last_x
            if abs(dx) >= 3:
                d = 1 if dx > 0 else -1
                if self._stroke_dir and d != self._stroke_dir:
                    self._stroke_times.append(now)
                self._stroke_dir = d
        self._stroke_last_x = x
        while self._stroke_times and now - self._stroke_times[0] > 1.2:
            self._stroke_times.popleft()
        if len(self._stroke_times) >= 2 and now - self._last_pet_t > 0.5:
            self._last_pet_t = now
            self.play_anim("happy", force=True)
            self._flash("pet ♥")

    def _flash(self, text: str) -> None:
        # Status labels (grab / poke / pet…) only in --debug
        if not self._debug:
            return
        self._status = text
        self._status_until = time.monotonic() + 1.5
        self.update()
