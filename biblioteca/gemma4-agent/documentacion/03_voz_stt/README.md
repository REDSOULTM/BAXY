# 03 — Voz / STT

Cubre todo el pipeline de voz: reconocimiento (STT), wake-word y síntesis (TTS).

**Estado vigente:**
- **STT:** Whisper int8 en **CPU** en producción; **Parakeet** disponible por flag. 0 VRAM (el LLM se queda con la GPU).
- **Wake-word:** runtime **LiveKit** servido con onnxruntime puro (ctx del agente = 12288).
- **TTS:** **Piper** (VITS) con playback streaming (default ON).

`research/` contiene la investigación de soporte (Parakeet/sherpa, biasing
contextual, faster-whisper int8, mediciones A/B de latencia). Para el estado
ítem-por-ítem ver [`../_backlog/BACKLOG_MAESTRO.md`](../_backlog/BACKLOG_MAESTRO.md).
