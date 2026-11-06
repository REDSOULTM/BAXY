"""BAXY's Steam trailer (documentacion/STEAM_PUBLICACION.md, section 4): 1920x1080, 30 fps, H.264 + AAC.

Valve wants an Early Access trailer that shows the product in use, so its middle is real takes of BAXY doing what a
person asked, each with the phrase said on screen. Around them, the avatar's shots animated with Higgsfield (Kling 3.0
Turbo from the store's key art): it wakes up, listens, and waves goodbye. Under all of it, an instrumental track (ElevenLabs
Music through Higgsfield) that drops when BAXY speaks in a take. A take not recorded yet becomes a card that names it,
so the cut can be watched before every take exists.

    py scripts/steam/make_trailer.py --lang es --shots D:\\BAXY-SteamBuild\\higgsfield\\video \\
        --takes D:\\BAXY-SteamBuild\\tomas\\es --music D:\\BAXY-SteamBuild\\higgsfield\\audio\\music.mp3 \\
        --output D:\\BAXY-SteamBuild\\trailer\\baxy_trailer_es.mp4

Steam shows each language its own trailer (the English one is the base): one cut per language, with its own texts and
its own takes, asked of BAXY in that language. --shots holds intro.mp4, listen.mp4 and outro.mp4; --takes holds what
grabar_tomas.ps1 records for each take: NN.mp4 (the desktop) and NN_baxy.mp4 (BAXY's window), laid out as a stream
scene (scene), and censura.json with what to blur on each desktop.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont
from make_screenshots import blur_chain, censura
from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[2]
FONT = next((ROOT / "src" / "Baxy.FieldUi" / "dist" / "assets").glob("chakra-petch-latin-600-normal-*.woff2"))
NIGHT = ROOT / "src" / "Baxy.FieldUi" / "public" / "bg" / "baxy-bgdark.jpg"
SIZE = "1920:1080"
FPS = 30


# BAXY's colours (the avatar's neon blue, its red core) and white.
WHITE, NEON, RED = "0xF5F8FF", "0x6EA0FF", "0xFF4D62"


@dataclass(frozen=True)
class Layer:
    """A piece of text, or with ``bar`` an accent bar of that width and height, that fades and slides in at ``start``
    seconds into its segment. A part that follows another on the same line takes x "after:<n>", n that part's index."""
    text: str
    size: int
    color: str
    x: str
    y: int
    start: float
    bar: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class Segment:
    kind: str  # "shot" (an avatar clip), "take" (a real recording) or "card" (text on the night background)
    source: str = ""
    caption: str = ""  # a take's phrase
    seconds: float = 0.0  # a card's length; for a shot, where to cut it (0: whole)
    layers: tuple[Layer, ...] = ()
    from_left: bool = False  # a wider shot cropped from its left edge (normalize)


# The cut, in order, in each language. A take's caption is what the person asks BAXY in it. The intro clip Kling made
# cuts to another background at 3.47 s: only its first 3.4 s are used, then the first card, then BAXY listening.
TEXTS = {
    "es": {
        "card1": ("Tu compañero", "que vive en ", "tu PC"),
        "listen": ("Le hablas.", "Lo hace.", ("Abre tus programas", "Maneja cualquier ventana", "Busca en la web por ti")),
        "takes": ["«Abre Spotify y pon lo-fi para estudiar»", "«En la calculadora calcula 37 por 12»",
                  "«Abre la configuración de colores y dime si el modo es claro u oscuro»", "«Sube el volumen al 40 %»",
                  "«Abre el Bloc de notas y escribe: lista, pan y leche»"],
        "card2": ("Local", "Privado", "Honesto"),
        "early": "Acceso anticipado",
        "wishlist": "Añádelo a tu lista de deseados",
        "pending": "Toma pendiente",
        "live": "EN VIVO", "ask": "TÚ LE PIDES", "real": "Grabación real", "faster": "más rápido",
    },
    "en": {
        "card1": ("Your companion", "that lives on ", "your PC"),
        "listen": ("You say it.", "It does it.", ("Opens your programs", "Works any window", "Searches the web for you")),
        "takes": ["“Open Spotify and play some lo-fi to study”", "“In the calculator, work out 37 times 12”",
                  "“Open the color settings and tell me if the mode is light or dark”", "“Turn the volume up to 40%”",
                  "“Open Notepad and type: list, bread and milk”"],
        "card2": ("Local", "Private", "Honest"),
        "early": "Early Access",
        "wishlist": "Add it to your wishlist",
        "pending": "Take pending",
        "live": "LIVE", "ask": "YOU ASK", "real": "Real recording", "faster": "faster",
    },
}


def cut_for(lang: str) -> list[Segment]:
    text = TEXTS[lang]
    first, second, accent = text["card1"]
    said, done, abilities = text["listen"]
    words = text["card2"]
    left = "160"
    # Card 1: the name as an eyebrow, the phrase large over two lines with «your PC» in BAXY's red, a red accent bar.
    card1 = (Layer("B   A   X   Y", 44, NEON, left, 330, 0.1), Layer(first, 128, WHITE, left, 400, 0.25),
             Layer(second, 128, WHITE, left, 545, 0.45), Layer(accent, 128, RED, "after:2", 545, 0.65),
             Layer("", 0, RED, left, 712, 0.85, bar=(240, 8)))
    # BAXY listening: on the empty left, what it is about, then three things it does, one after another.
    listen = [Layer(said, 96, WHITE, "100", 250, 0.5), Layer(done, 96, RED, "100", 365, 1.0)]
    for i, ability in enumerate(abilities):
        listen += [Layer("", 0, NEON, "104", 570 + i * 72, 1.7 + i * 0.45, bar=(14, 14)),
                   Layer(ability, 42, WHITE, "134", 555 + i * 72, 1.7 + i * 0.45)]
    # Card 2: three words with red dots between them, and the red accent bar.
    card2 = [Layer("B   A   X   Y", 44, NEON, left, 340, 0.1)]
    for i, word in enumerate(words):
        card2.append(Layer(word, 112, WHITE, left if i == 0 else f"after:{len(card2) - 1}", 410, 0.25 + i * 0.3))
        if i < len(words) - 1:
            card2.append(Layer("  ·  ", 112, RED, f"after:{len(card2) - 1}", 410, 0.25 + i * 0.3))
    card2.append(Layer("", 0, RED, left, 575, 1.3, bar=(240, 8)))
    outro = (Layer("BAXY", 150, WHITE, "100", 330, 0.2), Layer(text["early"], 60, NEON, "110", 520, 0.6),
             Layer(text["wishlist"], 36, RED, "110", 612, 1.4))
    return [
        Segment("shot", "intro.mp4", seconds=3.4, layers=(Layer("BAXY", 150, WHITE, "134", 390, 0.3),)),
        Segment("card", seconds=2.8, layers=card1),
        Segment("shot", "listen.mp4", layers=tuple(listen), from_left=True),
        *[Segment("take", f"{i:02d}.mp4", phrase) for i, phrase in enumerate(text["takes"], start=1)],
        Segment("card", seconds=3.2, layers=tuple(card2)),
        Segment("shot", "outro.mp4", layers=outro),
    ]


def ttf(folder: Path) -> Path:
    face = TTFont(str(FONT))
    face.flavor = None
    path = folder / "chakra.ttf"
    face.save(str(path))
    return path


# x264 with every core failed to allocate on the PC (2026-11-04, 5 GB of RAM free): a fixed number of threads.
VIDEO = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-threads", "6"]
# How long two segments overlap in their transition (transition).
FADE = 0.5
# A take longer than this has its middle sped up, with the speed on screen (scene): its start (the phrase sent) and
# its end (the answer and what changed) stay at real speed.
TAKE_MAX, TAKE_HEAD, TAKE_TAIL = 11.0, 2.5, 4.5

# The stream scene of a take, on the night background: the desktop on the left; on the right a column with BAXY's
# avatar as the streamer's camera and, under it, BAXY's own conversation panel as the chat (what it is doing, step by
# step); under the desktop, what the person asked. The window's parts as fractions of its capture (1600x1000 at the
# notebook's 125 %, grabar_tomas.ps1; the window's own wide shape, as the person sees it): the avatar's square,
# from the antenna to the chest, and the conversation panel's lower part.
DESK = (24, 24, 1472, 828)
CAM = (1520, 24, 376, 376)
CHAT = (1520, 416, 376, 640)
AVATAR_CROP = "crop=ih*0.80:ih*0.80:iw*0.218:ih*0.06"
CHAT_CROP = "crop=iw*0.255:ih*0.53:iw*0.737:ih*0.46"


def ffmpeg(*args: str, cwd: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, cwd=cwd)


def text_filter(work: Path, name: str, text: str, size: int, y: str, x: str = "(w-text_w)/2") -> str:
    """A drawtext read from a file, so quotes and «» need no escaping."""
    (work / f"{name}.txt").write_text(text, encoding="utf-8")
    return (f"drawtext=fontfile=chakra.ttf:textfile={name}.txt:fontsize={size}:fontcolor=0xF5F8FF"
            f":borderw=2:bordercolor=0x0B1220:shadowcolor=0x6EA0FF@0.6:shadowx=0:shadowy=0"
            f":x={x}:y={y}")


def layers_filter(work: Path, name: str, layers: tuple[Layer, ...]) -> str:
    """Each layer as a drawtext (or drawbox) that fades in over 0.35 s and slides up 18 px as it does."""
    faces: dict[int, ImageFont.FreeTypeFont] = {}
    filters: list[str] = []
    ends: list[int] = []  # where each layer ends, for a part that follows it on the same line
    for i, layer in enumerate(layers):
        x = str(ends[int(layer.x.split(":")[1])]) if layer.x.startswith("after:") else layer.x
        ease = f"min(1,max(0,(t-{layer.start})/0.35))"
        if layer.bar != (0, 0):
            width, height = layer.bar
            filters.append(f"drawbox=x={x}:y={layer.y}:w={width}:h={height}:color={layer.color}:t=fill"
                           f":enable='gte(t,{layer.start})'")
            ends.append(int(x) + width)
            continue
        if layer.size not in faces:
            faces[layer.size] = ImageFont.truetype(str(work / "chakra.ttf"), layer.size)
        ends.append(int(x) + round(faces[layer.size].getlength(layer.text)))
        (work / f"{name}_{i}.txt").write_text(layer.text, encoding="utf-8")
        filters.append(f"drawtext=fontfile=chakra.ttf:textfile={name}_{i}.txt:fontsize={layer.size}"
                       f":fontcolor={layer.color}:shadowcolor={NEON}@0.45:shadowx=0:shadowy=0:borderw=1"
                       f":bordercolor=0x0B1220:x={x}:y='{layer.y}+18*(1-{ease})':alpha='{ease}'")
    return ",".join(filters)


def normalize(chain: str, cover: bool, from_left: bool = False) -> str:
    """To 1920x1080: the avatar's art fills the frame (cropped, from its left edge when the robot stands right of
    centre, so the text keeps the left); a take is never cropped, only padded."""
    crop = f"crop={SIZE}:(iw-1920)*0.12:(ih-1080)/2" if from_left else f"crop={SIZE}"
    fit = (f"scale={SIZE}:force_original_aspect_ratio=increase,{crop}" if cover else
           f"scale={SIZE}:force_original_aspect_ratio=decrease,pad={SIZE}:(ow-iw)/2:(oh-ih)/2:color=0x05070F")
    return f"{fit},{chain + ',' if chain else ''}fps={FPS},format=yuv420p"


def frame(x: int, y: int, w: int, h: int, color: str = NEON) -> str:
    """A thin neon frame just outside a box, with a soft halo."""
    return (f"drawbox=x={x - 6}:y={y - 6}:w={w + 12}:h={h + 12}:color={color}@0.18:t=6,"
            f"drawbox=x={x - 2}:y={y - 2}:w={w + 4}:h={h + 4}:color={color}@0.9:t=2")


def scene(segment: Segment, index: int, desktop: Path, window: Path, work: Path, text: dict) -> Path:
    """A take as a stream scene (DESK, CAM, CHAT), its middle sped up past TAKE_MAX with the speed on screen."""
    out = work / f"seg{index:02d}.mp4"
    length = min(duration(desktop), duration(window))
    dx, dy, dw, dh = DESK
    cx, cy, cw, ch = CAM
    tx, ty, tw, th = CHAT
    (work / f"ask{index}.txt").write_text(text["ask"], encoding="utf-8")
    (work / f"say{index}.txt").write_text(segment.caption, encoding="utf-8")
    (work / f"live{index}.txt").write_text(f"BAXY  ·  {text['live']}", encoding="utf-8")
    (work / f"real{index}.txt").write_text(text["real"], encoding="utf-8")
    font = "fontfile=chakra.ttf"
    # The phrase as large as fits under the desktop (56 px at most).
    say = 56
    while say > 30 and ImageFont.truetype(str(work / "chakra.ttf"), say).getlength(segment.caption) > dw - 60:
        say -= 2
    graph = [
        f"[0:v]scale=2112:-2,crop=1920:1080:'96*t/{length:.2f}':'54*t/{length:.2f}',"
        f"eq=brightness=-0.04:saturation=1.1,fps={FPS},trim=0:{length:.3f}[night]",
        *blur_chain("1:v", censura(desktop.parent).get(desktop.stem, []), "clean"),
        f"[clean]fps={FPS},scale={dw}:{dh}:flags=lanczos,setsar=1[desk]",
        f"[2:v]fps={FPS},split=2[w1][w2]",
        f"[w1]{AVATAR_CROP},scale={cw}:{ch}:flags=lanczos,setsar=1[cam]",
        f"[w2]{CHAT_CROP},scale={tw}:-2:flags=lanczos,crop={tw}:min(ih\\,{th}):0:ih-min(ih\\,{th}),setsar=1[chat]",
        f"[night][desk]overlay={dx}:{dy}:shortest=1[a]",
        f"[a][cam]overlay={cx}:{cy}:shortest=1[b]",
        f"[b][chat]overlay={tx}:{ty}+{th}-overlay_h:shortest=1,"
        + ",".join([frame(*DESK), frame(*CAM, color=RED), frame(*CHAT)])
        # The camera's badge: a red dot that breathes, BAXY and «live».
        + f",drawbox=x={cx + 2}:y={cy + 2}:w=178:h=40:color=0x0B1220@0.85:t=fill"
        f",drawbox=x={cx + 16}:y={cy + 16}:w=12:h=12:color={RED}:t=fill:enable='lt(mod(t\\,1.2)\\,0.8)'"
        f",drawtext={font}:textfile=live{index}.txt:fontsize=20:fontcolor={WHITE}:x={cx + 38}:y={cy + 11}"
        # Under the desktop: what the person asked, large, with its eyebrow and the red accent bar.
        f",drawbox=x={dx}:y={dy + dh + 34}:w=8:h=150:color={RED}:t=fill"
        f",drawtext={font}:textfile=ask{index}.txt:fontsize=26:fontcolor={NEON}:x={dx + 30}:y={dy + dh + 40}"
        f",drawtext={font}:textfile=say{index}.txt:expansion=none:fontsize={say}:fontcolor={WHITE}:borderw=1:bordercolor=0x0B1220"
        f":shadowcolor={NEON}@0.45:shadowx=0:shadowy=0:x={dx + 30}:y={dy + dh + 86}"
        f",drawtext={font}:textfile=real{index}.txt:fontsize=22:fontcolor={WHITE}@0.6"
        f":x={dx + dw}-text_w:y={dy + dh + 44}[v]",
    ]
    if length > TAKE_MAX:
        middle = length - TAKE_HEAD - TAKE_TAIL
        factor = middle / (TAKE_MAX - TAKE_HEAD - TAKE_TAIL)
        (work / f"fast{index}.txt").write_text(f"×{factor:.0f}  {text['faster']}" if factor >= 1.5 else
                                               f"×{factor:.1f}  {text['faster']}", encoding="utf-8")
        end = length - TAKE_TAIL
        graph[-1] = graph[-1][:-3] + ",split=3[p1][p2][p3]"
        graph += [
            f"[p1]trim=0:{TAKE_HEAD},setpts=PTS-STARTPTS[h]",
            f"[p2]trim={TAKE_HEAD}:{end:.3f},setpts=(PTS-STARTPTS)/{factor:.4f},fps={FPS},"
            f"drawbox=x={dx + dw - 330}:y={dy + 20}:w=310:h=56:color=0x0B1220@0.85:t=fill,"
            f"drawtext={font}:textfile=fast{index}.txt:fontsize=30:fontcolor={WHITE}:x={dx + dw - 36}-text_w:y={dy + 33}[m]",
            f"[p3]trim={end:.3f},setpts=PTS-STARTPTS[e]",
            "[h][m][e]concat=n=3:v=1:a=0[v]",
        ]
    ffmpeg("-loop", "1", "-framerate", str(FPS), "-i", str(NIGHT), "-i", str(desktop), "-i", str(window),
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
           "-filter_complex", ";".join(graph), "-map", "[v]", "-map", "3:a",
           *VIDEO, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
           str(out), cwd=work)
    return out


def render(segment: Segment, index: int, shots: Path, takes: Path, work: Path, text: dict) -> Path:
    out = work / f"seg{index:02d}.mp4"
    encode = [*VIDEO, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", str(out)]
    silence = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    source = (shots if segment.kind == "shot" else takes) / segment.source
    window = source.with_name(source.stem + "_baxy.mp4")
    if segment.kind == "take" and source.is_file() and window.is_file():
        return scene(segment, index, source, window, work, text)
    if segment.kind == "card" or (segment.kind == "take" and not source.is_file()):
        seconds = segment.seconds or 3.0
        chain = (layers_filter(work, f"l{index}", segment.layers) if segment.kind == "card" else
                 text_filter(work, f"t{index}", f"{text['pending']} · {segment.caption}", 46, "(h-text_h)/2"))
        # The night background drifts closer while the card is on screen.
        drift = f"scale=2112:-2,crop=1920:1080:'96*t/{seconds}':'54*t/{seconds}',eq=brightness=0.04:saturation=1.15"
        ffmpeg("-loop", "1", "-framerate", str(FPS), "-i", str(NIGHT), *silence, "-t", str(seconds),
               "-vf", normalize(f"{drift},{chain}", cover=True), *encode, cwd=work)
        return out
    # A shot's text sits on the empty left side the key art leaves; a take's phrase sits low, as a subtitle.
    if segment.kind == "shot":
        chain = layers_filter(work, f"l{index}", segment.layers) if segment.layers else ""
    else:
        chain = text_filter(work, f"t{index}", segment.caption, 54, "h-text_h-70")
    # A shot's own sound (the video model's ambience) would fight the music: only a take keeps its sound, BAXY's voice.
    has_audio = segment.kind == "take" and bool(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0",
         str(source)], capture_output=True, text=True, check=True).stdout.strip())
    cut = ["-t", str(segment.seconds)] if segment.kind == "shot" and segment.seconds else []
    inputs = [*cut, "-i", str(source)] + ([] if has_audio else silence)
    maps = ["-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0"]
    ffmpeg(*inputs, *maps, "-vf", normalize(chain, cover=segment.kind == "shot", from_left=segment.from_left),
           *encode, cwd=work)
    return out


def duration(path: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip())


def transition(before: Segment, after: Segment) -> str:
    """The avatar listening opens in a circle and slides up into what follows; take to take slides sideways; the rest
    cross-fades."""
    if after.source == "listen.mp4":
        return "circleopen"
    if before.source == "listen.mp4":
        return "smoothup"
    if before.kind == "take" and after.kind == "take":
        return "smoothleft"
    return "fade"


def join(cut: list[Segment], parts: list[Path], work: Path) -> Path:
    """The segments one after another, each overlapping the next by FADE seconds through a transition."""
    inputs: list[str] = []
    for part in parts:
        inputs += ["-i", part.name]
    # xfade wants both sides alike: the same size, pixel format, frame rate and time base (a sped-up take's differs).
    graph = [f"[{i}:v]scale={SIZE},setsar=1,fps={FPS},format=yuv420p,settb=AVTB[n{i}]" for i in range(len(parts))]
    video, audio, length = "[n0]", "[0:a]", duration(parts[0])
    for i in range(1, len(parts)):
        offset = length - FADE
        graph.append(f"{video}[n{i}]xfade=transition={transition(cut[i - 1], cut[i])}:duration={FADE}"
                     f":offset={offset:.3f}[v{i}]")
        graph.append(f"{audio}[{i}:a]acrossfade=d={FADE}[a{i}]")
        video, audio, length = f"[v{i}]", f"[a{i}]", offset + duration(parts[i])
    out = work / "cut.mp4"
    ffmpeg(*inputs, "-filter_complex", ";".join(graph), "-map", video, "-map", audio, *VIDEO, "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", out.name, cwd=work)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Tráiler de BAXY para Steam.")
    parser.add_argument("--lang", choices=sorted(TEXTS), required=True)
    parser.add_argument("--shots", type=Path, required=True)
    parser.add_argument("--takes", type=Path, required=True)
    parser.add_argument("--music", type=Path, help="pista instrumental bajo todo el tráiler")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="baxy-trailer-") as folder:
        work = Path(folder)
        ttf(work)
        cut = cut_for(args.lang)
        parts = [render(s, i, args.shots.resolve(), args.takes.resolve(), work, TEXTS[args.lang])
                 for i, s in enumerate(cut)]
        joined = join(cut, parts, work)
        if not args.music:
            ffmpeg("-i", joined.name, "-c", "copy", "-movflags", "+faststart", str(args.output.resolve()), cwd=work)
        else:
            length = duration(joined)
            # The music under everything, ducked by the takes' sound (BAXY's voice), fading out on the last frames.
            mix = (f"[0:a]asplit=2[voice][key];[1:a]atrim=0:{length:.3f},asetpts=PTS-STARTPTS,"
                   f"afade=t=out:st={max(length - 2.5, 0):.3f}:d=2.5,volume=0.8[music];"
                   "[music][key]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[ducked];"
                   "[ducked][voice]amix=inputs=2:duration=first:normalize=0[out]")
            ffmpeg("-i", "cut.mp4", "-i", str(args.music.resolve()), "-filter_complex", mix, "-map", "0:v",
                   "-map", "[out]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                   str(args.output.resolve()), cwd=work)
    missing = [s.source for s in cut_for(args.lang) if s.kind == "take" and not (args.takes / s.source).is_file()]
    print(f"{args.output}  tomas pendientes: {', '.join(missing) if missing else 'ninguna'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
