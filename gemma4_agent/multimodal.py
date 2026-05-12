"""Helpers for OpenAI-compatible image and audio chat content."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def image_part(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{_b64(path)}"},
    }


def audio_part(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    fmt = path.suffix.lower().lstrip(".") or "wav"
    if fmt == "wave":
        fmt = "wav"
    return {
        "type": "input_audio",
        "input_audio": {"data": _b64(path), "format": fmt},
    }


def user_content(text: str, images: list[Path] | None = None, audios: list[Path] | None = None) -> str | list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for image in images or []:
        parts.append(image_part(image))
    for audio in audios or []:
        parts.append(audio_part(audio))
    if not parts:
        return text
    parts.append({"type": "text", "text": text})
    return parts
