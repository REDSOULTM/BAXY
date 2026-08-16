# Hardcode & App Hack Audit — Carter v2

Generated 2026-05-01 by the OPUS hardcode-elimination pass.
Scope: every file under `src/carter_v2/**` and `tests/**`.
Method: structural grep + manual read of every site flagged below.

---

## 1. Veredicto brutal

**Sí, Carter todavía depende de hardcodes léxicos en runtime.** Después
de la pasada F8 / C1 quedaron tres familias de basura crítica:

1. **Listas multilingües de verbos / pronombres dentro de
   `mission.py`** — el regex `_IMPERATIVE_PAIR_RE` que el usuario
   detectó es real y decide si una misión se descompone en dos
   pasos. Habla español, italiano, portugués e inglés con vocabulario
   fijo. Cualquier idioma fuera de esa lista (alemán, francés, chino,
   japonés, ruso, …) jamás dispara compound y Carter trata
   "abre Notepad und schließe es" como un single shot.

2. **Listas multilingües de affordances en
   `capabilities/gui_agent.py`** (`_SEARCH_TOKENS`,
   `_SETTINGS_TOKENS`, `_CLOSE_TOKENS`, `_PLAY_TOKENS`,
   `_BACK_TOKENS`). Mezclan vocabulario ES / EN / JP / ZH / RU / AR.
   No son listas internas de tools: deciden qué *fallback visual*
   se intenta sobre la pantalla del usuario.

3. **Hacks por aplicación** dispersos:
   - `agent.py::_update_active_app_context` codifica
     `window="Steam"` y `process="steam.exe"` cuando ve
     `steam_open_client`.
   - `mission_observation.py::_PROCESS_PREFIXES` lista
     `"steam_"` junto a `app_/process_/uninstall_`.
   - `tool_catalog_selection.py::_CAPABILITY_PEERS` incluye un
     grupo `{"steam_open_client", "steam_run", "steam_stop"}`.
   - `tool_normalizer.py` contiene normalizaciones específicas de
     `steam_*`.
   - `capabilities/app_resolver.py::_ALIASES` codifica
     `"bloc de notas" → "notepad"`, `"opera gx browser" → "opera gx"`,
     etc.

4. **Listas de marcadores por idioma en `tool_normalizer.py`:**
   - `_looks_like_existence_query`: `("existe", "exists", "exist ")`
   - `_looks_like_email_inbox_query`: `("email","correo","inbox", …)`
     y `("ultimo","último","ultimos","últimos","recent","latest","last")`

5. **Vocabulario en `invariants.py`:**
   - `_PUBLIC_TOKEN_RE = r"\b(?:public|publica|wan|external|externa|internet)\b"`
   - el guard `"ública" in text.lower()` (manual, español).
   - `_GIT_VERB_TOKEN_RE = r"\b(status|diff|log|state)\b"` — vocabulario
     técnico inglés, no estructural.

6. **Brand-leaked system prompt (`turn/_system_prompt.py`):**
   - Cita explícita: "(steam, discord, spotify, edge, chrome,
     electron-based …)"
   - "(notepad, explorer, calculator, settings, office)"
   - Ejemplos del usuario embebidos en la política
     ("¿qué hora es?", "what time is it?",
     "¿cuál es la capital de Francia?", "Biblioteca on a Spanish Steam",
     "Quien eres", "borra todos los archivos del sistema", …).

7. **Hacks en tests:** `test_brain_router_fase7.py`,
   `test_agent_intent_continuity.py`, `test_agent_misrouting_and_memory_hardening.py`,
   `test_a11_multilang_identity.py` validan frases exactas o
   apps específicas. Algunos se quedan como smoke (documentados),
   los que protegían listas léxicas se reescriben para validar
   comportamiento estructural.

Severidad: alta. Hay ~400 LoC de hardcode crítico repartido en
9 archivos runtime. La pasada F8 atacó la mitad superior — esta
pasada (H1–H8) cierra el resto.

---

## 2. Tabla de hallazgos

| ID | archivo | símbolo / línea | tipo | severidad | razón | reemplazo | test |
|---|---|---|---|---|---|---|---|
| H-MIS-01 | `src/carter_v2/turn/mission.py` | `_STRUCTURAL_CONNECTOR_RE` | LANGUAGE_HARDCODE | crítico | regex con `y luego / and then / luego / después / after that` decide si hay misión compuesta | borrar; mantener solo punctuation + pipeline glyph + multi-sentence detector | `tests/test_mission_language_neutral.py` |
| H-MIS-02 | `src/carter_v2/turn/mission.py` | `_IMPERATIVE_PAIR_RE`, `_ENCLITIC_TOKEN_RE`, `_OBJECT_PRONOUN_RE` | LANGUAGE_HARDCODE | crítico | bare `y/e/and` + morfología romance / pronombres ingleses como gate de compound | borrar; usar señales estructurales (puntos, `;`, glyph, múltiples cláusulas separadas por puntuación fuerte) | idem |
| H-MIS-03 | `src/carter_v2/turn/mission.py` | `_SPLIT_PATTERNS` (`then_en`, `then_es`, `imperative_pair`) | LANGUAGE_HARDCODE | crítico | divide por palabras concretas | borrar; usar solo `;`, `->`, `=>`, `→`, `.`, `?`, `!`, `,` | idem |
| H-INV-01 | `src/carter_v2/turn/invariants.py` | `_PUBLIC_TOKEN_RE` con `publica/externa/internet` | LANGUAGE_HARDCODE | medio | invariant IP redirect inspecciona vocabulario | reducir a `\bpublic\b` + `\bwan\b` (técnicos universales); descartar resto | `tests/test_no_runtime_hardcodes.py` |
| H-INV-02 | `src/carter_v2/turn/invariants.py` | `"ública" in text.lower()` | LANGUAGE_HARDCODE | medio | parche español manual | borrar | idem |
| H-INV-03 | `src/carter_v2/turn/invariants.py` | `_GIT_VERB_TOKEN_RE = (status\|diff\|log\|state)` | ACCEPTABLE_INTERNAL_CONSTANT | bajo | son sub-comandos git universales (no localizados); aceptable | mantener pero documentar | n/a |
| H-NRM-01 | `src/carter_v2/adapters/tool_normalizer.py` | `_looks_like_existence_query` (`existe/exists/exist`) | LANGUAGE_HARDCODE | medio | decide redirect filesystem | borrar; el LLM elige `filesystem_get_stat` por descripción | guard test |
| H-NRM-02 | `src/carter_v2/adapters/tool_normalizer.py` | `_looks_like_email_inbox_query` | LANGUAGE_HARDCODE | medio | inspecciona vocabulario multilingüe | borrar | guard test |
| H-NRM-03 | `src/carter_v2/adapters/tool_normalizer.py` | `_memory_save_args_from_text`, `_memory_recall_key_from_text` | LANGUAGE_HARDCODE / DEAD_CODE | medio | regex con `recuerda que mi / remember that my / mi X es` | borrar (ya están sin call-site tras F8) | guard test |
| H-NRM-04 | `src/carter_v2/adapters/tool_normalizer.py` | rama de redirect `steam_*` | APP_HACK | medio | clavija dura por app | mantener solo redirect genérico cuando `resource_resolver` resuelve `app` con confidence ≥ 0.75 | normalizer test |
| H-AGT-01 | `src/carter_v2/turn/agent.py` | `if tool == "steam_open_client": window="Steam"; process="steam.exe"` | APP_HACK / BRAND_HACK | crítico | rama por app dentro del loop del agente | borrar; usar `result.data.get("window_title")` / `process_name` o dejar que la propia capability los declare | guard test |
| H-AGT-02 | `src/carter_v2/turn/agent.py` | `_ACTIVE_APP_DEPRIORITIZED_TOOL_NAMES` incluye `"steam_search"` | APP_HACK | medio | nombre de app entre nombres genéricos | reemplazar por categoría (`startswith("steam_")` ya está cubierto por la regla de prefijo, pero mejor: dropear y dejar que el catálogo per-step gestione) | guard test |
| H-AGT-03 | `src/carter_v2/turn/agent.py` | comentario `# otherwise short identity questions ("Quien eres")` | DOC_LEAK | bajo | comentario referencia frase de usuario | reemplazar por descripción genérica | n/a |
| H-OBS-01 | `src/carter_v2/turn/mission_observation.py` | `_PROCESS_PREFIXES` con `"steam_"` | APP_HACK | medio | prefijo de marca en clasificador estructural | quitar `"steam_"`; basta `app_/process_/uninstall_` | `tests/test_no_app_hacks_in_agent.py` |
| H-CAT-01 | `src/carter_v2/turn/tool_catalog_selection.py` | `frozenset({"steam_open_client", "steam_run", "steam_stop"})` en `_CAPABILITY_PEERS` | APP_HACK | medio | grupo per-app dentro del selector neutral | borrar entrada; las herramientas steam ya quedan agrupadas por su prefijo cuando se piden explícitamente | guard test |
| H-GUI-01 | `src/carter_v2/capabilities/gui_agent.py` | `_SEARCH_TOKENS / _SETTINGS_TOKENS / _CLOSE_TOKENS / _PLAY_TOKENS / _BACK_TOKENS` | LANGUAGE_HARDCODE | crítico | listas multilingües ES/EN/JP/ZH/RU/AR deciden qué affordances probar | reemplazar por slots semánticos exposed por el LLM (ya usa planner LLM) o por categorías estructurales sin lookup léxico | guard test |
| H-GUI-02 | `src/carter_v2/capabilities/gui_agent.py` | candidatos hardcodeados `"campo de busqueda"`, `"caja de búsqueda"`, `"icono de lupa"` | LANGUAGE_HARDCODE | medio | candidates en español dentro del fallback genérico | reducir a frases inglesas neutras (vocabulario interno hacia el modelo de visión, no del usuario) | guard test |
| H-RSV-01 | `src/carter_v2/capabilities/app_resolver.py` | `_ALIASES = {"bloc de notas": "notepad", "calculadora": "calculator", "vs code": "visual studio code", "opera gx": …}` | APP_HACK / LANGUAGE_HARDCODE | medio | diccionario léxico per-app | borrar; el matcher fuzzy + Get-StartApps cubre el caso real (Windows ya devuelve nombres localizados) | resolver test |
| H-PRM-01 | `src/carter_v2/turn/_system_prompt.py` | `"(steam, discord, spotify, edge, chrome, electron-based …)"` y `"(notepad, explorer, calculator, settings, office)"` | BRAND_HACK / PROMPT_HARDCODE | medio | nombres de apps en system prompt | reemplazar por categoría: "opaque/CEF apps" vs "UIA-friendly apps" sin nombres | guard test (escaneo del prompt) |
| H-PRM-02 | `src/carter_v2/turn/_system_prompt.py` | ejemplos con frases del usuario en ES/EN ("¿qué hora es?", "what time is it?", "Biblioteca", "Quien eres", "borra todos los archivos del sistema", …) | PROMPT_HARDCODE | medio | el system prompt enseña con frases concretas en idiomas concretos | dejar política abstracta sin frases (Carter responde en el idioma del usuario) | guard test |
| H-PRM-03 | `src/carter_v2/turn/_system_prompt.py` | bloque vision_status hardcoded de apps | BRAND_HACK | medio | mismo problema, bloque dinámico | reemplazar por descripción genérica de "opaque/CEF/Chromium-style windows" | guard test |
| H-MEM-01 | `src/carter_v2/session/memory.py` | bloques `"[Notas duraderas de Carter]"`, `"[Entidades frecuentes:"`, `"[Historial reciente]"` | LANGUAGE_HARDCODE (output) | bajo | el header inyectado es ES fijo; el LLM responde en idioma del usuario, pero el preámbulo siempre habla español | reescribir headers en inglés neutro (idioma interno), o sin idioma | n/a |
| H-TST-01 | `tests/test_a11_multilang_identity.py` | valida frases exactas | TEST_HARDCODE | bajo | smoke documentado | mantener como smoke con marcador |
| H-TST-02 | `tests/test_brain_router_fase7.py` | "abre steam y luego cierra discord", "打开 Steam" | TEST_HARDCODE | bajo | mantener como smoke |
| H-TST-03 | `tests/test_mission_state.py` | espera split por "y luego" / "y" + enclítico | TEST_HARDCODE | medio | reescribir para validar el contrato neutral nuevo (split por puntuación / glyph) |
| H-DOC-01 | `src/carter_v2/main.py` líneas 367–413 | banner ASCII con ejemplos por marca | DOCUMENTATION | bajo | aceptable (solo banner CLI), pero conviene neutralizar | banner abstracto |

Total filas: 24.
Críticas (runtime, deciden routing): 6 (H-MIS-01..03, H-AGT-01, H-GUI-01, H-PRM-01).

---

## 3. Clasificación

**Crítico (runtime, decide routing/planning/tools):**
- H-MIS-01, H-MIS-02, H-MIS-03 — mission decomposition.
- H-GUI-01 — multilingual affordance lists deciden visual fallbacks.
- H-AGT-01 — special-case Steam dentro del agente.
- H-PRM-01 / H-PRM-03 — system prompt cita marcas concretas.

**Medio (fallback / sugerencia):**
- H-INV-01, H-INV-02 — invariant IP redirect.
- H-NRM-01, H-NRM-02, H-NRM-03 — normalizer language markers.
- H-NRM-04 — steam-specific normalizer.
- H-AGT-02 — `steam_search` en deprioritized list.
- H-OBS-01 — `steam_` prefix.
- H-CAT-01 — peer group con steam tools.
- H-RSV-01 — alias dict app_resolver.
- H-PRM-02 — ejemplos por idioma en system prompt.

**Aceptable (constante interna o smoke documentado):**
- H-INV-03 (sub-comandos git universales).
- H-TST-01..03 (smoke con frases reales del usuario, documentados como tales).
- H-DOC-01 (banner CLI).

**Documentación-only:**
- H-AGT-03 (comentario).
- H-MEM-01 (headers de prompt — borderline; los neutralizamos).

---

## 4. Reemplazos universales (resumen)

| familia | hardcode | reemplazo |
|---|---|---|
| compound detection | listas de conectores y verbos | señales estructurales: `;`, `->`, `=>`, `→`, terminadores `.?!` repetidos, `,` con dos cláusulas con verbo implícito (≥3 tokens cada una). LLM judge opcional vía `CARTER_INTENT_DECOMPOSITION_LLM=1` |
| affordance fallback (GUI) | listas léxicas multilingües | el planner LLM ya genera el `target` en el idioma de la UI; eliminamos el fallback léxico y dejamos solo candidatos genéricos en *inglés interno* (vocabulario del modelo de visión, no del usuario) |
| app special-cases | ramas `if tool == "steam_*"` | metadata genérica del `CapabilityResult` (`window_title`, `process_name`); las capabilities steam ya pueblan estos campos |
| brand prompts | listas de nombres de app | descripciones por categoría (UIA-friendly vs opaque/CEF) |
| language markers en queries | `existe/exists`, `correo/email/inbox`, `last/latest/recent` | el LLM lo decide por descripción de tool |
| diccionarios `_ALIASES` | léxico ES → EN | matcher fuzzy + lo que devuelve `Get-StartApps` (Windows ya localiza) |

---

## 5. Plan de eliminación

- **H1** — refactor `mission.py` (M1).
- **H2** — refactor `invariants.py`, `tool_normalizer.py`, agent.py (M2).
- **H3** — quitar app-hacks en `agent.py`, `mission_observation.py`, `tool_catalog_selection.py`, `app_resolver.py` (M3).
- **H4** — limpiar `_system_prompt.py` y headers en `memory.py` (M4).
- **H5** — actualizar tests rotos.
- **H6** — `audit/hardcode_guard.py` + `audit/HARDCODE_GUARD.json`.
- **H7** — nuevos tests de gates (`test_no_runtime_hardcodes.py`, etc.).
- **H8** — `HARDCODE_ELIMINATION_REPORT.md`.

No se introducen listas nuevas. Se sustituyen reglas léxicas por
señales estructurales (puntuación, prefijos de tools, presencia de
metadatos en `CapabilityResult`, categorías UIA vs opaque, peers
estructurales por convención de naming).
