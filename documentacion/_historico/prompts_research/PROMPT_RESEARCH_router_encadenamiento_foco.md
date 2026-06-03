# Prompt de investigación — Router robusto + Encadenamiento multi-tool + Foco/maximize (Carter Agent)

Copiá esto a claude.ai (con research/web). Es la profundización de implementación
de 3 problemas (A router, B encadenamiento, C foco GUI) sobre NUESTRA arquitectura
real. Un informe anterior ya dio el panorama; acá quiero CÓDIGO concreto para
nuestro stack y que considere los hallazgos nuevos. Distinguí confirmado de
hipotético, citá fuentes recientes, snippets listos para pegar.

---

## 0. Stack (confirmado en código)

- **Modelo**: Gemma 4 E4B-it Q4_K_M (GGUF), llama.cpp b9090+, monoslot, 6 GB,
  Windows. Function-calling nativo (`--jinja`). Asistente de VOZ.
- **Router de tools** (ya existe, NO partir de cero): pipeline
  `semantic_router.py` (encoder `paraphrase-multilingual-MiniLM-L12-v2` fine-
  tuneado + Tool2Vec + RRF) → `intent_router.py` (`classify_intent` info/acción
  por anclas multilingües; `wants_knowledge`) → `abstain_head.py` (gate no-tool)
  → `planner.py`. Holdout recall 0.881. 65 tools; el router elige 4-6 por turno.
- **Loop de agente**: `max_agent_turns=8` — el agente PUEDE llamar tool_A, ver el
  resultado, y llamar tool_B en la siguiente iteración. El encadenamiento es
  posible; el problema es que el modelo NO usa el resultado.

## 1. HALLAZGOS NUEVOS de esta sesión (contexto crítico)

- **El router degrada en SILENCIO**: instalar `torchcodec` rompió sentence-
  transformers → `classify_intent`→None, `suggest_tools`→[] → TODO se mis-ruteó
  ("¿qué es Mortal Kombat?" creó un documento porque el fallback solo ofrecía
  `office`). Tras desinstalar: classify_intent info=0.48>action=0.30, top tool
  =web. Lección: el sistema NECESITA auto-diagnóstico que falle ruidoso, no que
  degrade a un fallback arbitrario.
- **`intent_router.classify_intent` YA EXISTE y funciona** (con el encoder sano).
  No hay que crear el clasificador info/acción desde cero — hay que hacerlo
  ROBUSTO al sesgo de nombres propios y agregarle el health-check.

## 2. Los 3 problemas (evidencia de logs reales, sesión #847)

### A — Router robusto y auto-diagnóstico
Aun con encoder sano, nombres propios (juegos/pelis/apps) sesgan el embedding
hacia tools de creación. Necesito: (a) hacer `classify_intent` robusto a nombres
propios (¿gate sintáctico interrogativo qué/quién/cuándo/por qué/cuál + "?" ANTES
del retrieval? ¿enmascarar entidades antes de embeber?); (b) **health-check del
encoder al startup** que falle visible (no silencioso) si el modelo no cargó;
(c) preservar el recall holdout 0.881. Quiero el código concreto del gate y del
health-check, y cómo integrarlos sin romper el RRF+Tool2Vec existente.

### B — Encadenamiento multi-tool (search→open, search→play)
"Abre el primer Word en Descargas" → el modelo llamó `filesystem.search`
(encontró .docx) pero NO encadenó `office.open(path=...)` en la siguiente
iteración del loop (que SÍ existe, max_agent_turns=8). En otra iteración llamó
`office.open` SIN path → falló "no me diste ruta". Es un modelo de 4B: la
literatura dice que los ~4B tienen "tool-call bias" y fallan el encadenamiento
multi-paso. Necesito el patrón MÁS FIABLE para que use el resultado de tool_A
como input de tool_B: ¿planner determinista por plantilla para los pares
conocidos (search→open, search→play, search→read)? ¿reflexión obligatoria
inyectada tras cada tool_result? ¿validación de args (no llamar open con
path=None)? Quiero el código del despachador de patrones deterministas + el
fallback con reflexión, pensado para integrarse en un loop que ya existe.

### C — Foco+maximize 100% fiable antes de teclear (Windows)
Al teclear en apps por GUI (WhatsApp, Spotify) a veces la ventana está
minimizada/sin foco → la acción falla o va a la ventana equivocada. Hoy hay
`window(action=focus)` (restore+maximize) + verificación del título de la
ventana activa antes de teclear, pero NO es 100% fiable (foreground-lock de
Windows). El tipeo ya es robusto a Unicode (clipboard-paste). Necesito la
secuencia canónica en CÓDIGO (no dependiendo del LLM) para garantizar
foreground+maximize: SetForegroundWindow + el truco ALT documentado por
Microsoft + AttachThreadInput + ShowWindow + verificación + retry con backoff,
y el manejo de UWP/Windows Store apps (WhatsApp es UWP) vía UI Automation.
Quiero el módulo `win_focus.py` completo y robusto, con los pitfalls (procesos
elevados, foreground-lock, error 87 de AttachThreadInput).

## 3. Restricciones

100% local, OSS, Windows 10/11. El modelo es chico (4B) — los patrones no pueden
asumir razonamiento fuerte. Multi-idioma (es/en/pt/it al menos). No romper el
router existente (recall 0.881) ni el tool-calling (que ya es 12/12 en el smoke).

## 4. Formato

Por cada problema (A, B, C): diagnóstico, opciones con tabla comparativa
(criterios medibles), fuentes oficiales/papers recientes, veredicto VIABLE para
ESTE stack, y CÓDIGO/pseudocódigo Python listo para pegar e integrar en los
archivos reales (semantic_router.py/intent_router.py/planner.py para A-B, un
win_focus.py nuevo para C). Priorizá A (router robusto+health-check, es lo que
ya nos rompió) y B (encadenamiento, es el fallo de UX más visible). Distinguí lo
confirmado de lo hipotético; marcá lo que hay que MEDIR en nuestro dataset.
