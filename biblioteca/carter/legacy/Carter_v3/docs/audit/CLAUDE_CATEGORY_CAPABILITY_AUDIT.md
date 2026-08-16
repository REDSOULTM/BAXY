# CLAUDE_CATEGORY_CAPABILITY_AUDIT.md
# Auditoría de Capacidades Reales por Categoría Oficial
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

| Cat | Capacidad esperada | Estado real | Evidencia tests | Evidencia manual | Gaps | Prioridad |
|---|---|---|---|---|---|---|
| C01 — Conversación simple | Responder "hola", "a", "ok", "qué?", "nada" sin activar tools. Respuesta rápida (<8s). Sin herramientas. | MOSTLY_READY | test_runtime_persona_and_capabilities pasa. IntentClassifier detecta trivial_lowinfo. | No hay spotcheck manual reciente con modelo real. | Latencia real no medida en CI. "gracias" (7 chars) puede no ir a trivial_lowinfo. | MEDIUM |
| C02 — Identidad de Carter | Responder quién es, qué puede hacer, qué no puede. Sin mentiras. Describir stack real. | MOSTLY_READY | test_runtime_persona_and_capabilities pasa. system_prompt con arquitectura honesta incluido. | No hay spotcheck manual reciente. | Dependiente de que el LLM interprete bien el system_prompt de arquitectura. Con modelos débiles puede dar respuesta genérica. | MEDIUM |
| C03 — Conocimiento general | Responder preguntas sin tools innecesarias. "¿Quién es Batman?" → respuesta directa. | MOSTLY_READY | test_llm_first_responses pasa — verifica que Carter no llama tools para preguntas generales. | No reciente. | Con modelos muy débiles (phi3.5-mini), el LLM puede intentar llamar tools irrelevantes. | LOW |
| C04 — Memoria y preferencias | Guardar nombre/preferencias, recordarlas, olvidarlas. Persistencia entre sesiones vía SQLite. | MOSTLY_READY | test_memory pasa. test_memory_runtime_consistency pasa. memory_save/recall/delete implementados. | No reciente. | El detector declarativo es heurístico — puede fallar en frases no-declarativas. La oferta de guardar memoria requiere confirmación del usuario (diseño correcto). | LOW |
| C05 — Distinción intención vs. acción | "¿Puedes mutear?" (capacidad, no ejecución) vs. "mutea" (ejecución). No ejecutar sin pedirlo. | PARTIAL | test_runtime_no_fake_success_live_cases cubre algunos casos. | No reciente. | El sistema prompt dice "call it now if clearly fits" — puede ejecutar cuando el usuario solo pregunta capacidad. Gap real identificado en runtime audit hallazgo 12. | HIGH |
| C06 — Tool routing y contratos | Hora → clock_now. Volumen leer → system_get_volume. Volumen ajustar → system_set_volume. Tool mínima y correcta. | MOSTLY_READY | test_request_patterns_routing pasa. test_no_semantic_hardcodes pasa. | No reciente. | Routing pre-LLM via `synthesise_structural_tool_calls` puede entrar en conflicto con lo que el LLM decide. | LOW |
| C07 — Apps, ventanas, procesos | Abrir Notepad, verificar proceso, cerrar, verificar ausencia. Sin fake success. | PARTIAL | test_verifier_actions pasa (unit). test_graceful_close pasa. | BLOQUEADO en live-safe-all — no hay evidencia de live open/close real reciente. | En live-safe-all, Carter dice "no ejecuté". No hay test que demuestre live open+verify Notepad exitosamente. | BLOCKER para validación completa |
| C08 — Web y browser | Abrir URL, verificar tab. Cerrar tab. Buscar en web. Distinguir URL de búsqueda. | PARTIAL | test_web_helpers pasa. test_web_dispatch pasa (unit). | BLOQUEADO en live-safe-all. | web_open_url y web_search bloqueados en live-safe-all. No hay evidencia reciente de apertura real con verificación. | BLOCKER para validación completa |
| C09 — Steam biblioteca vs. tienda | No usar steam_run para búsquedas. Distinguir "busca juegos de Batman en Steam" (web) de "abre Steam" (app). | PARTIAL | test_no_semantic_hardcodes verifica ausencia de `steam` en runtime. | No reciente. | El parser de la guía tiene hack de steam. El runtime no. La distinción biblioteca/tienda depende de que el LLM entienda la diferencia — no hay regla explícita en runtime. | MEDIUM |
| C10 — Filesystem | Crear carpeta con confirmación, leer archivo, buscar archivos, borrar con backup. Sin fake success. | PARTIAL | test_filesystem_dispatch pasa. test_verifier verificar file existence. | BLOQUEADO: write/delete bloqueados en live-safe-all. | La política de filesystem requiere que el path sea "owned" (creado por Carter) para delete sin confirmación adicional. Nuevo path → requiere confirmación. Correcto per spec. | MEDIUM |
| C11 — Terminal y política | Ejecutar comandos seguros (python --version). Bloquear rm -rf, shutdown, format. | MOSTLY_READY | test_terminal_dispatch pasa. test_security pasa con 29 tests. PolicyEngine con 20+ patterns. | terminal_run_command bloqueado en live-safe-all pero política sí evaluada. | Pattern de shutdown no cubre `shutdown` en inglés solitario. Ver hallazgo 9 en runtime audit. | MEDIUM |
| C12 — Safety y fake success | Bloquear mensajes ofensivos que pidan acciones. Nunca decir "hecho" sin verificación. | MOSTLY_READY | test_guards pasa. fake_success_guard activo. test_runtime_no_fake_success_live_cases pasa. | No reciente. | fake_success_guard solo bloquea inicio de respuesta. Claims en medio de texto no bloqueados. | MEDIUM |
| C13 — GUI/visión con re-observación | Tomar screenshot verificado, listar ventanas, click en UI si es necesario, verificar resultado visual. | WEAK | test_vision_without_vlm pasa (unit sin VLM). UiaProbe implementado. | BLOQUEADO: gui_click/gui_type bloqueados en live-safe-all. window_list y screenshot sí corren. | gui_click real requiere modo `live` sin live-safe-all. No hay evidencia de click+verify exitoso reciente. | BLOCKER para GUI real |
| C14 — Misiones compuestas | "Abre X, busca Y, dime qué encontraste" — múltiples pasos, verificación por paso, progreso reportado. | PARTIAL | compound_action detectado en IntentClassifier. step_budget=6 en agent. | No reciente. | Sin progress reporting durante la misión. Con modelos débiles el LLM puede no generar multi-tool correctamente. Misiones de >2 pasos no probadas live. | HIGH |
| C15 — Latencia y recursos | Inputs triviales < 8s. Tools simples < 12s. No GPU overhead para saludos. | WEAK | test_llm_first_responses verifica que triviales van a LLM directamente (sin tools). Latencia no medida en CI. | Sin medición live reciente. | Los tests de latencia en la matriz son en modo scripted (0ms). No hay medición real de tiempo con Ollama + modelo. | HIGH |
| C16 — Multilingüe y typos | Español informal, inglés, mezclas, "abre stean" → abre Steam. Tolerancia a typos. | MOSTLY_READY | test_no_semantic_hardcodes verifica no hay listas de idioma. script_mismatch_guard en guards. fuzzy resolver. | No reciente. | Typo threshold del resolver puede ser demasiado alto para nombres de apps. "stean" → fuzzy match a "steam" depende de threshold. | MEDIUM |
| C17 — Follow-ups y contexto | "Ciérralo" después de abrir Notepad → cierra Notepad. Sin contamination. pending_intent para sí/ok. | MOSTLY_READY | test_pending_intent_followups pasa. session_state.prior_deictic_match implementado. | No reciente. | `_short_same_language_nonsecret` rechaza "Sí" y "OK" con mayúscula — gap en confirmación de follow-up. | MEDIUM |
| C18 — Regresiones reales | Bugs reales del usuario capturados como casos permanentes. Smoke tests de uso real. | PARTIAL | test_live_regressions_from_user_log existe pero con pocos casos. | No hay transcripts reales recientes documentados como regresiones. | C18 debería tener al menos 30 bugs reales capturados. La guía dice que cada bug se convierte en caso permanente. | MEDIUM |

---

## Resumen de estado por categoría

| Rango | Categorías |
|---|---|
| MOSTLY_READY (5) | C01, C02, C03, C04, C11 (con gaps menores) |
| PARTIAL con gaps significativos (8) | C06, C07, C09, C10, C12, C14, C17, C18 |
| WEAK — necesita trabajo real (3) | C05 (intención vs acción), C13 (GUI real), C15 (latencia real) |
| BLOCKER para validación real (2) | C07 y C13 necesitan `live` mode real con rollback |

---

## Qué debe hacer Codex por categoría

### C05 — Distinción intención vs. acción
- Revisar system_prompt para que no incite ejecución cuando el usuario pregunta capacidad
- Agregar test: "¿puedes mutear?" → NO ejecuta mute, responde "sí puedo si me lo pides"

### C07 — Apps (BLOCKER validación)
- Crear test de integración live (con modelo real) para: open Notepad → verify process → close → verify absence
- Documentar protocolo para run `live` seguro con cleanup

### C08 — Web (BLOCKER validación)
- Crear test live para: abrir https://example.com → verificar tab domain → cerrar → verificar ausencia

### C13 — GUI real (BLOCKER)
- Actualmente sin evidencia de gui_click real exitoso
- Necesita test live: screenshot → verify file exists → es lo mínimo
- gui_click/gui_type requieren entorno live real

### C14 — Misiones compuestas
- Agregar progress reporting entre steps (emit "Ejecutando paso N/M: ...")
- Test live de misión de 3 pasos: abre X → lee Y → cierra X

### C15 — Latencia
- Agregar medición de latencia real con Ollama en CI (aunque sea opcional/no-blocking)
- Definir qué modelo se usa para latencia benchmark

### C17 — Follow-ups
- Fix: `_short_same_language_nonsecret` debe aceptar "Sí", "OK", "YES" como confirmaciones

### C18 — Regresiones
- Capturar al menos 5 bugs reales del usuario como casos permanentes con test correspondiente
