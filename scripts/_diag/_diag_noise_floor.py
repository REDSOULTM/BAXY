"""Diagnóstico EN VIVO de la auto-calibración del piso de ruido del micrófono.

Mide tu micrófono REAL y muestra qué umbral elegiría la calibración — para
confirmar que queda por encima del ruido de fondo (no dispara solo) y por debajo
de tu voz normal (no te ignora). Usa la MISMA lógica que el pipeline en runtime.

Uso (corré esto vos; no gasta cuota de LLM):
    python scripts/_diag/_diag_noise_floor.py

Fases (te va guiando):
  1. AMBIENTE — 3s en silencio (NO hables): mide el piso de ruido del mic.
  2. VOZ      — 3s hablando normal: mide el RMS de tu voz.
Al final compara el umbral calibrado contra ambos y dice si quedó bien.
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np  # noqa: E402

# Importamos el módulo de calibración por ruta directa (sin disparar el __init__
# del paquete voice, que carga audio/onnx pesado).
import importlib.util as _ilu  # noqa: E402
_root = Path(__file__).resolve().parent.parent.parent
_spec = _ilu.spec_from_file_location(
    "noise_calibration", _root / "gemma4_agent" / "voice" / "noise_calibration.py")
nc = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(nc)

SAMPLE_RATE = 16000
WINDOW = int(0.20 * SAMPLE_RATE)   # 0.20s ~ el _RMS_WINDOW_S del pipeline


def _show_default_input():
    """Muestra cuál es el micrófono DEFAULT del sistema (el que SIEMPRE se usa)."""
    import sounddevice as sd
    try:
        default_in = sd.default.device[0] if sd.default.device else None
        if default_in is not None and default_in >= 0:
            name = sd.query_devices(default_in)["name"]
            print(f"Micrófono DEFAULT del sistema: [{default_in}] {name}")
            return
    except Exception:
        pass
    print("Micrófono DEFAULT del sistema: (no se pudo leer)")


def _wasapi_default_input():
    """(device_index, native_samplerate) del mic default vía WASAPI. WASAPI es el
    host API moderno de Windows: respeta el default real. NO resamplea solo, así
    que hay que capturar a SU tasa nativa (típico 48000) y resamplear después.
    (None, None) si no hay WASAPI."""
    import sounddevice as sd
    try:
        for h in sd.query_hostapis():
            if "WASAPI" in h["name"]:
                di = h.get("default_input_device", -1)
                if di is not None and di >= 0:
                    sr = int(sd.query_devices(di)["default_samplerate"])
                    return di, sr
    except Exception:
        pass
    return None, None


_REC_DEVICE = None     # WASAPI default si existe, si no None
_REC_NATIVE_SR = SAMPLE_RATE  # tasa nativa del device (se captura a esta y se resamplea)


def _resample_to_16k(audio: np.ndarray, src_sr: int) -> np.ndarray:
    """Resamplea int16 mono de src_sr -> 16000. scipy si está (anti-alias), si no
    decimación lineal. Probado: 48k->16k preserva el nivel."""
    if src_sr == SAMPLE_RATE or audio.size == 0:
        return audio
    try:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(int(src_sr), SAMPLE_RATE)
        up, down = SAMPLE_RATE // g, int(src_sr) // g
        return resample_poly(audio.astype(np.float64), up, down).astype(np.int16)
    except Exception:
        # fallback sin scipy: interpolación lineal
        n_out = int(round(audio.size * SAMPLE_RATE / src_sr))
        idx = np.linspace(0, audio.size - 1, n_out)
        return np.interp(idx, np.arange(audio.size), audio).astype(np.int16)


def _record(seconds: float) -> np.ndarray:
    import sounddevice as sd
    # Capturar a la tasa NATIVA del device (WASAPI no resamplea 48k->16k solo) y
    # resamplear a 16k en software. SIEMPRE el default del sistema (vía WASAPI).
    raw = sd.rec(int(seconds * _REC_NATIVE_SR), samplerate=_REC_NATIVE_SR,
                 channels=1, dtype="int16", device=_REC_DEVICE)
    sd.wait()
    return _resample_to_16k(raw.reshape(-1), _REC_NATIVE_SR)


def _window_rms(audio: np.ndarray) -> list[float]:
    out = []
    for i in range(0, len(audio) - WINDOW, WINDOW):
        x = audio[i:i + WINDOW].astype(np.float64)
        out.append(float(np.sqrt(np.mean(x * x))))
    return out


def main() -> int:
    global _REC_DEVICE, _REC_NATIVE_SR
    try:
        import sounddevice as sd  # noqa: F401
    except Exception as exc:
        print(f"sounddevice no disponible: {exc}")
        return 1

    print("=== Diagnóstico del piso de ruido del micrófono ===\n")
    # SIEMPRE el default del sistema (regla del user). Solo lo MOSTRAMOS.
    _show_default_input()
    # Capturamos por WASAPI a su tasa nativa (el default MME no soporta 16kHz y
    # devuelve ceros) y resampleamos a 16k.
    _REC_DEVICE, _native = _wasapi_default_input()
    if _REC_DEVICE is not None and _native:
        _REC_NATIVE_SR = _native
        try:
            print(f"Capturando vía WASAPI: [{_REC_DEVICE}] "
                  f"{sd.query_devices(_REC_DEVICE)['name']} @ {_native}Hz -> 16k")
        except Exception:
            pass
    else:
        print("WASAPI no disponible -> uso el default crudo a 16k.")
    # NOTA: la detección de mic-muteado (pycaw/COM) vive en el PIPELINE real, no
    # acá — en este script de diag llamarla deja un puntero COM que comtypes
    # libera mal (access violation cosmético). El medidor en vivo de abajo ya
    # detecta 'captura 0' (que es lo que un mic muteado produce), así que no la
    # necesitamos en el diag.
    print()

    # Medidor en vivo 2s: si esto queda en ~0 (y el mic NO está muteado), revisá
    # permisos de micrófono de Windows. Te deja VER que entra audio antes de medir.
    print("Medidor en vivo 2s — hablá o hacé ruido y mirá si el nivel sube:")
    probe = _record(2.0)
    probe_peak = max(_window_rms(probe)) if len(probe) > WINDOW else 0.0
    print(f"  nivel pico captado: {probe_peak:.0f}", end="")
    if probe_peak < 5:
        print("  <- ¡CASI 0! El mic no está capturando.")
        print("     Probá otro device: python scripts/_diag/_diag_noise_floor.py <nº>")
        print("     y revisá permisos de micrófono de Windows (Configuración > Privacidad > Micrófono).")
        return 1
    print("  OK, entra audio.\n")

    print("FASE 1/2 — AMBIENTE: quedate en SILENCIO 3 segundos (no hables)...")
    time.sleep(1.0)
    amb = _record(3.0)
    amb_rms = _window_rms(amb)
    cal = nc.NoiseFloorCalibrator()
    cal.calibrate(amb_rms)
    print(f"  piso de ruido (percentil): {cal.noise_floor:.0f}")
    print(f"  -> UMBRAL que se elegiría: {cal.threshold:.0f}\n")

    print("FASE 2/2 — VOZ: hablá normal 3 segundos (decí cualquier cosa)...")
    time.sleep(1.0)
    voz = _record(3.0)
    voz_rms = _window_rms(voz)
    voz_peak = max(voz_rms) if voz_rms else 0.0
    print(f"  pico de tu voz: {voz_peak:.0f}\n")

    print("=== VEREDICTO ===")
    t = cal.threshold or 0
    floor = cal.noise_floor or 0
    print(f"  ruido {floor:.0f}  <  UMBRAL {t:.0f}  <  voz {voz_peak:.0f}")
    if voz_peak < 5:
        print("  capta tu voz: NO SE MIDIÓ (no se detectó voz — ¿hablaste? probá de nuevo)")
        print("  (el umbral relativo está bien; faltó tu voz para confirmar el veredicto)")
        return 0
    ok_noise = t > floor                 # umbral por encima del ruido
    ok_voice = voz_peak > t              # tu voz por encima del umbral
    print(f"  no dispara con ruido: {'SÍ' if ok_noise else 'NO (umbral <= ruido)'}")
    print(f"  capta tu voz:         {'SÍ' if ok_voice else 'NO (voz <= umbral; hablá más fuerte/cerca o bajá GEMMA4_VOICE_GATE_FACTOR)'}")
    if ok_noise and ok_voice:
        margen = (voz_peak - t) / max(1.0, t - floor)
        print(f"  -> OK: umbral entre ruido y voz (margen de voz {margen:.1f}x). Bien para tu mic.")
    else:
        print("  -> Ajustá GEMMA4_VOICE_GATE_FACTOR (default 1.6) y volvé a correr.")
    return 0


if __name__ == "__main__":
    _rc = main()
    # os._exit evita que los finalizadores __del__ de comtypes (objetos COM de
    # pycaw) corran tras desinicializarse COM -> sin eso, el intérprete escupe un
    # 'access violation' COSMÉTICO al cerrar (post-resultado). Salimos limpio.
    import sys as _sys
    _sys.stdout.flush()
    _sys.stderr.flush()
    os._exit(int(_rc or 0))
