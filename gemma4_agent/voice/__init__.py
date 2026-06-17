"""Subsistema de voz — reescritura Parakeet-only (2026-06-17).

Cadena:

    mic (16 kHz mono, frames de 512 samples / 32 ms)
      → captura WASAPI + resample + AEC loopback (audio_io)
      → Silero VAD (gate de ruido + fin-de-habla)
      → wake-word LiveKit "Baxy" (runtime ONNX puro, livekit_runtime)
      → máquina de estados de captura (EOS tri-estado, gates de energía)
      → Parakeet-TDT-v3 int8 CPU (parakeet_stt) — ÚNICO motor STT
      → corrector fonético contra inventario de dominio (corrector)
      → texto al LLM (con hint de idioma del perfil)

Mapa de módulos:
    audio_io      — captura de mic + ring buffer + AEC + resample
    vad           — wrapper Silero VAD (gate + trim)
    wake          — detector LiveKit (+ fallback openWakeWord)
    livekit_runtime — inferencia LiveKit en onnxruntime puro (Py 3.10)
    parakeet_stt  — STT Parakeet-TDT-v3 (sherpa-onnx, único motor)
    inventory     — vocabulario de dominio (apps, contactos, canciones)
    corrector     — corrector fonético dual ES/EN (RapidFuzz + Metaphone)
    lang_profiles — perfil de idioma del usuario (hint al agente)
    pipeline      — orquestador: compone todo en la máquina de estados
    tts           — Piper TTS

Wake word: "Baxy" (modelo baxy.onnx; elegido por generalización cross-idioma).
STT: Parakeet-TDT-0.6b-v3 int8 en CPU. Whisper ELIMINADO (reescritura 2026-06-17):
Parakeet es ~20x más rápido y no alucina en silencio; el LID no es forzable, así
que el idioma se mitiga con contexto + hint al agente (ver lang_profiles).

Modelos en ~/.gemma4/models/{sherpa-onnx-nemo-parakeet...,piper}/ + el wake
ONNX en voice/models/livekit/.
"""
