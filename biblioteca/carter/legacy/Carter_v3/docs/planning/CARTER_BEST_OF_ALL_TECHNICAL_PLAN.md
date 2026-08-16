# CARTER_BEST_OF_ALL_TECHNICAL_PLAN.md
# Plan Técnico para Convertir Carter en el Mejor
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## FASE A — Congelar y limpiar repo

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| A | Committear working tree. Eliminar docs/archivos obsoletos del repo de forma ordenada. Crear branch limpio desde el estado actual. | `git add` de archivos nuevos no commiteados. `git rm` de docs eliminados del working tree (los que están como `deleted` en git status). Commit con mensaje descriptivo. | Todo el repo | `pytest` debe pasar 0 fallos | `git status` muestra working tree limpio. Tag nuevo que describe el estado real. | Pueden perderse docs útiles si se eliminan sin revisar. Revisar antes de `git rm` masivo. |

---

## FASE B — Cerrar bloqueadores de auditoría Claude

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| B | Resolver los 6 bloqueadores documentados en CLAUDE_CARTER_V3_AUDIT_VERDICT.md | Fix B2: relajar `_short_same_language_nonsecret` para afirmativos cortos. Fix B3: extender fake_success_guard a mid-text. Fix B4: notify_toast→SKIPPED. Fix B5: emit progreso en loop steps. Fix B6: matizar system_prompt. | `session_state.py`, `guards.py`, `tools/catalog.py`, `tools/verifier.py`, `response_composer.py`, `agent.py`, `turn_support.py` | `pytest` 0 fallos. `test_pending_intent_followups.py` debe pasar B2. `test_guards.py` debe pasar B3. | Todos los bloqueadores resueltos y testeados. `pytest` limpio. `hardcode_guard` limpio. | B3 (mid-text guard) puede producir falsos positivos en respuestas válidas. Testear exhaustivamente con ejemplos negativos. |

---

## FASE C — Validar live real (apps, web, GUI, terminal, filesystem)

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| C | Ejecutar spotcheck manual del CLAUDE_MANUAL_SPOTCHECK_SET.md con modelo Ollama real corriendo. Documentar resultados. Medir latencia. | Solo documentación de resultados. Si se encuentran bugs nuevos, documentarlos como casos de regresión. | `Carter_v3/docs/audit/LIVE_VALIDATION_2026_05.md` (nuevo) | Spotcheck manual 12+ casos (ver lista en CARTER_100_PERCENT_GAP_ANALYSIS.md) | Documentación de resultados con fecha, modelo usado, latencia real. Al menos 10/12 casos pasan. | El modelo real puede fallar en casos que ScriptedAdapter pasa. Cualquier fallo nuevo debe documentarse y posiblemente convertirse en test de regresión. |

---

## FASE D — Mejorar progress reporting y task journal

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| D | Emitir mensajes de progreso al usuario durante el loop de steps. Mostrar el plan de pasos antes de ejecutar. | En `agent.py:loop de steps`: antes de cada step, emitir via heartbeat o yield al caller: "Ejecutando paso {n}/{total}: {tool_name} {target}...". En `_materialise_steps`: emitir plan de pasos al inicio de misión compuesta. | `agent.py`, `heartbeat.py` (o CLI output layer) | Nuevo test: misión con 3 steps debe emitir 3 mensajes intermedios. | Usuario ve progreso en tiempo real durante misión compuesta. Silencio máximo: 1 step entre emits. | Overhead mínimo. Si se emite via heartbeat, no debe bloquear el turn thread. |

---

## FASE E — Mejorar planner / executor / recovery

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| E | Error classification estructural (retry/skip/abort). Model failover entre adapters. Context compaction básica. | Nuevo `error_taxonomy.py` con reglas de retry/skip/abort sin LLM. En `config.py`: lista priorizada de adapters; si primary falla, intentar siguiente. En `turn_support.py:build_messages`: si turns > N, resumir turns viejos. | `recovery.py`, nuevo `error_taxonomy.py`, `config.py`, `turn_support.py` | Tests de error taxonomy: error transitorio→retry, error permanente→abort. Test de failover: si primary adapter unavailable, usa secondary. | Recovery más robusta. Failover funcional. Contexto no truncado silenciosamente. | La compaction requiere llamada extra al LLM (costo de latencia). Hacer configurable (off por defecto). |

---

## FASE F — Mejorar observation loop sin VLM obligatorio

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| F | Validar y mejorar la perception ladder. Asegurar que UIA probe funcione en apps reales. Documentar cuándo OCR es fallback viable. SSRF protection en web_fetch. | Auditar `perception/uia_probe.py` en apps reales (Notepad, Chrome). Agregar SSRF protection en `tools/web_helpers.py`. Documentar resultados de OCR en screenshots reales. | `perception/uia_probe.py`, `tools/web_helpers.py`, `tools/dispatch_web.py` | Test de SSRF: URLs privadas (127.0.0.1, 192.168.x.x) deben ser bloqueadas. | SSRF protection activa y testeada. UIA probe funciona en al menos 2 apps reales documentadas. | UIA puede ser lento en apps complejas. OCR puede ser inexacto. Documentar limitaciones. |

---

## FASE G — Mejorar test harness live

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| G | Agregar al menos 10 tests live con LLM real (usando Ollama o fallback scripted marcado como "live validation"). Capturar regresiones reales del usuario. | Nuevos casos en `test_live_regressions_from_user_log.py`. Un nuevo runner que ejecuta con Ollama real si disponible. | `tests/test_live_regressions_from_user_log.py`, nuevo `tests/run_live_validation.py` | 10+ casos live con Ollama real pasan. | Suite live documentada y ejecutable. Regresiones del usuario capturadas como tests permanentes. | Ollama debe estar corriendo para esta suite. Marcar claramente qué tests requieren LLM real vs scripted. |

---

## FASE H — Preparar arquitectura para voz/cámara

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| H | Definir las interfaces que voz y cámara usarán, sin implementarlas. Documentar el pipeline. Asegurar que el núcleo texto no requiere cambios para soportar voz/cámara encima. | Crear `docs/roadmap/voice_camera_architecture.md`. Definir interface de input normalizada: cualquier fuente (texto, voz, cámara) debe convertirse a una estructura unificada antes de entrar al AgentEngine. | `docs/roadmap/voice_camera_architecture.md` (nuevo), `agent.py` (revisar interface de input) | No hay tests de implementación, solo de interfaz: `test_input_normalization.py` | Documento de arquitectura de voz/cámara aprobado. AgentEngine acepta input normalizado independientemente de la fuente. | Si el AgentEngine tiene coupling fuerte con el tipo de input actual, puede requerir refactorización. |

---

## FASE I — Construir voz (solo después de H)

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| I | Implementar pipeline de voz: STT → texto → AgentEngine → texto → TTS. Sin VLM. Sin cámara. Sin wake word en primera versión. | Nuevo módulo `voice/`: STT con Whisper local (whisper.cpp o faster-whisper), TTS con pyttsx3 o Kokoro-82M. Input normalizado a texto antes del AgentEngine. | Nuevo `voice/stt.py`, `voice/tts.py`, `voice/pipeline.py`, `cli/voice_mode.py` | Tests de STT: audio de prueba → transcripción correcta. Tests de TTS: texto → audio generado. Tests de pipeline: input voz → output voz correcto. | Voz funcional en hardware del usuario. Latencia total < 15s para comandos simples. STT y TTS locales. | Whisper puede ser lento en CPU. Kokoro requiere ~1GB. Probar en hardware real antes de commitear. |

---

## FASE J — Cámara/visión física (solo después de I)

| Fase | Objetivo | Cambios | Archivos | Tests | Criterio de cierre | Riesgos |
|---|---|---|---|---|---|---|
| J | Implementar webcam snapshot como herramienta opcional. Integrar VLM local si disponible para análisis. | Nuevo `camera/webcam.py` usando cv2. Nuevo tool `camera_snapshot`. Si VLM disponible: análisis de imagen. Sin VLM: solo captura y guarda. | Nuevo `camera/`, nuevos tools en catalog | Tests de captura: webcam snapshots guarda archivo válido. | camera_snapshot funcional. VLM análisis opcional. Sin VLM obligatorio. Privacidad: foto no se envía a cloud sin permiso. | cv2 puede fallar con algunos drivers de cámara en Windows. VLM requiere VRAM adicional. |

---

## Orden de ejecución recomendado para Codex

```
A → B → C (validación manual, no código) → D → E → F → G → H
                                                              ↓
                                            (solo si núcleo texto está al 100%)
                                                              ↓
                                                       I → J
```
