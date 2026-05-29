# Plan de optimización de tokens del prompt + tools (latencia)

**Autor:** Opus 4.8, 2026-05-28. **Base:** auditoría ESTÁTICA medida con
`scripts/_audit_prompt_tokens.py` (estimación chars/3.6). **Regla dura:** cada
reescritura de un rule/descripción es QUALITY-SENSITIVE → **validación EN VIVO
obligatoria** antes de mergear (regla #1: medí, no celebres; #3.5: probá en vivo).
NO se puede "garantizar calidad" a ciegas — por eso esto es un PLAN medido, no
cambios aplicados.

## Datos medidos

**Piso del system prompt (CADA turno): ~2520 tok**
- `core_lean.md`: 1016 tok
- 6 reglas always-on (Plan A2): 1504 tok → `app`:444, `system`:369, `audio`:318,
  `window`:168, `session`:124, `web`:81
  - **`app`+`system`+`audio` = 1131 tok en TODOS los turnos** (máxima leverage).

**Ballenas (se mandan SOLO cuando su tool entra al subset, cap 5-8):**
| tool | guía total | desc (schema) | rule (prosa) |
|---|---|---|---|
| **media** | **2226** | 393 | **1833** |
| whatsapp | 1439 | **918** | 521 |
| browser | 1315 | 167 | **1148** |
| routine | 1302 | 238 | **1064** |
| gui | 866 | 316 | 550 |
| audio | 709 | 391 | 318 |
| office | 559 | 90 | 469 |

**Turno de acción típico** (piso + 5 schemas): ~4788 tok sin historial. Con FA-off
(~4100 tok/s prefill) eso es ~1.2s de prefill por llamada; bajarlo 30% = ~0.4s/call,
×2-5 calls/turno de acción = win real de latencia.

## Levers priorizados (impacto × seguridad)

### A. Always-on (pega cada turno — MÁXIMA leverage)
1. **rule `app` (444→~200)** y **`system` (369→~200)**: son los 2 always-on más
   gordos. Densificar (mismo contenido, menos prosa) ahorra ~400 tok en CADA turno.
   - Gate vivo: abrir/cerrar apps + system(time/disk/cpu/brightness) siguen ruteando 8/8.

### B. Ballenas de acción (cuando entran al subset)
2. **rule `media` (1833→~700)**: el item individual más grande. Cubre todos los
   providers + auto_play + casting en prosa larga. Densificar/tabular ahorra ~1100 tok
   en cualquier turno de media (muy común).
   - Gate vivo CRÍTICO: streaming (Spotify random, Netflix/Disney profile flow,
     youtube_play, pausa/stop) sin regresión — la memoria tiene MUCHOS fixes acá.
3. **rule `browser` (1148→~450)** y **`routine` (1064→~450)**: idem.
   - Gate vivo: browser.open por nombre/URL + youtube_play; routine create/cron/import.
4. **desc `whatsapp` (918→~450)**: la descripción del schema con TODOS los ejemplos
   de slot-filling. Mover los ejemplos al rule (consolidar) o comprimir.
   - Gate vivo CRÍTICO: slot-filling (body/contact/channel) + los fraseos PATTERN que
     los ejemplos arreglaron — NO romper "mandale a X que Y".

### C. Duplicación desc↔rule
5. Varios tools enseñan lo mismo en la `description` del schema Y en el `rule`
   (ej. `audio` desc 391 + rule 318). Consolidar en UNO solo ahorra ~la mitad.
   - Gate vivo: el tool sigue usándose bien con la guía en un solo lugar.

## Ahorro estimado (con validación)
Turno de acción típico ~4788 → **~3000-3300 tok** (-30-35%) reescribiendo A+B+C.
Eso baja el prefill FA-off proporcionalmente Y reduce dilución de atención (mejor
tool-calling en el E2B débil — RAG-MCP/EasyTool). Combinado con FR-CoT, es el
camino a turnos de acción dentro del presupuesto.

## Cómo ejecutarlo BIEN (cuando el usuario no juegue)
Por cada rule a densificar, el ciclo es:
1. Reescribir DENSO preservando CADA instrucción/anti-patrón (entender el bug que
   arregló — leer git blame del rule, no borrar a ciegas).
2. Detrás de flag `GEMMA4_LEAN_RULES=1` (dormant), o reemplazo directo + backup.
3. Validar EN VIVO los fraseos de ESE dominio (3-4 variantes c/u) + medir tokens.
4. Gate: tool-calling ≥ baseline en ese dominio, 0 regresión. Si pasa, mergear.
Hacerlo de a un dominio (no todo junto) para aislar regresiones.

## Lo que NO se debe hacer
- Reescribir los rules a ciegas (sin vivo) y declarar "optimizado": el E2B es
  no-determinista; un rule mal podado mis-rutea (ej. media→browser) y solo el vivo
  lo agarra. La memoria ya tiene el precedente (FR-CoT rompió media así).
- Tocar el `core_lean.md` (1016 tok): es el núcleo anti-alucinación/voz/tool-call;
  ya es lean; el ROI está en los rules gordos, no acá.

## Estado — ESCRITO (dormant) 2026-05-28
Las 7 reglas pesadas YA están reescritas densas como `<rule>.lean.md` (media,
browser, routine, app, system, audio, gui), cargadas solo con **`GEMMA4_LEAN_RULES=1`**
(default off = los `.md` de siempre, sin cambio). Wiring en `agent_prompt._load_tool_rules`.

**Medido (chars/3.6):** -30% en las 7 (media -37%, browser -32%, routine -34%,
gui -21%, app -22%, system -17%, audio -14%). Always-on (app+system+audio) ahorra
~210 tok en CADA turno; un turno de media ahorra ~900 tok (media lean + always-on).

**Validado con stubs** (`tests/test_lean_rules.py`, 5 tests): wiring on/off, las lean
son más chicas, y PRESERVAN los anti-patrones críticos (via_cdp, streaming_profile,
ANTI-URL-FABRICATION, on_phrase/trigger types, launch_requested, calculator-pattern,
mute/unmute, operate-app-by-keyboard). 98 tests verdes con el flag off.

**FALTA (validación EN VIVO, usuario sin jugar):** prender `GEMMA4_LEAN_RULES=1` +
probar los fraseos de cada dominio (media streaming/pause, browser nombre/URL/store,
routine triggers, app open/honesty, system/audio/gui) — gate: tool-calling ≥ baseline,
0 regresión. Si un dominio regresa, ajustar SU `.lean.md` en vivo (no a ciegas).
Si pasa todo → default-on.

### Descripciones de schema LEAN — TAMBIÉN ESCRITAS (dormant) 2026-05-28
Las 4 descripciones más pesadas reescritas lean en `tools.py` (`LEAN_DESCRIPTIONS`),
aplicadas SOLO en `schemas_for_names` (el subset que ve el LLM) cuando
`GEMMA4_LEAN_RULES=1` — **NO muta el literal global** (`COMPOUND_TOOL_SCHEMAS`), así
el contract-test (`test_tool_registry_contract`) sigue verde verbatim:
- whatsapp 918→316 (-66%), computer_use 466→234 (-50%), media 393→204 (-48%),
  audio 391→125 (-68%). **Total -59%.**
Validado `tests/test_lean_descriptions.py` (6 tests): más chicas, preservan los
tokens críticos de SELECCIÓN (send_message/SLOT FILLING/auto_send; goal/Discord/NOT
for; provider/spotify/streaming_profile; set_volume/media_stop/NOT to close), y NO
mutan el global. **OJO: las descripciones DRIVEN la selección de tool → es el trim de
MAYOR riesgo** (una desc mal podada hace que el modelo elija el tool equivocado).
Validar en vivo con MÁS cuidado que los rules, sobre todo whatsapp (slot-filling) y
computer_use (routing vs whatsapp/app).

Pendiente (próximo batch, mismo mecanismo): el `whatsapp` RULE (521 tok, no leaneado
aún), y descs medianas (session 350, browser_real 364, gui 316, steam, window).
Ver `SPRINT_frcot_latencia_accion.md` (palanca ortogonal: thinking).
