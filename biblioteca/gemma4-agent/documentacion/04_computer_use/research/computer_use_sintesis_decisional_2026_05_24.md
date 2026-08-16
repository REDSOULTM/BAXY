# Síntesis decisional — Computer-use GUI (triangulación de 3 fuentes)

**Fecha:** 2026-05-24
**Fuentes trianguladas:**
1. **claude.ai** — `investigaciones_recibidas/9_computer_use_gui.md` (plan de 8 fases).
2. **Investigación propia** — `computer_use_investigacion_propia_2026_05_24.md` (web, 10 fuentes).
3. **Código + entorno real** — verificado en vivo esta sesión.

**Para qué sirve:** decidir cómo construir el control GUI tipo humano que pidió
RED, con evidencia triangulada y no una sola opinión. CLAUDE.md: investigar +
medir antes de tocar.

---

## 1. Convergencia (las 3 fuentes coinciden → alta confianza)

| Punto | claude.ai | Mi investigación | Veredicto |
|---|---|---|---|
| **Visión-por-paso NO cabe en vram4** | "NO-VIABLE; ~1.5-2.5s por VLM call rompe budget" | UI-TARS-7B vision-native ~8-16GB, 27.5% OSWorld | ✅ CONFIRMADO triple |
| **Arquitectura = macros deterministas observe→act→verify, 4B solo decide objetivo** | opción (b), única viable | UFO² UIA-first + Agent-S2 grounding routing | ✅ CONFIRMADO |
| **UIA primario, visión último recurso** | cascada UIA→OCR→visión gateada | UFO² híbrido, visión=vector de ataque | ✅ CONFIRMADO |
| **Verificación SIN VLM (UIA delta + frame-diff + Win32 events)** | verify_post_action 3 señales, fusión 2-de-3 | UIA property-change events + frame-diff + SetWinEventHook | ✅ CONFIRMADO |
| **Techo honesto: NO "misiones arbitrarias", SÍ subset UIA-rico ≤5 pasos** | "40-60% Tier-1, 15-25% custom" | SOTA frontera 52.5% WAA, humano 72% | ✅ CONFIRMADO — decir la verdad a RED |
| **Eval-set con verifier estructural por SO, no "tool dijo ok"** | Fase 0 obligatoria | (implícito en mi crítica al bench de Carter) | ✅ CONFIRMADO |
| **CEF flag con consentimiento, no relaunch silencioso** | sí | sí + gotcha lazy/async | ✅ CONFIRMADO |
| **Riesgo: gate de acciones GUI + no teclear passwords + injection** | R0-R5 + secret handoff + IsPassword | prompt injection #1, visión spoofeable | ✅ CONFIRMADO |

**Conclusión:** la arquitectura está decidida con triple evidencia. No es opinión.

---

## 2. Lo que mi investigación AGREGA a la de claude.ai (complementa)

- **El GOTCHA del árbol AX lazy/async de Chromium** (verificado: primera lectura
  UIA tras el flag devuelve VACÍO, las siguientes funcionan). claude.ai menciona
  el flag pero NO este detalle de implementación. → la cascada DEBE reintentar el
  walk UIA tras delay antes de caer a OCR, o falla siempre el 1er intento en
  Discord/Spotify. **Crítico para que funcione en la práctica.**
- **La visión como vector de ataque** (Visual Confused Deputy, MIP, VPI-Bench):
  refuerza el argumento PRO UIA-first más allá de la latencia — leer estructura
  es menos spoofeable que leer pixeles.
- **Número de grounding concreto:** UI-TARS-7B saca 49.6% en ScreenSpot-Pro
  (grounding puro). Útil para calibrar expectativa: ni un VLM dedicado clava el
  click más de la mitad en UIs difíciles.

## 3. Lo que claude.ai AGREGA a la mía (complementa)

- **verify_post_action con fusión 2-de-3 señales + código concreto** (dHash 8×8
  Hamming≥6 sobre ROI, no full-screen; UIA cacheRequest bulk; drain de WinEvent
  buffer correlacionado por thread_id). Esto es el corazón y está muy bien
  especificado. **Adoptable casi tal cual.**
- **Detección de password por `IsPasswordPropertyId` (UIA prop 30019)** +
  protocolo de secret handoff (ceder control, no leer el valor, no loguear).
  Concreto y necesario.
- **user-activity monitor con `GetLastInputInfo`** para no pelear el mouse con el
  user. No lo tenía en mi research.
- **Tabla de recovery por tipo de fallo** (target_not_found/stale/focus_lost/...)
  con budget y acción pre-retry. Lista para implementar.
- **RuntimeId para re-bindear elementos** sin re-escanear (caché por turno).
- **Roadmap de 8 fases con gates medibles** — disciplina exacta que pide CLAUDE.md.

## 4. Correcciones contra el ENTORNO REAL (medido esta sesión)

| Afirmación de claude.ai | Realidad medida | Implicación |
|---|---|---|
| "mmproj 992 MB BF16, dudá del 946 reportado" | Tenemos AMBOS: `mmproj-BF16.gguf` (991.5MB) y `mmproj-F16.gguf` (990.4MB) en models/E4B/ | ~990MB confirmado; usamos F16 hoy. El watchdog (inv 6) ya contempla ~946-990MB. |
| "tok/s 40-60, sospechar si >80" | **70.5 tok/s decode medido** (prompt 402 tok/s) | Estamos en el rango alto. Su presupuesto de latencia es válido y hasta algo conservador para nosotros. |
| "medir si cache-reuse funciona con swa-full" | YA medido en sesiones previas: cache-reuse SÍ funciona en b9090 (617/625 cacheados) | No es el problema que él teme. ✅ |
| "audio nativo NO cableado en llama-server" | Cierto y ya resuelto: usamos Parakeet/Whisper aparte (no dependemos de audio del modelo) | Sin acción. ✅ |

## 5. Lo que YA TENEMOS y NO hay que reconstruir (verificado en código)

- Primitivos Win32 reales (mouse SetCursorPos+mouse_event, teclado, screenshot mss).
- `uia` tool (tree/find/click/focus/set_value).
- `gui` tool (click/type/keypress/scroll/drag/locate_text/click_text/locate_image).
- `win_focus.py` golden focus (AllowSetForegroundWindow + ALT + AttachThreadInput).
- `grounding_gate.py` (detecta claims sin evidencia) + anti-unverified-claim.
- `safety.classify_tool_call` (gate de riesgo) + email confirmation.
- `verify_core.py` verificadores estructurales (pycaw/EnumWindows/Path).
- `loop_detection.py` (6 patrones result-aware + no_progress).
- `mission_goal.py` verifier por-misión (arg-aware).
- `profile_watcher.py` (monitoreo CPU/RAM/GPU con histéresis).
- PaddleOCR, cv2, mss, uiautomation, pywinauto, win32api instalados.

**El GAP confirmado (en nuestro código, `mission_outcome.py:34`):** `gui` =
"click es dispatch ciego sin verify post". Tenemos las manos, faltan los ojos en
el loop.

---

## 6. Roadmap consolidado (adaptado a NUESTRO estado real)

Las 8 fases de claude.ai, ajustadas a lo que ya tenemos (varias fases parten de
código existente, no de cero). Cada una con gate medible. **Una por vez, medir,
commit/revertir.**

| Fase | Qué (sobre lo que YA tenemos) | Gate de éxito | Riesgo |
|---|---|---|---|
| **0** | **Eval-set 30 misiones** con `goal_verifier()` estructural por SO (volumen→pycaw, Notepad+texto→UIA, etc.). Reusar verify_core/mission_goal. | 100% reproducible (2 runs sin agente = mismo estado) | Bajo |
| **1** | **`verify_post_action()`** = UIA-delta (cacheRequest) + dHash ROI (Hamming≥6) + WinEvent drain, fusión 2-de-3. Cablear al `gui` tool (cierra el "click ciego"). | <5% falsos PASS en eval-set | Bajo (aditivo) |
| **2** | **Macros `click_button(label)`/`fill_field`/`toggle`/`select_menu`/`wait_for`** observe→act→verify→recover. El 4B da objetivo, no coordenadas. | Task SR ≥40% vs ~15% status quo (Tier-1 UIA-rico) | Medio |
| **3** | **Cascada UIA→OCR→visión** + cache por turno + RuntimeId rebind + **gotcha lazy de Chromium** (reintento walk) + CEF flag con consentimiento | SR Discord/Spotify 0→≥30% | Medio |
| **4** | **Tabla de recovery** (P4) integrada con loop_detector existente | clicks-sin-efecto post-retry <10% | Bajo |
| **5** | **Riesgo R0-R5** + secret handoff (IsPassword 30019) + user-activity monitor (GetLastInputInfo). Extender safety.classify_tool_call. | 0 leaks de password en 100 runs | Medio |
| **6** | **Speculative N=2** validado step-by-step, SOLO si el 4B acierta >80% next-action (medir antes) | latencia p50 −25% vs Fase 2 | Alto (medir) |
| **7** | **Checkpoint JSON mínimo** (reusar state.atomic_write) SOLO para modo misión | 100% misiones interrumpidas reanudan | Bajo |
| **8** | **Visión gateada** (mmproj lazy + crops 384×384 + ≤2 calls/misión) | +10pts SR en custom-render vs Fase 3 | Medio |

**Umbrales que abortan/revierten** (de claude.ai, los adopto):
- Fase 1 falsos PASS >10% → verifier malo, NO seguir.
- Fase 2 Task SR <30% en Tier-1 → macros/UIA mal, no escalar.
- Latencia p95 >7s → el 4B no sirve para descomposición.
- Vision calls/misión >2 steady-state → cascada rota.

**Principios-ley aplicados a TODO el roadmap (CLAUDE.md):**
- Nada de hardcodes/keywords por app/idioma; clasificación por embeddings o por
  estado del SO ([[feedback_no_monolingual_regex]], [[feedback_no_canned_replies]]).
- El LLM decide objetivo; el código determinista hace los pasos.
- Verificación estructural, nunca "el tool dijo ok".
- Confirmar antes de irreversible / comunicación / passwords.
- vram4 manda: visión es último recurso raro, nunca por paso.

---

## 6.bis — BASELINE Fase 0 medido (2026-05-24, contra el agente real)

Primera corrida del eval-set (`scripts/gui_eval/`, 7 misiones Tier-1) contra el
agente real. **Esta es la foto contra la que medimos las fases siguientes.**

| Métrica | Valor |
|---|---|
| Task Success Rate (real, por estado SO) | **71.4%** (5/7) |
| **Falso-PASS rate** | **14.3%** (1/7) |
| Latencia p50 / p95 | 4.8s / 14.7s (p95 = 1er turno frío) |

Detalle:
- ✅ volumen 30/50/10 (es/en/pt) + mute = **4/4** — el control atómico del SO es sólido.
- ✅ abrir Notepad = PASS.
- ❌ `t1_open_calc` = FAIL honesto (no logró abrir calc UWP; lo reportó).
- ❌ `t1_notepad_write` = **FALSO-PASS**: "abrí Notepad y escribí hola mundo" → el
  agente cree que sí (1 step, sin error) pero el texto NO está en el SO. **Es el
  "type ciego sin verify" en vivo, en la misión multi-paso — exactamente lo que
  la investigación predijo y lo que la Fase 1 (verify_post_action) debe cerrar.**

**Lecturas:**
1. El subset alcanzable (atómico, UIA-rico) ya funciona — confirma la tesis.
2. El falso-PASS aparece en multi-paso (abrir+escribir) → el gap del loop
   observe→act→verify es real y medible. Gate Fase 1: bajar falso-PASS de 14.3% a <5%.
3. Latencia: 1er turno 14.7s (frío). Pre-calentar o excluir warmup. Resto 1.7-2.3s.

## 6.ter — FASE 1 hecha (verify_post_action) — resultado HONESTO

`gemma4_agent/gui_verify.py` + cableado en `t_gui` (commit pendiente). Tras
click/type: frame-diff de ROI (dHash 8×8, Hamming≥6) + foreground check, anota
`state_changed` en el result; si False → `verified=False` +
`completion_status="dispatched_no_effect"`. Sin VLM. Gate GEMMA4_GUI_VERIFY=0.
7 tests unitarios; 28 contract tests OK. Medido: capture 34ms + dHash 4ms.

Re-corrida del eval:
- Task SR 71.4% → **85.7%** (calc pasó esta vez; warm-up influye).
- Falso-PASS 14.3% → **0.0%** ✓ (gate <5% cumplido).

**HONESTIDAD (no auto-engaño, lección de Carter):** el falso-PASS bajó a 0 por
DOS razones, y hay que distinguirlas:
1. verify_post_action está construido, funciona y es el cimiento correcto para
   las macros de Fase 2. PERO en el caso que fallaba (`t1_notepad_write`) NO fue
   el factor: el agente solo abrió Notepad (1 step) y NUNCA llamó gui.type, así
   que no hubo acción que verificar.
2. El "falso-PASS" de Fase 0 era EN PARTE un artefacto de mi heurística de
   medición (`_agent_reported_success`): el agente FUE honesto ("no alcancé a
   completar, ¿la repetimos?") pero mi detector no reconocía esa frase. Lo
   corregí (ahora reconoce "no alcancé/no completé/pendiente/...").

**Problema real que SIGUE abierto:** `t1_notepad_write` sigue FAIL — el agente NO
encadena "abrir Notepad Y escribir". Es trabajo de FASE 2 (macros observe→act→
verify + chaining determinista). verify_post_action es el cimiento; las macros lo
van a USAR para no avanzar al paso 2 hasta confirmar el paso 1.

## 7. Decisión

**La arquitectura está triangulada y decidida.** El próximo paso correcto es la
**Fase 0 (eval-set)** — sin medir el estado actual no podemos saber si cada fase
mejora, y construir a ciegas sería repetir el error de Carter (acumular capas que
pasan el bench pero fallan en real).

**Techo honesto que le comunicamos a RED:** vamos a hacer que el agente controle
el PC como humano **de forma confiable en el subset alcanzable** (apps con UIA
rico, misiones ≤5 pasos, verificadas) — no "cualquier misión imposible", porque
ni el SOTA mundial (52.5% Windows) lo logra. La meta medible: subir nuestra Task
SR real en misiones GUI, fase por fase, con número.

NO se tocó runtime en esta sesión — es investigación + decisión. La construcción
empieza cuando RED apruebe arrancar por Fase 0.
