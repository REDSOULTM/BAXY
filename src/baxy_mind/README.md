# baxy-mind — sidecar de inteligencia (ADR-0005)

Segundo proceso local de BAXY 1.0: router de intención por embeddings, LLM de
conversación/tools y voz. Corre sobre la frontera JSONL UTF-8 + Job Object del
cuerpo determinista. Los modelos JAMÁS viven en el core .NET.

El mapa de ownership, build y flujos del producto completo está en
[`documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md`](../../documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/README.md).

## Activación

La mente es **opcional y degradable**: sin ella, App conserva solo rutas
deterministas acotadas App → Core para slices privadas soportadas; Core no
interpreta lenguaje libre y esa entrada falla cerrada sin ejecutar. La baseline
vigente y sus conteos se mantienen únicamente en
[`REGISTRO_DE_MANTENIBILIDAD.md`](../../documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md).

Para una app instalada no hace falta declarar variables manualmente. La primera
preparación recibe `-Python` explícitamente en
`scripts/setup_mind_voice.ps1` y `scripts/register_mind_runtime.ps1`; las
siguientes ejecuciones reutilizan el Python del manifiesto registrado. El
registro valida el grafo Python y los assets locales antes de escribir
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`. BAXY lo descubre al arrancar
y configura planner/LLM/STT en el proceso. La escucha continua requiere un
manifiesto ONNX de «Baxy» calibrado en el almacén externo. Ese manifiesto puede
habilitar una ruta híbrida adicional: VAD conserva provisionalmente una frase
sin ducking ni eventos visibles y, al terminar, exige a la vez un score acústico
independiente y un nombre canónico al inicio de la transcripción local. Sin un
activo calibrado, el botón de micrófono directo sigue disponible y no se simula
un wake con transcripción continua. El runtime
se mantiene separado del ZIP de producto porque sus assets locales superan 5
GiB; el instalador y su actualización siguen siendo pequeños.

| Variable | Valor | Rol |
|---|---|---|
| `BAXY_MIND_PYTHON` | ruta a `python.exe` de un entorno con las deps de abajo | habilita la mente (el shell lanza `python -X utf8 -m baxy_mind`) |
| `BAXY_MIND_PYTHONPATH` | ruta a `src/` del repo (o donde viva `baxy_mind`) | import del paquete |
| `BAXY_MIND_LLM_GGUF` | ruta del GGUF ganador (Qwen3-4B Q4_K_M) | LLM; sin ella siguen encoder, evidencia, voz y control plane, pero no hay generación LLM para turno/planner |
| `BAXY_MIND_LLAMA_SERVER` | ruta de `llama-server.exe` (build CUDA b9980 atestado o CPU) | runtime del LLM |
| `BAXY_MIND_NGL` | `99` (GPU) / `0` (CPU puro) | con `0`, llama-server añade `-dev none --no-kv-offload --no-op-offload --no-mmproj-offload`; Flash Attention queda activo porque la caché V Q8 lo exige |
| `BAXY_MIND_TURN_CORPUS` | JSONL promocionado opcional | corpus exacto de evidencia; si no existe, la mente continúa sin esa señal |
| `BAXY_MIND_TURN_EVIDENCE_CACHE` | directorio opcional | par E5 v4 JSON/NPY sin textos; por defecto usa el almacén local del runtime |
| `BAXY_MIND_TURN_EVIDENCE_POLICY` | JSON promocionado opcional | sonda one-sided vinculada por hashes al corpus y al encoder |
| `BAXY_MIND_STT_DIR` | bundle sherpa Parakeet int8 | verificador STT final; prioridad explícita, manifest registrado y candidatos declarados en `assets.manifest.json` |
| `BAXY_VOICE_STREAMING_STT_DIR` | bundle sherpa Nemotron 3.5 Streaming int8 | primera pasada local opcional; por defecto descubre el bundle hermano instalado |
| `BAXY_VOICE_STREAMING_STT` | `on` / `off` | activa explícitamente hipótesis ASR parciales, solo después de un turno abierto; queda apagado hasta aprobar un corpus de promoción |
| `BAXY_VOICE_STREAMING_LANGUAGE` | `auto`, `es-ES`, `en-US`, … | locale del stream Nemotron; `auto` por defecto |
| `BAXY_VOICE_WAKE_ON_START` | `1/true/on` | escucha continua desde la app; apagada si no se declara |
| `BAXY_VOICE_WAKE_MANIFEST` | ruta al manifiesto `baxy-wakeword-v1.json` | modelo ONNX KWS acústico; por defecto usa los candidatos declarados en `assets.manifest.json` |
| `BAXY_VOICE_WAKE_CASCADE_MANIFEST` | ruta al manifiesto `baxy-wake-cascade-v1/v2.json` | cascada acústica y, solo si el manifiesto calibrado lo declara, ruta endpoint score-gated |
| `BAXY_VOICE_LEXICAL_WAKE_FALLBACK` | `on` solo para migración | restaura el prefijo STT heredado; apagado por defecto y nunca se presenta como KWS |
| `BAXY_VOICE_WAKE_ALIASES` | CSV opcional | solo limpieza estricta del prefijo ya autorizado o fallback explícito |
| `BAXY_VOICE_SAPI_VOICE` | fragmento del nombre de una voz SAPI | preferencia TTS; por defecto elige una voz española instalada |

Las dependencias directas se declaran en `requirements-runtime-win-x64.in`;
`requirements-voice.txt` aporta únicamente las entradas del componente de voz.
El grafo aprobado completo se instala desde `pylock.runtime-win-x64.toml`, que
fija cada versión, wheel y SHA-256 para CPython 3.12/Windows x64. Pytest vive en
el perfil separado `pylock.test-win-x64.toml`. Ambos locks se regeneran o
comprueban con `scripts/lock_python_dependencies.ps1 -Profile Runtime|Test`.
Modelos: `intfloat/multilingual-e5-small` (caché HF), GGUF del LLM, bundle
Parakeet int8 obligatorio y Nemotron 3.5 Streaming int8 opcional, ambos
resueltos desde el descriptor común. El KWS vigente usa una cascada local
HyperSpotter/log-Mel ONNX con assets y umbrales ligados por hash. La ruta
endpoint opcional reutiliza un verificador log-Mel independiente y una lista
cerrada que excluye pronunciaciones ambiguas como `Basi`/`basic`/`vas y`.
`VoiceEngine.start()` prepara Parakeet y Nemotron; mientras espera no ejecuta
ASR continuo: solo decodifica una locución VAD completa si el manifiesto
calibrado habilita la ruta endpoint. Nemotron solo
publica parciales de un turno ya autorizado; Parakeet+AEC conserva la
transcripción final que llega al flujo `MissionInput` de App y, si corresponde,
al core.

Para instalar el primer pase en el almacén externo de assets, ejecuta
`scripts\install_nemotron_streaming_stt.ps1`. El script comprueba tres ONNX,
`tokens.txt` y un tamaño mínimo del encoder, evita reemplazar un bundle
existente y deja para instalaciones nuevas un recibo con el SHA-256 observado
después de descargar. Ese recibo no compara el archivo con un digest esperado,
por lo que no acredita por sí solo identidad de supply chain.

Para publicar el modelo de activación, entrena el clasificador en un entorno
CUDA aislado con `scripts\baxy-wakeword-production.yaml`, evalúalo con
`scripts\evaluate_wake_corpus.py --wake-manifest ... --positive ... --negative
... --output ...` y luego instala solo un informe promocionable mediante
`scripts\install_baxy_wake_model.ps1 -ModelPath ... -CalibrationReport ...`.
La compuerta adicional `scripts\run_wakeword_physical_room_gate.py` reproduce
ese corpus por un altavoz explícito y evalúa únicamente lo capturado por un
micrófono explícito; requiere `--physical-output`, no conserva audio y puede
emitir el mismo informe v3 solo cuando también cumple la suficiencia y los
límites estadísticos del producto.
El informe deliberadamente no conserva audio, nombres de archivo ni
transcripciones, y exige corpus suficiente antes de habilitar el modelo. El
contrato actual es `baxy-wake-corpus-gate-v3`: vincula el ONNX, cada parámetro
de decisión y el informe por SHA-256; exige FRR ≤5 % y un límite unilateral
Poisson de FAR al 95 % ≤0,1 activaciones/hora. Con cero falsos positivos, eso
requiere al menos 30 h negativas (5 h no prueban ese límite).

## Protocolo (baxy.mind.v1)

Una línea = un JSON UTF-8 (tope 1 MiB). stdout: `hello` al arrancar, luego
respuestas por `id` y únicamente dos tipos no solicitados:
`voice.transcript` y `voice.event` (con subtipo en su campo `event`).

Si existe GGUF, Mind crea el LLM e inicia `start_warmup()` antes de emitir
`hello`. El shell entrega `catalog.configure` inmediatamente después del saludo
y `catalog.ready` espera readiness del LLM dentro de los presupuestos de
startup.

La configuración usa el `hello` exacto del proceso Core hijo que App validó por
PID y comparación de
descriptores. No es una firma criptográfica del mensaje. La mente no lee
snapshots de catálogo en disco: recibe el conjunto exacto validado por Core; su
conteo vigente se mantiene en el registro de mantenibilidad.
El mismo mensaje puede incluir `applicationCatalog`, un inventario acotado,
verificado y normalizado por el provider de Inicio de Windows. Sus nombres se
usan únicamente para coincidencia exacta de objetivos `app.open` y
`app.installed`: no entran en prompts, embeddings, historial ni respuestas.

`turn.decide` es la única frontera pública que decide el tipo de turno y
formula una respuesta conversacional. El shell solicita `plan` únicamente
cuando `turn.result.kind == "plan"`; una decisión `action` usa la operación
cerrada y la extracción tipada de argumentos, sin una segunda decisión abierta.
Cuando el turno contiene efectos explícitos reconocibles, `effectOperations`
los conserva en orden hasta la planificación. El shell los reenvía como
`expectedOperations`; `plan` puede materializar sus argumentos y dependencias,
pero no sustituirlos ni omitirlos.

Solicitudes anunciadas por `hello.requests`:

| Solicitud anunciada | Respuesta | Semántica |
|---|---|---|
| `catalog.configure {capabilities, applicationCatalog?, gameCatalog?}` | `catalog.ready {count}` | catálogo cerrado del core y entidades verificadas de aplicaciones y juegos instalados; una sola configuración por proceso |
| `turn.decide {text, history}` | `turn.result {kind, operation, effectOperations, question, reply}` | única decisión contextual y única generación conversacional; reconoce efectos explícitos contra el catálogo cerrado y la evidencia semántica sólo puede reforzar conversación o abstenerse |
| `plan {text, history, recovery?, expectedOperations?}` | `plan.result {kind, question, steps}` | se solicita sólo tras `turn.result.kind == "plan"`; conserva exactamente los efectos reconocidos, incorpora dependencias observables, mantiene DAG ≤16 y argumentos literales con evidencia |
| `plan.ground {objective, operation, purpose, observations}` | `plan.ground.result {arguments}` | materializa IDs/estado sólo después de dependencias verificadas |
| `narrate {userText, operation, outcome}` | `narrate.result {text}` | resultado tipado → lenguaje natural |
| `voice.start` / `voice.stop` | `voice.started/stopped` | acuses del handler, no prueba de cleanup físico final; `direct`: VAD → ASR; `wake`: KWS acústico o VAD → score acústico + prefijo canónico → ASR/AEC |
| `voice.status` | `voice.status.result` | disponibilidad real de mic, STT, VAD, TTS, AEC y ducking |
| `voice.speak` / `voice.cancel` | aceptación/cancelación | SAPI local; permite barge-in sin Piper/GPL |
| `shutdown` | `shutdown.ack` | acuse terminal de transporte; puede preceder a `lifecycle.close` y no prueba reap físico |

Implementadas y consumidas por App, pero no anunciadas:

| Solicitud omitida del anuncio | Respuesta | Semántica |
|---|---|---|
| `arguments {operation, text}` | `arguments.result {arguments, ok, question}` | JSON Schema, evidencia literal, grounding determinista y abstención |
| `message.compose {userText, intent, facts}` | `message.compose.result {text}` | compone lenguaje natural desde hechos acotados |

`turn.evidence.status` también está implementada sin anuncio y la usa tooling
de gates. Es una deuda de contrato vigente: `arguments` y `message.compose` ya
tienen consumidores, por lo que corregirla exige actualizar ambos extremos, el
handshake y las pruebas de compatibilidad.

## Evidencia semántica de turnos

El corpus promocionado contiene 25.156 filas: 17.784 públicas de train
(PRESTO/MASSIVE) y 7.372 históricas filtradas. Las históricas tienen etiquetas
débiles o ruidosas: participan únicamente en el índice y en diagnósticos de
familia, no entrenan la sonda y su texto nunca llega al LLM. Dev/test público
permanece en un holdout disjunto de 9.172 filas; el gate comprobó cero
solapamientos de texto normalizado con runtime.

`TurnEvidenceService` construye en segundo plano embeddings normalizados de
`intfloat/multilingual-e5-small`. El caché `baxy.turn-evidence.v4` es un par
atómico JSON/NPY ligado al SHA-256 del corpus y a la identidad del encoder. Su
metadata declara `contains_text:false`: guarda vectores y campos estructurados,
no frases. Una migración sólo elimina cachés literales anteriores después de
persistir, recargar y verificar v4.

La política publicada combina una sonda logística calibrada con consenso kNN.
Su autoridad es `conversation_signal_or_abstain_only`: ambos clasificadores
deben aceptar para aportar una señal `conversation`; de otro modo devuelve
cero evidencia. Incluso al aceptar, entrega modos y puntuaciones agregables,
con familias vacías y sin ejemplos textuales. El kNN de familia se conserva
sólo como diagnóstico y jamás se ofrece al LLM como acción.

El kNN puro fue rechazado honestamente: ninguno de 256 perfiles satisfizo los
límites de validation y no publicó política. La alternativa one-sided congeló
sus umbrales en validation y ejecutó una sola evaluación final sobre 2.728 IDs
de test sellados antes de la puntuación final; el sello no contiene textos ni
etiquetas. El resultado vigente aprobó 9/9 controles: precisión conversacional
0,994083 (Wilson inferior 0,973916), recall 0,42 (Wilson inferior 0,380079),
cero señales accionables y límite superior Wilson de falso accionable
0,006718 sobre 0/400 casos. El recall bruto de familia diagnóstico a k=7 fue
0,991838. Evidencia:
`artifacts/product/turn_evidence_encoder_gate.json`,
`artifacts/product/turn_linear_probe_validation.json`,
`artifacts/product/turn_linear_probe_gate.json` y ADR-0009.

Un candidato jerárquico E5 de desarrollo v2 se evaluó por misión y sin
autoridad de ejecución. Quedó rechazado: seleccionó 12/2.300 turnos
`supported_effect` (0,005217 < 0,02) y dos rutas de guards del prerregistro no
resolvían contra el artefacto. No se corrigieron a posteriori, no se publicaron
pesos ni fast paths y no se abrió el test oficial MTOP ni el holdout final
reservado. El runtime conserva la política one-sided anterior como evidencia
consultiva y el LLM contextual como decisor.

El gate shell end-to-end posterior a retirar atajos por frase aprobó 4/4
recorridos read-only en 142,772 s, sin efectos externos ni timeouts y con
journal HMAC validado:
`artifacts/product/mind_shell_e2e_gate.json`.

## Invariantes

- Fail-closed: si no hay LLM/planner, no se degrada a una acción decidida por
  frases; no se ejecuta una acción parcial. `memory.*` conserva su frontera
  privada determinista. `memory.*` nunca se puentea desde la mente.
- El router de producción requiere embeddings E5: no existe un regex, una
  coincidencia exacta o una respuesta escrita a mano que pueda sustituir su
  resultado semántico. Un timeout, ID no coincidente o respuesta inválida
  retira el worker y falla cerrado; una respuesta tardía no se reutiliza.
- Los términos de corrección de voz y la relevancia de operaciones se derivan
  del catálogo validado (nombres, descripciones y enums), no de inventarios
  fijos de verbos o entidades.
- Los nombres de aplicaciones provienen del snapshot verificado del core y
  solo conceden autoridad mediante una coincidencia exacta y anclada; nunca se
  interpolan en el LLM ni habilitan coincidencia difusa.
- Propuesta y auditoría deben conservar la misma secuencia de operaciones. El
  modelo no controla riesgo, confirmación, retry, verifier ni éxito.
- La evidencia recuperada de corpus es local, acotada y unilateral. El
  artefacto promocionado conserva procedencia/licencia, usa sólo train público
  para la sonda, mantiene dev/test fuera de runtime y no entrega históricos
  literales al LLM; nunca añade operaciones ni convierte frases en reglas.
- El candidato jerárquico de desarrollo no forma parte del runtime. Sus pesos
  no autorizan conversación, acción, familia ni operación; cualquier promoción
  futura exige un prerregistro nuevo y otro conjunto final todavía sellado.
- El grounding sólo recibe una proyección de IDs, estados, revisiones y hashes;
  no recibe texto libre de web, OCR o documentos.
- El banco offline de regresión del router (`data/intent_bank.jsonl`, 638
  anclas) se regenera con `tools/build_bank.py` desde
  `tools/router_bank_sources.py` y `tools/data/router_cases.jsonl`; no se carga
  en el worker productivo encoder-only y crece por telemetría→exemplars, nunca
  por retrain ni por listas de frases.
- Regresión: `scripts/test_mind_router_oracles.py` (675/675 contra oráculos),
  `scripts/measure_mind_budget.py` (gate 12), `scripts/test_mind_voice.py`
  (gate 7 headless).


## Adaptador opcional de prosa CPU

El perfil `cpu_prose_adapter` de `mind-runtime-v1.json` contiene `schema`
(`baxy-cpu-prose-adapter-v1`), `gguf`, `gguf_sha256` y `base_gguf_sha256`.
El registro verifica el adaptador y su correspondencia con el modelo base.
`register_mind_runtime.ps1 -CpuProseAdapter <archivo.gguf>` prepara ese perfil
con hashes calculados; omitirlo mantiene el runtime sin adaptador. Esta capacidad
no equivale a promover automáticamente un archivo ni a validar otros modelos.

El shell exporta el perfil verificado al sidecar. El owner `cpu_prose_adapter.py`
comprueba los bytes, verifica la carga en llama.cpp y establece/consulta escala
cero antes de publicar readiness. Cada petición ajena a la prosa CPU lleva escala
cero explícita. Sólo las observaciones completas de CPU en composición usan el
perfil cualificado; conversación, clasificación, progreso, confirmaciones,
observaciones mixtas y fallos conservan el modelo base. No se crean respuestas
fijas ni llamadas adicionales de composición. Los errores de identidad/carga del
adaptador detienen el arranque; no se ocultan desactivándolo silenciosamente.
