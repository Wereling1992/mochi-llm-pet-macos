# Bow.Pixel Cat 85+ setup

## 1. Download art

https://bowpixel.itch.io/meow-cat-85-animation  
(pay-what-you-want / free)

Unzip. You need at least one colour pair, e.g.:

- `Cat_Ginger.aseprite`
- `Cat_Ginger.png`   (or the exported spritesheet PNG)

## 2. Put files here

Recommended layout under `macos_combined_proto/assets/bowpixel/`:

```
bowpixel/
  Cat_Ginger.png
  Cat_Ginger.aseprite   # optional but needed to regenerate manifest
  anim_manifest.yaml    # generated
```

## 3. Generate manifest

From `macos_combined_proto`:

```bash
python3 tools/aseprite_to_manifest.py \
  assets/bowpixel/Cat_Ginger.aseprite \
  assets/bowpixel/Cat_Ginger.png \
  --out assets/bowpixel/anim_manifest.yaml \
  --sheet-rel Cat_Ginger.png
```

If you only have the PNG and not the .aseprite, copy the example:

```bash
cp assets/bowpixel/anim_manifest.ginger.example.yaml assets/bowpixel/anim_manifest.yaml
```

Then open `anim_manifest.yaml` and set:

```yaml
sheet: Cat_Ginger.png
```

(The example assumes frame layout from the official export; if frames look wrong, regenerate from .aseprite.)

## 4. Run

```bash
cd macos_combined_proto
python3 run_combined.py --manifest assets/bowpixel/anim_manifest.yaml --scale 3
```

Other colours: `Cat_Grey` / `Cat_Grey_White` — same steps, change filenames.
