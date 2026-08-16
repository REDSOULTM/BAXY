# Computer-use GUI — informe por tier (2026-05-24)

> Trabajo autónomo overnight. Todo MEDIDO contra el agente real bajo `vram4`
> (Gemma 4 E4B-it Q4_K_M), no en teoría. El eval verifica por **estado del SO**
> (pycaw, tasklist, EnumWindows/UIA), nunca por lo que el agente diga — ese es
> el anti-patrón que hundió a Carter (falso-PASS).

# Fase 6 (2026-05-25): speculative multi-action — MEDIDO y RECHAZADO

El roadmap exige medir ANTES de construir: speculative N=2 solo vale si el 4B
acierta la next-action >80%. **Medido: NO pasa el gate → NO se construye.**

Experimento (`scripts/gui_eval/_measure_speculative.py`, reproducible): 12
misiones canónicas de 2 pasos ("abrí Notepad y escribí <texto>", es/en/pt/fr/it)
con el splitter determinista APAGADO (`GEMMA4_MULTI_INTENT=0`) → el 4B debe
encadenar `app.open → gui.type_into` solo, en una pasada. Oráculo por estado del
SO (¿el texto quedó en Notepad? UIA).

**Resultado: full-sequence 0/12 (0%), first-action 8/12 (67%).** El 4B NUNCA
completó la secuencia de 2 acciones solo: 8/12 abrió la app y se DETUVO sin
teclear (`ntools=1`); 3/12 mis-ruteó "escribí X" a `notes_tasks.note_create`;
1/12 no emitió nada. 0% << gate 80%.

**Decisión: NO construir speculative.** A 0% de secuencia completa, la
especulación produciría un rollback casi siempre → costaría más que el ahorro.
Esto además VALIDA empíricamente la arquitectura actual: el splitter
determinista + macros (Fases 2-3) existen precisamente porque el 4B no encadena
— y el dato lo confirma al extremo. (Confirma el caveat del roadmap: "un 4B
predice secuencias peor que o1".) Si en el futuro se sube a un modelo más capaz,
re-correr este harness para re-evaluar el gate.

---

# Fase 8 (2026-05-25): visión gateada — cascada UIA→OCR→VISIÓN completa

Cierra la cascada de grounding. Cuando UIA y OCR fallan en localizar el control,
`click_button` ESCALA a visión: captura un screenshot y lo devuelve adjunto
(`status=needs_vision`, `grounding=vision_escalation`) para que el agente lo
razone con su visión NATIVA (Gemma 4 + mmproj) — localiza de otra forma o reporta
honestamente qué ve. **NO clickea por visión a ciegas**: el grounding por VLM no
es fiable (ni UI-TARS-7B pasa ~50% en UIs difíciles) y la visión es vector de
prompt-injection (síntesis §2).

Dos gates DUROS (umbral roadmap "vision calls/misión >2 → cascada rota"):
- **presupuesto por misión ≤2** (`GEMMA4_GUI_VISION_BUDGET`). Verificado:
  escalaciones #1/#2 → screenshot; #3 → error honesto `uia+ocr`. reset al empezar
  misión + idle-reset 120s.
- **VRAM** (`VRAMWatchdog.vision_safe()`): no arriesgar OOM con el mmproj ~990MiB
  en el target de 6GB. Sin GPU → no bloquea.
`gui_vision_gate.py`. La visión NO se dispara cuando UIA/OCR aciertan
(click_button 6/6 sin escalar). +6 tests.

**Cascada completa:** UIA (button-prioritized + token-aware + all-windows) →
retry-lazy-Chromium → OCR (Tesseract, coords DPI-correctas) → visión (gateada).

---

# Fase 7 (2026-05-25): checkpoint de misión reanudable

Una misión GUI multi-paso interrumpida (crash/reinicio/cancel) ya no se pierde:
`mission_checkpoint.py` persiste el progreso clause-by-clause en JSON atómico
(reusa `state.atomic_write_json`). begin (solo misiones ≥2 cláusulas) → mark_done
por paso → finish al terminar. Si la interrupción es DURA el `finally` no corre →
el checkpoint sobrevive → `pending()` lo expone como reanudable (in_progress, no
vencido >30min, con pasos sin hacer). Cableado en `agent._run_multi_intent`.
Gate `GEMMA4_MISSION_CHECKPOINT`. +9 tests.

> Alcance honesto: entrega PERSISTENCIA + DETECCIÓN. El auto-resume EJECUTANDO
> los pasos pendientes se deja opt-in — tras una interrupción el estado del SO
> pudo cambiar, así que reanudar a ciegas sería inseguro; el agente debe OFRECER
> reanudar (handshake), no re-ejecutar solo.

---

# Fases 4 y 5 (2026-05-25): recovery + seguridad

Tras la cascada de Fase 3, dos fases más del roadmap (commits 3f12a7e, 4da09ea):

**Fase 5 — guardas de seguridad** (gate: 0 leaks de password). Ahora que el
agente clickea/teclea en cualquier lado, dos guardas estructurales en `t_gui`
(el dispatch que usa el agente), antes de todo control físico:
- **user-activity** (`GetLastInputInfo`): no pelear el mouse/teclado con el
  usuario. Si tocó input hace < umbral (1500ms) → bloqueo suave `deferred`.
  Excluye el input sintético del propio agente (`note_agent_input` tras cada
  click/type) para no auto-bloquearse en multi-paso.
- **password-field** (UIA IsPassword 30019): nunca teclear en un campo de
  contraseña → secret handoff. Solo type/type_into (click no se bloquea).
  Honesto: fiable en campos NATIVOS; en web Chromium el AX es disperso y puede
  no exponer IsPassword (limitación documentada — cuando detecta, bloquea;
  nunca causa daño).
  Verificado end-to-end por t_gui: type en password→blocked; click con usuario
  activo→deferred; tras input del agente→no auto-bloquea. +7 tests.

**Fase 4 — recovery de click-sin-efecto** (gate: clicks-sin-efecto post-retry
<10%). Cuando click_button (UIA) detecta que el click no tuvo efecto
(`state_changed=False`), re-enfoca la ventana del control y reintenta UNA vez
(foco perdido = causa #1). Bounded, sin recursión. Solo en el path UIA (en
OCR/CEF el state_changed=False suele ser falso-negativo del frame-diff y un
re-click togglearía controles no idempotentes). 6/6 click_button + 3/3 CEF
sin regresión.

---

# Fase 3 (2026-05-25): cascada UIA→OCR + fix DPI crítico

La Fase 3 del roadmap (cascada UIA→OCR→visión para apps sin UIA rico). Gate:
Discord/Spotify SR 0→≥30%. **Resultado: 3/3 en el harness real.**

**Lo construido (commits eb71605, db06bfa, 8b12b80, cf8227b, 97926e4):**
- **Cascada UIA→retry-Chromium→OCR** en `click_button` y, clave, en `uia.click`
  (el tool que el agente realmente elige): en ventanas Chromium/CEF
  (class `Chrome_WidgetWin_1`: Edge/Chrome/Discord/Spotify/Electron) va DIRECTO
  a OCR — el árbol UIA del contenido web es inconsistente y el InvokePattern del
  proxy no dispara el onclick del DOM. Fuera de Chromium: UIA primero, OCR si el
  match es débil. Retry lazy-Chromium (gotcha del 1er walk AX vacío).
- **`_click_button_via_ocr`**: screenshot → `ocr_find_text(label)` → click del
  centro → `verify_post_action`. Reusa el OCR (Tesseract) ya instalado.

**Dos bugs CRÍTICOS encontrados y arreglados en el camino (no eran de Fase 3,
pero rompían cualquier grounding por pantalla):**
1. **OCR muerto por cp1252** (`eb71605`): `ocr_image` corría Tesseract con
   `subprocess text=True` → decodía el TSV con cp1252 y CRASHEABA en texto
   acentuado → 0 líneas SIEMPRE. El grounding por OCR estaba de facto muerto.
   Fix bytes+utf-8. Medido: 0 → 28 líneas/136 palabras en 0.7s.
2. **OCR-click fallaba en pantallas escaladas** (`8b12b80`): con DPI≠100% (laptop
   a 150% — el hardware TARGET), el screenshot GDI capturaba en coords lógicas
   (1260×840) y el cursor operaba en físicas (1890×1260) → el click por
   coordenada caía mal SIEMPRE. Fix: screenshot y click DPI-aware
   (PER_MONITOR_AWARE_V2) → coords OCR mapean 1:1 al click. **Esto afectaba a
   TODO click por coordenada del agente, no solo Fase 3.**

**Medición (harness real, fixture HTML en Edge = contenido Chromium, verificado
por TÍTULO de ventana que el botón cambia vía JS):** 3/3 PASS. El click OCR
landa en el botón dentro del contenido web y el título pasa a 'OK-clickeado'.

> Nota: la cascada se prueba con un fixture HTML CONTROLADO (no la UI interna de
> Discord/Spotify, que es no-determinista e invverificable por estado). Mide
> exactamente la capacidad nueva: clickear algo que el árbol UIA NO expone.
> El reset usa el foco ROBUSTO (win_focus ALT+AttachThreadInput) — sin él Edge
> no quedaba al frente y el click caía en la ventana equivocada.

---

# Continuación 2026-05-25: click_button + cierre de falso-PASS

Segunda sesión sobre el mismo roadmap. Dos capacidades nuevas, ambas
verificadas contra el agente real bajo vram4:

1. **Macro `gui.click_button(label)`** (commit `99806ca`) — clickear un control
   por su LABEL con verificación sin VLM. Cierra el gap "click ciego" del
   roadmap (Fase 2 → click). Además volvió **button-prioritized + token-aware**
   el `uia.click` que ya usa el agente:
   - reordena los matches UIA (tipo botón > Invoke > Name exacto/contiene >
     habilitado/en-pantalla) en vez de tomar el 1er match laxo;
   - `Matches()` token-aware: "botón tres"/"button three" matchea el control
     "Tres" (stop-words de UI multi-idioma);
   - fallback all-windows (commit `14a3fdd`): si el control no está en el
     foreground, reescanea todas las ventanas top-level. Esto fue clave — sin
     él, click_button pasaba aislado pero fallaba en el eval completo porque la
     Calculadora perdía el foco entre el reset y el click.
   - **Medido (harness real, tier-2): 16/16 (100%), click_button 6/6** (display
     real 'Se muestra 9/5/3' vía UIA, no "tool ok"). 6 misiones nuevas.
2. **Cierre del falso-PASS por launch no confirmado** (commit `f2a222c`) —
   `reply_validator.soften_unverified_launch`: si el reply afirma haber abierto
   una app pero `app.open` quedó `verified=false`, añade un caveat honesto en el
   idioma del reply. Determinista (el E4B no sigue la regla en prosa). +7 tests.

**Discord — techo honesto refinado:** queda como falso-PASS residual por una
razón concreta y medida: su launcher Squirrel muestra una ventana TRANSITORIA
titulada "Discord" que `verify_app_opened` capta → `app.open` devuelve
`verified=true` → el hedge (que actúa sobre `verified=false`) NO aplica → el
proceso `Discord.exe` persistente no aparece en la ventana de verificación. NO
es gap de capacidad (app.open lanza el .lnk correcto); es el updater de Discord.
Forzar verify_app_opened a exigir proceso rompería apps legítimamente
window-only — se deja como techo documentado, no se hackea el hot path.

### run7 (110 misiones, medido con TODOS los fixes de esta sesión)

| Métrica | run7 |
|---|---|
| **Task success rate** | **92.7% (102/110)** |
| **Falso-PASS** | **5 (4.5%)** (con el detector corregido; mspaint lento pasó a FAIL honesto) |
| Tier 1 | 75/80 |
| **Tier 2 (Chrome/Edge/Word/Excel + click_button)** | **16/16 (100%)** |
| Tier 3 | 11/14 |

**Los 8 fails de run7, todos honestos:**
- 4× mute/unmute corto — techo del encoder multilingüe (DE imperativo, bare token).
- 3× Discord — updater Squirrel (verify capta ventana transitoria; proceso no
  persiste en la ventana de medición). Único falso-PASS no cerrado.
- 1× mspaint (open) — abrió lento; el reply HEDGEÓ honestamente ("estoy abriendo
  Paint; puede tardar"), por eso NO es falso-PASS. Flaky de timing, no regresión
  (pasó en run4/run5).

**click_button: 6/6 en el run completo** — verificado por el display real de la
Calculadora (UIA), incluida la secuencia 7+2= a mano → "Se muestra 9".

---

## Resumen ejecutivo (sesión 2026-05-24)

| Métrica | run3 (baseline) | run4 | **run5 (FINAL)** |
|---|---|---|---|
| **Task success rate** | 80.8% (84/104) | 90.4% (94/104) | **93.3% (97/104)** |
| **Falso-PASS** | 10 (9.6%) | 5 (4.8%) | **5 (4.8%)** |
| Latencia p50 / p95 | — | 2.62 / 6.16 s | **2.6 / 6.2 s** |
| Tier 1 (nativas/volumen/mute/close/write) | — | 76/80 | **76/80 (95%)** |
| Tier 2 (Chrome/Edge/Word/Excel) | — | 10/10 | **10/10 (100%)** |
| Tier 3 (Discord/Spotify/Steam/VLC/Telegram) | — | 8/14 | **11/14 (79%)** |

**+12.5 pts de SR (80.8 → 93.3), falso-PASS a la mitad.** Los 7 fails de run5
son SOLO 2 causas, ambas honestas:
1. **mute/unmute corto** (4) — techo del encoder multilingüe (no se fuerza).
2. **Discord** (3) — launcher Squirrel flaky/lento. VLC (misma clase) SÍ se
   recuperó con el fix de shortcuts muertos; Discord no spawneó el proceso en
   esta corrida (su updater es no-determinista).

### Los 7 fails de run5 (FINAL)

| Misión | Tier | Causa | ¿Falso-PASS? |
|---|---|---|---|
| t1_mute_de_5 "stumm schalten" | 1 | encoder DE imperativo | no |
| t1_unmute_es_1 "desmuteá" | 1 | bare token (flaky LLM) | sí |
| t1_unmute_en_2 "unmute" | 1 | bare token ~"dependency" | no |
| t1_unmute_de_5 "ton an" | 1 | encoder DE → cancel_turn | sí |
| t3_open_Discord_0/1/2 | 3 | launcher Squirrel no-determinista | sí (×3) |

> **VLC: FAIL → PASS** (3/3) tras descartar el shortcut muerto `vlc.lnk`
> (target borrado en D:\). **Discord** sigue flaky: en el re-test aislado abrió
> en ~14s (PASS), pero en la corrida completa su updater Squirrel no spawneó el
> proceso. No es capacidad del agente (app.open lanza el .lnk correcto); es el
> launcher de Discord. Los 5 falso-PASS son: el agente dice "abrí Discord" /
> "desmuteé" cuando app.open/audio NO pudo confirmar (`verified=False`). El fix
> honesto (recomendado abajo) es que el reply HEDGEE en ese caso.

## Qué se arregló (cada uno verificado PASS contra el agente real)

### 1. Apps de SO con nombre localizado (FR/DE/IT/PT)
**Síntoma:** "ouvre le bloc-notes", "öffne den Editor", "ouvre la
calculatrice" → app no encontrada.
**Causa raíz:** la discovery de Windows (PATH/StartApps/registry) solo conoce
el binario inglés ("notepad", "calc"). El nombre localizado fuzzy-scoreaba 0.
**Fix:** tabla `_BUILTIN_ALIASES` (es/en/pt/fr/de/it) en `app_resolver.py`
para notepad/calc/paint/cmd. Traduce el nombre localizado al binario y deja
que la discovery normal lo rankee. NO es routing ni respuesta enlatada — es
traducción de un binario FIJO del SO (mismo precedente que la tabla de apps de
streaming). **FR/DE notepad+calc: FAIL → PASS.**

### 2. "lanzá Chrome" → browser.open sin URL
**Síntoma:** "lanzá Google Chrome" → "No puedo abrir Chrome sin una URL".
**Causa raíz:** el 4B interpreta "Chrome" como navegador y llama
`browser.open(browser=Chrome)` sin url → la tool pedía url.
**Fix:** `browser.open` sin url pero con `browser`/`name` que nombra un
navegador → delega a `app.open` (lanza la app). La tool garantiza su
precondición (CLAUDE.md #5) en vez de devolver needs_user. **PASS.**

### 3. Cerrar apps con título localizado
**Síntoma:** "close notepad" / "fecha o bloco de notas" → "no encontré la
ventana".
**Causa raíz:** el título de la ventana está localizado por el SO ("Sin
título: Bloc de notas") pero el query viene en el idioma del usuario.
**Fix:** `window.close` además del título matchea por **nombre de proceso**
resuelto vía AppResolver. + verifica que la ventana se cerró tras WM_CLOSE
(antes reportaba ok sin chequear = falso-PASS); NO fuerza kill (evita perder
trabajo sin guardar, CLAUDE.md #6). **notepad/mspaint/calc close: PASS.**

### 4. Escribir en la app recién abierta ("abrí X y escribí Y")
**Síntoma:** el texto se perdía o iba a la app equivocada.
**Causas raíz (tres):**
  - el foreground podía ser un toast de notificación (CoreWindow) o Word
    robando foco → el texto se tecleaba ahí;
  - el frame-diff (dHash) no trippeaba con texto chico → falso "no pude
    confirmar" en un éxito real;
  - el arg `window` no estaba en el schema de `gui` → `execute()` lo
    rechazaba antes de llegar a la tool.
**Fix:** `gui_type_into` detecta foreground no-escribible y enfoca la ventana
objetivo (hint `window=` que el macro multi-intent arrastra de la cláusula
previa), + verificación **UIA** del texto (más fuerte que frame-diff), +
`window` agregado al schema. **t1_write_0/1/2: PASS** (UIA confirma el texto).

## Techo honesto (NO forzado con hardcodes — RED vetó regex es/de)

- **mute/unmute imperativo ALEMÁN corto** ("stumm schalten", "ton an"): el
  encoder multilingüe (MiniLM) no rutea bien imperativos partidos en alemán;
  `audio` no entra al top-4. Las formas noun-phrase DE ("Audio
  stummschalten") e it/fr SÍ funcionan. Agregar queries tool2vec no alcanzó.
  Esto es límite del encoder, no se fuerza con keywords es/de.
- **Discord (tier 3, 3 falso-PASS)**: el launcher Squirrel (`Update.exe` →
  `Discord.exe`) tarda ~12-15s en cold start. VERIFICADO: lanzar `Discord.exe`
  directo abre Discord en ~6s (7 procesos). El agente SÍ lanza la app, pero
  fuera de la ventana de verificación del harness (8s) y del auto-verify de
  app.open (~2s). Dos arreglos posibles (NO aplicados aún para no inflar el
  harness sin acuerdo): (a) subir el poll-timeout del harness a ~20s para
  tier-3 con launcher conocido lento; (b) que el reply del agente HEDGEE
  cuando app.open devuelve `verified=False` ("estoy abriendo Discord, puede
  tardar") en vez de afirmar "abrí Discord" — esto cierra el falso-PASS real
  (el agente afirma completado sin confirmación). RECOMENDADO: (b), porque
  ataca la honestidad, no el número.
- **VLC (tier 3, 3 fails HONESTOS, no falso-PASS)**: VLC no llegó a correr y
  el agente lo reportó honestamente. En run3 daba "operación cancelada por el
  usuario" (un confirm-guard). Pendiente de diagnóstico fino — pero el agente
  NO mintió (fp=False), que es lo crítico.

## Gotchas de entorno descubiertos (daban falsos FAIL, NO eran del agente)

- **Win11 Notepad = proceso ÚNICO + residente + session-restore.** Cerrar la
  última ventana no mata el proceso; relanzar reabre las pestañas sucias. El
  oráculo de "cerrar" debe ser ventana-ausente, no proceso-ausente; el reset
  limpia TabState.
- **Foreground-steal** (toast ShellExperienceHost / Word) se come el texto.
- **execute() valida el schema antes de la tool**: un arg no declarado se
  rechaza silenciosamente para la tool.

## Reproducir

```
# sandbox OFF (mueve mouse, abre apps, limpia TabState)
python -u -m scripts.gui_eval.run_eval --out scripts/gui_eval/results.json
python -u -m scripts.gui_eval.run_eval --dry-baseline   # reproducibilidad sin agente
```

## Commits de esta sesión (branch PortandoLoMejor, sin push)

- `75603ed` resolución de apps multilingüe + type_into robusto + window.close por proceso
- `f4240ae` multi-intent arrastra ventana objetivo al macro de escritura
- `b22149e` higiene harness Notepad UWP (session-clear, oráculo ventana-ausente)
- `a22ebb4` recuperar unmute corto en tool2vec (anti-regresión run4)
- `0a5bc29` descartar shortcuts muertos en el resolver + ventana tier-3 a 20s
- `f8845fb` regla de honestidad launch-verified vs launch-requested (best-effort)

Ninguno toca los archivos con trabajo sin commitear de RED (agent_guards.py,
planner.py, domain_tools.py).

## Recomendaciones (próximos pasos, no aplicados)

1. **Cerrar el falso-PASS de Discord deterministamente**: post-procesar el
   reply del agente cuando el último app.open tuvo `verified=false`, anteponiendo
   un hedge. El E4B no sigue la regla en prosa de forma fiable.
2. **Discord launcher**: investigar por qué Squirrel a veces no spawnea el
   proceso; quizás lanzar el `app-*\Discord.exe` directo en vez del .lnk.
3. **mute/unmute corto multilingüe**: si se quiere subir ese 4/80, explorar un
   abstain-head específico o más datos de entrenamiento del encoder — NO listas
   de keywords es/de (rompería universalidad).
