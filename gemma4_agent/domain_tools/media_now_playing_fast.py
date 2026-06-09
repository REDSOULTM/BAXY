"""now_playing (SMTC) in-process con `winsdk` — extraído de domain_tools/__init__.py
(2026-06-09, ratchet archivo-dios). La versión PowerShell+WinRT (Add-Type + AsTask)
tarda ~1.9s por la compilación/activación WinRT; winsdk lee el mismo
GlobalSystemMediaTransportControlsSessionManager in-process en ~10ms (~56x).

Devuelve el MISMO dict _ok(...) que la ruta PowerShell o None (-> caller cae al
PowerShell). Best-effort.
"""
from __future__ import annotations

from typing import Any, Optional


def media_now_playing_winsdk() -> Optional[dict[str, Any]]:
    from . import _ok
    try:
        import asyncio
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as _Mgr,
        )
    except Exception:
        return None

    def _enum_tail(v: Any) -> str:
        # 'MediaPlaybackType.MUSIC' -> 'Music'; '...PlaybackStatus.PLAYING' -> 'Playing'
        s = str(v)
        tail = s.rsplit(".", 1)[-1]
        return tail.capitalize() if tail else s

    async def _query():
        mgr = await _Mgr.request_async()
        sess = mgr.get_current_session()
        if sess is None:
            return {"has_session": False}
        props = await sess.try_get_media_properties_async()
        info = sess.get_playback_info()
        tl = sess.get_timeline_properties()
        ctrls = info.controls
        return {
            "has_session": True,
            "title": props.title, "artist": props.artist,
            "album_title": props.album_title,
            "source_app_user_model_id": sess.source_app_user_model_id,
            "playback_status": _enum_tail(info.playback_status),
            "playback_type": _enum_tail(info.playback_type) if info.playback_type is not None else None,
            "is_play_enabled": bool(ctrls.is_play_enabled),
            "is_pause_enabled": bool(ctrls.is_pause_enabled),
            "is_next_enabled": bool(ctrls.is_next_enabled),
            "is_previous_enabled": bool(ctrls.is_previous_enabled),
            "position_seconds": tl.position.total_seconds() if tl.position is not None else None,
            "end_seconds": tl.end_time.total_seconds() if tl.end_time is not None else None,
        }

    try:
        data = asyncio.run(_query())
    except Exception:
        return None
    if not data.get("has_session"):
        return _ok(has_session=False, note="no active media session", source="winsdk")
    return _ok(
        has_session=True, title=data.get("title"), artist=data.get("artist"),
        album=data.get("album_title"), source_app=data.get("source_app_user_model_id"),
        playback_status=data.get("playback_status"), playback_type=data.get("playback_type"),
        controls={"play": data.get("is_play_enabled"), "pause": data.get("is_pause_enabled"),
                  "next": data.get("is_next_enabled"), "previous": data.get("is_previous_enabled")},
        position_seconds=data.get("position_seconds"), end_seconds=data.get("end_seconds"),
        verified=True, evidence={"source": "Windows.Media.Control.GSMTCSM (winsdk)"},
    )


__all__ = ["media_now_playing_winsdk"]
