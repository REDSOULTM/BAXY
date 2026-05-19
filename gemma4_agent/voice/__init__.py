"""Voice module — clean slate after Sprint R3.1 (2026-05-19).

The previous pipeline (Vosk/openWakeWord wake + faster-whisper STT +
recorder + controller) was removed because it proved fragile in real
production (false wakes on ambient noise, mistranscriptions of
English app/song names embedded in Spanish, single-voice fine-tune
that didn't generalize).

Current state:
- `tts.py`        — Piper TTS, kept as-is (works, the agent's voice).
- `audio_io.py`   — Mic capture utilities, kept for reuse in the new
                    pipeline.
- `tests/`        — Test audio + ground-truth annotations preserved
                    for evaluation of the new pipeline.

Pending: replacement architecture is in research (see
docs/architecture/voice_pipeline_redesign_research_prompt.md).

Backup of the deleted pipeline: git branch
`pre-voice-rewrite-2026-05-19`.
"""
