"""Reanudar el VIDEO/MEDIA ACTUAL en vez de abrir una búsqueda nueva.

Extraído de domain_tools/__init__.py (2026-06-08, ratchet archivo-dios). Cuando el
usuario pide "seguí/reanudá/poné" el video o media ACTUAL sin nombrar un título o
target de búsqueda, no inventamos una query de YouTube: detectamos la sesión de
media en curso (Windows SMTC) y la reanudamos. La detección es ESTRUCTURAL (raíces
de palabra multi-idioma + filler), espejo de `_is_generic_music_query`; un solo
token de contenido real hace la query explícita ("video de gatos", "despacito"
siguen buscando normal).

Los constantes base (`_GENERIC_CONTENT_ROOTS`, `_GENERIC_FILLER_WORDS`) y los
helpers de resultado (`_ok`, `_err`, `_media_now_playing`) viven en
domain_tools/__init__.py; se importan a nivel de función para no crear un ciclo de
import en tiempo de carga.
"""
from __future__ import annotations

import functools
import unicodedata
from typing import Any, Callable

# current-video nouns / playback state; prefix match cubre conjugaciones.
_VIDEO_EXTRA_ROOTS = (
    "video", "clip", "youtube", "watch", "viendo", "vist", "ultim", "last",
    "current", "actual", "paus", "resume", "rean", "continu",
)
_CURRENT_MEDIA_FILLER_EXTRA = frozenset({
    "si", "yes", "sim", "oui", "ja", "este", "esta", "esto", "ese", "esa",
    "eso", "this", "that", "it", "my", "mi", "now", "ahora", "vi", "veo",
    "saw", "seen", "estoy", "estas", "estan", "i", "am", "we", "are",
    "currently", "lo", "la", "le", "el", "the", "que", "estaba", "estabas",
    "estaban", "estuve", "was", "were",
})
_CURRENT_MEDIA_RESUME_ROOTS = (
    "pon", "reproduc", "play", "resume", "rean", "continu", "sigue", "segu",
    "toca", "dale",
)


@functools.lru_cache(maxsize=1)
def _video_roots() -> tuple[str, ...]:
    from . import _GENERIC_CONTENT_ROOTS
    return (*_GENERIC_CONTENT_ROOTS, *_VIDEO_EXTRA_ROOTS)


@functools.lru_cache(maxsize=1)
def _current_media_filler() -> frozenset:
    from . import _GENERIC_FILLER_WORDS
    return _GENERIC_FILLER_WORDS | _CURRENT_MEDIA_FILLER_EXTRA


def fold_media_words(text: str) -> list[str]:
    raw = unicodedata.normalize("NFKD", str(text or "").casefold())
    chars: list[str] = []
    for ch in raw:
        if unicodedata.combining(ch):
            continue
        chars.append(ch if ch.isalnum() else " ")
    return [w for w in "".join(chars).split() if w]


def is_generic_video_query(query: str) -> bool:
    """True when a YouTube query refers to current/generic video, not a title.

    This mirrors _is_generic_music_query: a single real content token makes the
    query explicit, so "video de gatos" and "despacito" still search normally.
    """
    if not query or not query.strip():
        return True
    words = fold_media_words(query)
    if not words:
        return True
    if len(words) > 8:
        return False
    roots = _video_roots()
    filler = _current_media_filler()
    for w in words:
        if w in filler:
            continue
        if any(w.startswith(root) for root in roots):
            continue
        return False
    return True


def looks_like_current_video_resume_request(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    words = fold_media_words(raw)
    if not words:
        return False
    if "?" in raw or (words and words[0] in {"que", "what", "which", "cual"}):
        return False
    if not any(
        w.startswith(root)
        for w in words
        for root in _CURRENT_MEDIA_RESUME_ROOTS
    ):
        return False
    return is_generic_video_query(raw)


def maybe_resume_current_video(
    provider: str,
    query: str,
    executor: Callable[..., Any],
) -> dict[str, Any] | None:
    from . import _media_now_playing, _ok, _err
    if provider not in {"youtube", "yt", "browser"}:
        return None
    if not is_generic_video_query(query):
        return None

    now = _media_now_playing()
    if not isinstance(now, dict) or not now.get("ok") or not now.get("has_session"):
        return None

    playback_type = str(now.get("playback_type") or "").casefold()
    if playback_type == "music":
        return None

    playback_status = str(now.get("playback_status") or "").casefold()
    if playback_status == "playing":
        return _ok(
            action="status",
            provider="current_media",
            requested_provider=provider,
            query=query,
            now_playing=now,
            played=True,
            status="done",
            verified=True,
            completion_status="current_media_already_playing",
            note="Current media session is already playing; no new YouTube search was opened.",
        )

    controls = now.get("controls") if isinstance(now.get("controls"), dict) else {}
    if controls and controls.get("play") is False:
        return None

    result = executor("audio", {"action": "media_play_pause"})
    if not isinstance(result, dict):
        result = {"ok": bool(result), "raw": result}
    if result.get("ok") is False:
        return _err(
            "could not resume current media session",
            action="resume",
            provider="current_media",
            requested_provider=provider,
            query=query,
            now_playing=now,
            resume_result=result,
            status=result.get("status") or "failed",
            verified=False,
            completion_status="current_media_resume_failed",
        )
    return _ok(
        action="resume",
        provider="current_media",
        requested_provider=provider,
        query=query,
        now_playing=now,
        resume_result=result,
        played=True,
        status=result.get("status") or "dispatched",
        verified=result.get("verified"),
        completion_status="resumed_current_media",
        note="Resumed the existing media session instead of opening a new YouTube search.",
    )


__all__ = [
    "fold_media_words",
    "is_generic_video_query",
    "looks_like_current_video_resume_request",
    "maybe_resume_current_video",
]
