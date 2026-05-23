"""Probar Parakeet-TDT-0.6b-v3 (sherpa-onnx, CPU) con TU micrófono, EN VIVO.

NO toca el pipeline de producción (que sigue usando Whisper). Graba del mic y
transcribe con Parakeet mostrando la transcripción PARCIAL en tiempo real
(re-transcribe el audio acumulado cada ~1.2s mientras hablás).

Uso:
    python scripts/probar_parakeet_mic.py                 # elige mic por defecto
    python scripts/probar_parakeet_mic.py --list          # listar micrófonos
    python scripts/probar_parakeet_mic.py --device 53     # forzar un mic
    python scripts/probar_parakeet_mic.py --hotwords      # con biasing de nombres

Enter para empezar a grabar, Enter de nuevo para cortar. 'q'+Enter para salir.
"""
from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "data" / "stt_eval" / "sherpa" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
SR = 16000  # Parakeet espera 16k


def build_recognizer(use_hotwords: bool):
    import sherpa_onnx
    kw = dict(
        encoder=str(MD / "encoder.int8.onnx"), decoder=str(MD / "decoder.int8.onnx"),
        joiner=str(MD / "joiner.int8.onnx"), tokens=str(MD / "tokens.txt"),
        num_threads=4, model_type="nemo_transducer", decoding_method="greedy_search",
    )
    if use_hotwords:
        hw = MD / "_mic_hotwords.txt"
        hw.write_text("Chrome :2.0\nSteam :2.0\nSpotify :2.0\nDiscord :2.0\n"
                      "Netflix :2.0\nDisney :2.0\nYouTube :2.0\nGemma :2.5\n", encoding="utf-8")
        kw.update(decoding_method="modified_beam_search", max_active_paths=8,
                  modeling_unit="bpe", bpe_vocab=str(MD / "bpe.vocab"),
                  hotwords_file=str(hw), hotwords_score=1.5)
    return sherpa_onnx.OfflineRecognizer.from_transducer(**kw)


def _resample_16k(audio_f32: np.ndarray, sr_in: int) -> np.ndarray:
    if sr_in == SR:
        return audio_f32
    from math import gcd
    import scipy.signal
    g = gcd(sr_in, SR)
    return scipy.signal.resample_poly(audio_f32, SR // g, sr_in // g).astype(np.float32)


def transcribe(rec, audio_f32_16k: np.ndarray) -> str:
    if audio_f32_16k.size < int(0.2 * SR):
        return ""
    s = rec.create_stream()
    s.accept_waveform(SR, audio_f32_16k)
    rec.decode_stream(s)
    return s.result.text.strip()


_VAD = None


def _trim_silence(audio_f32_16k: np.ndarray) -> np.ndarray:
    """Recorta el silencio lateral con el MISMO VAD que prod (Silero).

    Crítico: un clip de 39s mayormente silencio hace ALUCINAR a Parakeet
    ('abre Steam' -> 'Habristi'). Prod recorta antes de transcribir; el A/B
    debe medir lo que el motor realmente recibe. Si no hay VAD, no recorta."""
    global _VAD
    try:
        import sys as _sys
        _sys.path.insert(0, str(ROOT))
        if _VAD is None:
            from gemma4_agent.voice.vad import SileroVAD
            _VAD = SileroVAD()
            _VAD.load()
        _VAD.reset()
        i16 = np.clip(audio_f32_16k * 32768.0, -32768, 32767).astype(np.int16)
        trimmed = _VAD.trim_silence(i16)
        if trimmed is not None and trimmed.size >= int(0.08 * SR):
            return trimmed.astype(np.float32) / 32768.0
    except Exception:
        pass
    return audio_f32_16k


def record_live(rec, device, native_sr: int):
    """Graba hasta Enter mostrando SOLO la barra de nivel del mic (no texto).

    Parakeet es OFFLINE: re-transcribir audio incompleto da parciales-basura
    inestables ('Habristi' por 'abre Steam') que NO representan la calidad
    real. La transcripción correcta es la del clip COMPLETO, que se hace al
    cortar (en main). Acá solo confirmamos visualmente que el mic capta."""
    import sounddevice as sd
    import sys
    chunks: list[np.ndarray] = []
    stop = threading.Event()

    def _cb(indata, n, t, status):
        chunks.append(indata.copy().reshape(-1).astype(np.float32) / 32768.0)

    def _wait_enter():
        input(); stop.set()

    print("  🎙️  grabando... (hablá; Enter para cortar)", flush=True)
    threading.Thread(target=_wait_enter, daemon=True).start()
    last_len = 0
    with sd.InputStream(samplerate=native_sr, channels=1, dtype="int16",
                         device=device, callback=_cb):
        while not stop.is_set():
            time.sleep(0.08)
            if chunks:
                # nivel = RMS de la ÚLTIMA ventana (no del acumulado), para que
                # la barra reaccione a lo que decís AHORA, no al promedio total.
                recent = np.concatenate(chunks[-6:])
                lvl = int(min(10, np.sqrt(np.mean(recent ** 2)) * 200))
                line = f"  [{'█'*lvl}{'·'*(10-lvl)}] grabando…"
                pad = max(0, last_len - len(line))
                sys.stdout.write("\r" + line + " " * pad)
                sys.stdout.flush()
                last_len = len(line)
    sys.stdout.write("\r" + " " * (last_len + 2) + "\r")  # limpiar línea
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return _resample_16k(np.concatenate(chunks), native_sr)


# Lista de comandos para el modo --guided. El script te DICTA cada uno, vos lo
# repetís, y se guarda tu texto esperado (ground-truth) + lo que Parakeet oyó.
# Cubre: apps/juegos/servicios en inglés (lo crítico), streaming, artistas,
# canciones, y comandos en español puro (control). Diversidad de verbos.
GUIDED_COMMANDS = [
    # --- abrir apps (nombres en inglés) ---
    "abre Steam", "abre Chrome", "abre Spotify", "abre Discord", "abre WhatsApp",
    "abrime Firefox", "andá a Telegram", "lanzá Visual Studio Code", "abre OBS",
    "abre Twitch", "abre Slack", "ejecutá Photoshop", "abre Notion", "abre Brave",
    # --- juegos ---
    "lanzá Counter-Strike", "abre Marvel Rivals", "abre Cyberpunk",
    "pon Hollow Knight", "abre Among Us", "lanzá Minecraft",
    # --- streaming (título en plataforma) ---
    "pon Stranger Things en Netflix", "pon Daredevil en Disney Plus",
    "reproduce The Boys en Prime Video", "pon House of the Dragon en HBO Max",
    "pon Breaking Bad en Netflix", "abre YouTube",
    # --- artistas / canciones ---
    "pon una canción de Bad Bunny", "reproduce Benson Boone en Spotify",
    "pon Michael Jackson", "reproduce Bohemian Rhapsody", "pon Karol G",
    "reproduce Blinding Lights de The Weeknd",
    # --- español puro (control: NO debe corromperse) ---
    "sube el volumen", "baja el volumen al mínimo", "qué hora es",
    "pausa la música", "cierra la ventana", "qué día es hoy",
    "mándale un mensaje a Juan", "cuánta batería me queda",
    "pon el temporizador en cinco minutos", "siguiente canción",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hotwords", action="store_true")
    ap.add_argument("--guided", action="store_true",
                     help="te dicta comandos y guarda el ground-truth (para A/B)")
    ap.add_argument("--set2", action="store_true",
                     help="usa el segundo bloque de 42 comandos (amplía el dataset)")
    ap.add_argument("--list", action="store_true", help="listar micrófonos y salir")
    ap.add_argument("--device", type=int, default=None, help="índice del mic a usar")
    args = ap.parse_args()

    import sounddevice as sd
    if args.list:
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                print(f"  [{i}] {d['name'][:50]} (sr={int(d['default_samplerate'])})")
        return 0

    device = args.device if args.device is not None else sd.default.device[0]
    native_sr = int(sd.query_devices(device)["default_samplerate"])
    print(f"Mic: [{device}] {sd.query_devices(device)['name'][:40]} @ {native_sr}Hz "
          f"-> resample a {SR}Hz")

    if not MD.exists():
        print(f"FALTA el modelo en {MD}"); return 1
    print("Cargando Parakeet-TDT-0.6b-v3 (CPU)...", flush=True)
    t0 = time.time()
    rec = build_recognizer(args.hotwords)
    print(f"Listo en {time.time()-t0:.1f}s. Modo: {'hotwords' if args.hotwords else 'greedy'}")

    # --- Grabación de la sesión para banco de prueba futuro ---
    # Cada clip se guarda en data/stt_eval/real_mic/ + manifest.tsv (audio +
    # transcripción de Parakeet + duración). Reusable como held-out de VOZ REAL.
    import scipy.io.wavfile as wavf
    import datetime
    rec_dir = ROOT / "data" / "stt_eval" / "real_mic"
    rec_dir.mkdir(parents=True, exist_ok=True)
    manifest = rec_dir / "manifest.tsv"
    if not manifest.exists():
        manifest.write_text("file\texpected\tparakeet_text\tdur_s\tmode\tts\n", encoding="utf-8")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Grabando sesión en {rec_dir}\n")

    # --set2 implica modo guiado con el segundo bloque de comandos.
    if args.set2:
        args.guided = True
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from guided_commands_set2 import GUIDED_COMMANDS_SET2
        queue = [c[0] for c in GUIDED_COMMANDS_SET2]  # solo el texto a decir
    else:
        queue = list(GUIDED_COMMANDS) if args.guided else None
    if args.guided:
        print(f"MODO GUIADO: te dicto {len(queue)} comandos. Para cada uno: Enter, "
              f"lo decís, Enter para cortar. Se guarda tu texto como ground-truth.\n"
              f"(Enter vacío = repetir el mismo; 's' = saltar; 'q' = terminar)\n")

    n = 0
    idx = 0
    while True:
        if args.guided:
            if idx >= len(queue):
                print("¡Terminaste la lista! 🎉"); break
            expected = queue[idx]
            print(f"  [{idx+1}/{len(queue)}] DECÍ:  «{expected}»")
            cmd = input("    Enter para grabar (s=saltar, q=salir): ").strip().lower()
            if cmd == "q":
                break
            if cmd == "s":
                idx += 1; continue
        else:
            expected = ""
            cmd = input("Enter para grabar (o 'q' para salir): ").strip().lower()
            if cmd == "q":
                break
        a16_raw = record_live(rec, device, native_sr)
        dur_raw = a16_raw.size / SR
        if a16_raw.size < int(0.2 * SR):
            print("  (clip muy corto / sin audio — repetí)\n"); continue
        # Recortar silencio lateral (como prod) ANTES de transcribir: evita
        # que segundos de silencio hagan alucinar a Parakeet.
        a16 = _trim_silence(a16_raw)
        dur = a16.size / SR
        peak = float(np.max(np.abs(a16)))
        t0 = time.time()
        final = transcribe(rec, a16)
        el = (time.time() - t0) * 1000
        print(f"  Parakeet → {final!r}")
        trim_note = f", recortado {dur_raw:.1f}s→{dur:.1f}s" if dur_raw - dur > 0.3 else ""
        print(f"    ({dur:.1f}s, pico={peak:.2f}, {el:.0f}ms{trim_note})" +
              ("  ⚠️ pico bajo: ¿mic? probá --list/--device" if peak < 0.02 else "") + "\n")
        fn = f"mic_{stamp}_{n:03d}.wav"
        wavf.write(str(rec_dir / fn), SR,  # guardar el clip RECORTADO (lo transcrito)
                   np.clip(a16 * 32768.0, -32768, 32767).astype(np.int16))
        with open(manifest, "a", encoding="utf-8") as mf:
            exp = expected.replace("\t", " ")
            par = final.replace("\t", " ").replace("\n", " ")
            mf.write(f"{fn}\t{exp}\t{par}\t{dur:.1f}\t{'hotwords' if args.hotwords else 'greedy'}\t{stamp}\n")
        n += 1
        if args.guided:
            idx += 1
    if n:
        print(f"\nGuardados {n} clips en {rec_dir}/manifest.tsv. "
              f"{'La columna expected es tu ground-truth (modo guiado).' if args.guided else 'Corregí expected a mano si querés ground-truth.'}")

    hw = MD / "_mic_hotwords.txt"
    if hw.exists():
        hw.unlink()
    print("listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
