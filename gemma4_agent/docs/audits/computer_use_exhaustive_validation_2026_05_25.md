# Validación exhaustiva de computer-use — 2026-05-25

Sesión de validación pedida por RED: "haz por lo menos 10 casos de prueba por
cada cosa hecha con GUI, computer-use, directo con el LLM... sin quedarte en la
satisfacción de mediocridad". Toda medición por **estado del SO**, no por el texto
del modelo. Branch `PortandoLoMejor`.

> Nota de honestidad (CLAUDE.md §3): se reportan los números crudos, incluido lo
> que falló y por qué, y se separa lo MEDIDO de la hipótesis.

## Resultados medidos

| Área | Resultado | Cómo se midió |
|---|---|---|
| `type_into` (Calculadora) | **10/10** | display `CalculatorResults` por UIA en subproceso |
| `click_button` (Calculadora, 40 clicks en 10 secuencias) | **10/10** | clicks por NOMBRE de botón (Dos/Más/Es igual a…) → display |
| `click_button` (Discord, árbol **caliente**) | **10/10**, 0 robos de foco | ok + element name + foreground sin cambiar |
| `click_button` (Discord, árbol **frío**, usuario en otra app) | **5/5**, roba foco | el provider de Discord exige foreground (ver abajo) |
| LLM e2e computer-use (Calculadora, 1 sesión multi-turno) | **9/9** operaciones | `run_text("escribí X y apretá igual")` → display |

## Causas raíz encontradas y corregidas

### 1. BUG DE PRODUCCIÓN — la guarda de actividad-del-usuario se auto-bloqueaba
`gui_safety.check_user_activity()` usa `GetLastInputInfo` para no pelear el
teclado si el usuario está activo. El propio input SINTÉTICO del agente (el
ALT-trick de `_focus_window_chen`, los keypress por SendKeys-PowerShell, el
Invoke de `_uia_click_inproc`) reseteaba `GetLastInputInfo` PERO no se marcaba
con `note_agent_input()`. Resultado: tras enfocar una ventana, la acción
SIGUIENTE veía "actividad reciente" y la atribuía al usuario → `blocked:
user_active` → el agente difería su propia acción. **Medido**: type_into tras
enfocar daba `blocked=user_active` desde el 1er turno (notepad 0/n). **Fix**:
`note_agent_input()` en los 3 sitios que generan input sintético
(`_focus_window_chen` ALT-trick, `gui_keypress` rama SendKeys, `_uia_click_inproc`).
Tras el fix: notepad 6/6, calc 10/10. Esto explica parte del histórico
"anda 2-3 y muere" en multi-paso.

### 2. Cascada `click_button` ahora es foreground-safe
El modelo viejo ("Electron solo puebla su árbol con foco") era una correlación
no aislada. Medición limpia: el árbol in-process de Discord se lee COMPLETO
(708 controles, 10/10 clicks) aunque Discord NO tenga el foreground, **si el
árbol está caliente**. El 6/10 viejo no era COMError ni árbol colapsado: era el
robo de foco compitiendo con el usuario activo. **Fix**: la cascada lee
in-process PRIMERO (no toca el foreground del usuario); solo si falla, enfoca
como fallback y reintenta. `focus_stolen` queda en el result. En uso real, con
el usuario trabajando, no se le roba el foco salvo necesidad.

### 3. Determinante REAL del árbol UIA de Discord = **temperatura del árbol**
Medido inequívoco esta sesión: Discord frío = 6 controles; **enfocarlo lo lleva
a 698** (`6 → 698` reproducible). No es "intermitente patológico" (diagnóstico
viejo, ERRÓNEO) ni falta de flag: el provider de Discord expone el árbol
on-demand mientras hay un cliente UIA conectado + foreground; al desconectarse
se enfría. Consecuencia operativa: con árbol caliente el agente clickea SIN robar
foco; con árbol frío (usuario en otra app) DEBE enfocar Discord para poblarlo
(robo de foco inevitable, autorizado por RED). La cascada maneja ambos.

### 4. Regla de prompt — limpiar la entrada de una app es TECLADO, no filesystem
Medido con el LLM: "borrá y escribí 5x5…" hacía que el 4B ruteara "borrá" a
`filesystem.delete` ("¿qué archivo querés borrar?"). El router NO tiene la culpa
(sugiere gui/uia/input para el comando completo); es el 4B débil pattern-matching
"borrá"→borrar-archivo. **Fix** en `prompts/tool_rules/gui.md`: enseñar que
limpiar lo que ve una app abierta (display de calc, un campo) es
`keypress ESC` o `CTRL+A`+`DELETE`, NUNCA `filesystem`. Aun así, "borrá" como
verbo suelto sigue siendo un comando ambiguo (límite del 4B, documentado).

## Límites honestos (no se fuerzan)

- **El verify del agente sub-reporta**: en las 9/9 operaciones LLM, el display
  quedó correcto PERO las respuestas decían "no pude verificar el resultado". El
  frame-diff/UIA-snapshot no siempre capta el cambio del display de la calc. La
  ACCIÓN tiene éxito; la auto-confianza es pesimista (honesto, no peligroso).
- **La herencia de contexto GUI encadena solo si cada turno `run_text` previo usó
  una tool GUI**. Si el 4B rechaza una vez (p.ej. por "borrá"→filesystem), rompe
  la cadena y los turnos siguientes también fallan. Mitigación futura posible:
  herencia por ESTADO DEL SO (app abierta) y no solo por turno previo — NO
  implementado esta sesión (riesgo de regresión en no-tool conversacional).
- **Notepad de Win11 es mal fixture de test** (instancia única con pestañas,
  diálogos de Guardar, session-restore). NO es un problema del agente: calc
  prueba type_into 10/10. Se descartó como fixture.

## Incidente y su resolución (transparencia con RED)
El harness, al usar `notepad.exe`, cayó en el Notepad del usuario con `ram.txt`
abierto (buffer SIN guardar, no existe en disco) y le antepuso texto de prueba.
Se **restauró** el contenido original vía UIA `SetValue` (título sin asterisco =
buffer == disco/restaurado) y quedó preservado en el session-restore (TabState) +
un proceso vivo. **Sin pérdida de datos.** El harness ahora usa archivos propios
con guarda por nombre único y nunca toca ventanas que no creó.

## Harnesses (reproducibles)
- `scripts/_exhaustive_gui_test.py` — calc type_into + notepad (archivo propio).
- `scripts/_exhaustive_click_test.py` — calc click_button por nombre.
- `scripts/_exhaustive_llm_test.py` — LLM e2e multi-turno (vram4 en :8080).
- `scripts/_exhaustive_discord_test.py` — Discord en condiciones reales.
- Resultados crudos: `scripts/gui_eval/_exhaustive_*_results.json`.

---

## ADDENDUM — navegación-en-app + envío-de-mensaje en Discord (continuación, mismo día)

Tras la validación de arriba, RED reportó dos fallas reales de computer-use en
Discord vía la UI. Diagnóstico en vivo + fixes (commits 3d0efbc, 69f3c76, a4186f3,
42a3549):

### 5. "Ve a discord y pon el chat de X" iba a WhatsApp y cancelaba el turno
Cadena de 3 fallas: (a) el SPLITTER partía "Ve a discord" | "pon el chat de X" y la
2da cláusula, aislada, perdía "discord" → el router la puntuaba whatsapp=0.58 (medido)
→ abría el chat en WhatsApp. (b) La desambiguación por estado del SO se SALTABA si el
router ya había puesto uia. (c) Los distractores que se sacaban eran muy pocos
({game_launcher,app,steam}), no whatsapp/contacts/media/session. FIX: un "ir/entrar a
<app>" puro NO parte (es prefijo de contexto); la desambiguación corre siempre que una
ventana matchee; se sacan los distractores de mensajería/lanzamiento conservando la
tool dedicada si la ventana ES de esa app.

### 6. BUG RAÍZ — el macro de navegación-en-app NUNCA corría por run_content
`_try_in_app_nav(content, turn_id)` se llamaba con `turn_id` ANTES de asignarlo
(estaba ~30 líneas abajo) → `UnboundLocalError` SIEMPRE, tragado por `except: pass`
→ el macro determinista jamás se ejecutaba vía run_text; TODO caía al LLM (que
desambigua mal y no encadena). Por eso "andaba en llamada directa pero no por el
agente". FIX: generar `turn_id` antes del macro; el except ahora deja traza.

### 7. Árbol UIA "intermitente" de Discord = ventana MINIMIZADA
Lo que parecía intermitencia patológica era: Discord minimizado (iconic, rect en
-21333) NO renderiza su DOM → árbol UIA colapsa a ~5 controles → todo find/click
falla. MEDIDO: `ShowWindow(SW_RESTORE)` lo lleva de 5 → 646/698 controles.
`_focus_window_chen` no des-minimizaba (SetForegroundWindow no restaura); FIX: agrega
`IsIconic`+`ShowWindow(SW_RESTORE)`. Universal (cualquier app minimizada).

### 8. Chats NO visibles: quick-switcher (Ctrl+K) + verify por TÍTULO
Un chat que no está en la vista actual no tiene control clickeable. Vía universal en
apps de chat Electron: Ctrl+K → nombre → Enter. Determinista (no depende del árbol
ni de que el 4B encadene), verifica por el TÍTULO de la ventana (refleja el chat
activo). El `state_changed` (frame-diff) daba False cuando el foco saltaba tras el
click y el agente reportaba fallo de un éxito real → ahora se verifica por título.
Combos de teclado (ctrl+k) migrados a SendInput in-process (PowerShell-SendKeys no
aterrizaba fiable por el robo de foco). Match case-insensitive ("cbayeah"→"CbaYeah").

### 9. ENVÍO de mensajes — "escribe a X en discord y dile que ..."
El 4B decía "no tengo la herramienta" (falso: tiene gui/uia). NUEVO macro
`_try_in_app_message`: quick-switcher al contacto + type(mensaje) + Enter, verify
por estado del SO. `extract_message_to` separa (contacto, mensaje) multi-idioma;
"a <contacto>" OBLIGATORIO para escribe/write (así "escribí 2+2" NO se confunde con
mensaje); "que" se preserva ("dile que haces" → "que haces"). MEDIDO en vivo: envió
"que haces" a CbaYeah (verificado: aparece en el chat). Sin mensaje → abre y pregunta.

**Estado final Discord (medido):** "Ve a discord y pon el chat de cbayeah" → abre el
chat (restaura si está minimizado, navega, verifica por título). "escribe a cbayeah
en discord y dile que haces" → navega + teclea + ENVÍA, verificado en el chat. La
navegación/envío-en-app es DETERMINISTA y foreground-safe; el robo de foco solo
ocurre si el árbol está frío (app minimizada/sin foco), que RED autorizó.

---

## ADDENDUM 2 — REDISEÑO UNIVERSAL (RED: "está mal diseñado, una función por cada cosa")

RED señaló (con razón) que los macros por-intención (`_try_in_app_nav`,
`_try_in_app_message`, ...) eran el árbol de if/else que CLAUDE.md prohíbe: una
función + regex por cada fraseo, no escala. Rediseño a UNA capa universal, decidido
MIDIENDO (gates antes):

**Mediciones (todas verificadas por estado del SO):**
- ¿El 4B ENCADENA acciones solo (sin capa)? **2/10** — hace `focus` y para.
  -> hace falta una capa determinista (no es sobre-diseño).
- ¿El 4B emite un PLAN de primitivas? **10/10 parseable, 7/10 correcto** (los 3
  "fallos" eran gate estricto: send==Enter, click válido para canal). El 4B
  PLANIFICA bien aunque no EJECUTE.

**Dos opciones construidas y comparadas:**
- **OPCIÓN A — ejecutor de planes** (`computer_use.py`): el 4B emite un plan de
  primitivas (cualquier idioma/fraseo); `PlanExecutor` corre las primitivas
  ATÓMICAS (focus_app/open_chat/open_url/type/send/keypress/click) reusando los
  tools/helpers que ya existen, verificando por estado del SO entre pasos.
  **MEDIDO 16/16 = 100%** en apps VARIADAS: calc 4/4, browser(Opera) 4/4,
  chat(Discord) 4/4, notepad 4/4. GATE (global≥80% Y peor-tipo≥60%) PASA.
- **OPCIÓN B — clasificador verbo→primitiva por embeddings** (`computer_use_b.py`):
  clasifica el objetivo a UNA primitiva por embeddings multilingües. RECHAZADA por
  DISEÑO: estructuralmente NO compone multi-paso (no puede hacer la cuenta de calc
  `type+keypress` ni un mensaje `open_chat+type+send`) — su techo es 1 primitiva por
  comando. Se deja en el repo como referencia medida, no se usa.

**APLICADO: Opción A.** `_try_computer_use` (UNA entrada) reemplaza los dos macros
en `run_content`; `_try_in_app_nav` y `_try_in_app_message` BORRADOS (los helpers
`_quick_switcher_nav`/`_title_now_matches`/`_app_window_title` quedan — los reusa el
ejecutor). Gate de activación universal: una ventana abierta matchea el comando
(estado del SO). Gate de apagado: GEMMA4_COMPUTER_USE=0. +tests test_computer_use.py
(parse_plan vocabulario cerrado + dispatch del ejecutor, mockeado sin GUI).

**Regla para adelante:** una intención/fraseo nuevo de computer-use NO pide otra
función — el 4B lo planifica con las primitivas que hay. Solo una CAPACIDAD nueva
(rara) pide una primitiva nueva. Harnesses: _measure_4b_composes.py,
_measure_4b_plan_emission.py, _measure_cu_optionA.py, _measure_cu_optionB.py.
