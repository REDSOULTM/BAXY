# Mapa real del turno end-to-end (2026-07-30)

Mapa respaldado por archivos y símbolos del checkout, construido durante la
revisión integral del 30 de julio de 2026. Las latencias citadas provienen de
los artefactos fechados bajo `artifacts/fixes/` de esa campaña; el estado
térmico de todas las mediciones fue SM 900 MHz constante. Complementa, no
sustituye, `MAPA_DEL_SISTEMA.md` y la guía de latencia.

## Cadena de procesos y ownership

| # | Componente | Proceso/hilo | Símbolos clave | Contrato | Latencia medida |
|---|---|---|---|---|---|
| 1 | Entrada visible | WebView2 (proceso Edge) | `src/Baxy.FieldUi/dist` sellado; bridge nativo | `baxy.field.v1`, mensajes tipados, sin autoridad | render fuera de alcance sin sesión interactiva |
| 2 | Orquestación UX | WPF UI thread + tasks | `MainWindowViewModel.cs` (3.111 líneas), `AppSurfaceNavigator` | publica mensaje completo; sin streaming | transporte no-LLM 1–2 ms |
| 3 | Host de sidecars | App, procesos hijos | `LocalJsonlSidecarProcess.cs` (drain stderr 8 KiB), `BoundedUtf8LineReader.cs`, `MindSidecarClient.cs` | JSONL UTF-8, framing acotado, budgets monotónicos | writer 7 ms/20k; reader 18 ms bench |
| 4 | Mente (sidecar) | Python `baxy_mind.__main__` | `main()`: lane urgente vs serial; `catalog.configure` en ~2526 | `baxy.mind.v1` (hello, catalog, turn.decide, arguments, narrate, turn.evidence.status) | spawn→hello 0,49 s; catálogo 3,4–4,6 s |
| 5 | Encoder E5 | subproceso `baxy_mind.router_worker` | `ProcessIntentRouter` (`router.py:413`): launcher daemon, spawn diferido (default **3 s**, antes 6), colas y locks de lifecycle | JSON por stdin/stdout; `{"type":"ready"}` | spawn→ready **19,05 s** (suelo físico); encode 66 ms |
| 6 | Evidencia semántica | hilo daemon `baxy-turn-evidence` | `TurnEvidenceService` (`turn_evidence.py:1424`), `TurnEvidenceIndex.from_corpus` con caché de vectores en `%LOCALAPPDATA%\BAXYRuntime\turn-evidence` | advisory fail-open: `candidate_families()`→`()`, `retrieve()`→`[]` si no está listo | building→ready **14,8–21,8 s** tras catálogo |
| 7 | Promoción semántica | hilo daemon `baxy-planner-e5-promotion` | `promote_planner_resources` (`__main__.py:2401`): espera build ≤185 s, `router.try_ready`, swap bajo `planner_resources_lock` | intercambia `PlannerCatalog` léxico→semántico | segundos tras ready |
| 8 | Decisión de turno | serial en el sidecar | `LlmRuntime.decide_turn` (`llm.py:2365`), `_build_turn_policy_payload` (`llm.py:465`), scheduler P/G/L→V→C, K especulativo con cancelación, LRU exactas G/L/V/C (32) | P JSON Schema; G/L GBNF; máx. 3 POST | P nuevo 2,3–4,1 s; turno p50 4,1 s |
| 9 | Servidor del modelo | subproceso `llama-server` b9980 | `_server_command` (`llm.py:1125`): 3 slots GPU, ctx 4096×3, KV Q8, FA, `--reasoning off/budget 0`; pool HTTP `llm_transport.py` (3 conexiones, keep-alive 4 s/90) | OpenAI-compat loopback | prefill 708–859 t/s; decode 25–48 t/s; 3 slots ≈2,05×; backpressure ~1 decode; cancel +87 ms |
| 10 | Núcleo ejecutable | subproceso NativeAOT | `CoreProcessClient.cs` → `Baxy.Core/Program.cs` (composition root) | `baxy.local.v1`; catálogo 168 validado en hello | hello frío 1,889 s; ops calientes 0,03–0,19 s |
| 11 | Autoridad | dentro de Core | `Baxy.Kernel` (`ProductCatalog.cs`, schema/riesgo/confirmación, `RequestFingerprint`, journal/replay) | única fuente de autoridad; replay idempotente | fingerprint 365 ms/50k bench |
| 12 | Efectos | dentro de Core | `Baxy.Providers.Windows` (observación-primero; `EffectMayHaveOccurred`) | postcondición o ambigüedad explícita | por provider; sin efectos en benchmarks |
| 13 | Narración | mente + App | `narrate`/`message.compose` | LLM formula todo lo visible | narrate p50 0,19–0,25 s |

## Estado mutable, colas y cancelación (verificado)

- El sidecar conserva un lane serial para trabajo de modelo y una cola urgente
  para control (`__main__.py`); cancelación y shutdown tienen prioridad.
- `ProcessIntentRouter`: `_closed` event + `_lifecycle_lock` cierran la carrera
  spawn/cierre (un hijo creado durante shutdown se mata localmente).
- `decide_turn` cancela L/V huérfanas al fallar un intento
  (`_retire_deferred_*`, `llm.py:2383`); una inferencia cancelada no publica
  caché.
- Retries de P: 2 intentos wire × 2 lógicos, `seed = base + logical*1009 +
  attempt`, temp 0→0,1 (`_post_schema_object`, `llm.py:1764`); G/L válidos se
  reutilizan en el retry (promoción 2026-07-30).
- LRU G/L/V/C: exactas, 32 entradas, solo con proceso de modelo poseído; se
  vacían al reemplazarlo.
- Backpressure físico: 4º POST encola ~un decode y nunca falla; la
  recuperación tras cancelar a mitad de decode cuesta +87 ms
  (`server_concurrency_cancel_20260730.json`).

## La frontera bifásica (hallazgo prioritario)

`catalog.configure` publica un catálogo léxico síncrono y arranca en segundo
plano evidencia+promoción. Hasta la promoción (~15–22 s), el prompt de P se
compone sin familias preferidas ni scores semánticos: el mismo texto puede
recibir otra decisión según el instante de llegada
(`evidence_readiness_stability_verdict_20260730.json`). Descomposición de la
ventana: retraso de spawn (3 s desde esta campaña; 6 s antes) + **suelo E5 de
~19 s** (imports+modelo; medido standalone) + caché de vectores (~1–2 s) +
swap. El suelo E5 es del activo/stack, no una perilla interna.

La brecha de fidelidad gates↔producto quedó cerrada: la certificación canónica
ejerce el default productivo de 3 s y el arranque inmediato del encoder es un
escenario de estrés explícito
(`sidecar_environment(..., router_start_stress=True)`).

### Cuánta superficie queda expuesta (medido)

`scripts/detect_promotion_boundary_decisions.py` recorre el corpus completo
—carga congelada de 30 turnos más los pools positivos y distractores del banco
de router— bajo el régimen léxico y bajo el promovido, con dos pasadas
semánticas para distinguir régimen de caché
(`promotion_boundary_decisions_20260730.json`, 2026-07-30):

| Métrica | Valor |
|---|---:|
| Textos únicos del corpus | 330 |
| Resueltos por el reconocedor determinista (independientes del régimen por construcción) | **107** |
| Decididos por el modelo | 223 |
| De esos, con distinta composición de prompt entre regímenes | 223 |
| De esos, con distinto conjunto de operaciones visibles | 223 |
| De esos, con distinto primer candidato | 163 |
| Inestabilidad por estado de caché dentro del régimen semántico | **0** |

Lectura: dentro de un régimen las resources semánticas son deterministas —el
estado de caché no cambia nada—, pero entre regímenes el catálogo léxico
(28 herramientas fijas) y el promovido (19–24, distintas) muestran al modelo
conjuntos de candidatos distintos para **todo** turno que no resuelva el
reconocedor determinista. Es una propiedad del diseño bifásico, no un defecto
localizado: la única variante que la elimina es V-A (bloquear la admisión
hasta readiness), rechazada por decisión de producto por su coste de SLA. Por
eso la vía practicable es ampliar la resolución determinista, y esa es la
métrica que esta campaña movió.

### Cobertura determinista promovida (2026-07-30)

`effect_intent.py` resuelve ahora, sin modelo y sin evidencia semántica, las
preguntas de estado del equipo (batería, carga, CPU/núcleos, RAM, disco,
GPU/VRAM, versión de Windows, resumen) y las de audio (nivel y estado de
silencio), además del silencio global con sus sinónimos. La compuerta de acto
de habla acepta cabezas interrogativas de cantidad y formas nominales, y un
vocativo inicial («che baxy…») ya no desplaza la petición.

La frontera de autoridad se mantiene por vetos explícitos y probados:
conocimiento general de hardware, consejo/compra/precio, diagnóstico causal,
temperatura, atribución por proceso, observación sostenida en el tiempo, otro
dispositivo, estado pasado o hipotético, ámbito de aplicación, micrófono,
memoria privada del asistente y combinaciones de alcances que el enum del
catálogo no mide en una sola lectura.

Prueba física en los dos regímenes y en los dos órdenes
(`r3_regime_stability_verdict_20260730.json`): 22 turnos × 4 pasadas
(frío/asentado × orden 1/2), **misma decisión contractual en las cuatro**,
1 intento en todos los casos, 0 errores de validación, máximo 5,84 s. Los tres
drenajes conocidos desaparecieron: turn-04 y turn-24 pasan a `audio.status` y
turn-06, turn-00 y turn-23 a `system.status`, todos en 0,001–0,038 s.

## Rutas y latencias por tipo de turno (medidas)

| Ruta | p50 medido | Composición |
|---|---:|---|
| Explícita (sin LLM) | 0,001–0,038 s | JSONL + router + resolución explícita |
| Conversación nueva | ~3,3–4,8 s | E5+grounding 0,19 s → P crítica → chat solapado/K especulativo |
| Acción | ~2,2 s | P + V/C en slot de G; extracción literal 0,0002 s cuando aplica |
| Plan | ~4,3–5,8 s | P + validadores |
| Clarify con drenaje | 14–19,5 s | 4 intentos P drenados + clarificación (causa raíz probada; sin corrección interna segura). Ya no aparece en los turnos de estado, que ahora resuelve el reconocedor determinista |
| Chat puro caliente | 1,4–2,5 s | indistinguible del modelo aislado (delta p50 −6 ms, p=1,0) |
