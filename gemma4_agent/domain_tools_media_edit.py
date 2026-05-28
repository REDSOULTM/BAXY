"""Media Edit (ffmpeg) domain tool — extracted from domain_tools.py (R2 sprint
2026-05-28).

Audio/video editing via ffmpeg. status reporta ffmpeg+ffprobe disponibles.
Cada action devuelve path output + exit_code + command. Lossless cuando es
posible (trim usa -c copy). EBU R128 loudnorm para normalize.

Funciones extraídas (10):
  media_edit_tool                 (entry, 9 acciones)
  _media_edit_probe               (ffprobe -show_format -show_streams)
  _media_edit_input               (validar path)
  _media_edit_output              (genera path en state/media_edit/)
  _run_ffmpeg                     (helper común con -y -hide_banner)
  _media_edit_trim                (lossless copy)
  _media_edit_concat              (demuxer + list file, escape '\\'')
  _media_edit_extract_audio       (mp3/aac/wav/flac/ogg/m4a)
  _media_edit_subtitles_extract   (-map 0:s:<track>)
  _media_edit_normalize           (loudnorm EBU R128)
  _media_edit_thumbnail
  _media_edit_transcode           (mp4/mkv/webm con codec adecuado)

Helpers desde domain_tools (lazy): _safe_name."""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from ._shared import _err, _ok
from .state import AgentState


__all__ = [
    "media_edit_tool",
    "_media_edit_probe",
    "_media_edit_input",
    "_media_edit_output",
    "_run_ffmpeg",
    "_media_edit_trim",
    "_media_edit_concat",
    "_media_edit_extract_audio",
    "_media_edit_subtitles_extract",
    "_media_edit_normalize",
    "_media_edit_thumbnail",
    "_media_edit_transcode",
]


def media_edit_tool(args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    """Compound tool for ffmpeg-based audio/video editing.

    Actions: status, trim, concat, extract_audio, subtitles_extract, normalize,
    thumbnail, transcode, probe. Each action returns the output path, ffmpeg
    exit code, and the command run.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
        return _ok(
            ffmpeg=bool(ffmpeg), ffmpeg_path=ffmpeg,
            ffprobe=bool(ffprobe), ffprobe_path=ffprobe,
            install_hint="winget install Gyan.FFmpeg",
        )
    ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if not ffmpeg:
        return _err(
            "ffmpeg is not installed",
            status="needs_dependency",
            install_hint="winget install Gyan.FFmpeg",
        )
    if action == "probe":
        return _media_edit_probe(args)
    if action == "trim":
        return _media_edit_trim(ffmpeg, args, state)
    if action == "concat":
        return _media_edit_concat(ffmpeg, args, state)
    if action == "extract_audio":
        return _media_edit_extract_audio(ffmpeg, args, state)
    if action == "subtitles_extract":
        return _media_edit_subtitles_extract(ffmpeg, args, state)
    if action == "normalize":
        return _media_edit_normalize(ffmpeg, args, state)
    if action == "thumbnail":
        return _media_edit_thumbnail(ffmpeg, args, state)
    if action == "transcode":
        return _media_edit_transcode(ffmpeg, args, state)
    return _err(
        "unknown media_edit action", action=action,
        valid_actions=[
            "status", "probe", "trim", "concat", "extract_audio",
            "subtitles_extract", "normalize", "thumbnail", "transcode",
        ],
        status="needs_user",
    )


def _media_edit_probe(args: dict[str, Any]) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not ffprobe:
        return _err("ffprobe is not installed", status="needs_dependency", install_hint="winget install Gyan.FFmpeg")
    path = _media_edit_input(args)
    if isinstance(path, dict):
        return path
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        return _err("ffprobe failed", stderr=proc.stderr, exit_code=proc.returncode)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _err("ffprobe returned invalid JSON", raw=proc.stdout[:500])
    return _ok(path=str(path), probe=data)


def _media_edit_input(args: dict[str, Any]) -> Path | dict[str, Any]:
    raw = str(args.get("path") or args.get("input") or args.get("src") or "").strip()
    if not raw:
        return _err("missing input path")
    path = Path(raw).expanduser()
    if not path.is_file():
        return _err("input file not found", path=str(path))
    return path


def _media_edit_output(args: dict[str, Any], state: AgentState, src: Path, suffix: str) -> Path:
    from .domain_tools_helpers import _safe_name
    raw = str(args.get("output") or args.get("dst") or args.get("out") or "").strip()
    if raw:
        p = Path(raw).expanduser()
    else:
        out_dir = state.path.parent / "media_edit"
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f"{_safe_name(src.stem)}_{int(time.time())}{suffix}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _run_ffmpeg(ffmpeg: str, cmd: list[str], timeout: int = 600) -> dict[str, Any]:
    proc = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *cmd], capture_output=True, text=True, timeout=timeout)
    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-3000:],
        "stderr": (proc.stderr or "")[-3000:],
        "command": ["ffmpeg", *cmd],
    }


def _media_edit_trim(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    start = str(args.get("start") or "0").strip()
    duration = str(args.get("duration") or "").strip()
    end = str(args.get("end") or "").strip()
    out = _media_edit_output(args, state, src, src.suffix)
    cmd: list[str] = ["-ss", start, "-i", str(src)]
    if duration:
        cmd.extend(["-t", duration])
    elif end:
        cmd.extend(["-to", end])
    cmd.extend(["-c", "copy", str(out)])
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), start=start, duration=duration or None, end=end or None, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_concat(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    raw_inputs = args.get("inputs")
    inputs: list[Any] = raw_inputs if isinstance(raw_inputs, list) else []
    if len(inputs) < 2:
        return _err("concat requires at least 2 inputs")
    paths: list[Path] = []
    for raw in inputs:
        p = Path(str(raw)).expanduser()
        if not p.is_file():
            return _err("concat input not found", path=str(p))
        paths.append(p)
    out = _media_edit_output(args, state, paths[0], paths[0].suffix)
    # ffmpeg concat demuxer expects a list file.
    list_file = out.with_suffix(".concat.txt")
    # T2-media_edit-concat-list-injection-045: escape `'` como `'\''` per
    # ffmpeg concat demuxer docs.
    list_file.write_text(
        "\n".join(f"file '{p.as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for p in paths) + "\n",
        encoding="utf-8",
    )
    cmd = ["-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    try:
        list_file.unlink()
    except OSError:
        pass
    return _ok(path=str(out), inputs=[str(p) for p in paths], verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_extract_audio(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    fmt = str(args.get("format") or "mp3").lower()
    if fmt not in {"mp3", "aac", "wav", "flac", "ogg", "m4a"}:
        return _err(f"unsupported audio format: {fmt}", supported=["mp3", "aac", "wav", "flac", "ogg", "m4a"])
    out = _media_edit_output(args, state, src, f".{fmt}")
    codec_map = {"mp3": "libmp3lame", "aac": "aac", "wav": "pcm_s16le", "flac": "flac", "ogg": "libvorbis", "m4a": "aac"}
    cmd = ["-i", str(src), "-vn", "-c:a", codec_map[fmt], str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), format=fmt, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_subtitles_extract(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    track = int(args.get("track", 0))
    out = _media_edit_output(args, state, src, ".srt")
    cmd = ["-i", str(src), "-map", f"0:s:{track}", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    if result["exit_code"] != 0:
        return _ok(
            path=str(out), src=str(src), track=track,
            verified=False, status="needs_verification",
            note="No embedded subtitle track at that index, or ffmpeg cannot extract this codec.",
            **result,
        )
    return _ok(path=str(out), src=str(src), track=track, verified=out.is_file() and out.stat().st_size > 0, size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_normalize(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    out = _media_edit_output(args, state, src, src.suffix)
    # EBU R128 loudnorm: I=-23 LUFS, TP=-2 dB, LRA=7. Single-pass.
    cmd = ["-i", str(src), "-af", "loudnorm=I=-23:TP=-2:LRA=7", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd, timeout=900)
    return _ok(path=str(out), src=str(src), filter="loudnorm I=-23 TP=-2 LRA=7", verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_thumbnail(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    at = str(args.get("at") or args.get("time") or "00:00:01").strip()
    out = _media_edit_output(args, state, src, ".png")
    cmd = ["-ss", at, "-i", str(src), "-frames:v", "1", str(out)]
    result = _run_ffmpeg(ffmpeg, cmd)
    return _ok(path=str(out), src=str(src), at=at, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)


def _media_edit_transcode(ffmpeg: str, args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    src = _media_edit_input(args)
    if isinstance(src, dict):
        return src
    fmt = str(args.get("format") or "mp4").lower()
    crf = int(args.get("crf", 23))
    preset = str(args.get("preset") or "medium")
    out = _media_edit_output(args, state, src, f".{fmt}")
    if fmt in {"mp4", "mkv", "webm"}:
        vcodec = "libvpx-vp9" if fmt == "webm" else "libx264"
        acodec = "libopus" if fmt == "webm" else "aac"
        cmd = ["-i", str(src), "-c:v", vcodec, "-preset", preset, "-crf", str(crf), "-c:a", acodec, str(out)]
    else:
        return _err(f"unsupported transcode format: {fmt}", supported=["mp4", "mkv", "webm"])
    result = _run_ffmpeg(ffmpeg, cmd, timeout=1800)
    return _ok(path=str(out), src=str(src), format=fmt, crf=crf, preset=preset, verified=result["exit_code"] == 0 and out.is_file(), size=out.stat().st_size if out.is_file() else 0, **result)
