# Review arquitectónico — 3 bugs del agente voice local

Antes de entrar bug por bug: los tres síntomas comparten una raíz común. El sistema trata como **independientes** tres decisiones que en realidad son la misma pregunta vista desde tres ángulos: *"¿qué acción concreta sobre el mundo se requiere acá?"*. El planner la responde lexicalmente (Bug 1), el RAG la responde por similitud de texto crudo (Bug 2), y el evaluator la responde por un flag binario del planner (Bug 3). Ninguno chequea contra la realidad observable (`tool_events`). Los fixes que propongo abajo apuntan a introducir un único concepto de *acción canónica* (capability label) que atraviesa los tres componentes.

---

## Bug 1: Routing por intent semántico, no por mención de plataforma

### Diagnóstico arquitectónico

No es un problema de routing ni de tools: es un problema de **representación de intent**. El planner está mapeando *superficie léxica del usuario* → *nombre de tool*, pero la tool `media` no está descrita por verbos sino por un *outcome* ("consumir contenido audiovisual"). El gap entre "quiero ver daredevil born again" y el anchor "play music / reproducir canción" no es resoluble con MiniLM porque MiniLM compara forma, no función. Falta una capa de **normalización de intent a una taxonomía cerrada de capabilities** sobre la que sí se puede hacer matching estable. El catálogo de títulos es irrelevante; lo que hay que clasificar es la *categoría de acción*, que es finita y pequeña (~10-15 labels).

### Estrategias evaluadas

**A. Micro-LLM call de canonicalización con GBNF (intent rewriter).** Antes del routing, una llamada constrained a Gemma que devuelve `{action_type: enum, object_type: enum, modality: enum}` con grammar GBNF (output ~20 tokens). Sobre esa forma canónica, embeddings funcionan. Trade-offs: latency=+200-350ms (output corto + grammar acelera), complejidad=media (un componente más en la cadena), robustez=alta para inputs novedosos, mantenimiento=bajo (la taxonomía es estable). La descarto como primera opción porque agrega una segunda LLM call al hot path y rompe el budget de 4-5s en turnos con cola.

**B. Zero-shot capability classifier con NLI multilingüe (mDeBERTa-v3-base-xnli o similar, ~280MB).** El input del usuario se clasifica contra una lista chica de labels en español: "consumir contenido audiovisual", "controlar reproducción", "gestionar agenda", "leer mensajes", "navegar web", "consultar memoria personal", etc. El clasificador devuelve scores; cualquier label > umbral activa el bucket de tools asociado. Corre en CPU en 50-120ms por query (encoder, no decoder). Trade-offs: latency=+~80ms (paralelo al embedding actual, no secuencial), complejidad=baja (un modelo más, sin pipeline cambiado), robustez=alta — los labels son abstractos, no dependen del catálogo de títulos, "quiero ver daredevil born again" entaila "consumir contenido audiovisual" igual que "ponéme la última de Pedro Pascal". Mantenimiento=bajo (cambiás labels, no listas).

**C. Expandir el subset por defecto: incluir media+browser siempre que `needs_pc_action` esté en duda.** No-fix elegante: si el planner no está seguro, pasá al LLM más tools de las necesarias y dejá que el modelo decida con tool_choice. Trade-offs: latency=+~80-120ms por schemas extra en el prompt, complejidad=trivial, robustez=alta para falsos negativos / mediocre para falsos positivos (el modelo puede inventar tool calls). El problema real con esta opción en este stack: Gemma 3n/4 en 8B con tool calling vía prompt no tiene `tool_choice="auto"` reliable — si le metés 10 tools en el subset, a veces llama tools irrelevantes.

### Recomendación

**B + un fallback estilo C cuando el clasificador está bajo umbral.** Razón explícita: el NLI clasifica *función*, no *léxico*, que es exactamente la propiedad que falta. mDeBERTa-v3 multilingüe es el sweet spot de tamaño/calidad para esto (los benchmarks de Luna y MiniCheck muestran que encoders chicos finetuneados sobre NLI matchean a LLMs de 7B en tareas de entailment, a 1/30 del costo). Corre en paralelo al planner actual (no en serie), así que el costo amortizado real al hot path es ~30-50ms. La taxonomía de ~15 labels es lo único que mantenés, y se reusa para Bug 3.

Importante: el clasificador **no decide la tool específica**, decide la *categoría*. La selección final de `media` vs `browser` la sigue haciendo el embedding router actual, pero ya sobre un input enriquecido con `capability=consumir_audiovisual`, contra anchors de tool que también incluyen el capability tag. Así MiniLM sí matchea.

### Failure mode post-fix

Cuando el clasificador NLI esté indeciso entre dos capabilities (p. ej. "quiero ver mis fotos del finde" → ambiguo entre `consumir_audiovisual` y `consultar_memoria`), cae a la rama C (incluir ambos tool buckets). Resultado: el LLM ve `photos_tool` y `media_tool`, y normalmente elige bien la de fotos porque tiene "fotos" literal en el schema. Falla **honesta**: si elige mal, ejecuta una acción visible (abre Disney+ con query "fotos del finde"), el evaluator de Bug 3 lo detecta como mismatch entre intent declarado y reply, y rectifica. No hay mentira silenciosa.

---

## Bug 2: RAG inyecta replies de éxito que el LLM mimetiza

### Diagnóstico arquitectónico

El RAG está **conflacionando dos tipos de conocimiento** en un único campo de texto libre: (1) conocimiento procedural ("para esta clase de input, las tools que funcionaron son media+disney"), y (2) conocimiento estilístico ("así sonó el reply pasado"). Al inyectar el `summary` del turno pasado como prosa en pasado, le estás dando al LLM un *few-shot example* del reply, no una *política*. Modelos de 3-12B son particularmente susceptibles a esto: en ausencia de tools en su subset, completan por imitación del shot más similar. El bug no es el RAG, es la **falta de provenance separation** entre "qué pasó / qué tools / qué resultado" y "qué se dijo".

### Estrategias evaluadas

**A. Provenance-tagged RAG con prohibición de exponer el reply pasado.** El past turn se proyecta a campos estructurados que se inyectan como *policy hint*, no como prosa: `past_lesson[d=2h]: tools_used=[media] provider=disney_plus profile=null outcome=PASS_verified_visual_playback`; `past_lesson[d=5h]: tools_used=[media] provider=disney_plus outcome=PARTIAL reason=search_page_only_no_playback_confirmed`. El reply textual pasado **nunca** entra al prompt. El LLM recibe pattern matching para decidir qué tools/argumentos usar, no material para copy-paste. Trade-offs: latency=0 (misma retrieval, formato distinto), complejidad=baja (cambia el formatter del recall), robustez=alta, mantenimiento=bajo. La requiere migración del schema de `experience.sqlite` para indexar los campos estructurados (tools_used, provider, profile, outcome_code, failure_reason_code), pero ya tenés `tools_used` y `status`, sólo falta normalizar el resto.

**B. GBNF grammar que prohíba verbos en pasado en el reply cuando `tool_events==[]`.** Forzar gramaticalmente al reply a usar futuro/condicional si no hubo tool calls. Trade-offs: latency=mínima, complejidad=alta (gramática en español para conjugación de verbos es no trivial), robustez=frágil (la mentira puede expresarse en presente: "estoy abriendo Disney+"). La descarto: GBNF restringe forma, no contenido. La mentira es semántica, no léxica.

**C. Two-section prompt con etiquetas explícitas "DO NOT COPY".** Mantener el reply pasado pero rotularlo como `# REFERENCE_ONLY_DO_NOT_REPRODUCE`. Trade-offs: gratis, pero modelos 3-12B obedecen mal este tipo de meta-instrucción cuando el ejemplo está visualmente cerca y es semánticamente perfecto para el query actual. Es lo que ya hace implícitamente el sistema y no funcionó.

### Recomendación

**A — provenance-tagged RAG.** Razón explícita: ataca la causa (mezcla de tipos de conocimiento en un canal) en lugar del síntoma (el modelo copia). Es la única solución que respeta el principio de "no enterrar el RAG, exponerlo mejor". Latency cero. El caso 542 ("mismo input hace 2h, PASS") sigue siendo info de oro, pero ahora se expone como: `past_lesson: este input exacto fue resuelto con media→disney_plus, status=PASS hace 2h`. Esa línea le dice al planner+LLM *qué hacer*, no *qué decir*.

Pseudocódigo del recall reformulado:

```
def format_past_turn_for_prompt(turn):
    return (
        f"past[d={turn.age}]: "
        f"intent_class={turn.capability_label} "          # de Bug 1
        f"tools={turn.tools_used} "
        f"args_signature={turn.normalized_args} "         # ej. provider=disney_plus
        f"outcome={turn.status_code} "                     # PASS/PARTIAL/FAILED
        f"failure_reason={turn.failure_code or 'none'}"    # enum, no prosa
    )
# Importante: turn.reply_text NUNCA entra al prompt.
```

El campo `summary` actual se sigue persistiendo en sqlite para debugging humano, pero queda fuera del retrieval-to-prompt path.

### Failure mode post-fix

Cuando el past turn tiene `outcome=PARTIAL`, el LLM ve la lesson pero no tiene un script verbal para copiar. Puede entonces (a) llamar la tool y reintentar (caso deseado), o (b) generar un reply genérico tipo "voy a intentar abrirte Daredevil Born Again en Disney+", que es **honesto en intención**: declara futuro, no pasado. Si la tool falla downstream, Bug 3 lo cubre. Falla peligrosa improbable: el LLM podría inventar un provider distinto al sugerido en la lesson, pero el evaluator de Bug 3 detecta que `tool_events` no matchea con claims del reply.

---

## Bug 3: Evaluator declara PASS porque "no se esperaba tool action"

### Diagnóstico arquitectónico

El evaluator está usando `needs_pc_action` (una **predicción** del planner *antes* del LLM) como si fuera *ground truth* de lo que el LLM *debería haber* dicho. No hay ningún componente que cierre el loop entre **lo que el reply afirma** y **lo que efectivamente ocurrió** (tool_events). El false-confirmation guard existente cubre 5 prefijos exact-match; eso es un parche, no un check de grounding. La propiedad faltante es **claim-evidence consistency**: cada vez que el reply hace una aserción sobre el estado del mundo (acciones ejecutadas, hechos recuperados), tiene que ser entailed por la traza observable.

### Estrategias evaluadas

**A. Inline NLI grounding gate con mDeBERTa.** Usar el mismo encoder NLI del Bug 1 (modelo ya cargado en RAM, costo marginal cero), con un framing: premise = traza estructurada serializada ("Tools llamadas: ninguna. Acciones ejecutadas: ninguna."), hypothesis = reply del LLM. Si NLI devuelve `contradiction` con score > umbral, se reemplaza el reply por el fallback honesto generalizado ("Quise ayudarte pero no pude ejecutar nada esta vez. ¿Querés que lo intente con [tool sugerida por planner]?"). Trade-offs: latency=+50-150ms en el hot path (encoder corto sobre texto corto en CPU/iGPU), complejidad=media, robustez=alta para claims explícitas (abrí/busqué/encontré/agendé), aceptable para claims subtle. Mantenimiento=bajo.

**B. GBNF reply schema con tags `<acted>` vs `<spoke>`.** Forzar al LLM a emitir cada oración con un tag declarando si describe acción ejecutada o sólo habla. Evaluator chequea matching contra tool_events: cualquier `<acted action="X">` sin un `tool_event` correspondiente → block. Trade-offs: latency=mínima, complejidad=alta (toda la pipeline TTS tiene que strip los tags), robustez=máxima por construcción. La considero seriamente porque es la única solución que **hace imposible** la mentira por design, no por detección. La descarto como primera opción por el costo de migración: cambia el contrato de output del LLM, todos los prompts/few-shots/RAG lessons tienen que hablar el mismo dialecto.

**C. Async post-hoc reflection con Gemma + feed al lesson store.** Dejar pasar el reply al usuario, pero correr en background una segunda llamada (Gemma con grammar JSON: `{lied: bool, lie_type: enum, suggested_correction: str}`) que actualiza el outcome del turn en sqlite. Trade-offs: latency hot-path=0, complejidad=baja, robustez=mediocre para *este* turno (la mentira ya se dijo), pero excelente para *futuros* turnos similares vía RAG. La descarto como única solución porque el usuario ya escuchó la mentira. La uso como complemento.

### Recomendación

**A inline + C async, en ese orden de prioridad.** Razón explícita: A reusa un modelo que ya está cargado por Bug 1 (mDeBERTa) — el costo incremental de RAM es cero y el costo de latency es ~80ms amortizable. Ese es el único componente que evita que el usuario escuche la mentira en este turno. C corre desacoplado del hot path y alimenta el provenance store de Bug 2, cerrando el loop: una mentira detectada en background se vuelve un `past_lesson[outcome=FAILED reason=hallucinated_action]` que en futuros recalls le advierte al LLM "este patrón en el pasado mintió".

Justificación de latency: 80ms en CPU encoder es absorbible porque el TTS no arranca hasta tener el reply completo (no estás streaming a TTS, por la naturaleza del voice agent corto de 1-2 frases). Si quisieras ocultarlo más, podés correr NLI sobre los primeros 30 tokens generados en paralelo con el resto del decoding del LLM — para cuando el LLM termina, la verdict ya está. Esto es viable con llama-server porque exponé streaming endpoint.

Pseudocódigo del check:

```
PREMISE_TEMPLATE = (
    "Estado verificable del sistema durante este turno:\n"
    "- Tools ejecutadas: {tool_list_or_none}\n"
    "- Resultados confirmados: {tool_outcomes_or_none}\n"
    "- Páginas abiertas/modificadas: {browser_events_or_none}"
)

def grounding_check(reply_text, tool_events):
    premise = PREMISE_TEMPLATE.format(...)
    # mDeBERTa zero-shot entailment, multilingual
    result = nli(premise=premise, hypothesis=reply_text,
                 labels=["entailment", "neutral", "contradiction"])
    if result.contradiction > 0.55:  # calibrar offline
        return FAIL("reply claims actions not in tool_events")
    if result.neutral > 0.7 and contains_past_tense_action(reply_text):
        return SUSPICIOUS("vague action claim, no evidence")
    return PASS
```

Nota sobre `contains_past_tense_action`: explícitamente **no es** una lista de verbos. Es un POS tagger en español (spaCy es-core-news-sm, ~12MB, corre en <10ms) chequeando si hay verbo en pretérito perfecto/indefinido + sujeto en 1ra persona implícita. Esto sí es léxico, pero no es allowlist/denylist — es feature lingüístico genérico. Si Emmanuel prefiere evitar incluso esto, dejá sólo el threshold de NLI; pierde algo de recall en mentiras sutiles.

### Failure mode post-fix

Falsos positivos (reply legítimo bloqueado): cuando el LLM responde "te dejo en Disney+ Daredevil Born Again" *después* de haber ejecutado la tool correctamente, NLI puede dudar si el premise menciona la tool pero no el título. Mitigable enriqueciendo el premise con args de la tool call: "Tools ejecutadas: media.play(title='Daredevil Born Again', provider='disney_plus')". Falla **honesta**: si bloquea de más, el usuario escucha "no pude confirmar la acción, ¿está reproduciéndose?", que es molesto pero no engañoso.

Falsos negativos (mentira sutil pasa): claims tipo "ya está en marcha" sin verbo de acción explícito pueden pasar NLI como neutral. Aquí entra C: el job async la detecta con un prompt más rico y marca el turno como FAILED en el lesson store, así no se repite la próxima vez. El usuario escucha la mentira *una vez*, no recurrentemente.

---

## Orden de implementación y dependencias

Los tres fixes están acoplados pero **no** son del mismo orden de criticidad. Bug 3 es la única red de seguridad: sin él, mejoras en 1 y 2 reducen la *frecuencia* de mentiras pero no la *posibilidad*. Por eso el orden es **3 → 1 → 2**, contraintuitivo respecto al número.

**Paso 1 (semana 1): Bug 3, mDeBERTa grounding gate inline.** Es el único cambio que se puede deployar standalone y *baja la severidad de los otros dos bugs antes de tocarlos*. Una vez que tenés el gate, las mentiras existentes se interceptan; podés iterar Bug 1 y 2 con telemetría real de "cuántos turnos disparan el fallback honesto" como métrica de progreso. Además, descargás el modelo NLI que vas a reusar en Bug 1, así que esta inversión paga doble.

**Paso 2 (semana 2): Bug 1, NLI capability classifier + expansión condicional del subset.** Con el grounding gate ya activo, podés experimentar con la taxonomía de capabilities sin riesgo de regresiones silenciosas: si rompés routing, el gate lo captura como FAILED en vez de pasar como PASS. La mayoría de las features que el usuario percibe como "no funciona" se van a destrabar acá. Reutilizá el modelo NLI: una sola carga de mDeBERTa-v3-base-xnli sirve para clasificar capability (Bug 1) y para grounding entailment (Bug 3) con prompts distintos.

**Paso 3 (semana 3+): Bug 2, provenance separation en el lesson store.** Es el menos urgente porque, una vez que Bug 1 está bien (la tool media aparece en el subset), el LLM tiene la opción de ejecutar de verdad y el incentivo a copiar el reply pasado baja drásticamente — la mayoría de las veces va a llamar la tool. Bug 2 polishea el caso donde el RAG sigue tentando mimicry (turnos donde el embedding similarity es altísima pero la tool subset está vacía por otra razón). Requiere una migración de schema sqlite y la introducción de campos enum (failure_code, outcome_code) que se completan progresivamente — no es bloqueante.

**Lo que se puede paralelizar.** El finetune/calibración del umbral NLI para Bug 3 y la definición de la taxonomía de capabilities para Bug 1 son tareas independientes que pueden ir en paralelo. La migración sqlite de Bug 2 puede empezar como un job de backfill en background mientras 1 y 3 están en review. El único orden duro es: el grounding gate (3) tiene que estar antes de loosen el routing (1), porque relajar routing significa más tools en subset, lo que significa más superficie de error si el LLM se descontrola.

**Cuando los tres estén juntos**, la propiedad emergente es que el sistema tiene un *concepto de capability* compartido entre planner, RAG y evaluator. El mismo label "consumir_audiovisual" aparece en (a) la decisión del subset, (b) el indexado del past turn, (c) el premise del grounding check. Eso convierte tres heurísticas inconexas en un único pipeline tipo-checked. Y honestamente: si los tres bugs no se hubieran observado, la falta de ese concepto compartido seguiría siendo deuda técnica latente.

**Lo que sigue siendo limitación real, no resuelta.** Ninguno de los tres fixes resuelve el caso "el modelo no conoce el título Daredevil Born Again y le pregunta al usuario en qué plataforma está" cuando el RAG no tiene un past hit. Eso *no se puede resolver bien* sin (a) una tool de búsqueda de catálogo (TMDB/JustWatch API) que el agente pueda invocar, o (b) un cache de "títulos vistos recientemente → provider" alimentado por turnos pasados. La opción (a) es la correcta de mediano plazo; (b) es un parche. Pero ninguno de los dos cae dentro del scope de los 3 bugs reportados. Vale la pena mencionarlo para que no se confunda como un fix pendiente de estos tres — es un eje distinto.