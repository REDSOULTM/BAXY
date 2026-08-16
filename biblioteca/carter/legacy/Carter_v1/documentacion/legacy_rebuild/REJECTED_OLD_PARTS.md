# REJECTED_OLD_PARTS.md — Lo que NO se trajo del proyecto anterior

## Voice Stack (9 modulos, ~5000 LOC)
- speech_to_text.py, stt_audio.py, stt_text.py, stt_transcribe.py
- stt_whisper.py, stt_moonshine.py, stt_entity_catalog.py
- stt_metrics.py, stt_events.py, text_to_speech.py
- **Razon**: Carter v2 es texto. Voice es un proyecto separado.
- **Deps eliminadas**: pyaudio, webrtcvad, faster-whisper, moonshine, pyttsx3, openwakeword

## GUI (8 modulos, ~750 LOC)
- app.py, tray.py, panels/*
- **Razon**: Carter v2 es CLI/REPL. GUI sera capa separada si se necesita.
- **Deps eliminadas**: customtkinter, pystray

## Tool Registry (59 tools, 10 modulos, ~800 LOC)
- audio_manager.py, audio_devices.py, software_launcher.py
- system_control.py, input_automator.py, media_controller.py
- windows_manager.py, app_discovery.py, user_paths.py
- **Razon**: Filosofia zero predefined tools. Carter genera su propio codigo.
- **Deps eliminadas**: pycaw, screen-brightness-control

## LangGraph + langchain-core
- orchestrator.py (1759 LOC)
- **Razon**: Un while loop hace lo mismo. LangGraph agrega complejidad sin beneficio.
- **Deps eliminadas**: langgraph, langchain-core

## Command Router (2619 LOC)
- command_router.py con 40+ regex patterns
- **Razon**: Carter no tiene commands predefinidos. Todo pasa por el LLM.

## Visual Grounding (5168 LOC)
- visual_grounding.py con OCR, UIA, pyautogui, LLM planner
- **Razon**: Carter lo hace generando codigo con PIL/pyautogui cuando lo necesita.
- El patron observe-plan-act-verify se conserva en el prompt, no como modulo.
- **Deps eliminadas**: rapidocr_onnxruntime, opencv-python, comtypes

## Social Presence + Transparent Continuity (~1300 LOC)
- social_presence.py, transparent_continuity.py
- **Razon**: Features de nicho. Carter las puede implementar bajo demanda.

## Launcher Workflows (879 LOC)
- launcher_workflows.py con logica hardcodeada para Steam/Epic/EA
- **Razon**: Carter descubre como interactuar con launchers generando codigo.

## Speaker Verifier (~350 LOC)
- speaker_verifier.py
- **Razon**: Parte del voice stack eliminado.

## Entity Catalog (553 entities hardcoded)
- stt_entity_catalog.py
- **Razon**: Carter busca info con codigo, no con catalogos estaticos.

## llama-cpp-python
- ai_core.py, llm_models.py
- **Razon**: Carter usa Ollama (API HTTP). Mas simple, mismo resultado.

## Runtime Diagnostics (1156 LOC)
- runtime_diagnostics.py con 33 command matrix
- **Razon**: Tests nuevos cubren lo relevante con pytest.
