"""Create WebP previews without modifying original artwork.

Optional tooling: Pillow. Run: python3 tools/optimize_images.py
The static site itself needs no Python packages or build step.
"""
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "media" / "previews"


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    originals = [ROOT / "main_art.png", ROOT / "render1.png"]
    originals += [ROOT / f"render{i}.jpg" for i in range(2, 16)]
    originals += [ROOT / f"render{i}.png" for i in (16, 17)]
    total = 0
    for source in originals:
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original)
            # Some .jpg uploads are PNGs. Dropping alpha exposes hidden edge
            # colors, creating a pale outline around transparent artwork.
            has_alpha = ('A' in image.getbands() and image.getchannel('A').getextrema()[0] < 255)
            has_alpha |= 'transparency' in image.info
            image = image.convert("RGBA" if has_alpha else "RGB")
            widths = (480, 960) if source.stem == "main_art" else (480, 960, 1600)
            for width in widths:
                preview = image.copy()
                preview.thumbnail((width, round(width * image.height / image.width)))
                target = OUTPUT / f"{source.stem}-{width}.webp"
                preview.save(target, "WEBP", quality=90 if width == 1600 else 86, method=6)
                total += target.stat().st_size
    print(f"Preview files: {total / 1024 / 1024:.2f} MiB; originals unchanged")


if __name__ == "__main__":
    main()
