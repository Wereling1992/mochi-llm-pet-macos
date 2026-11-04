#!/usr/bin/env python3
"""mochi-llm-pet-macos — single-tree entry (perception + overlay + deskpet + LLM).

    python3 run.py --manifest assets/bowpixel/anim_manifest.yaml --scale 3

Config: copy config.example.toml -> config.toml (or use env vars).
Default LLM: Ollama local (provider=ollama). If unreachable, falls back to rule_based.
"""

from __future__ import annotations

import argparse
import inspect
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# Single-package layout: project root on sys.path
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _ensure_placeholder_manifest() -> Path:
    assets = _HERE / "assets"
    man = assets / "anim_manifest.yaml"
    if man.is_file() and (assets / "placeholder_cat.png").is_file():
        return man
    import importlib.util

    mp = _HERE / "overlay" / "make_placeholder.py"
    if not mp.is_file():
        raise FileNotFoundError(f"Missing {mp}")
    spec = importlib.util.spec_from_file_location("make_placeholder", mp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.generate(assets)


def _make_pet_window(PetWindow, scale, click_through, debug, manifest):
    sig = inspect.signature(PetWindow.__init__)
    kwargs = {}
    params = sig.parameters
    if "click_through" in params:
        kwargs["click_through"] = click_through
    if "debug" in params:
        kwargs["debug"] = debug
    if "manifest" in params:
        kwargs["manifest"] = manifest
        return PetWindow(scale=scale, **kwargs)
    win = PetWindow(scale=scale, **kwargs)
    if not hasattr(win, "load_manifest"):
        raise RuntimeError("macos_overlay_proto outdated")
    win.load_manifest(manifest)
    return win


def _all_monitor_rects(app) -> list:
    """All QScreen geometries as (left, top, right, bottom) in Qt coords."""
    out = []
    for scr in app.screens() or []:
        g = scr.geometry()  # full screen, not only available
        out.append((float(g.x()), float(g.y()), float(g.x() + g.width()), float(g.y() + g.height())))
    if not out:
        out = [(0.0, 0.0, 1920.0, 1080.0)]
    return out


def main() -> int:
    if sys.platform != "darwin":
        print(f"macOS only (got {sys.platform})", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description="macOS mochi deskpet + LLM")
    parser.add_argument("--config", type=str, default="", help="path to config.toml")
    parser.add_argument("--manifest", type=str, default="")
    parser.add_argument("--scale", type=int, default=0, help="0 = use config.render.scale")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="force rule_based only (skip brain worker)",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "sit_front", "follow_cursor", "idle"),
        default="auto",
        help="auto = brain/fallback; others force an intent",
    )
    args = parser.parse_args()

    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("pip install PyQt6 PyYAML Pillow pydantic tenacity httpx mss", file=sys.stderr)
        return 1

    try:
        from perception import MacSensors
        from overlay import PetWindow
    except ImportError as e:
        print(f"Import failed: {e}", file=sys.stderr)
        return 1

    from deskpet.adapter import to_world
    from deskpet.body.body import Body
    from deskpet.brain.agent import BrainAgent
    from deskpet.brain.fallback import rule_based
    from deskpet.config import Config
    from deskpet.log import setup as log_setup
    from deskpet.player_bridge import PlayerBridge
    from deskpet.triggers.events import EventBus, TriggerEvent
    from deskpet.types import Emotion, Intent, Verb, Vec2
    from deskpet.world_holder import WorldHolder

    log_setup()
    cfg_path = args.config or str(_HERE / "config.toml")
    if Path(cfg_path).is_file():
        cfg = Config.load(cfg_path)
    else:
        cfg = Config()
        if not args.no_llm:
            print(f"(no {cfg_path} — using defaults: {cfg.llm.provider} / {cfg.llm.model})")
            print("  copy config.example.toml -> config.toml to customize")

    scale = args.scale if args.scale > 0 else int(cfg.render.scale)

    if args.manifest:
        manifest = Path(args.manifest).expanduser().resolve()
        if not manifest.is_file():
            print(f"manifest not found: {manifest}", file=sys.stderr)
            return 1
    else:
        # prefer assets from config, then bowpixel, then placeholder
        candidates = [
            _HERE / cfg.render.assets_dir / "anim_manifest.yaml",
            _HERE / "assets" / "bowpixel" / "anim_manifest.yaml",
            _HERE / "assets" / "anim_manifest.yaml",
        ]
        manifest = next((p for p in candidates if p.is_file()), None)
        if manifest is None:
            try:
                manifest = _ensure_placeholder_manifest()
            except Exception as e:
                print(f"manifest failed: {e}", file=sys.stderr)
                return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    sensors = MacSensors(fast_ms=50, medium_ms=350)
    win = _make_pet_window(
        PetWindow, scale=scale, click_through=True, debug=args.debug, manifest=manifest
    )
    player = getattr(win, "player", None)
    if player is None:
        print("PetWindow has no .player", file=sys.stderr)
        return 1

    bridge = PlayerBridge(player)
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        start = Vec2(geo.x() + geo.width() * 0.5, geo.y() + geo.height() * 0.55)
        screen_rect = (
            float(geo.x()),
            float(geo.y()),
            float(geo.x() + geo.width()),
            float(geo.y() + geo.height()),
        )
    else:
        start = Vec2(400.0, 400.0)
        screen_rect = (0.0, 0.0, 1920.0, 1080.0)

    body = Body(start_pos=start)
    body.attach_player(bridge)
    body._available = set(bridge.clips.keys())
    body._available |= set(getattr(player, "_aliases", {}).keys())
    body._available |= set(getattr(player, "_states", {}).keys())

    world = WorldHolder()
    bus = EventBus()

    # Optional memory
    memory_store = None
    try:
        from deskpet.memory.store import MemoryStore

        memory_store = MemoryStore(cfg.memory.db_path)
    except Exception as e:
        print(f"(memory disabled: {e})")

    agent = BrainAgent(cfg, memory_store=memory_store)
    ok = agent.check_health()
    print(
        f"sprite loaded={getattr(player, 'loaded', False)}  "
        f"llm={cfg.llm.provider}/{cfg.llm.model}  "
        f"reachable={ok}  degraded={agent.degraded}"
    )

    thread = worker = None
    if not args.no_llm and args.mode == "auto":
        from deskpet.brain.worker import start_worker

        thread, worker = start_worker(cfg, agent, world, bus)

        def _on_intent(intent: Intent) -> None:
            if body.physics.active:
                return
            body.set_intent(intent)
            if args.debug or True:
                src = getattr(agent, "last_source", "?")
                say = f' say="{intent.say}"' if intent.say else ""
                print(
                    f"[brain:{src}] {intent.verb.value} → {intent.target or '—'} "
                    f"({intent.emotion.value}){say}"
                )
            if intent.say and hasattr(win, "say"):
                win.say(intent.say)
            elif intent.say and hasattr(win, "flash"):
                win.flash((intent.say or "")[:28])

        worker.intentReady.connect(_on_intent)

        def _on_done() -> None:
            bus.emit(TriggerEvent.BODY_ACTION_DONE)

        body.on_action_done = _on_done
        thread.start()
    else:
        body.on_action_done = lambda: None

    if hasattr(win, "set_world_pos"):
        win.set_world_pos(body.motion.pos.x, body.motion.pos.y)
    win.show()
    win.raise_()

    state = {
        "last_t": time.monotonic(),
        "last_rule": 0.0,
        "last_log": 0.0,
        "was_dragging": False,
    }

    def _force_intent(mode: str, snap) -> Intent:
        if mode == "follow_cursor":
            return Intent(
                verb=Verb.FOLLOW_CURSOR,
                emotion=Emotion.MISCHIEVOUS,
                thought="(force) follow",
            )
        if mode == "sit_front":
            return Intent(
                verb=Verb.SIT_ON,
                target="active_window",
                edge="top",
                emotion=Emotion.CURIOUS,
                thought="(force) sit_front",
            )
        if mode == "idle":
            return Intent(verb=Verb.IDLE, emotion=Emotion.NEUTRAL, thought="(force) idle")
        return rule_based(snap)

    def tick() -> None:
        now = time.monotonic()
        dt = min(0.05, now - state["last_t"])
        state["last_t"] = now

        snap = sensors.tick(now)
        scr = app.primaryScreen()
        if scr is not None:
            g = scr.availableGeometry()
            screen_rect_local = (
                float(g.x()),
                float(g.y()),
                float(g.x() + g.width()),
                float(g.y() + g.height()),
            )
        else:
            screen_rect_local = screen_rect

        dragging = hasattr(win, "is_dragging") and win.is_dragging
        if dragging:
            if hasattr(win, "sprite_anchor_offset"):
                ax, ay = win.sprite_anchor_offset
            else:
                ax = ay = 0.0
            pos = Vec2(win.x() + ax, win.y() + ay)
            body.motion.pos = pos
            body.motion.vel = Vec2(0.0, 0.0)
            if not body.physics.active:
                body.grab()
            body.drag_to(pos, now)
            state["was_dragging"] = True
            return

        if state["was_dragging"] and body.physics.active and body.physics.state == "held":
            body.release(now)
            state["was_dragging"] = False
            bus.emit(TriggerEvent.BODY_ACTION_DONE)

        world_snap = to_world(
            snap,
            screen_rect=screen_rect_local,
            pet_pos=body.motion.pos,
            monitors_rects=_all_monitor_rects(app),
        )
        world.update(world_snap)

        if args.mode != "auto":
            body.set_intent(_force_intent(args.mode, world_snap))
        elif args.no_llm or worker is None:
            # rule-only path
            if now - state["last_rule"] >= 4.0 or state["last_rule"] == 0.0:
                if body._done_signaled or state["last_rule"] == 0.0:
                    body.set_intent(rule_based(world_snap))
                    state["last_rule"] = now

        body.step(dt, world_snap)

        if hasattr(win, "set_world_pos"):
            win.set_world_pos(
                body.motion.pos.x,
                body.motion.pos.y,
                facing=body.motion.facing,
            )

        if args.debug and now - state["last_log"] > 1.5:
            state["last_log"] = now
            sp = getattr(player, "state", "?")
            print(
                f"[tick] verb={body.current_intent.verb.value} "
                f"anim={body.anim_state}->{sp} "
                f"pos=({body.motion.pos.x:.0f},{body.motion.pos.y:.0f})"
            )

    def _shutdown() -> None:
        if worker is not None:
            worker.stop()
        if thread is not None:
            thread.quit()
            thread.wait(2000)

    app.aboutToQuit.connect(_shutdown)

    timer = QTimer()
    timer.setInterval(16)
    timer.timeout.connect(tick)
    timer.start()

    # Ctrl+C → quit Qt cleanly (avoids KeyboardInterrupt mid-timer traceback)
    def _sigint(*_args) -> None:
        print("\nShutting down…")
        app.quit()

    try:
        signal.signal(signal.SIGINT, _sigint)
        signal.signal(signal.SIGTERM, _sigint)
    except Exception:
        pass

    sensors.tick()
    print("Running — Body + brain (mode=%s, no_llm=%s)" % (args.mode, args.no_llm))
    print("  Ctrl+C to quit")
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(0)
