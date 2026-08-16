# WHAT_NOT_TO_COPY_FROM_COMPETITORS.md
# Qué NO Copiar de Competidores
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

| Patrón a evitar | Competidor donde aparece | Por qué es malo para Carter | Riesgo | Alternativa Carter |
|---|---|---|---|---|
| **Cloud LLM obligatorio** | Mark XXXIX (100% Gemini) | Rompe Valor 1 (local-first) y Valor 2 (privacidad). Sin internet = inútil. | CRÍTICO | Mantener Ollama como primer adapter; cloud como opt-in con consent |
| **Identidad de marca ajena** | Mark XXXIX ("JARVIS", "Tony Stark") | Trademark de Marvel/Disney. Proyecto no publicable como producto. Viola licencias. | LEGAL | Carter es Carter. Nombre propio, sin deudas de marca. |
| **64-entry app aliases dict** | Mark XXXIX (_APP_ALIASES) | Hardcode por app. Viola Valor 6 y 7 de ContextoCarter. Falla con apps no listadas. | ALTO | fuzzy resolver dinámico de Carter (ya implementado y superior) |
| **if/elif dispatch para tools** | Mark XXXIX (_execute_tool) | Escala mal. Cada nueva tool requiere una nueva rama. Sin schema enforcement. | MEDIO | Dispatch table con handlers registrables (ya implementado en Carter) |
| **Sin test suite** | Mark XXXIX | Sin tests = sin confianza. Cualquier cambio puede romper algo sin saberlo. | ALTO | Mantener y expandir los 490 tests de Carter. Agregar tests live. |
| **LLM para "fix generation"** | Mark XXXIX (generate_fix) | Pedir al LLM que escriba un script de fix es una superficie de ataque. El fix podría contener código malicioso. | ALTO | Error taxonomy estructural con retry/skip/abort basado en reglas |
| **Voz "Charon" hardcoded** | Mark XXXIX | Hardcode de provider específico. Si Gemini cambia la voz o la depreca, Mark falla. | MEDIO | Configuración de voz como profile en models registry |
| **Fake success implícito** | Mark XXXIX (sin verifier) | El asistente dice "hecho" sin verificar. Rompe confianza del usuario. Viola Valor 3 y 4 de ContextoCarter. | CRÍTICO | El sistema de verifiers de Carter con CONFIRMED/UNVERIFIED es la respuesta correcta |
| **Sin policy pre-LLM** | Mark XXXIX | El LLM puede recibir y ejecutar solicitudes peligrosas antes de ser evaluadas. | ALTO | PolicyEngine de Carter con 20+ patterns, pre-LLM, antes de cualquier costo |
| **Sin secret filter en memoria** | Mark XXXIX | Contraseñas, tokens, API keys pueden guardarse en long_term.json y exponerse. | ALTO | Memory store de Carter con `contains_secret()` antes de escribir |
| **Memory sin dedup** | Mark XXXIX | La memoria crece indefinidamente con entradas repetidas. | BAJO | dedupe_window de Carter |
| **pyautogui para send_message** | Mark XXXIX | Hardcodea el layout de UI de WhatsApp/Telegram/Discord. Cualquier actualización de la app rompe la automation. Anti-Valor 7. | ALTO | No implementar send_message con UI automation por layout. Si se implementa, usar API oficial o protocolo estable. |
| **Leer/parsear posición exacta de botones** | Mark XXXIX / OS-Copilot | Coordinate-based GUI automation sin UIA es frágil. Resolución, DPI, layout pueden cambiar. | ALTO | UIA accessibility tree (Carter ya hace esto), AttachThreadInput solo como fallback para CEF |
| **Multi-agent sin step budget** | AutoGPT | Loop infinito, tokens ilimitados, sin control de costos. | ALTO | step_budget=6 de Carter + fallback chains acotadas |
| **LLM como árbitro de mission_status** | Mayoría de competidores | El LLM puede alucinar éxito. Si el texto del LLM vota el status, Carter puede mentir. | CRÍTICO | compute_mission_status() de Carter es puramente estructural. El LLM nunca vota. |
| **Docker obligatorio** | OpenClaw (para sandbox) | Overhead inaceptable para un asistente single-user en Windows. Usuario casual no tiene Docker. | MEDIO | Para Carter single-user, la política + verifier son el sandbox. Docker es opcional para terminal CRITICAL. |
| **Multi-canal de mensajería** | OpenClaw (25+ canales) | Diferente nicho. Añade complejidad sin mejorar el objetivo Jarvis-local. | BAJO | Carter es local. El "canal" es el teclado del usuario. |
| **ClawHub plugin marketplace** | OpenClaw | Gran overhead de infraestructura para single-user app. | BAJO | Plugin-like via model registry YAML es suficiente por ahora |
| **Memoria sin TTL** | Mayoría | Memorias viejas e incorrectas nunca expiran. | MEDIO | session_state de Carter con TTL. Para memoria persistente: campo `superseded_by`. |
| **VLM obligatorio para GUI** | Agent-S / Claude Computer Use | VLM consume VRAM extra. En hardware limitado (6GB), añadir VLM para GUI puede crashear el PC. | ALTO | Perception ladder de Carter: INTERNAL→PROCESS→WINDOW→SYSTEM_API→WEB→SCREENSHOT→OCR→VLM. VLM es el último recurso. |
| **Copiar bloques de código de competidores** | Todos | Puede traer licencias incompatibles, hardcodes ocultos, dependencias innecesarias, y patrones que violan ContextoCarter. | LEGAL/TÉCNICO | Estudiar arquitectura, adaptar conceptos de forma original con el código de Carter como base |
| **HUD de 1500 líneas como monolito** | Mark XXXIX (ui.py) | Si la UI falla, no hay CLI fallback. El núcleo debe ser testeable sin UI. | MEDIO | CLI primero. UI es capa encima. Nunca mezclar lógica de negocio con UI. |
| **Gemini como vision en producción sin alternativa local** | Mark XXXIX | Si Gemini falla → visión inoperante. Sin privacidad. | ALTO | Perception ladder con OCR local como fallback antes de cualquier VLM cloud |
| **Agent "decides" si fue exitoso via texto** | Mark XXXIX / AutoGPT / Open Interpreter | El LLM puede decir "parece que funcionó" basado en outputs de texto que en realidad no prueban nada. | CRÍTICO | Carter: verifier lee el estado real del OS, no la descripción textual de lo que pasó |
| **Logs con datos sensibles** | Mayoría (sin filtro) | Logs pueden contener contraseñas, tokens, rutas de archivos privados si no se filtran. | ALTO | Aplicar secret_filter a todo lo que se loguea. Truncar valores largos en logs. |
