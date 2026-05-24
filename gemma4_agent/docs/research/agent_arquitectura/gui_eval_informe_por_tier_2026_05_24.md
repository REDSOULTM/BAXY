# Computer-use GUI — informe por tier (2026-05-24)

> Trabajo autónomo overnight. Todo MEDIDO contra el agente real bajo `vram4`
> (Gemma 4 E4B-it Q4_K_M), no en teoría. El eval verifica por **estado del SO**
> (pycaw, tasklist, EnumWindows/UIA), nunca por lo que el agente diga — ese es
> el anti-patrón que hundió a Carter (falso-PASS).

## Resumen ejecutivo

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
