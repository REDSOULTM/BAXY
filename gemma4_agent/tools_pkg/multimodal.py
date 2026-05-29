"""Helpers for OpenAI-compatible image and audio chat content."""

from __future__ import annotations

import base64
import logging
import mimetypes
import threading
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Image processing counter (item 1.7 del roadmap de optimizacion).
#
# Issue ggml-org/llama.cpp #21690: el mmproj de Gemma 4 produce un
# leak progresivo (~6.4 MiB/imagen GPU + 46 MiB host/request). En
# 6 GB de VRAM se confirma OOM tras ~60-80 imagenes. Mitigacion:
# emitir un evento "vision_relaunch" cuando el counter alcance
# IMAGE_RELAUNCH_THRESHOLD (40 imagenes, margen sobre el OOM real),
# para que el orchestrator (NO agent.py) decida recyclar el server.
#
# El counter es module-level + thread-safe. El callback es opcional:
# si nadie se registra, solo loggeamos. Esto evita acoplar
# multimodal.py al manager del server.
# ------------------------------------------------------------------

IMAGE_RELAUNCH_THRESHOLD = 40

_image_counter_lock = threading.Lock()
_image_counter = 0
_relaunch_callback: Callable[[int], None] | None = None
# Image count at which we last FIRED the relaunch callback. The fire condition
# is current >= threshold AND we haven't already fired for THIS threshold band
# (i.e. current - _last_fired_at >= threshold). This fixes the prior `== `
# check: if the recycle failed or returned early WITHOUT resetting the counter,
# `==` never matched again (41 != 40) so the leak grew unbounded with no retry.
# Now an un-reset counter re-fires every `threshold` more images (coarse retry),
# and a successful reset (counter -> 0) re-arms immediately.
_last_fired_at = 0


def set_vision_relaunch_callback(cb: Callable[[int], None] | None) -> None:
    """Registra el callback que se invoca al cruzar IMAGE_RELAUNCH_THRESHOLD.

    El callback recibe el conteo actual de imágenes; tipicamente
    reciclara el llama-server. NULL desinstala el callback.
    El orchestrator (agent_runner / server) lo registra al arrancar.
    """
    global _relaunch_callback
    _relaunch_callback = cb


def reset_image_counter() -> None:
    """Reset del counter, llamado por el orchestrator tras recyclar.

    Tambien re-arma el latch de relanzamiento (_last_fired_at) para que el
    proximo cruce del umbral vuelva a disparar."""
    global _image_counter, _last_fired_at
    with _image_counter_lock:
        _image_counter = 0
        _last_fired_at = 0


def get_image_counter() -> int:
    """Lectura del counter actual (para tests y telemetria)."""
    with _image_counter_lock:
        return _image_counter


def _bump_image_counter() -> None:
    """Incrementa el counter; si cruza el umbral, dispara el callback Y
    publica al bus de eventos.

    Doble notificacion intencional:
    - El callback es para el orchestrator que lo registra explicitamente
      (typicamente agent_runner.py).
    - El evento al bus es para listeners genericos (UI, telemetria) y
      como fallback si nadie registro callback.
    """
    global _image_counter, _last_fired_at
    with _image_counter_lock:
        _image_counter += 1
        current = _image_counter
        # Fire on reaching the threshold and again every `threshold` images
        # after that if no reset happened (a failed/early recycle leaves the
        # counter climbing — we must keep retrying, not go silent forever).
        crossed = (current >= IMAGE_RELAUNCH_THRESHOLD
                   and current - _last_fired_at >= IMAGE_RELAUNCH_THRESHOLD)
        if crossed:
            _last_fired_at = current

    if not crossed:
        return

    # 1) Publish al bus (best-effort; si events_bus no importable, ok).
    try:
        from ..infra.events_bus import BUS
        BUS.publish({
            "kind": "vision_threshold_reached",
            "image_count": current,
            "threshold": IMAGE_RELAUNCH_THRESHOLD,
            "issue": "ggml-org/llama.cpp#21690",
        })
    except Exception as exc:
        logger.debug("event bus publish failed: %s", exc)

    # 2) Callback si esta registrado.
    if _relaunch_callback is not None:
        try:
            _relaunch_callback(current)
        except Exception as exc:
            logger.warning("vision_relaunch callback raised: %s", exc)


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def image_part(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    _bump_image_counter()
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
