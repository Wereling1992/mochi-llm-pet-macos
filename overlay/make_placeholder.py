"""Generate a simple placeholder cat spritesheet + mochi-compatible manifest.

Does not require external art. Replace assets/ with Bow.Pixel Cat 85+ later.
"""

from __future__ import annotations

from pathlib import Path


def generate(out_dir: Path) -> Path:
    """Write placeholder_cat.png + anim_manifest.yaml. Returns manifest path."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as e:
        raise RuntimeError("Pillow required: pip install Pillow") from e

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fw = fh = 32
    cols = 4
    # 3 rows: idle(0-3), walk(4-7), sit(8-11)
    rows = 3
    sheet = Image.new("RGBA", (fw * cols, fh * rows), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet)

    def cat_pose(frame_idx: int, phase: float, mode: str) -> None:
        row, col = divmod(frame_idx, cols)
        ox, oy = col * fw, row * fh
        # body
        cx, cy = ox + 16, oy + 18
        bob = int(1.5 * __import__("math").sin(phase * 6.28))
        if mode == "sit":
            cy += 2
        body = [cx - 8, cy - 6 + bob, cx + 8, cy + 8 + bob]
        draw.ellipse(body, fill=(255, 168, 90, 255), outline=(160, 90, 40, 255))
        # head
        hx, hy = cx, cy - 8 + bob
        draw.ellipse([hx - 7, hy - 7, hx + 7, hy + 7], fill=(255, 168, 90, 255), outline=(160, 90, 40, 255))
        # ears
        for s in (-1, 1):
            ex = hx + s * 5
            draw.polygon(
                [(ex, hy - 10), (ex - 3, hy - 3), (ex + 3, hy - 3)],
                fill=(255, 168, 90, 255),
                outline=(160, 90, 40, 255),
            )
        # eyes
        for s in (-1, 1):
            draw.ellipse([hx + s * 3 - 1, hy - 2, hx + s * 3 + 1, hy + 1], fill=(40, 30, 20, 255))
        # legs / walk offset
        if mode == "walk":
            leg = int(3 * __import__("math").sin(phase * 6.28 + frame_idx))
            draw.line([(cx - 4, cy + 6 + bob), (cx - 4, cy + 10 + bob + leg)], fill=(160, 90, 40, 255), width=2)
            draw.line([(cx + 4, cy + 6 + bob), (cx + 4, cy + 10 + bob - leg)], fill=(160, 90, 40, 255), width=2)
        elif mode == "sit":
            draw.ellipse([cx - 6, cy + 4 + bob, cx + 6, cy + 10 + bob], fill=(255, 150, 80, 255))
        # tail
        tw = 4 if mode != "walk" else int(4 * __import__("math").cos(phase * 6.28))
        draw.arc([cx + 6, cy - 4 + bob, cx + 14, cy + 6 + bob], 200, 320, fill=(160, 90, 40, 255), width=2)

    for i in range(4):
        cat_pose(i, i / 4.0, "idle")
    for i in range(4):
        cat_pose(4 + i, i / 4.0, "walk")
    for i in range(4):
        cat_pose(8 + i, i / 4.0, "sit")

    png_path = out_dir / "placeholder_cat.png"
    sheet.save(png_path)

    manifest = """# Placeholder cat — replace with Bow.Pixel Cat 85+ for real art
sheet: placeholder_cat.png
frame_size: [32, 32]
columns: 4
default_fps: 8
states:
  Idle_1: { from: 0, to: 3, fps: 6.0, loop: true }
  W_1: { from: 4, to: 7, fps: 10.0, loop: true }
  Sit_1: { from: 8, to: 11, fps: 5.0, loop: true }
  Dream: { from: 8, to: 11, fps: 3.0, loop: true }
  Fall: { from: 4, to: 4, fps: 10.0, loop: false }
  Attack_1: { from: 4, to: 7, fps: 14.0, loop: false }
aliases:
  idle: Idle_1
  walk: W_1
  run: W_1
  sit: Sit_1
  sleep: Dream
  fall: Fall
  pounce: Attack_1
  happy: Idle_1
  watch: Sit_1
"""
    man_path = out_dir / "anim_manifest.yaml"
    man_path.write_text(manifest, encoding="utf-8")
    return man_path


if __name__ == "__main__":
    p = generate(Path(__file__).resolve().parent.parent / "assets")
    print("wrote", p)
