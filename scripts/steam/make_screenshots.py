"""BAXY's store screenshots (documentacion/STEAM_PUBLICACION.md, section 8): one 1920x1080 PNG per take.

Valve asks that screenshots show the product as it is, without marketing text over them. Each one is a take's
desktop at the moment of the answer, with BAXY's whole window over it in a lower corner, as a person would have it
open (on the side the take left quiet, so it does not hide what changed): real pixels from the two recordings grabar_tomas.ps1 makes (NN.mp4, the desktop, and NN_baxy.mp4, the window).
Anything personal the desktop showed (an account name, an e-mail) is blurred with the take's boxes in censura.json
(censura below), the same ones the trailer uses.

    py scripts/steam/make_screenshots.py --takes D:\\BAXY-SteamBuild\\tomas\\es --output D:\\BAXY-SteamBuild\\tienda\\capturas\\es
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

# How far before the end of the take the frame is taken: the answer is on screen, and the take has not closed yet.
BEFORE_END = 2.0
WINDOW_HEIGHT = 560  # BAXY's wide window over the desktop, about half its size on the notebook
MARGIN = 28


def duration(path: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip())


def frame(video: Path, at: float) -> Image.Image:
    png = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(png)).convert("L")


def quiet_side(desktop: Path, at: float, size: tuple[int, int]) -> str:
    """The lower corner where BAXY's window (``size``) hides least: the one with less detail (text, controls) on the
    desktop at that moment. The wallpaper is smooth, so an app's window is what has edges. "left" or "right"."""
    change = frame(desktop, at).filter(ImageFilter.FIND_EDGES)
    width, height = change.size
    w, h = size
    top = height - h - MARGIN
    left = ImageStat.Stat(change.crop((MARGIN, top, MARGIN + w, height - MARGIN))).mean[0]
    right = ImageStat.Stat(change.crop((width - w - MARGIN, top, width - MARGIN, height - MARGIN))).mean[0]
    return "left" if left < right else "right"


def censura(takes: Path) -> dict[str, list[list[int]]]:
    """The boxes to blur on each take's desktop, in its own 1920x1080 pixels: {"01": [[x, y, w, h], ...]}. A box
    with two more numbers, [x, y, w, h, from, to], is blurred only between those seconds of the take."""
    path = takes / "censura.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def blur_chain(label: str, boxes: list[list[float]], out: str, timed: bool = True) -> list[str]:
    """Filters that blur each box of ``label`` (a 1920x1080 stream) and name the result ``out``. A still (``timed``
    false) blurs every box, whatever its seconds."""
    if not boxes:
        return [f"[{label}]null[{out}]"]
    graph = [f"[{label}]split={len(boxes) + 1}[base]" + "".join(f"[c{i}]" for i in range(len(boxes)))]
    current = "base"
    for i, box in enumerate(boxes):
        x, y, w, h = (int(v) for v in box[:4])
        when = f":enable='between(t,{box[4]},{box[5]})'" if timed and len(box) == 6 else ""
        graph.append(f"[c{i}]crop={w}:{h}:{x}:{y},gblur=sigma=22:steps=3[b{i}]")
        graph.append(f"[{current}][b{i}]overlay={x}:{y}{when}[o{i}]")
        current = f"o{i}"
    graph.append(f"[{current}]null[{out}]")
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Capturas de BAXY para la tienda.")
    parser.add_argument("--takes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    boxes = censura(args.takes)
    # The corner is chosen by detail on the desktop; capturas.json ({"03": "left"}) fixes it for a take where the
    # choice hides what matters.
    chosen = args.takes / "capturas.json"
    sides = json.loads(chosen.read_text(encoding="utf-8")) if chosen.is_file() else {}
    made = []
    for desktop in sorted(args.takes.glob("[0-9][0-9].mp4")):
        window = desktop.with_name(desktop.stem + "_baxy.mp4")
        if not window.is_file():
            continue
        at = f"{max(duration(window) - BEFORE_END, 0):.2f}"
        source = frame(window, float(at)).size
        size = (round(source[0] * WINDOW_HEIGHT / source[1]), WINDOW_HEIGHT)
        side = sides.get(desktop.stem) or quiet_side(desktop, float(at), size)
        x = f"{MARGIN}" if side == "left" else f"W-w-{MARGIN}"
        shadow_x = f"{MARGIN + 10}" if x == f"{MARGIN}" else f"W-w-{MARGIN - 10}"
        out = args.output / f"captura_{desktop.stem}.png"
        graph = blur_chain("0:v", boxes.get(desktop.stem, []), "desk", timed=False) + [
            f"[1:v]scale=-2:{WINDOW_HEIGHT}:flags=lanczos,setsar=1[win]",
            # A soft shadow under the window, so it sits over the desktop.
            "[win]format=rgba,split[w][s];[s]drawbox=c=black@1:t=fill,gblur=sigma=18,colorchannelmixer=aa=0.55[shadow]",
            f"[desk][shadow]overlay={shadow_x}:H-h-{MARGIN - 14}[d]",
            f"[d][w]overlay={x}:H-h-{MARGIN}[v]",
        ]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", at, "-i", str(desktop), "-ss", at, "-i", str(window),
                        "-filter_complex", ";".join(graph), "-map", "[v]", "-frames:v", "1", str(out)], check=True)
        made.append(out.name)
    print(f"{args.output}: {', '.join(made) if made else 'ninguna toma con su ventana'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
