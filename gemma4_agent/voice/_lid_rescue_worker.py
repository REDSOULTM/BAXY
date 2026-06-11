"""Worker EFÍMERO del rescate LID: carga Whisper, transcribe UN wav y muere.

Existe por el target de hardware (8 GB RAM): Whisper-small residente cuesta
~686 MB (medido 2026-06-11) y hasta el unload in-process retiene ~418 MB en el
allocator. Un subproceso devuelve el 100% al SO al terminar. Importa
faster_whisper DIRECTO (no el paquete gemma4_agent) para que el arranque sea
lo más liviano posible.

Uso: python _lid_rescue_worker.py <wav_path> <language>
Salida: la transcripción por stdout (una línea, UTF-8). Exit 0 = ok.
"""
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print("", flush=True)
        return 2
    wav_path, language = sys.argv[1], sys.argv[2]
    try:
        from pathlib import Path

        from faster_whisper import WhisperModel

        # Mismo modelo/config que stt.py (DECODE_KWARGS + WHISPER_MODEL_DIR):
        # download_root compartido = sin re-descarga ni red en el target;
        # without_timestamps=False = anti-alucinación medido (ver stt.py).
        model = WhisperModel(
            "small", device="cpu", compute_type="int8", cpu_threads=4,
            download_root=str(Path.home() / ".gemma4" / "models" / "whisper"),
        )
        segments, _info = model.transcribe(
            wav_path, language=language, task="transcribe",
            beam_size=1, best_of=1, temperature=0.0,
            condition_on_previous_text=False, vad_filter=False,
            without_timestamps=False,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.flush()
        return 0
    except Exception as exc:  # el caller trata stdout vacío como fallo
        sys.stderr.write(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
