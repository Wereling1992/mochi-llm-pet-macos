#!/usr/bin/env python3
"""Overlay-only demo. Run from repo root:

    python3 tools/run_overlay_demo.py
"""
from __future__ import annotations
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

#!/usr/bin/env python3
"""macOS transparent pet overlay prototype.

    cd macos_overlay_proto
    python3 -m pip install -r requirements.txt
    python3 run_overlay.py

    # with coordinate debug prints:
    python3 run_overlay.py --debug

    # disable click-through entirely (always interactive):
    python3 run_overlay.py --no-click-through
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    if sys.platform != "darwin":
        print(
            "This prototype targets macOS (darwin).\n"
            f"Current platform: {sys.platform}",
            file=sys.stderr,
        )
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug",
        action="store_true",
        help="print cursor vs sprite rect every 0.5s",
    )
    parser.add_argument(
        "--no-click-through",
        action="store_true",
        help="never enable ignoresMouseEvents (always interactive)",
    )
    args = parser.parse_args()

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print(
            "PyQt6 not installed.\n"
            "  python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    from overlay import PetWindow

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    win = PetWindow(
        scale=1,
        click_through=not args.no_click_through,
        debug=args.debug,
    )
    screen = app.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        win.move(
            geo.x() + geo.width() - win.width() - 40,
            geo.y() + geo.height() - win.height() - 60,
        )
    win.show()
    win.raise_()
    win.activateWindow()

    print("Overlay running.")
    print("  1. You should see 'click me' / 'ready — drag me' above the cat")
    print("  2. Click and drag the orange cat — it must move")
    print("  3. Quick click = poke; wipe left-right = pet")
    if not args.no_click_through:
        print("  4. After that, moving away enables click-through")
    print("  Quit: Ctrl+C or close the process")
    if args.debug:
        print("  [debug mode on]")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
