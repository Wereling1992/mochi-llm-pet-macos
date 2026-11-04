# Assets

This repo **does not ship** the full cat sprite sheet (third-party art).

## Recommended art: Bow.Pixel «Cat 85+»

Download **Meow - Cat 85+ Animation** from itch.io (pay-what-you-want / often free):

**https://bowpixel.itch.io/meow-cat-85-animation**

After unzipping, you want at least one colour’s spritesheet PNG, for example:

- `Cat_Ginger.png` (or Grey / Grey_White, etc.)

Optional: the matching `.aseprite` if you regenerate the manifest yourself.

## Install into this project

```text
assets/bowpixel/
  Cat_Ginger.png          ← you download
  anim_manifest.yaml      ← copy from example (see below)
```

```bash
mkdir -p assets/bowpixel

# 1) Copy the PNG from the itch download into assets/bowpixel/
# 2) Manifest: either use the example shipped with this repo…
cp assets/bowpixel/anim_manifest.ginger.example.yaml \
   assets/bowpixel/anim_manifest.yaml

# …or keep anim_manifest.yaml if it already points at Cat_Ginger.png
```

Open `assets/bowpixel/anim_manifest.yaml` and confirm:

```yaml
sheet: Cat_Ginger.png
frame_size: [32, 32]
columns: 10
```

(`sheet` is relative to the manifest’s folder.)

## Run

```bash
python3 run.py --manifest assets/bowpixel/anim_manifest.yaml --scale 3
```

## Without Bow.Pixel

The app can use a tiny **placeholder** cat for smoke tests. Full animations need Cat 85+ (or any sheet that matches the manifest’s frame indices).

## License

Bow.Pixel assets remain under **their** license — follow itch.io / author terms.
Do not commit or re-upload the commercial sheet unless the license allows it.
