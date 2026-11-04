#!/usr/bin/env python3
"""Perception-only demo. Run from repo root:

    python3 tools/run_perception_demo.py
"""
from __future__ import annotations
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#!/usr/bin/env python3
"""Live demo of the macOS perception prototype.

Run on a real Mac:

    cd macos_perception_proto
    python3 -m pip install -r requirements.txt
    python3 run_demo.py

Permissions:
  - Cursor + idle + window bounds: no special permission needed.
  - Window titles (kCGWindowName): often empty until you grant
    System Settings → Privacy & Security → Screen Recording to Terminal
    (or whatever host runs this script).
  - Clipboard content hashing works without extra permission.
"""

from __future__ import annotations

import argparse
import sys
import time


def main() -> int:
    if sys.platform != "darwin":
        print(
            "This prototype only runs on macOS (darwin).\n"
            f"Current platform: {sys.platform}\n"
            "Copy the folder to a Mac and run it there.",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser(description="macOS perception prototype demo")
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="seconds between full dumps (default 1.0)",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=12,
        help="how many windows to print (default 12)",
    )
    args = parser.parse_args()

    try:
        from perception import MacSensors
    except ImportError as e:
        print(
            "Import failed. Did you install dependencies?\n"
            "  pip install -r requirements.txt\n"
            f"Detail: {e}",
            file=sys.stderr,
        )
        return 1

    sensors = MacSensors(fast_ms=50, medium_ms=300)
    print("macOS perception prototype — Ctrl+C to stop")
    print("Tip: grant Screen Recording to this terminal for window titles.\n")

    try:
        while True:
            snap = sensors.tick()
            # force a rebuild path once per interval for the dump
            sensors._rebuild()
            snap = sensors.snapshot

            print("─" * 60)
            print(
                f"cursor=({snap.cursor.x:.0f}, {snap.cursor.y:.0f})  "
                f"idle={snap.idle_seconds:.1f}s  "
                f"windows={len(snap.windows)}"
            )
            if snap.clipboard_hash:
                print(f"clipboard changed → {snap.clipboard_hash}")
            if snap.error:
                print(f"ERROR: {snap.error}")

            if snap.foreground:
                fg = snap.foreground
                print(
                    f"foreground: [{fg.process}] {fg.title!r}  "
                    f"rect=({fg.rect.left:.0f},{fg.rect.top:.0f}"
                    f"-{fg.rect.right:.0f},{fg.rect.bottom:.0f})"
                )
            else:
                print("foreground: (none)")

            print("top windows:")
            for w in snap.windows[: args.max_windows]:
                mark = "★" if w.is_foreground else " "
                title = w.title if w.title else "—"
                print(
                    f"  {mark} z={w.z:02d}  {w.process:20s}  "
                    f"{title[:40]:40s}  "
                    f"{w.rect.width:.0f}x{w.rect.height:.0f}"
                )
            print()
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        print("\nbye")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
