# mochi-llm-pet-macos

macOS port of [mochi-llm-pet](https://github.com/NatBrian/mochi-llm-pet): a desktop cat driven by perception + optional LLM.

**Platform:** macOS only (Apple Silicon and Intel should work; developed around M1-class Macs).

## Layout

```text
run.py              entry point
perception/         Quartz window/cursor/idle sensors
overlay/            transparent always-on-top pet window (PyQt6)
deskpet/            upstream body / brain / memory / types + macOS adapters
assets/             sprite sheets + anim_manifest
config.example.toml copy to config.toml
```

## Setup

```bash
cd mochi-llm-pet-macos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.toml config.toml
```

### Permissions

- **Screen Recording** (required for window list / screenshots)
- Accessibility (recommended)

Grant them to **Terminal** (or whatever runs Python) in System Settings.

### LLM

Default is local Ollama (`provider = "ollama"`). Start Ollama and pull a model, or set a cloud provider + API key in `config.toml` / env (`OPENAI_API_KEY`, etc.).

If the provider is unreachable, the pet falls back to rule-based behaviour.

### Sprites (Cat 85+)

This project expects **Bow.Pixel «Cat 85+»** art. It is **not** bundled — download it yourself:

1. Open https://bowpixel.itch.io/meow-cat-85-animation  
2. Download / unzip **Meow - Cat 85+ Animation**  
3. Copy e.g. `Cat_Ginger.png` → `assets/bowpixel/Cat_Ginger.png`  
4. Manifest:

```bash
cp assets/bowpixel/anim_manifest.ginger.example.yaml \
   assets/bowpixel/anim_manifest.yaml
```

Details: [`assets/README.md`](assets/README.md) and [`assets/bowpixel/README.md`](assets/bowpixel/README.md).

## Run

```bash
python3 run.py --manifest assets/bowpixel/anim_manifest.yaml --scale 3
```

Useful flags:

- `--debug` — hitbox outline + status labels
- `--no-llm` — rule-based only
- `--mode sit_front|follow_cursor|idle|auto`

Quit with Ctrl+C.

## Optional demos

```bash
python3 tools/run_perception_demo.py
python3 tools/run_overlay_demo.py
```

## Credits

- Upstream: [NatBrian/mochi-llm-pet](https://github.com/NatBrian/mochi-llm-pet)
- This tree is a macOS-focused packaging of perception + overlay + deskpet wiring.
