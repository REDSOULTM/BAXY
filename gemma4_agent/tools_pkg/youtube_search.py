"""Resolución de YouTube (URL de watch + primer resultado de búsqueda), extraída
de tools.py (split del archivo-dios, 2026-06-19). Funciones puras de parseo +
una búsqueda HTTP contra el HTML público de YouTube; sin estado ni dependencias
del paquete (solo stdlib), así que no cicla con tools.py.
"""
from __future__ import annotations

import json
import re
import urllib.request
from urllib.parse import quote_plus


def _looks_like_youtube_watch_url(text: str) -> bool:
    return bool(re.search(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]{11}", text))


def _youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&autoplay=1"


def _youtube_first_result(query: str) -> dict[str, str] | None:
    if not query:
        return None
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read(2_000_000).decode("utf-8", errors="replace")
    except Exception:
        return None

    seen: set[str] = set()
    for video_id in re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', text):
        if video_id in seen:
            continue
        seen.add(video_id)
        if video_id.startswith(("UC", "PL")):
            continue
        title = _youtube_title_near_video_id(text, video_id)
        return {"video_id": video_id, "title": title or query}
    return None


def _youtube_title_near_video_id(text: str, video_id: str) -> str | None:
    pos = text.find(f'"videoId":"{video_id}"')
    if pos < 0:
        return None
    chunk = text[pos: pos + 5000]
    match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', chunk)
    if not match:
        match = re.search(r'"title":\{"simpleText":"([^"]+)"', chunk)
    if not match:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)
