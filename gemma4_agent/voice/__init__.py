"""Voice pipeline v2 — clean rebuild (2026-05-19).

Architecture (per docs/architecture/voice_pipeline_redesign_research_report.md):

    mic stream (16 kHz mono, 20 ms frames)
      → Silero VAD (gate)
      → openWakeWord (wake-word detection)
      → command capture state machine (end-of-speech via VAD)
      → faster-whisper small int8 (STT)
      → RapidFuzz post-correction against domain inventory
      → text out to LLM

Module map:
    audio_io      — mic capture + ring buffer + frame primitives
    vad           — Silero VAD wrapper
    wake          — openWakeWord wrapper (stock + custom model paths)
    stt           — faster-whisper streaming wrapper
    inventory     — domain vocab loader (apps, contacts, songs)
    corrector     — RapidFuzz fuzzy-match post-corrector
    pipeline      — orchestrator: composes the above into a state machine
    tts           — Piper TTS (kept from v1, unchanged)

Wake phrase: "Hey Gemma" (planned via custom training).
Until the custom hey_gemma.onnx exists, the pipeline falls back to
the stock `hey_jarvis` openWakeWord model so the system is usable
during development. The fallback is logged loud and clear.

OS support: Windows + macOS arm64 + Linux x86_64. All deps have
pre-built wheels for Python 3.10-3.12.

Models: downloaded on first use to ~/.gemma4/models/{whisper,oww}/.
Total disk: ~490 MB.
"""
