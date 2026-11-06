"""BAXY's Steam store and library images (documentacion/STEAM_PUBLICACION.md, section 4), at Valve's sizes.

The key art is three images generated with Higgsfield (Nano Banana Pro) from frames of the avatar's own clips, so the
robot stays the product's: a wide one (21:9), a landscape one (16:9) and a vertical one (2:3), kept outside the repo
(D:\\BAXY-SteamBuild\\higgsfield\\key). Each store piece is a crop of one of them with BAXY's name set in the interface's
typeface (Chakra Petch, OFL-1.1) over the empty side the art leaves for it. The library hero carries no text, as Valve
asks; the library logo is the name alone on transparency.

    py scripts/steam/make_store_art.py D:\\BAXY-SteamBuild\\higgsfield\\key D:\\BAXY-SteamBuild\\tienda
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "src" / "Baxy.FieldUi"
ICON = ROOT / "scripts" / "brand" / "baxy-icon-256.png"
FONT = next((UI / "dist" / "assets").glob("chakra-petch-latin-600-normal-*.woff2"))
LANCZOS = Image.Resampling.LANCZOS

BLUE = (110, 160, 255)
RED = (255, 70, 90)


def font(size: int) -> ImageFont.FreeTypeFont:
    face = TTFont(str(FONT))
    face.flavor = None
    data = io.BytesIO()
    face.save(data)
    data.seek(0)
    return ImageFont.truetype(data, size)


def crop(art: Image.Image, size: tuple[int, int], focus: tuple[float, float]) -> Image.Image:
    """``art`` scaled to cover ``size`` and cut around ``focus`` (fractions of the art's width and height)."""
    width, height = size
    scale = max(width / art.width, height / art.height)
    scaled = art.resize((round(art.width * scale), round(art.height * scale)), LANCZOS)
    left = min(max(round(scaled.width * focus[0] - width / 2), 0), scaled.width - width)
    top = min(max(round(scaled.height * focus[1] - height / 2), 0), scaled.height - height)
    return scaled.crop((left, top, left + width, top + height)).convert("RGB")


def name(canvas: Image.Image, size: int, center: tuple[float, float], underline: bool = True) -> Image.Image:
    """BAXY's name in white, with the avatar's blue glow and a thin red line under it, centred on ``center``."""
    face = font(size)
    box = face.getbbox("BAXY")
    width, height = box[2] - box[0], box[3] - box[1]
    cx, cy = round(canvas.width * center[0]), round(canvas.height * center[1])
    x, y = cx - width // 2 - box[0], cy - height // 2 - box[1]
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), "BAXY", font=face, fill=BLUE + (255,))
    glow = glow.filter(ImageFilter.GaussianBlur(max(3, size // 12)))
    out = Image.alpha_composite(Image.alpha_composite(canvas.convert("RGBA"), glow), glow)
    draw = ImageDraw.Draw(out)
    draw.text((x, y), "BAXY", font=face, fill=(245, 248, 255, 255))
    if underline:
        line = cy + height // 2 + max(4, size // 9)
        draw.rectangle((cx - width // 3, line, cx + width // 3, line + max(2, size // 36)), fill=RED)
    return out.convert("RGB")


def logo(size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    face = font(round(size[1] * 0.62))
    box = face.getbbox("BAXY")
    x = (size[0] - (box[2] - box[0])) // 2 - box[0]
    y = (size[1] - (box[3] - box[1])) // 2 - box[1]
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((x, y), "BAXY", font=face, fill=BLUE + (200,))
    canvas = Image.alpha_composite(canvas, glow.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(canvas).text((x, y), "BAXY", font=face, fill=(245, 248, 255, 255))
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="Imágenes de la tienda de Steam de BAXY.")
    parser.add_argument("key", type=Path, help="carpeta con hero_a.png, wide_b.png y vertical_b.png")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    wide = Image.open(args.key / "hero_a.png")
    landscape = Image.open(args.key / "wide_b.png")
    vertical = Image.open(args.key / "vertical_b.png")

    # name: (art, size, crop focus, (title size, title center) or None)
    pieces = {
        "header_capsule_920x430.png": (landscape, (920, 430), (0.52, 0.42), (142, (0.27, 0.48))),
        "small_capsule_462x174.png": (landscape, (462, 174), (0.58, 0.40), (74, (0.27, 0.47))),
        "main_capsule_1232x706.png": (landscape, (1232, 706), (0.50, 0.50), (210, (0.27, 0.48))),
        "vertical_capsule_748x896.png": (vertical, (748, 896), (0.50, 0.42), (150, (0.50, 0.86))),
        "library_capsule_600x900.png": (vertical, (600, 900), (0.50, 0.50), (130, (0.50, 0.86))),
        "library_header_920x430.png": (landscape, (920, 430), (0.52, 0.42), (142, (0.27, 0.48))),
        "library_hero_3840x1240.png": (wide, (3840, 1240), (0.50, 0.44), None),
        "event_cover_800x450.png": (landscape, (800, 450), (0.50, 0.50), (130, (0.27, 0.48))),
        "event_header_1920x622.png": (wide, (1920, 622), (0.55, 0.44), (190, (0.24, 0.48))),
        # itch.io's cover (630x500, and at twice the size for sharp screens), from the same art.
        "itch/cover_630x500.png": (landscape, (630, 500), (0.60, 0.45), (96, (0.27, 0.50))),
        "itch/cover_1260x1000.png": (landscape, (1260, 1000), (0.60, 0.45), (192, (0.27, 0.50))),
    }
    (args.output / "itch").mkdir(exist_ok=True)
    for filename, (art, size, focus, title) in pieces.items():
        image = crop(art, size, focus)
        if title:
            image = name(image, title[0], title[1])
        image.save(args.output / filename)
    # The page background: Valve lays the page over it; only the wide art's empty nebula, dimmed and soft.
    nebula = wide.crop((0, 0, round(wide.width * 0.45), wide.height))
    background = crop(nebula, (1438, 810), (0.5, 0.5)).filter(ImageFilter.GaussianBlur(6))
    ImageEnhance.Brightness(background).enhance(0.8).save(args.output / "page_background_1438x810.png")
    logo((1280, 720)).save(args.output / "library_logo_1280x720.png")
    icon = Image.open(ICON).convert("RGBA")
    icon.save(args.output / "shortcut_icon_256x256.png")
    icon.resize((184, 184), LANCZOS).convert("RGB").save(args.output / "app_icon_184x184.jpg", quality=95)
    for path in sorted(args.output.glob("*.*")):
        if path.name.startswith("_"):
            continue
        with Image.open(path) as image:
            print(f"{path.name}\t{image.size[0]}x{image.size[1]}\t{path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
