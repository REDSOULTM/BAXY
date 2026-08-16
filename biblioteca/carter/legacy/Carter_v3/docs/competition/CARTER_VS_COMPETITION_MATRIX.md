# CARTER_VS_COMPETITION_MATRIX.md
# Carter v3 vs. Competencia — Matriz Comparativa de 30 Dimensiones
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# HONESTIDAD: Se pone a Carter ganador solo donde hay evidencia real.

---

## Escala de evaluación
- **MEJOR** = Ventaja clara sobre los competidores
- **IGUAL** = Comparable a competidores relevantes
- **PARCIAL** = Tiene la capacidad pero con gaps
- **PEOR** = Por debajo de competidores relevantes
- **NO TIENE** = Funcionalidad no implementada

---

| Dimensión | Carter v3 | Mark XXXIX | OpenClaw | Otros (Open Interp./OpenHands/etc.) | Ganador | Recomendación para Carter |
|---|---|---|---|---|---|---|
| **1. Local-first** | MEJOR (diseño, LLM local con Ollama) | PEOR (100% Gemini cloud) | IGUAL (Ollama plugin disponible) | IGUAL/PARCIAL (mayoría soportan Ollama) | **Carter** | Mantener como ventaja diferenciadora clave |
| **2. Privacidad** | MEJOR (cero cloud obligatorio, datos en disco local) | PEOR (todo va a Google) | PARCIAL (Ollama ok, pero canales de mensajería envían datos) | PARCIAL (depende del setup) | **Carter** | Documentar mejor como valor de venta |
| **3. Tool calling** | IGUAL (32 tools declarativas con schemas JSON) | PARCIAL (18 tools con dispatch if/elif) | MEJOR (TypeBox schemas + sandbox + policy + failover) | PARCIAL (variable por framework) | OpenClaw (seguridad) / Carter (confiabilidad) | Agregar SSRF protection y path policy más explícita |
| **4. Seguridad/policy** | MEJOR (PolicyEngine 20+ patterns + 8 guards + secret filter + HIGH/CRITICAL gates) | PEOR (ningún sistema propio de policy) | IGUAL (Docker sandbox, SSRF, exec approval, audit) | PARCIAL (mayoría sin policy pre-LLM) | **Carter vs Mark; OpenClaw igual** | Agregar SSRF en web_fetch, exec approval para CRITICAL |
| **5. Verifier / no fake success** | MEJOR (14 verifiers, causal baseline, CONFIRMED vs UNVERIFIED explícito) | PEOR (sin verifier, asume éxito) | PEOR (sin verifier por tool) | PEOR (mayoría sin verifier) | **Carter** (único con verifier real) | Fix B3 (fake_success mid-text), Fix B4 (notify_toast) |
| **6. Memoria** | PARCIAL (SQLite con secret filter, dedup, TTL de session state) | PARCIAL (JSON categorizado, sin secret filter) | MEJOR (vector embeddings, dreaming, multimodal) | PEOR (mayoría solo contexto) | OpenClaw (semántica) / Carter (seguridad) | Agregar semantic recall via embeddings simples |
| **7. Preferences** | PARCIAL (memory store general, sin categorías explícitas) | PARCIAL (6 categorías JSON) | PARCIAL (memory.md injection) | PEOR | **Mark** (categorías) | Agregar categorías de preferencias al memory store |
| **8. App control (Windows)** | MEJOR (fuzzy resolver + UIA + AttachThreadInput + CEF support) | PARCIAL (64 aliases fijos + pyautogui básico, falla en CEF) | NO TIENE | PEOR/NO | **Carter** (único con CEF support) | Validar live con Steam, Discord, Spotify |
| **9. Browser/web** | PEOR (web_open_url básico + web_search, sin automatización real) | MEJOR (Playwright con tabs, forms, smart_click, múltiples perfiles) | MEJOR (Playwright en Docker sandbox) | IGUAL (OpenHands tiene Playwright) | Mark y OpenClaw | **BRECHA CRÍTICA**: Agregar Playwright para web automation real |
| **10. Filesystem** | PARCIAL (5 tools con ownership guard, pero sin validación live) | PARCIAL (file_controller básico) | MEJOR (read/write/edit/apply_patch + path policy) | PARCIAL | OpenClaw | Agregar apply_patch tool, validar live |
| **11. Terminal** | PARCIAL (terminal_run_command, sin PTY, sin long-running process) | PARCIAL (code_helper llama a Gemini para generar comandos) | MEJOR (exec con PTY, process tool, long-running) | MEJOR (Open Interpreter) | OpenClaw | Agregar PTY support o al menos async terminal |
| **12. GUI automation** | PARCIAL (gui_click via AttachThreadInput para CEF, UIA probe, screenshot) | PARCIAL (pyautogui básico, sin CEF) | NO TIENE | PARCIAL (Agent-S VLM-based) | **Carter** (mejor en desktop nativo) | Validar live gui_click con Steam/Discord |
| **13. Screen observation** | PARCIAL (ladder INTERNAL→VLM, UIA probe, OCR, screenshot) | MEJOR (mss + cv2 + Gemini vision, funcional en producción) | PARCIAL (Canvas/browser screenshots, sin desktop) | MEJOR (Agent-S VLM-based, Claude CU) | Mark (funcional) / Agent-S (calidad) | Validar VLM integration cuando hay VLM disponible |
| **14. Voice/STT** | NO TIENE | MEJOR (Gemini Live nativo, en producción) | MEJOR (Deepgram/sherpa-onnx, producción) | PARCIAL (mayoría tienen STT básico) | Mark y OpenClaw | **Fuera de scope ahora** — pendiente post-núcleo |
| **15. Camera/vision física** | NO TIENE | MEJOR (cv2 + Gemini, funcional) | MEJOR (mobile nodes) | PARCIAL | Mark | **Fuera de scope ahora** |
| **16. Multi-step planning** | PARCIAL (step_budget=6, fallback chains, compound_action classifier) | PARCIAL (Gemini genera JSON plan, max 5 pasos, 3 retries) | MEJOR (subagents, update_plan tool, depth limits) | MEJOR (LangGraph, AutoGen) | OpenClaw (multi-agent) | Agregar progress reporting entre steps, max_steps configurable |
| **17. Progress reporting** | PEOR (silencio hasta que termina, sin emits intermedios) | MEJOR (estados UI claros, typewriter log) | MEJOR (update_plan visible, session history) | PARCIAL | Mark y OpenClaw | **BRECHA ALTA**: Agregar emit de progreso entre steps |
| **18. Recovery** | PEOR (1 retry solo para app_open, 0.5s sleep) | PARCIAL (retry/replan/abort via LLM) | MEJOR (model failover, context compaction, sandbox recovery) | PARCIAL | OpenClaw | Generalizar retry a otros tools, agregar context compaction |
| **19. Latencia** | IGUAL/MEJOR (pre-LLM fast lane, step budget, TCP probe) | PEOR (doble session WebSocket + latencia Gemini) | PEOR (multi-hop: canal→gateway→LLM provider→response) | VARIABLE | **Carter** (más control sobre latencia) | Medir latencia real con Ollama, optimizar overhead pre-LLM |
| **20. Model flexibility** | PARCIAL (4 adapters, ModelCapabilityProfile sin if-model-name) | PEOR (solo Gemini, sin alternativas) | MEJOR (30+ providers, model failover) | IGUAL | OpenClaw | Agregar más adapters via profiles (llama.cpp, vLLM, etc.) |
| **21. Hardware adaptation** | MEJOR (VRAM 85% rule, ModelSelector, CPU/VRAM profiles en ContextoCarter) | PEOR (no hay, depende de Gemini cloud) | PEOR (no gestiona VRAM, delega al provider) | PEOR | **Carter** | Implementar degradación automática por RAM/VRAM |
| **22. Test coverage** | PARCIAL (490 tests con ScriptedAdapter, 0 tests con LLM real) | PEOR (sin test suite visible) | MEJOR (vitest + pytest + E2E + Docker) | PARCIAL | OpenClaw | Agregar al menos 5-10 tests live con Ollama real |
| **23. UX** | PEOR (solo CLI, sin progress, sin HUD) | MEJOR (PyQt6 HUD, estados, waveform, métricas) | MEJOR (multi-canal, TUI, web) | PARCIAL | Mark (desktop visual) | CLI con progress reporting es suficiente para fase texto |
| **24. Code simplicity** | PARCIAL (agent.py de 1100 líneas, fallback chains complejas) | MEJOR (simple: delega todo a Gemini) | PEOR (700+ archivos TypeScript) | VARIABLE | Mark (simple por delegación) | Refactorizar fallback chains fuera de agent.py |
| **25. Extensibility** | PEOR (sin plugin system, tools hardcoded en catalog) | PARCIAL (actions/ es extensible manualmente) | MEJOR (plugin SDK, ClawHub, ACP, MCP) | PARCIAL | OpenClaw | Agregar registro de tools desde archivos de configuración |
| **26. Maintainability** | PARCIAL (buena estructura de módulos, pero agent.py monolito) | PEOR (sin tests, monolito grande) | MEJOR (modular, bien tipado, CI) | PARCIAL | OpenClaw | Refactorizar agent.py, aumentar test coverage |
| **27. Reliability** | PARCIAL (490 tests pasan pero sin validación live real) | PEOR (sin tests, depende de Gemini uptime) | MEJOR (tests, failover, sandbox) | PARCIAL | OpenClaw | Validar live, agregar tests de regresión real |
| **28. Autonomía** | PARCIAL (step_budget=6, policy gates, confirmación requerida para HIGH) | PARCIAL (max 5 pasos, LLM decide retry) | MEJOR (subagents, cron, webhooks, autonomía configurable) | VARIABLE | OpenClaw | Nivel actual de autonomía es correcto para fase texto |
| **29. Offline use** | MEJOR (completamente funcional con Ollama local, sin internet) | PEOR (inútil sin Gemini) | MEJOR (Ollama + sherpa-onnx TTS) | VARIABLE | **Carter y OpenClaw (empate)** | Documentar y probar el modo completamente offline |
| **30. Readiness for Jarvis-like** | MEJOR (arquitectura diseñada exactamente para esto) | PARCIAL (funciona pero sin fundamentos robustos) | PARCIAL (excelente para mensajería, pero no para PC personal) | PEOR | **Carter** (por diseño) | Completar los bloqueadores del núcleo texto primero |

---

## Resumen de posiciones

| Competidor | Áreas donde gana a Carter | Áreas donde Carter gana |
|---|---|---|
| **Mark XXXIX** | Voz (14), Cámara (15), UX/Progress (17,23), Browser (9), Vision (13) | Todo lo demás (local-first, privacy, verifier, security, app control CEF, tests, hardcodes, identity) |
| **OpenClaw** | Memory (6), Browser (9), Terminal (11), Model flexibility (20), Tests (22), Extensibility (25), Recovery (18) | Local-first por diseño (1), Verifier (5), App control Windows (8,12), Hardware adaptation (21), Jarvis-readiness (30) |
| **Otros** | STT/TTS (Open Interpreter streamability, LangGraph state machine) | Carter tiene mejor foundation para PC-Jarvis en general |

## Las 5 brechas más críticas de Carter

1. **Browser automation** (dimensión 9) — Carter no tiene Playwright. Mark y OpenClaw sí.
2. **Progress reporting** (dimensión 17) — Carter está en silencio durante misiones. Mark y OpenClaw no.
3. **Test coverage live** (dimensión 22) — 490 tests scripted no validan el LLM real.
4. **Memory semántica** (dimensión 6) — Carter no tiene embeddings para recall semántico.
5. **Recovery generalizada** (dimensión 18) — Solo app_open tiene retry. Nada más tiene recovery.
