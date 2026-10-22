"""Generate responsive WebP previews; keep the artist's originals untouched.

Optional tooling: python3 -m pip install Pillow
Run from any directory: python3 scripts/optimize_images.py
"""
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "assets" / "images"


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "main_art.png", ROOT / "render1.png"]
    sources += [ROOT / f"render{i}.jpg" for i in range(2, 16)]
    total = 0
    for source in sources:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            for width in (480, 960, 1600):
                preview = image.copy()
                preview.thumbnail((width, round(width * image.height / image.width)))
                target = DESTINATION / f"{source.stem}-{width}.webp"
                preview.save(target, "WEBP", quality=80, method=6)
                total += target.stat().st_size
    print(f"Generated {len(sources) * 3} previews: {total / 1024 / 1024:.2f} MiB")


if __name__ == "__main__":
    main()
