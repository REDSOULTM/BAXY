"""B3b — earcon de progreso (sonido NO-VERBAL mientras una tool lenta corre).

Patrón de competidores (openclaw eventos `tool` en vivo): en vez de HABLAR
"buscando…"/"esperá" — que viola la regla de producto "nada enlatado" — emitimos un
sonido corto, suave y no-verbal cuando arranca una tool lenta (web/visión/browser,
~3s), para dar percepción de rapidez SIN texto enlatado ni dependencia de idioma.

Diseño/seguridad:
- Gated `GEMMA4_PROGRESS_EARCON` (default-off, opt-in hasta validar la NATURALIDAD
  por escucha — físico, lo valida el usuario).
- NO bloquea el turno: `sd.play(...)` es non-blocking (reproduce en background).
- Best-effort: cualquier error (sin sounddevice/sin device de audio) → no-op silencioso,
  nunca rompe el turno.
- Throttle: máx 1 earcon cada `_MIN_INTERVAL_S` (no spamear en cadenas de tools).
- Reproduce AUDIO (output a parlantes) — NO es input sintético, no cierra VS Code.
- Estructural: se dispara por la CLASE de tool (SLOW_TOOLS, por estado), no por keywords
  de idioma. Solo cuando hay contexto de voz (el caller pasa el sink/flag).
"""
import os
import time

# Tools "lentas" (network / visión / heavy) donde un earcon de progreso ayuda.
# Estructural (clase de tool), no por idioma. Las tools rápidas (audio/window/system)
# NO disparan earcon (no hay gap perceptible).
SLOW_TOOLS = frozenset({
    "web", "vision", "browser_real", "computer_use", "package", "maintenance",
    "download", "knowledge", "fact_check", "creative_local", "steam", "data_analysis",
    "document", "file_process",
})

_MIN_INTERVAL_S = 2.0
_last_earcon_ts = [0.0]  # mutable holder (module-level throttle)


def progress_earcon_enabled() -> bool:
    """Gate B3b. Default OFF (opt-in GEMMA4_PROGRESS_EARCON) hasta validar por escucha."""
    return (os.environ.get("GEMMA4_PROGRESS_EARCON", "0") or "0").strip().lower() not in {
        "0", "false", "no", "off"}


def _generate_tone():
    """Tono corto y suave: dos notas breves ascendentes (660→880 Hz) con fade in/out
    para evitar clicks. ~250ms total, volumen bajo (no molesto). float32 mono."""
    import numpy as np
    sr = 22050

    def _note(freq_hz: float, ms: int, vol: float = 0.16):
        n = int(sr * ms / 1000)
        t = np.linspace(0.0, ms / 1000.0, n, endpoint=False)
        wave = np.sin(2.0 * np.pi * freq_hz * t).astype("float32") * vol
        fade = max(1, int(sr * 0.008))  # 8ms fade evita clicks
        env = np.ones(n, dtype="float32")
        env[:fade] = np.linspace(0.0, 1.0, fade)
        env[-fade:] = np.linspace(1.0, 0.0, fade)
        return wave * env

    gap = np.zeros(int(sr * 0.04), dtype="float32")
    tone = np.concatenate([_note(660.0, 90), gap, _note(880.0, 110)])
    return tone, sr


def play_progress_earcon(*, force: bool = False) -> bool:
    """Reproduce el earcon de progreso si está habilitado. NON-BLOCKING + best-effort.

    Devuelve True si se disparó, False si gateado-off / throttled / sin audio.
    `force=True` saltea el throttle (para tests). Nunca lanza excepción.
    """
    if not progress_earcon_enabled():
        return False
    try:
        now = time.monotonic()
        if not force and (now - _last_earcon_ts[0]) < _MIN_INTERVAL_S:
            return False
        import sounddevice as sd
        tone, sr = _generate_tone()
        sd.play(tone, sr)  # non-blocking: reproduce en background, no espera
        _last_earcon_ts[0] = now
        return True
    except Exception:
        return False  # sin device / sin sounddevice / error -> silencioso


def reset_throttle() -> None:
    """Resetea el throttle (para tests)."""
    _last_earcon_ts[0] = 0.0
