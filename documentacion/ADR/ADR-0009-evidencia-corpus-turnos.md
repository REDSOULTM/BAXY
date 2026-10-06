# ADR-0009 — Evidencia recuperada del corpus para decidir turnos

- Estado: **aceptado; promoción one-sided sellada v2 vigente; candidato
  jerárquico de desarrollo rechazado sin promoción**.
- Fecha: 2026-07-25.
- Ámbito: decidir `conversation`, `clarify`, `action` o `plan` en el sidecar.
  No modifica la autoridad del core, `memory.*` ni la ejecución de providers.

## Decisión

El historial de 14.836 mensajes y 2.084 misiones no se compila como reglas de
frases. Tras los filtros y la deduplicación, el índice E5 contiene **25.156**
observaciones y separa tres usos:

1. **Evidencia histórica privada.** Las 7.372 filas históricas elegibles se
   conservan únicamente en el índice local y en los diagnósticos de recuperación
   por familia. Sus etiquetas son débiles o ruidosas: no entrenan la sonda y su
   texto nunca se envía al LLM.
2. **Entrenamiento público reproducible.** Las 17.784 filas públicas de train,
   procedentes de PRESTO y MASSIVE, entrenan una sonda lineal sobre embeddings
   E5. Los mapas sólo proyectan etiquetas ya publicadas a familias que existen
   en el catálogo; no crean capacidades.
3. **Evaluación pública disjunta.** Las 9.172 filas públicas de validation/test
   permanecen fuera del índice runtime. El gate comprobó cero solapamientos de
   texto normalizado con runtime. Validation calibra; test no interviene en la
   selección de umbrales.

La política promovida es deliberadamente unilateral: la sonda puede aportar
una señal de `conversation` o abstenerse. Un consenso kNN actúa como segundo
veto. Ninguna de las dos capas puede proponer `action`, `plan`, familia u
operación. No hay aprendizaje en vivo y una intención nueva jamás adquiere una
operación o permiso por ser frecuente.

El LLM continúa emitiendo el contrato JSON de cuatro ramas mediante
`turn.decide`, la única decisión semántica pública. Si devuelve `action`, el
shell solicita `arguments` bajo el schema de la operación ya cerrada, sin
reabrir la decisión; si devuelve `plan`, recién entonces solicita `plan`. El
shell valida operación, schema, riesgo, confirmación y resultado antes de
cualquier efecto. El catálogo público autenticado vigente contiene 168
operaciones; ni los mapas de corpus ni una similitud semántica pueden agregar
otra capacidad.

La extracción directa usa una inferencia JSON Schema sin diccionario de
frases. Los strings abiertos deben sobrevivir como subcadenas literales del
pedido; enum, booleanos y números se vuelven a groundear contra el texto y el
schema determinista. La evidencia escrita por el mismo modelo no se considera
autoridad ni se duplica en el envelope. Una salida bien formada pero no
verificable se transforma en abstención y reutiliza la pregunta natural
producida en esa misma inferencia; un fallo de formato/runtime permanece
técnico y fail-closed.

## Filtro de privacidad y calidad

`turn_evidence.py` acepta exclusivamente filas `canonical_source` de las
clases conversacionales/misiones públicas. Excluye:

- memoria privada y cualquier operación `memory.*`;
- `data_or_preferences` no vacío;
- filas marcadas `redacted`;
- duplicados no canónicos, clases de requisito/documentación y textos cuya
  misma forma tenga etiquetas incompatibles.

Esto separa el uso del corpus para aprendizaje/evaluación del permiso para
reinyectar texto en un prompt. La ruta activa no reinyecta ejemplos: el LLM
recibe únicamente un resumen estructurado de modos y puntuaciones cuando la
política unilateral acepta el turno.

El caché vectorial `baxy.turn-evidence.v4` se crea sólo en el equipo local, se
vincula al SHA-256 exacto del corpus y a la identidad/dimensión del encoder, y
se invalida ante cualquier cambio. El par atómico JSON/NPY conserva vectores y
metadatos estructurados con `contains_text:false`; no conserva frases fuente.
Una migración elimina pares v2/v3 que sí podían contener literales sólo después
de persistir, recargar y verificar el par v4. Un bundle instalado que no
contiene el corpus no activa esa evidencia por accidente.

## Implementación

`TurnEvidenceService` espera al encoder E5 y construye el índice en un hilo de
fondo después de `catalog.configure`; no bloquea el saludo ni el primer turno.
Cada consulta se codifica una sola vez. La política JSON se carga sin
`pickle`/`joblib`, verifica forma, finitud y SHA-256 de los pesos, y debe
coincidir con el corpus, el encoder y sus 384 dimensiones.

La sonda logística calibrada exige `P(conversation) >= 0,935316`. Después, los
7 vecinos diversos deben aportar al menos 5 votos conversacionales y acuerdo
ponderado >= 0,694286. Sólo si ambas condiciones se cumplen se entregan hasta
cuatro tarjetas `mode=conversation`, sin familias ni texto de ejemplo. El LLM
agrega esas tarjetas a conteos y rangos numéricos marcados como datos no
confiables. Si falla la política, el corpus, el encoder, el caché o cualquiera
de los dos clasificadores, se entrega una lista vacía y el sistema conserva la
puerta contextual sin degradar a reglas.

El exportador se invoca así, con una ruta privada explícita:

```powershell
experiments\mind_router_spike\.venv\Scripts\python.exe `
  scripts\build_turn_training_corpus.py `
  --output "$env:LOCALAPPDATA\BAXYRuntime\turn-training-v1.jsonl"
```

El manifest vecino registra SHA-256 de origen, filas excluidas, distribución
por modo, split y número de grupos. No se sube el resultado porque conserva
texto histórico elegible.

## Evidencia y estado del arte

- La separación jerárquica entre decisión, selección acotada y ejecución
  verificada coincide con trabajo reciente sobre routing y recuperación de
  tools; BAXY conserva además una rama explícita de abstención.
  <https://aclanthology.org/2024.findings-naacl.156/>
  <https://arxiv.org/abs/2403.06551>
- La aceptación selectiva se trata como control de riesgo, no como accuracy
  promedio: los umbrales se congelan antes del conjunto final y los límites
  unilaterales deciden promoción.
  <https://arxiv.org/abs/1705.08500>
  <https://arxiv.org/abs/2101.02703>
- Structured function calling mejora cuando el decode está guiado por schema,
  pero la validez sintáctica no prueba grounding semántico; por eso el core
  revalida cada argumento y una salida no verificable se abstiene.
  <https://aclanthology.org/2025.emnlp-main.1242/>
  <https://arxiv.org/abs/2501.10868>
- La recuperación aumenta la evidencia contextual sin fijar frases; el
  enrutamiento con incertidumbre y abstención es coherente con el trabajo de
  detección eficiente fuera de alcance en sistemas de diálogo.
  <https://arxiv.org/abs/2507.01541>
- Para intención abierta, los LLM zero-shot ayudan, pero los modelos ajustados
  al dominio siguen superando a los no ajustados en escenarios de descubrimiento
  y reconocimiento; por eso el dataset y el split por misión anteceden al
  fine-tuning. <https://aclanthology.org/2023.emnlp-main.636/>
- FunctionGemma está diseñado para ser ajustado en function calling y no para
  conversación directa. Es candidato a *student router* local, mientras Gemma
  E2B conserva conversación y planificación.
  <https://ai.google.dev/gemma/docs/functiongemma/model_card>
- La documentación de Google distingue la sintaxis de tool calling de entender
  cuándo usar cada tool, y recomienda ajustar el modelo con datos propios para
  resolver esa ambigüedad. <https://ai.google.dev/gemma/docs/functiongemma/finetuning-with-functiongemma>
- Ningún modelo ejecuta por sí solo: las llamadas se validan y ejecutan fuera
  del modelo. <https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4>

## Gate de promoción y rechazo honesto

La primera hipótesis, kNN puro con umbrales de abstención, se midió con el E5
real sobre todo el holdout. Fue rechazada y no publicó política:

- 0 de 256 perfiles fueron factibles en validation;
- el límite superior Wilson de falso accionable sobre conversación fue
  0,158574, por encima del máximo 0,01;
- el recall bruto de familia a k=5 fue 0,977732, por debajo del mínimo 0,98;
- en test, el mismo límite superior de falso accionable fue 0,149951.

El fallo queda preservado en
`artifacts/product/turn_evidence_encoder_gate.json`; no se reinterpretó como
éxito. La iteración autorizada sustituyó esa autoridad por una sonda logística
lineal `sklearn-1.9`, `lbfgs`, `C=1`, clases balanceadas, entrenada sólo sobre
las 17.784 filas públicas de train. Validation, con 3.460 filas, ajustó la
temperatura, el umbral conversacional, el consenso kNN y k=7 para el diagnóstico
de familia. El checkpoint congeló esos parámetros, los hashes de código, el
corpus y el encoder antes de puntuar el conjunto final.

La evaluación vigente se ejecutó **una sola vez** sobre 2.728 IDs del split
test seleccionados por el sello final v2. El sello no contiene textos ni
etiquetas (`contains_text_or_labels:false`), excluye la contaminación declarada
y su lista final de IDs tiene SHA-256
`fa087da33ffde997db39614cd03f98df60223642ce1d78899b49748aef2475a9`.
El comando final rechaza una segunda salida si el artefacto ya existe.

Resultado final, preservado en
`artifacts/product/turn_linear_probe_gate.json`:

- estado `passed`, política publicada y 9/9 comprobaciones satisfechas;
- precisión de la señal conversacional 0,994083; límite inferior Wilson
  0,973916;
- recall conversacional 0,42; límite inferior Wilson 0,380079;
- 0 señales accionables emitidas y 0/400 falsos accionables; límite superior
  Wilson 0,006718;
- recall bruto de familia a k=7 de 0,991838;
- diagnóstico selectivo de familia: precisión 0,962360 (límite inferior
  0,954641), recall 0,812715 (límite inferior 0,799054) y cobertura accionable
  0,828608 (límite inferior 0,815381).

La recuperación de familia sigue siendo **sólo diagnóstica** y nunca se envía
al LLM como acción. La política promovida
`baxy.turn-evidence-one-sided-policy.v1` conserva autoridad
`conversation_signal_or_abstain_only`; el catálogo, los schemas, el riesgo,
las confirmaciones y los verificadores continúan fuera del modelo.

## Candidato E5 jerárquico de desarrollo v2

Se evaluó una arquitectura jerárquica separada, sin autoridad de ejecución:
primero `no_effect` frente a `supported_effect`, luego conversación frente a
OOD, y finalmente shortlists de familia y operación. Se particionó por misión,
se calibró con el peor enunciado de cada misión y se prerregistraron umbrales
antes de una única corrida. Los históricos privados no entrenaron el candidato.

El gate
`artifacts/development/turn_policy_e5_selective_gate.json` terminó
`failed_no_runtime_promotion`. Hubo cero errores direccionales y coberturas de
familia/operación de 0,958261/0,940405, pero la selección de
`supported_effect` fue sólo **12/2.300 = 0,005217**, por debajo del mínimo
prerregistrado 0,02. Además, el prerregistro declaró erróneamente los guards
bajo `thresholds.selective_guards.*`, mientras el resultado los ubicó en
`selective_guards.*`. Esa ruta no se reparó después de observar el resultado.

Por ambos motivos no se publicó una política, no se habilitó fast path de
conversación ni señal supported y los pesos de desarrollo no pueden autorizar
acciones. El test oficial de MTOP permanece sellado a nivel de bytes —7.384
filas, `content_decoded:false`— y el holdout público final reservado tampoco
se abrió. El fallback vigente sigue siendo la decisión contextual del LLM con
la evidencia one-sided anterior únicamente como señal consultiva.

## Expansión pública v1

La promoción inicial se amplió a **25.156** observaciones runtime elegibles:
7.372 históricas ya filtradas y 17.784 de fuentes públicas. La meta de 20.000
no se alcanzó duplicando o generando frases: se superó solo con interacciones
humanas publicadas y etiquetadas para asistentes virtuales.

- **PRESTO v1** aporta 2.613 candidatos EN/ES de su partición train antes de la
  deduplicación cruzada. Solo se
  usan enunciados sin turno anterior, para que el texto aislado no dependa de
  contexto omitido. PRESTO contiene conversaciones multilingües reales, con
  disfluencias, revisiones y code-switching, y está bajo CC BY 4.0.
  <https://github.com/google-research-datasets/presto>
  <https://arxiv.org/abs/2303.08954>
- **MASSIVE v1.1** aporta ejemplos EN/ES de su partición train y conserva sus
  conjuntos dev/test como holdout. Para las localizaciones se exige al menos
  dos juicios de intención válidos y gramática >= 3; no se retienen workers,
  contactos, listas, notas ni anotaciones de slots. MASSIVE contiene más de
  un millón de utterances de asistentes en 52 lenguas y está bajo CC BY 4.0.
  <https://github.com/alexa/massive>
  <https://aclanthology.org/2023.acl-long.235/>

Los dos archivos `*_map.v1.json` son contratos declarativos de procedencia:
proyectan etiquetas *ya anotadas por la fuente* a familias del catálogo actual
de BAXY. No contienen frases ni se cargan en runtime. Antes de construir, el
script compara cada familia del mapa con `ProductCatalog.cs`; una familia que
no exista hace fallar la promoción. Las etiquetas de compra, taxi, llamadas,
IoT, reservas, redes sociales y otras capacidades ausentes se excluyen.

La receta reproducible usa los archivos oficiales ya descargados y conserva
SHA-256, licencias, filtros, conteos, duplicados y el split de origen en
`tests/data/turn_evidence_public_manifest.v1.json`:

```powershell
experiments\mind_router_spike\.venv\Scripts\python.exe `
  scripts\build_public_turn_evidence.py `
  --archive "$env:LOCALAPPDATA\BAXYRuntime\datasets\presto-v1\presto_v1.zip" `
  --massive-archive "$env:LOCALAPPDATA\BAXYRuntime\datasets\massive-v1.1\amazon-massive-dataset-1.1.tar.gz"
```

`turn_evidence_runtime.v1.jsonl` consume únicamente train público y evidencia
histórica ya filtrada. `turn_evidence_public_holdout.v1.jsonl` conserva 9.172
filas dev/test fuera de runtime; el gate real verificó cero solapamientos de
texto normalizado. Cada ejemplo sigue siendo evidencia no confiable: el modelo,
el catálogo cerrado, schemas, riesgo y confirmaciones conservan la autoridad.
