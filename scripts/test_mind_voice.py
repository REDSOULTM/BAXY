"""Gate 7 (parte headless) — voz al cerebro sin micrófono humano.

Genera locuciones ES/EN/spanglish con SAPI (voces de Windows), las pasa por
el camino ASR del motor de voz del sidecar después de una activación ya
autorizada (Silero VAD → segmentación por silencio → Parakeet int8) inyectando
el audio en lugar del micrófono, y verifica que el texto transcrito coincida
(normalizado, con tolerancia de puntuación) con la referencia.

Contrato medido — "voz al cerebro": el transcript (tras el corrector
fonético heredado) debe resolver exactamente el efecto esperado en la frontera
explícita que usa el producto. El router de embeddings congelado se conserva
como diagnóstico sin autoridad. La igualdad textual exacta NO es el contrato:
la decisión productiva tolera la variación del STT por diseño.

Qué acredita: STT real, VAD real, segmentación real, corrector real y routing
real. Qué NO acredita: micrófono físico/acústica del usuario (sesión guiada
pendiente-por-entorno; un paso: ejecutar la app con la mente configurada y
hablar).

Salida: artifacts/product/mind_voice_gate.json
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import unicodedata
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "artifacts" / "product" / "mind_voice_gate.json"
# (idioma, LCID SAPI, locución, ruta esperada del router, exige wake)
CASES = [
    ("es", "80A", "Baxy, pon el volumen al cincuenta por ciento",
     ("operation", "audio.volume", None), True),
    ("es", "80A", "pon el volumen al cincuenta por ciento",
     ("operation", "audio.volume", None), False),
    ("es", "80A", "crea una nota que diga comprar café",
     ("operation", "note.create", None), False),
    ("en", "409", "Baxy, how much disk space do I have left",
     ("operation", "system.status", {"scope": "disk"}), True),
    ("en", "409", "mute the sound please",
     ("operation", "audio.mute", None), False),
    ("spanglish", "80A", "oye Baxy check el volumen de la compu",
     ("operation", "audio.status", {}), True),
]

SAMPLE_RATE = 16_000


# Equivalencias de normalización inversa de texto (ITN): Parakeet emite
# números/porcentajes en dígitos («50%») donde la referencia hablada dice
# «cincuenta por ciento» — son la misma locución. «baxi» es el alias fonético
# documentado del nombre (fuera del vocabulario del STT).
_ITN = {
    "cincuenta": "50",
    "por ciento": "%",
    "percent": "%",
    "baxi": "baxy",
}


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    for spoken, written in _ITN.items():
        stripped = stripped.replace(spoken, written)
    collapsed = " ".join(re.sub(r"[^\w\s%]", " ", stripped).split())
    return collapsed.replace(" %", "%")


def synthesize(language_code: str, text: str) -> np.ndarray:
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    path = Path(temporary.name)
    temporary.close()
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        token = next(
            candidate
            for candidate in voice.GetVoices()
            if str(candidate.GetAttribute("Language")).upper() == language_code
        )
        voice.Voice = token
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(str(path), 3, False)  # SSFMCreateForWrite
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()
        with wave.open(str(path), "rb") as source:
            source_rate = source.getframerate()
            channels = source.getnchannels()
            if source.getsampwidth() != 2:
                raise RuntimeError("SAPI no produjo PCM16")
            audio = np.frombuffer(
                source.readframes(source.getnframes()),
                dtype=np.int16,
            )
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
        audio = audio.astype(np.float32) / 32768.0
    finally:
        path.unlink(missing_ok=True)
        pythoncom.CoUninitialize()
    if source_rate != SAMPLE_RATE:
        duration = len(audio) / source_rate
        target = int(duration * SAMPLE_RATE)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, target),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)
    return audio


def transcribe_streaming(recognizer, audio: np.ndarray) -> tuple[str, float]:
    """Exercise the online ASR path used only after wake authorization."""

    stream = recognizer.create_stream()
    stream.set_option("language", "auto")
    started = time.perf_counter()
    chunk = int(SAMPLE_RATE * 0.56)
    for offset in range(0, len(audio), chunk):
        stream.accept_waveform(SAMPLE_RATE, audio[offset : offset + chunk])
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)
    stream.input_finished()
    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)
    result = recognizer.get_result_all(stream)
    return (str(result.text or "").strip(), time.perf_counter() - started)


def main() -> None:
    from baxy_mind.voice import (
        SPEECH_THRESHOLD,
        TRAILING_SILENCE_S,
        SileroVad,
        VoiceEngine,
        WakePhraseMatcher,
    )

    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.router import IntentRouter

    transcripts: list[str] = []
    engine = VoiceEngine(transcripts.append)
    load_start = time.perf_counter()
    engine.load()
    router = IntentRouter()
    load_seconds = time.perf_counter() - load_start
    streaming = engine._streaming_recognizer  # noqa: SLF001 - gate de primer pase real
    voice_status = engine.status()

    results = []
    streaming_results = []
    wake_matcher = WakePhraseMatcher()
    available_operations = frozenset(expected[1] for *_, expected, _ in CASES)
    for language, voice_code, reference, expected, requires_wake in CASES:
        audio = synthesize(voice_code, reference)
        # Camino del motor: VAD frame a frame + cierre por silencio, sin mic.
        vad = SileroVad()
        window = int(vad.window_size_samples)
        padded = np.concatenate([
            np.zeros(SAMPLE_RATE // 2, np.float32),
            audio,
            np.zeros(int(SAMPLE_RATE * (TRAILING_SILENCE_S + 0.4)), np.float32),
        ])
        utterance: list[np.ndarray] = []
        speech_started = False
        silence = 0
        frames_needed = int(TRAILING_SILENCE_S * SAMPLE_RATE / window)
        segmented: np.ndarray | None = None
        for start in range(0, len(padded) - window, window):
            frame = padded[start:start + window]
            probability = vad.process(frame)
            if probability >= SPEECH_THRESHOLD:
                speech_started = True
                silence = 0
                utterance.append(frame)
            elif speech_started:
                silence += 1
                utterance.append(frame)
                if silence >= frames_needed:
                    segmented = np.concatenate(utterance)
                    break
        if segmented is None and utterance:
            segmented = np.concatenate(utterance)

        transcribe_start = time.perf_counter()
        stream = engine._recognizer.create_stream()  # noqa: SLF001 — gate del motor real
        stream.accept_waveform(SAMPLE_RATE, segmented if segmented is not None else audio)
        engine._recognizer.decode_stream(stream)  # noqa: SLF001
        transcript = (stream.result.text or "").strip()
        wake_matched, command = wake_matcher.strip(transcript)
        # This harness models a turn already authorized by KWS. The textual
        # prefix is cleaned only when Parakeet retained it in the 2 s pre-roll;
        # it is never a condition for routing.
        routed_text = command if requires_wake and wake_matched else transcript
        if transcript and engine._corrector is not None:  # noqa: SLF001
            routed_text = engine._corrector.correct(routed_text)  # noqa: SLF001
        latency = time.perf_counter() - transcribe_start

        decision = router.route(routed_text) if routed_text else None
        expected_kind, expected_operation, expected_args = expected
        offline_route_ok = (
            decision is not None
            and decision.kind == expected_kind
            and decision.operation == expected_operation
            and (expected_args is None or decision.arguments == expected_args)
        )
        product_intent = (
            resolve_explicit_effects(routed_text, available_operations)
            if routed_text
            else None
        )
        product_operations = (
            list(product_intent.operations) if product_intent is not None else []
        )
        route_ok = product_operations == [expected_operation]
        results.append(
            {
                "language": language,
                "reference": reference,
                "transcript": transcript,
                "routed_text": routed_text,
                "kws_authorized": requires_wake,
                "wake_prefix_cleaned": wake_matched,
                "vad_segmented": segmented is not None,
                "text_match_normalized": normalize(transcript) == normalize(reference),
                "routed_kind": decision.kind if decision else None,
                "routed_operation": decision.operation if decision else None,
                "routed_arguments": decision.arguments if decision else None,
                "offline_route_ok": offline_route_ok,
                "product_operations": product_operations,
                "route_ok": route_ok,
                "stt_seconds": round(latency, 3),
            }
        )
        if streaming is not None:
            try:
                streaming_transcript, streaming_latency = transcribe_streaming(
                    streaming,
                    segmented if segmented is not None else audio,
                )
                streaming_wake, streaming_command = wake_matcher.strip(streaming_transcript)
                streaming_text = (
                    streaming_command
                    if requires_wake and streaming_wake
                    else streaming_transcript
                )
                if streaming_text and engine._corrector is not None:  # noqa: SLF001
                    streaming_text = engine._corrector.correct(streaming_text)
                streaming_decision = router.route(streaming_text) if streaming_text else None
                streaming_intent = (
                    resolve_explicit_effects(streaming_text, available_operations)
                    if streaming_text
                    else None
                )
                streaming_operations = (
                    list(streaming_intent.operations)
                    if streaming_intent is not None
                    else []
                )
                streaming_results.append(
                    {
                        "language": language,
                        "wake_prefix_cleaned": streaming_wake,
                        "has_text": bool(streaming_transcript),
                        "offline_route_ok": (
                            streaming_decision is not None
                            and streaming_decision.kind == expected_kind
                            and streaming_decision.operation == expected_operation
                            and (
                                expected_args is None
                                or streaming_decision.arguments == expected_args
                            )
                        ),
                        "product_operations": streaming_operations,
                        "route_ok": streaming_operations == [expected_operation],
                        "stt_seconds": round(streaming_latency, 3),
                    }
                )
            except Exception as error:  # noqa: BLE001 - evidence, never promotion
                streaming_results.append(
                    {
                        "language": language,
                        "has_text": False,
                        "route_ok": False,
                        "error": type(error).__name__,
                    }
                )

    # Criterio de la compuerta: 6/6 segmentados por VAD y 6/6 decisiones
    # productivas exactas. Todo desvío queda registrado con transcript y ruta.
    matches = sum(1 for r in results if r["route_ok"])
    passed = all(r["vad_segmented"] for r in results) and matches == len(CASES)
    report = {
        "schema": "baxy-mind-voice-gate-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "adr": "ADR-0005",
        "stt": "parakeet-tdt-0.6b-v3 int8 (sherpa-onnx, CPU)",
        "decision_boundary": (
            "baxy_mind.effect_intent.resolve_explicit_effects; "
            "frozen embedding router is diagnostic only"
        ),
        "streaming_preview": {
            "available": streaming is not None,
            "model": voice_status.get("streamingSttModel"),
            "error": voice_status.get("streamingSttError"),
            "final_verifier": "parakeet-tdt-0.6b-v3-int8 + AEC",
            "promotion": "ASR partial only; requires a held-out microphone corpus",
            "cases": streaming_results,
        },
        "wake": {
            "backend": voice_status.get("wakeBackend"),
            "model": voice_status.get("wakeWordModel"),
            "error": voice_status.get("wakeWordError"),
            "note": "KWS is measured separately with evaluate_wake_corpus.py",
        },
        "vad": "silero-vad (CPU)",
        "tts_probe": "Windows SAPI Sabina (es-MX) / Zira (en-US), PCM16 local",
        "engine_load_seconds": round(load_seconds, 1),
        "cases": results,
        "status": "passed" if passed else "failed",
        "not_covered": "la identidad acústica del usuario requiere una sesión hablada por el usuario; mic, SAPI y loopback se cubren en voice_system_gate",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as destination:
        destination.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
