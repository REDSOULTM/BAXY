"""Fase W — Voz local: wake-word (Vosk) + STT streaming (faster-whisper) + TTS (Piper).

Diseno: cada submodulo es lazy-import. Si una dep no esta instalada, ese
subsistema queda en FAILED pero el resto funciona. controller.py orquesta los
3 y expone Qt signals para que la GUI se conecte sin tocar al agente directamente.

Modelos descargados a `~/.gemma4/models/{vosk,whisper,piper}/` con consentimiento.
"""
