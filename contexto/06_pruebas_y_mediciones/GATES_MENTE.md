# Gates de la mente — cierre con evidencia (Fable)

- Fecha: 2026-07-25. Rama `codex/baxy-rebuild-v3`. ADR-0005 aceptado.
- Regla aplicada: un gate solo se cierra con evidencia enlazada y regresión;
  lo que depende del entorno del usuario se marca `pendiente-por-entorno` y
  queda listo en un paso, sin fingirse cerrado.

## Gate 4 — Cero casos solucionables omitidos: **APROBADO**

- El router de PRODUCCIÓN (`src/baxy_mind`, e5-small + banco de 625 anclas)
  enruta **675/675** casos de los oráculos congelados (40 notas, 113 estado,
  171 audio, 77 GPU, 139 memoria) con la única desviación read-only
  documentada («cuánta memoria me queda libre» → `system.status:memory`,
  semánticamente correcta; el contrato del oráculo se cumple).
  Evidencia: `artifacts/product/mind_router_gate.json`.
- Generalización que el regex no tiene: **89,3 %** leave-one-out
  (`experiments/mind_router_spike/VEREDICTO.md`); los fallos seguros caen al
  LLM, los peligrosos quedaron en 5,5 % y el LLM+core validan detrás.
- El resto del ledger (fuera del catálogo congelado de 22 ops) recibe el
  fallback contractual del propio ledger: «admitir incertidumbre y ofrecer
  una vía concreta» — conversación honesta del LLM (30 probes juzgados,
  0 efectos fabricados del ganador) o guía explícita (memoria). Ninguna
  entrada muere en silencio.
- Regresión permanente: `scripts/test_mind_router_oracles.py` (un paso).
- La cobertura crece por telemetría→exemplars del banco, sin retrain y sin
  listas de frases (ley de no-keywords cumplida: cero regex nuevos; los seis
  archivos interinos declarados no crecieron).

## Gate 7 — Voz al cerebro: **APROBADO** (calibración personal pendiente)

- Cadena completa medida con el backend distribuible: Windows SAPI local →
  Silero VAD 6.2.1 → Parakeet-TDT-0.6B-v3 int8 CPU → wake cerrado/corrector →
  **6/6 segmentaciones, 3/3 wakes y 6/6 rutas ES/EN/spanglish**. Evidencia:
  `artifacts/product/mind_voice_gate.json`.
- La transcripción entra por la puerta única `MissionInput`
  (`VoiceTranscript`): misma validación, routing, riesgo y ejecución que el
  texto. El `MicButton` histórico quedó habilitado (contrato GUI SupersetOf,
  sin regresión).
- El gate de sistema abrió el micrófono USB real, loopback WASAPI, SAPI físico
  y cancelación; midió AEC, reutilizó un clip hablado histórico sin exponer su
  texto y pasó la UI real en modo wake/direct. Queda únicamente medir con el
  usuario presente FAR/FRR personal y barge-in humano sobre parlantes fuertes.
  Evidencia: `artifacts/product/voice_system_gate.json` y ADR-0007.

## Gate 8 — Operaciones componibles y riesgo: **APROBADO** (alcance 1.0)

- La política de riesgo/confirmación NO se movió: vive en el core
  determinista y toda operación propuesta por la mente entra por el MISMO
  camino tipado (schema, riesgo, verificador). `memory.*` jamás se puentea.
- Composición acotada: el LLM puede proponer hasta 2 operaciones por turno,
  ejecutadas en orden por ese camino. Composiciones fuera de catálogo fallan
  cerradas: 17/17 composiciones GPU del oráculo se abstienen en el router
  (`mind_router_gate.json`) y el ganador del torneo abstuvo 92,9 % de
  negativos con 100 % en composiciones muestreadas
  (`experiments/mind_llm_tournament/results/`).
- Composición libre multi-paso con planner persistente queda documentada
  como post-1.0; el contrato de 22 operaciones congeladas no la exige.

Actualización 2026-07-16: esa última línea describe el cierre histórico del
gate de mente y fue superada por ADR-0006. El planner durable ya existe sobre el
catálogo de 168 capacidades. Las 166 misiones compuestas se clasificaron y las
123 evaluables pasaron por el planner real sin ejecutar tools. El baseline fue
38 planes, 20 aclaraciones, 12 conversaciones y 53 rechazos seguros. Tras el
compilador determinista acotado, normalización de argumentos, consenso 2-de-3 y
degradación contractual, el resultado final es **47 planes, 61 aclaraciones,
15 conversaciones y 0 errores**; cero errores de proceso, cero memoria expuesta
y cero tools ejecutadas. Evidencia en `artifacts/planner_recovery/`.

## Gate 9 — Conversación general y respuesta natural: **APROBADO**

- `turn.decide` es la única decisión semántica y ya formula conversación. Una
  acción cerrada continúa por `arguments`; `plan` sólo se solicita después de
  `turn.result.kind=plan`. Ninguna de esas etapas reabre la capacidad elegida y
  el core conserva schema, riesgo, confirmación, efecto y postlectura.
- Conversación general ES/EN/spanglish medida con 30 probes congelados
  (24 del ledger curados a mano + 6 autorados): ganador Gemma-4 E2B QAT con
  **87 % juzgado, 0 llamadas mutantes y 0 capacidades inventadas**;
  revisión juzgada versionada
  (`experiments/mind_llm_tournament/results/convo_judged_review.md`).
- Respuesta natural: el narrador tipado determinista sigue siendo el default
  verificado (gate 11); la mente añade `narrate` (resultado tipado → texto
  natural, 5/5 en la carga del gate 12) y la conversación del LLM para todo
  lo no-operacional. Fallback determinista fail-closed intacto.
- Identidad y límites honestos verificados en los probes fuera de catálogo
  («no puedo cerrar aplicaciones», «no tengo internet»).
- El E2E posterior a retirar respuestas/intenciones por frase recorrió
  `MainWindowViewModel → MindSidecarClient → baxy_mind → core`: 4/4 pruebas
  read-only pasaron en 142,772 s, con las operaciones exactas esperadas,
  journal HMAC autenticado, cero efectos externos y cero timeouts. Evidencia:
  `artifacts/product/mind_shell_e2e_gate.json`.

## Promoción de evidencia semántica: **APROBADA (autoridad one-sided)**

- Corpus runtime: 25.156 filas, 17.784 públicas de train y 7.372 históricas
  filtradas. Las históricas no entrenan la sonda ni llegan como texto al LLM.
  El holdout público mantiene 9.172 filas validation/test fuera de runtime y
  cero solapamientos de texto normalizado.
- El gate E5 real confirmó un caché v4 de 25.156 × 384, recargable sin
  recodificar y con metadata `contains_text:false`. También rechazó el kNN
  puro: 0/256 perfiles factibles, por lo que no publicó una política.
  Evidencia: `artifacts/product/turn_evidence_encoder_gate.json`.
- La sonda lineal posterior tiene autoridad estricta
  `conversation_signal_or_abstain_only`; necesita además consenso kNN y emite
  cero señales accionables. Validation congeló parámetros y hashes antes de la
  evaluación final.
- La ejecución vigente utilizó 2.728 IDs seleccionados por el sello final v2,
  sin textos ni etiquetas en el sello, y aprobó 9/9 controles: precisión
  conversacional 0,994083 (Wilson inferior 0,973916), recall 0,42 (Wilson
  inferior 0,380079), 0/400 falsos accionables (Wilson superior 0,006718) y
  recall bruto de familia diagnóstico 0,991838 a k=7. La familia nunca se
  entrega al LLM como acción. Evidencia:
  `artifacts/product/turn_linear_probe_validation.json`,
  `artifacts/product/turn_linear_probe_gate.json` y ADR-0009.
- Este cierre sólo promueve la señal semántica unilateral; no declara una nueva
  corrida del gate conversacional ni valida instalación, efectos físicos o
  providers.

### Candidato jerárquico de desarrollo v2: **RECHAZADO**

- La evaluación estuvo separada del runtime y no tuvo autoridad de ejecución.
  Obtuvo cero errores direccionales, pero seleccionó sólo 12/2.300 turnos
  `supported_effect` (0,005217), por debajo del mínimo prerregistrado 0,02.
- Dos guards del prerregistro apuntaban a
  `thresholds.selective_guards.*`, mientras el artefacto real usa
  `selective_guards.*`. No se reparó esa ruta después de evaluar.
- Resultado: `failed_no_runtime_promotion`; no se publicaron pesos, fast path
  ni señal supported. El test oficial MTOP de 7.384 filas continúa sellado sin
  decodificar y el holdout final reservado no se abrió. Sigue vigente el LLM
  contextual con la política one-sided anterior sólo como evidencia consultiva.
  Evidencia:
  `artifacts/development/turn_policy_e5_selective_preregistration.json`,
  `artifacts/development/turn_policy_e5_selective_development.json` y
  `artifacts/development/turn_policy_e5_selective_gate.json`.

## Gate 12 — Recursos y fallback medidos: **APROBADO** (3 GiB)

- El sidecar completo se midió con el protocolo público v4 en dos perfiles:
  **45/45 solicitudes y cero errores por perfil** —30 `turn.decide`, 10
  `arguments` y 5 `narrate`—, sin ejecutar efectos. Evidencia:
  `artifacts/product/mind_budget_gate.json`.
- GPU (`-ngl 99`): VRAM dedicada atribuida al árbol **1.509,6 MiB ≤ 3.072** y
  RAM pico 2.934,4 MiB. `turn.decide` p50/p95/máximo
  5,762/15,097/19,513 s; `arguments` 1,188/1,495/1,495 s y `narrate`
  0,323/0,410/0,410 s.
- CPU puro (`-ngl 0 -dev none --no-kv-offload --no-op-offload
  --no-mmproj-offload`): VRAM atribuida **109,5 MiB ≤ 128**, RAM pico
  4.113,5 MiB y `turn.decide` p50/p95/máximo
  **19,509/19,528/19,532 s ≤ 22 s**. `arguments` quedó en
  11,526/13,970/13,970 s y `narrate` en 2,480/3,745/3,745 s.
- Saludo y catálogo compartieron un único handshake de 120 s; `catalog.ready`
  llegó en 7,047 s GPU y 5,522 s CPU. La memoria GPU se atribuyó por PDH al
  árbol de procesos; el total de `nvidia-smi` quedó sólo como contexto.
- `pendiente-por-entorno`: pasada en una GPU física de exactamente 3 GiB (este
  host tiene 16 GiB). Un paso: `scripts/measure_mind_budget.py`.

## Regresión del cuerpo

La suite completa vigente aprobó **2.063/2.080 pruebas .NET** —46 Contracts,
88 Kernel, 373 Providers, 1.092 Integration y 464 Setup— con 17 omisiones
explícitas y cero fallos. Python aprobó **611 tests y 350 subtests**, sin fallos
ni omisiones.
La mente es opcional: sin `BAXY_MIND_PYTHON`, el producto conserva el fallback
determinista del core.

## Estado de release

La instalación comprobada quedó en **BAXY 1.0.8**, con **1.0.7** como rollback.
Dos construcciones, paquetes y Setup fueron byte-idénticos desde
`b41dda11567a`; el paquete tiene SHA-256 `9e4abb30…f8cbb` y Setup
`c71fad8f…6fe5` (`NotSigned`). La atestación enlazada aprobó la activación
recuperada, rollback 1.0.8→1.0.7 y reactivación 1.0.7→1.0.8, con smoke de 168
capacidades en cada estado, 11 árboles inmutables y 1.780.271.404 bytes privados
idénticos. El gate limpio de instalación inicial/purge permanece
pendiente-por-entorno. Evidencia:
`artifacts/setup/baxy_1_0_8_release_attestation.json`.

## Pendiente-por-entorno consolidado (sin fingir cierre)

1. Gate 14: instalación desde cero + purge en perfil limpio (de Codex).
2. Gate 13: `app.open` físico sin procesos preexistentes (de Codex).
3. Gate 7: calibración corta de wake/barge-in con la voz del usuario.
4. Gate 12: pasada en GPU física de 3 GiB.

Cada uno queda ejecutable en un solo paso con su script/checklist.
