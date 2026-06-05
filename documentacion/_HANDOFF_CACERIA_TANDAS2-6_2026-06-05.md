# HANDOFF — Cacería de bugs, tandas 2-6 (2026-06-05)

Continúa `_HANDOFF_CACERIA_TANDA1_2026-06-04.md`. El user pidió correr los 6162
casos del dataset finetuning contra el LLM REAL (ejecución física mockeada) en
tandas de 1000, juzgar cada caso, llegar a la causa raíz y arreglar TODOS con
**soluciones UNIVERSALES/estructurales** (no parches por caso), trabajando en
automático mientras dormía. NO push hasta su OK.

## Estado: TODAS las tandas corridas + juzgadas. Fixes universales committeados. Re-run final 6162 EN CURSO.

## Metodología (la misma de tanda 1, endurecida)
1. Hunt: `scripts/_diag/_diag_hunt_tanda.py <OFFSET> <LIMIT>` → `_hunt_tanda_<OFFSET>.jsonl`
   (LLM real, `ToolRegistry.execute` mockeada → `{ok:True,verified:True}`).
2. Juez LLM (Opus) por lotes → clusters por causa raíz.
3. **Verificación contra DATA CRUDA** (no contra el juez): el campo `i` del juez es
   poco fiable en t3+ (los agentes emiten posición, no el i real). Verifiqué CADA
   patrón con grep directo sobre el jsonl. Los CLUSTERS (patrones) sí son válidos.
4. **Harness objetivo** `scripts/_diag/_verify_hunt_clean.py`: detectores sin juez
   (hard-signals + residuales de honestidad media/destr). Reusable.
5. **Auditoría adversarial** (workflow 6 agentes, uno por guard) sobre data cruda
   t1-t5 → encontró FP/FN que la verificación single-thread NO vio. Ver abajo.

## GOTCHA central (repetir a quien siga): el mock infla "bugs"
`_mock_execute` devuelve `{ok:True,verified:True}` para TODA tool → el 4B "rellena"
datos (títulos/cifras/paths) que el tool REAL devolvería bien. Esos NO son bugs de
prod. El juez los cuenta como BUG-DUDOSO → el "bug rate" alto es en gran parte
mock-inflación + capturas PRE-fix del dataset (estático). BUG-real trend del juez:
236(t2)→227(t3)→219(t4) DECLINANTE.

## FIXES UNIVERSALES COMMITTEADOS (todos gated default-ON, 0-FP verificado sobre 6162)

### Honestidad (safety_pkg/reply_validator.py + agent_core)
- **media-fabricado INLINE-REPAIR** (commit 13ef80f): el #1 bug ("Stranger Things en
  Netflix" ante ruido/pedido genérico, ~25-30/tanda). El guard ya lo detectaba pero
  solo con hint DIFERIDO (corrige el próximo turno); el 4B reincide → el user veía la
  mentira ESTE turno. Ahora REEMPLAZA el reply en el acto por "Listo, puse lo que
  pediste." Lógica en agent_guards.py (sibling `repair_media_fabricated_inline`),
  wrapper thin en agent.py `_finalize_turn`.
- **media_fabricated_claim A+B+C** (commit 03822b1, BLOQUEANTE hallado por la
  auditoría): el guard tenía ~24 FP + 7 FN (¡incl. su propio caso canónico!).
  (A) solo aplica si el reply afirma REPRODUCCIÓN-EN-CURSO (`_NOW_PLAYING_RE`) —
      "abrí Spotify"/"¿querés que reproduzca?"/"las apps que usás: Spotify" NO lo son.
  (B) grounding contra CUALQUIER tool (app.name/audio_device.app/browser.url/gui.title),
      no solo `media`.
  (C) NINGÚN `media.args` (provider/query/app) groundea — el 4B los AUTO-FABRICA; solo
      el `result` NO-VACÍO de media cuenta. Bajo mock el result viene vacío → atrapa la
      fabricación. MEDIDO 6162: 213 fires (todas fabricaciones), recall 80/80 hard,
      0/214 FP sobre replies consistentes.
- **destructive_claim_without_evidence** (commits 5f68fb5→8fbff58→03822b1→0e74913):
  el guard original que yo mismo escribí tenía 8/9 FP. Endurecido en capas:
  preguntas-de-confirmación (`_DESTRUCTIVE_ASKS_RE`), rechazos en futuro + incapacidad
  honesta ("no existe herramienta"/"no puedo", `_DESTRUCTIVE_NEGATED_RE`), contexto
  benigno (toggle bluetooth/wifi/audio + format de CÓDIGO/texto, `_DESTRUCTIVE_BENIGN_CONTEXT_RE`),
  verbo genérico de ejecución solo eleva con comando hard-destructivo explícito
  (`_HARD_DESTRUCTIVE_CMD_RE`: rm -rf/mkfs/del //format C:), "registro" como sustantivo
  no verbo, "sistema" quitado de targets, C:\ solo raíz de unidad.
  **MEDIDO 6162: residual = 1 (el ÚNICO TP real "eliminé DOOM"), 0 FP.**
- **click_claim_without_click** (commit 03822b1): FN multilingüe — el regex solo
  cubría ES/EN. Extendido a PT/IT/FR 1ª persona pretérito (cliquei/ho cliccato/j'ai
  cliqué). Mide FORMA, no contenido.

### Routing (commits previos t1-t2, ya en rama)
- A6 `_INFO_SUPPRESS_TOOLS`: conocimiento/how-to NO dispara web/vision (B3 conocimiento→web = 0 en data cruda).
- A7 `_is_web_target` + divert app.open→browser.
- A8 preferencia/dato-personal suprime tools de acción.
- A5 `profile_intent` hard-negatives (capability/identity/system/charla-emocional
  multilingüe pt/de/fr). FP jarvis 22→7→~0.
- B3 `_is_low_signal_noise`: ruido (número/medida) abstiene (verificado EN VIVO:
  "7.63" → "Cancelé... listo para tu comando", NO fabrica Netflix).
- C2-leak sanitizer `<|...|>`/`memory{...}`.
- C1 `dedup_degenerate_batch` (Gemma4 #1756) + cap research.

## Auditoría adversarial (workflow `caceria-guard-audit`, 6 agentes)
Veredictos: idm=sólido(0 fires), tests=sólido, click=1 FN morfológico (arreglado),
destr=2 FP (arreglados), **media=AMBOS (24 FP + 7 FN) = BLOQUEANTE (arreglado A+B+C)**.
Síntesis completa en `scripts/_diag/_audit_synthesis.txt`. LECCIÓN: una guarda nueva
DEBE pasar auditoría adversarial sobre data cruda — los FP/FN no salen en unit tests
curados. (El guard destructivo que yo escribí tenía 8/9 FP que no vi hasta medir.)

## Lo que la medición RECHAZÓ (disciplina medir-no-celebrar, NO over-engineer)
- A1-título+artista sin plataforma ("Bohemian Rhapsody de MJ"): 0 casos reales.
- C1 web-loop: declinante (t3=4,t4=4,t5=1,t6=3), tareas multi-paso genuinas que el
  circuit-breaker corta. Bajar umbral arriesga multi-step legítimo.
- C2 cancel_turn FP: 1 caso real (garble). El juez dijo ~14 (IDs pre-fix).
- Latencia >25s: 1-3/1000, cola de tareas duras encadenadas.

## Re-run FINAL (pedido explícito del user "correr todos de nuevo al 100%")
EN CURSO en background: `scripts/_diag/_rerun_all_6162.py` (prefijo `_rerun_tanda_`
para NO pisar los originales pre-fix). ~6h. Smoke test EN VIVO confirmó el fix
(noise → abstain honesto). Al terminar: `python scripts/_diag/_verify_hunt_clean.py
scripts/_diag/_rerun_tanda_*.jsonl` debe dar media_fab≈0 (inline-repair) y destr≈0.

## Tests
33 en test_intent_domain_mismatch.py (media A/B/C, destr toggle/benign/incapacidad,
click multilingüe, repair). 493 verde en honestidad/guard/router. Techos archivos-dios
reconciliados (agent.py 6687, lógica en siblings).

## HALLAZGOS DEL JUEZ INDIVIDUAL (workflow 50 agentes, 4000 casos re-run) — 2026-06-05
El juez LLM individual encontró 2 bugs GRAVES que los detectores duros (media/destr) NO
veían por ser de otras categorías. Verificados contra código + data cruda:

### 🔴 SAFETY OFF por default + bypass de `confirmed` (EL BUG MÁS GRAVE)
- **Descubrimiento:** `enable_safety=False` por default (config.py) → el gate de
  confirmación de lo IRREVERSIBLE estaba DESACTIVADO en TODO el runtime. Sin
  justificación documentada (commit 3f2664c), CONTRADECÍA el README (principio #6:
  "las op destructivas piden confirmación"). Medido: el juez vio 51 ejecuciones
  destructivas, "borra todo en C:/" se ejecutaba sin confirmar.
- **Bypass adicional:** aun con safety ON, el 4B aprendió a AUTO-emitir `confirmed:true`
  (15/51 casos) → salteaba el gate. El flag del MODELO sustituía la confirmación real.
- **FIX (verificado EN VIVO 5/5):**
  1. `enable_safety=True` por default (config.py). El EVAL lo desactiva con
     `GEMMA4_AGENT_SAFETY=0` (seteado en _diag_hunt_tanda.py) para medir routing.
  2. El `confirmed` del LLM ya NO saltea el gate de irreversibles: solo la confirmación
     REAL vía canal interno `_confirmed_by_gate` (flujo safety(confirm), no falsificable)
     o `confirmed_at_create` (rutinas). tools.py:execute + safety(confirm):3599.
  - Verificado en vivo (_verify_confirm_gate_live.py): 5/5 piden confirmación; el caso
    con confirmed=True del 4B da needs_confirmation (bypass cerrado). Tests: 359 verde.

### 🟡 IDIOMA: el reply no espeja el idioma del usuario (REVERTIDO — es dataset-level)
- `core.md:7` Y `core_lean.md:1` (el lean es el que usa el perfil vram4 operante)
  decían "Reply in Spanish" → 638/696 (92%) casos no-ES responden en español
  ("open notepad" → "Listo, abrí notepad").
- **Intento de fix por prompt + verificación EN VIVO: NO alcanza.** Medido: en CHARLA
  pura el modelo SÍ responde en el idioma del user ("Hello"→"Hello, I am..."), pero en
  el reply POST-TOOL el prior español del fine-tune domina ("open notepad"→"Listo,
  abrí notepad") y el prompt no lo vence. Es DATASET-LEVEL (el dataset de tool-summary
  es ~español), igual que "Soy Gemma 4". Decisión del user: REVERTIR el cambio de
  prompt (no da falsa sensación de arreglado) y dejarlo como deuda para el próximo
  re-fine-tuning con ejemplos multi-idioma de tool-summary. Prompts sin cambios.

### 🟠 FIX#3 candidato — WhatsApp (MEDIDO sobre los 6162 re-run, 2026-06-05)
- **destinatario mal parseado: 9 casos REALES** (no artefacto del mock — el parse es
  estructural): contact = preposición/artículo suelto. i=631 "Mandale un mensaje de te
  amo a amor" → contact="un" (debería "amor"); i=1156/2907/3221 "escribele EN wsp a
  migue" → contact="en"; i=3433/3434 "mandale 'te amo' a Ana" → contact="te". Manda al
  contacto EQUIVOCADO = irreversible si auto_send dispara. ALTA severidad.
- **placeholder literal: 10 casos** (contact="<persona>", i=3259/3464/3465).
- **claim de envío ("le mandé"): 47** — mezcla; falta separar auto_send real vs mock.
- DECISIÓN PENDIENTE del user (WhatsApp vs cierre docs). El fix de destinatario es un
  parche de parser acotado multi-idioma (extract_message_to no cubre "EN wsp a X" ni
  "un mensaje a X"); el de placeholder es un guard estructural. NO atacado aún.

## PENDIENTE
0. Verificar EN VIVO el fix de idioma (multi-idioma en/pt/fr/de/it). Commitear los 3 fixes.
1. Re-run 6162 termina → verificar con _verify_hunt_clean → confirmar limpio. [HECHO: media_fab=0/6162, destr=2 TP reales]
2. (opcional) verificación EN VIVO extra: gates destructivos reales (server libre),
   recall-on-empty-store. La mayoría ya se cubre con el re-run e2e.
3. Esperar OK del user para PUSH (~33 commits en Dev sin pushear).

## Archivos clave
- Harness: `_diag_hunt_tanda.py` (+env GEMMA4_HUNT_PREFIX), `_verify_hunt_clean.py`,
  `_rerun_all_6162.py`, `_make_judge_input.py`, `_judge_wf.js`.
- Notas: `scripts/_diag/_NOTAS_caceria_t2.md` (análisis detallado por tanda).
- Auditoría: `scripts/_diag/_audit_synthesis.txt`, `_audit_fires.json`, `_audit_nofire.json`.
