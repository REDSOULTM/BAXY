# Latencia end-to-end

Este documento ubica cada tramo de latencia del producto activo. No sustituye
los contratos, presupuestos ni gates físicos de las otras páginas de esta
guía. Una medición local describe el checkout, modelo y host usados; no
acredita por sí sola otra GPU, la instalación activa ni un efecto externo.

## Ruta completa de un turno

| Tramo | Owner | Trabajo principal | Regla de calidad o autoridad |
|---|---|---|---|
| Entrada visible | `Baxy.FieldUi` | Captura texto/voz y envía un mensaje nativo | No clasifica ni crea operaciones |
| Orquestación de UX | `Baxy.App` | Mantiene sesión, estado pendiente y procesos hijos | Valida el catálogo del Core antes de habilitar la mente |
| Decisión de turno | `baxy_mind` | Resuelve efectos explícitos o usa E5, política LLM y veto semántico | Sólo propone conversación, aclaración, acción o plan |
| Grounding de argumentos | `baxy_mind` + App | Extrae y normaliza argumentos cuando el schema tiene propiedades | Un schema vacío produce `{}`; un dato requerido conserva sus gates |
| Decisión ejecutable | `Baxy.Core` + `Baxy.Kernel` | Valida operación, schema, riesgo, confirmación, identidad, journal y replay | El catálogo cerrado y el kernel conservan la autoridad |
| Efecto o lectura | `Baxy.Providers.Windows` | Usa Windows o aplicaciones y realiza postlectura | Un efecto incierto no se convierte en éxito |
| Formulación final | `baxy_mind` + App | Narra el resultado tipado o compone un mensaje humano | Toda respuesta visible sigue formulada por el LLM |
| Entrega | App + FieldUi | Publica el mensaje completo y, mientras tanto, una indicación honesta de progreso | El protocolo no transmite tokens; la indicación nunca anticipa éxito |

Una acción real puede estar dominada por el provider: abrir una aplicación,
esperar una ventana, consultar Outlook o agotar un timeout de Bluetooth no es
latencia del modelo. Por eso se deben informar por separado:

1. tiempo hasta la decisión de la mente;
2. tiempo del Core/provider;
3. tiempo de formulación;
4. tiempo hasta el primer contenido visible y hasta la entrega completa.

## Ruta interna de `turn.decide`

El camino general es:

```text
texto e historial
  -> resolución explícita y aclaraciones cerradas
  -> shortlist E5 cuando hace falta
  -> [slot 1] P: clasificación contextual del LLM
     [slot 2] G: veto semántico independiente
     [slot 3] L: idioma independiente
     si G confirma forma de efecto y P sigue decodificando:
       -> V: verificación independiente del conteo en el slot liberado
     si P=acción y G/V son válidos:
       -> C: compatibilidad, estrictamente después de V y sólo si corresponde
     si G=(sin efecto, zero), no hay historial, L terminó y P no lo descarta:
       -> K: respuesta de conocimiento especulativa
  -> validaciones y grounding
  -> generación conversacional, acción, aclaración o plan
```

En GPU, P/G/L se lanzan juntas, pero no forman una barrera global. Una acción
puede empezar V en el slot que libera G mientras P termina y encadenar C sin
esperar a L; plan y aclaración tampoco esperan el idioma especulativo. Si el
resultado no consume esa V, su solicitud se cancela sin convertirla en barrera
de retorno. El scheduler conserva como máximo tres POST activos y C nunca
adelanta a V. Si P contradice K, la solicitud HTTP especulativa se cancela y no
se publica ni se entrega como handoff. En CPU se mantiene un solo slot y la
ejecución secuencial para no multiplicar la contención.

## Optimizaciones seguras vigentes

- El perfil GPU usa tres slots con 4.096 tokens de contexto cada uno,
  continuous batching, Flash Attention y KV Q8. El perfil CPU conserva un
  slot.
- La clasificación primaria conserva su prompt, JSON Schema y nombres de
  campos. El veto conserva el mismo conjunto cerrado de valores, pero serializa
  el objeto exacto con GBNF compacto; el idioma conserva el enum `es/en/mixed`
  en otro GBNF compacto. Esos dos wires pasaron gates de modelo propios: no son
  sólo cambios de scheduling.
- El encoder E5 memoiza por igualdad exacta sólo durante la solicitud. La
  expansión de familias, el ranking del catálogo, la evidencia y el veto de
  relevancia reciben el mismo vector y los mismos scores, pero el texto no
  vuelve a cruzar el proceso del encoder. En el tramo repetido medido pasó de
  tres cruces y 80–89 ms totales a uno y unos 27,5 ms.
- El ranking E5 selecciona primero el top-k y restaura después el orden estable
  histórico de los empates. Conserva los mismos vecinos aun cuando el banco
  contenga `NaN` o infinitos, casos en que vuelve al ordenamiento completo.
- El veto semántico idéntico se reutiliza durante la solicitud completa,
  incluidos sus reintentos lógicos. La detección de idioma válida se ejecuta
  una vez por solicitud y su resultado se reutiliza al formular una
  conversación o al reintentar P. Una inferencia cancelada nunca publica
  caché. L sigue siendo independiente del router, catálogo e historial.
- El runtime que posee el proceso del modelo conserva además cuatro LRU
  separadas de 32 entradas para resultados **válidos** de G, L, V y C. Las
  claves son exactas; C incluye texto, operación, descripción y schema
  canónico. No se memoizan inválidos, historia, shortlist, decisiones P,
  respuestas ni autoridad. Un miss sobre una caché vacía no toma lock y todo
  se borra al retirar o reemplazar `llama-server`. Un endpoint externo no
  habilita esta reutilización porque el runtime no puede atestar su lifecycle.
- Saludos, agradecimientos, despedidas, preguntas de cortesía por el estado,
  no-entendimiento y efectos literales ya cerrados no ejecutan E5 ni evidencia
  semántica que después se descartaría. Los patrones conversacionales cerrados
  también conservan su idioma ES/EN sin repetir el detector LLM. El acto social
  se consume con `re.fullmatch` sobre dos vocabularios cerrados, uno por
  idioma: en cuanto aparece otra cláusula el turno vuelve al modelo. El idioma
  sale de la rama que coincidió, no del contador de tokens, que devuelve `es`
  para `hi`. La envoltura social tampoco esconde una petición: un saludo
  inicial desplaza la cabeza del pedido igual que el vocativo, y una cláusula
  que es únicamente un saludo o una despedida no cuenta como petición
  pendiente.
- Cuando el veto independiente termina primero con `no_effect/zero`, no hay
  historial y el detector ya fijó el idioma, el mismo `chat` de conocimiento
  se prepara en un slot liberado mientras la política primaria termina. El
  resultado se entrega sólo si la decisión validada pide exactamente ese mismo
  chat; cualquier discrepancia cancela el socket y lo descarta.
- Cuando G termina primero y confirma una forma de efecto, V reutiliza ese
  mismo slot mientras P continúa. Tres réplicas, incluido el orden A/B inverso,
  conservaron salidas exactas y mejoraron el p50 de acción en 138, 49 y 26 ms.
  En 9 acciones el ahorro agregado fue 0,765 s, unos 85 ms por acción; no se
  añadió un cuarto decode concurrente.
- El transporte local conserva hasta tres conexiones HTTP/1.1 exclusivas,
  una por POST concurrente, con reutilización LIFO en el mismo hilo y límites
  por edad e inactividad inferiores a los del servidor b9980. Un fallo de
  conexión reabre una sola vez dentro del mismo presupuesto monotónico.
- App no solicita extracción de argumentos para un schema cerrado sin
  propiedades. Los schemas con propiedades opcionales o requeridas conservan
  la extracción y el grounding.
- Volumen, ajuste de volumen, mute, tareas y recordatorios pueden reutilizar el
  extractor literal conservador que ya usaban los planes. El objeto aún debe
  quedar completo después del mismo schema autenticado y del mismo grounding;
  ante ambigüedad se conserva la extracción LLM.
- Cuando el gate de grounding ya extrajo argumentos durante `turn.decide`, el
  resultado exacto se entrega una sola vez a la solicitud `arguments`
  inmediatamente posterior. No se vuelve a decodificar ni se relajan la
  evidencia literal, el schema o la normalización.

Ninguno de estos caminos omite schema, riesgo, confirmación, journal,
postlectura o replay de una operación que llegue al Core.

## Optimizaciones investigadas y rechazadas

No todo lo más rápido se promovió:

- abreviar todos los campos del JSON redujo la clasificación sintética, pero
  en un smoke estratificado cambió 47 resultados frente a `final39`, perdió
  21 familias de operación antes aceptadas y añadió un falso efecto;
- fusionar veto semántico e idioma en un solo enum recuperó tiempo adicional,
  pero alteró decisiones del corpus;
- retirar el detector de idioma y confiar en el campo de la política o en el
  prompt conversacional respondió en español ante entradas inglesas del A/B;
- un cuarto slot para anticipar también el conteo independiente aumentó el
  tramo caliente de decisión de 2,24–2,31 s a 2,93–3,09 s por contención;
- schemas `oneOf` por modo sesgaron Gemma hacia la primera rama;
- speculative decoding por n-gramas y KV FP16 no mejoraron la media de forma
  consistente;
- compactar a la vez la política primaria y el guard bajó el p50, pero cambió
  20 de 108 estados; sólo el guard exacto se promovió;
- MTP global o selectivo aceleró sondas directas, pero perdió operaciones
  correctas o dejó de acelerar el turno completo bajo contención de GPU;
- anticipar la extracción de argumentos al cierre de P/G aumentó la contención
  de los validadores y la cola posterior a V;
- fijar P/G/L a `id_slot` concretos no fue estable en tres réplicas; el
  scheduler automático de `llama.cpp` permanece activo;
- `--cache-reuse 64` redujo levemente un p95 aislado, pero empeoró el workload
  físico: p50 de turno 4,144→5,363 s, máximo 14,236→16,007 s y argumentos
  0,885→1,004 s;
- solapar catálogo y journal durante el arranque NativeAOT empeoró la mediana
  pareada y se revirtió; esperar además el task de polling de App alteraba la
  semántica de `Ready` por una expectativa de sólo unos 25 ms;
- reducir el silencio final de voz de 700 a 500 ms sin compensación cambió
  transcripciones y rutas. El 5/6 del gate fresco también aparece con el
  baseline de 700 ms por drift corrector/router, por lo que no se atribuye
  causalmente al endpoint. Un candidato de 500 ms con 192 ms de padding sólo
  para ASR fue exacto en 24/24 sondas sintéticas y 4/4 replays humanos
  redacted, pero no se promueve sin un corpus held-out de pausas y ruido real.

Estas variantes no forman parte del runtime activo.

## Medición física de esta campaña

El workload seguro del sidecar ejerció 30 decisiones, 10 extracciones y 5
narraciones con el catálogo de 168 operaciones. Comparado inmediatamente con
el perfil anterior de dos slots, el perfil de tres slots produjo:

| Métrica | Dos slots | Tres slots |
|---|---:|---:|
| `turn.decide` p50 | 4,206 s | 4,144 s |
| `turn.decide` p95 | 14,517 s | 13,134 s |
| `turn.decide` máximo | 15,046 s | 14,236 s |
| `arguments` p50 | 0,957 s | 0,885 s |
| `narrate` p50 | 0,244 s | 0,190 s |
| catálogo de mente listo | 5,405 s | 4,717 s |
| pico de VRAM total observado | 2.093 MiB | 2.109 MiB |

Las 45 solicitudes terminaron sin error. Es una comparación consecutiva en el
mismo host, no una promesa determinista para cualquier mensaje: la longitud de
salida y los reanálisis dominan la cola larga.

Un perfil adicional del propio `llama-server` sobre una pregunta de
conocimiento caliente separó 2,24–2,31 s de decisión y 1,27–1,29 s de
respuesta. La política produjo 88–92 tokens estructurados y permaneció como
camino crítico; el veto y el idioma terminaron antes. Reducir campos, tokens o
salida global sí cambia el contrato/calidad y por eso no se presenta como una
optimización neutral.

Dos mediciones adicionales separan costes que antes se atribuían al LLM:

- una extracción directa real tardó 0,7553 s y su handoff exacto 0,0006 s;
- `message.compose` tuvo p50 de 0,154 s y p95/máximo de 0,358 s;
- Core caliente tuvo medianas de 0,032–0,194 s para lecturas comunes;
  `gpu_usage` conservó 1,058 s porque PDH necesita dos muestras separadas por
  un segundo para calcular una tasa;
- el hello frío del Core tardó 1,889 s e incluyó el catálogo verificado de 290
  aplicaciones. Ese trabajo ocurre durante el arranque, en paralelo con la
  preparación de la mente, y no se repite por turno.

La campaña incremental del 29 de julio añadió tres mediciones:

- turnos explícitos de `system.time` quedaron en 0,0008 s de mediana caliente;
  un agradecimiento español bajó de 0,627 a 0,175 s y uno inglés midió
  0,123 s, conservando respuesta LLM;
- extracción end-to-end de `audio.volume` y `audio.mute` quedó en 0,0002 s de
  mediana caliente al demostrar el literal completo; un caso no cubierto por
  el extractor conservó cerca de 0,9 s y el LLM;
- el A/B consecutivo de una pregunta de conocimiento produjo 4,154 s de
  mediana sin preparar la respuesta y 3,758 s con preparación solapada,
  aproximadamente 9,5 % menos, con 5/5 respuestas válidas en ambos perfiles.

La investigación posterior aisló un defecto adicional en la detección de
idioma. El schema permitía espacios iniciales y el techo de 16 tokens podía
terminar antes de la llave final: una entrada inglesa produjo cuatro
inferencias con `finish_reason=length`, dos vacías y dos con JSON incompleto.
Subir solamente el techo reducía reintentos, pero hacía consumibles algunas
clasificaciones incorrectas, por lo que esa variante se rechazó. La solución
activa conserva exactamente el enum `es/en/mixed`, pero usa GBNF compacto y
cinco ejemplos balanceados:

- el A/B sobre los 30 probes conversacionales versionados pasó de 25/30, un
  error técnico y p50 0,409 s a 30/30, cero errores y p50 0,125 s;
- la salida física bajó de 17–32 tokens, con posibles truncamientos, a seis
  tokens y `finish_reason=stop`;
- cinco turnos ingleses end-to-end dieron p50 2,754 s y máximo 4,454 s. La
  corrida inmediatamente anterior con sólo el techo ampliado dio p50 3,875 s,
  y el perfil original llegó a 7,309 s cuando repitió cuatro detecciones.

También se agotaron las perillas de planificación del servidor sin promover
ninguna por intuición. En el mismo workload de cinco preguntas, el autoajuste
de hilos dio p50 3,618 s; fijar 1/4/8/16 hilos dio
4,935/4,319/4,323/4,487 s. Batch 512 empató dentro del ruido con el default
2048, 1024 fue algo peor y 4096 subió a 5,694 s. Polling 100 redujo apenas el
p50 de una corrida, pero elevó el máximo a 8,134 s; prioridad media llegó a
9,478 s. Threads, batch, polling y prioridad permanecen por defecto.

Una repetición posterior del workload completo terminó 45/45 sin errores, pero
dio `turn.decide` p50 4,696 s, p95 14,782 s y máximo 19,524 s. Al ser peor que
ambos perfiles consecutivos anteriores, se conserva como evidencia de ruido y
cola larga del host; no reemplaza la comparación de dos/tres slots ni se
presenta como mejora global.

## Cierre incremental del 29 de julio de 2026

Este cierre separa deliberadamente implementación, microbenchmark y E2E. Los
totales de bucles sintéticos no son segundos añadidos a un turno, y una prueba
determinista de scheduling no acredita por sí sola menor latencia física.

### Implementación vigente

- El scheduler reactivo conserva P/G/L concurrentes y encadena V→C para una
  acción tan pronto como existen sus dependencias; L deja de ser barrera para
  acción, plan y aclaración. Hay como máximo tres inferencias activas.
- La respuesta K sólo se especula bajo el predicado cerrado descrito arriba.
  Una divergencia cancela la lectura HTTP real. En una simulación determinista,
  un chat inútil de 2,202 s dejó de bloquear el retorno y la decisión terminó
  en menos de un segundo; esto no es un A/B E2E del modelo.
- Los planes explícitos ya cerrados omiten E5. Cuando sí se necesita evidencia,
  el encoder usa caché exacta por solicitud y el ranking top-k conserva
  exactamente orden y empates históricos.
- El cliente de `llama-server` reutiliza un pool acotado de tres conexiones. El
  servidor b9980 corta keep-alive a los 5 s o 100 solicitudes; BAXY usa 4 s y
  90 respectivamente para no intentar reutilizar una conexión vencida.
- App y Core leen/escriben JSONL directamente como UTF-8 y eliminan buffers o
  serializaciones intermedias en las rutas caracterizadas. El framing, límites,
  flush, durabilidad y envelopes públicos no cambian.
- El host JSONL compartido consume por defecto `stderr` desde que nace el
  sidecar con un único buffer de 8 KiB, contabiliza bytes y descarta su
  contenido limpiando la memoria. El pump comparte cancelación y reap del Job
  Object; evita que diagnóstico abundante llene el pipe antes del `hello`, sin
  incorporar trazas al protocolo ni a la interfaz. Core desactiva este drain
  genérico porque ya posee su propio reader y ring diagnóstico acotado; nunca
  hay dos lectores sobre el mismo pipe. El gate focal pasó 6/6, incluido un
  child process que escribió 2 MiB en `stderr` antes del `hello` y una lectura
  defectuosa simulada que acreditó que los dos waits de reap permanecen
  acotados.
- Los providers de calculadora, aplicaciones, media, navegador, Wi-Fi y Steam
  observan inmediatamente y sólo esperan si la postcondición aún no convergió.
  Las rutas con estado previo ambiguo conservan una espera o exigen identidad
  de documento/entrada y una transición posterior al dispatch. `system.status`
  conserva una ventana CPU limpia de 150 ms: el solapamiento experimental se
  revirtió porque el trabajo de los demás probes podía contaminar esa medida.

El intento de solapar catálogo y journal en el arranque de Core **no** forma
parte de la implementación vigente. Veinte pares NativeAOT de proceso frío,
con `hello` y catálogo exactos y 20/20 verificados, dieron p50
3.274,385→3.308,206 ms, una regresión de 33,820 ms; la mediana pareada empeoró
80,837 ms y sólo 8/20 pares mejoraron. Se revirtió.

### Microbenchmarks, no latencia E2E

| Tramo medido | Antes | Vigente | Alcance |
|---|---:|---:|---|
| E5, segmento repetido de una solicitud | 80–89 ms / 3 cruces | 27,5 ms / 1 cruce | Caché exacta; conserva duplicados y orden |
| Ranking estable de candidatos | 21,335 ms | 0,904 ms | 14.769 candidatos, 60 rondas |
| Ranking global | 43,891 ms | 0,643 ms | Banco real 25.156×384; `exact_order=true` |
| POST loopback HTTP | 1,149 ms | 0,528 ms | Pool: −54,1 %, ahorro absoluto 0,621 ms |
| App, writer 20.000×~4 KiB | 135,316 ms / 162,7 MiB | 7,031 ms / 16,9 KiB | Total del bucle |
| App, scanner 100.000×~4 KiB | 63,111 ms / 14,604 MiB | 34,952 ms / 6,402 MiB | Total del bucle |
| Core, reader JSONL | 33,57 ms / 60,61 MiB | 18,18 ms / 8,67 MiB | Total del benchmark |
| Core, writer por pipe | 1.024,30 ms / 40.000 writes | 457,47 ms / 20.000 writes | Mismo framing y flush |
| Kernel, `RequestFingerprint`, 50.000 | 844,11 ms / 498.275.600 B | 365,05 ms / 424.000.040 B | −56,8 % tiempo; −14,9 % asignación |

En el ranking, el producto punto tuvo p50 3,327 ms y el ahorro combinado de
las dos selecciones fue 63,680 ms. Las 25.156 filas son observaciones del
índice de recuperación, no 25.156 decisiones inferidas por el LLM.

Otros bucles de App bajaron `PreparedOperation` 696,37→315,46 ms,
`DurablePlanStore` 119,43→107,80 ms, el bridge de mente UTF-16→UTF-8
137,47→126,53 ms y el sondeo `HasExited` 218,14→121,45 ms. Son totales de alta
iteración. El experimento de `system.status` 150,9986→150,6894 ms fue una
diferencia submilisegundo y no forma parte del runtime: se priorizó la
semántica limpia de la muestra CPU. `gpu_usage` sigue alrededor de 1,058 s
porque su contador de tasa necesita dos muestras.

El fingerprint optimizado conserva exactamente los golden hashes y la
independencia del orden JSON; el benchmark vive junto a esas regresiones en
[`RequestFingerprintTests.cs`](../../../tests/Baxy.Kernel.Tests/RequestFingerprintTests.cs).

### Gates del modelo y del turno

El único wire semántico adicional promovido fue el guard cerrado:

| Gate 3×20 | JSON legible | GBNF compacto exacto |
|---|---:|---:|
| p50 | 6,992 s | 6,5155 s |
| fallos duros | 21 | 11 |
| falsos efectos | 2 | 0 |
| probes aprobados | 20 | 27 |
| operaciones aprobadas | 7 | 13 |

Compactar simultáneamente política primaria y guard bajó p50
5,860→4,625 s sobre 108 casos, pero cambió 20 estados. Por eso la política
`baxy_turn_decision` sigue en JSON Schema. La variante canónica en una línea
también provocó abortos de plan.

Se agotó además MTP/speculative decoding sobre la revisión exacta b9980:

- en 20 turnos, target-only dio p50 6,750 s, p95 17,078 s, 6 fallos duros y 9
  aprobados; MTP global dio 5,734 s, 13,547 s, 5 y 8 respectivamente, pero
  cambió 4 estados y perdió una acción CPU correcta;
- con `pmin=0.9`, 17/20 fueron más rápidos, pero se perdió un `web.search`;
  `pmin=0.99` todavía perdió esa operación y produjo abortos de plan;
- un servidor temporal de la misma revisión permitió aislar sólo el guard:
  20 pares directos bajaron p50 583,809→569,738 ms, con salida exacta y
  mediana pareada −19,285 ms;
- en el E2E final del mismo fingerprint, target-only dio p50 6,9845 s y MTP
  selectivo 7,0395 s. Sólo 4/20 fueron más rápidos y la mediana pareada empeoró
  0,242 s bajo la contención real del asistente.

El binario temporal nunca se instaló, los manifests no cambiaron y su
integración se retiró. MTP, Medusa y EAGLE requieren otro runtime o cabezas
entrenadas y nuevos activos; no son un refactor neutral.

La preextracción especulativa de argumentos también se rechazó. Al iniciarla
al cierre de P/G, ese tramo empeoró p50 5,253→5,712 s y p95
6,161→6,483 s. Medida desde V, la cola candidata empeoró 0,364 s en la mediana
pareada y 1,031 s en p95; sólo 3/7 pares ganaron, la compatibilidad C aumentó
40,5 % y la extracción E 53,9 %.

El pinning de slots se agotó con el
[`benchmark_llama_slot_pinning.py`](../../../experiments/mind_router_spike/benchmark_llama_slot_pinning.py)
y la cadena de artefactos
[A/B](../../../artifacts/fixes/llama_slot_pinning_ab_20260729.json),
[orden inverso](../../../artifacts/fixes/llama_slot_pinning_ab_reverse_20260729.json),
[tercera réplica](../../../artifacts/fixes/llama_slot_pinning_promoted_smoke_20260729.json)
y [veredicto](../../../artifacts/fixes/llama_slot_pinning_verdict_20260729.json).
La tercera réplica empeoró p50 90,9 ms y el total 1,289 s. En 18 pares
agregados sólo ganó 9/18; la mediana fue −10,7 ms, pero el peor caso añadió
0,956 s. No existe `id_slot` en las solicitudes productivas.

También se midió la caché de checkpoints incorporada en b9980. Frente a los
defaults de 32 checkpoints y separación mínima de 256 tokens, la variante
64/64 conservó salidas y modos exactos, pero cambió de dirección al invertir
el orden de los brazos. Ganó 7/12 pares, con extremos de −0,788 a +0,669 s.
Además, las medianas `cache_n` y `prompt_n` fueron idénticas en
P/G/L/V/C/E/chat: no reutilizó un solo token adicional en este workload. Se
rechazó sin cambiar producción; quedan el
[`benchmark`](../../../experiments/mind_router_spike/benchmark_llama_checkpoint_spacing.py)
y el
[`veredicto`](../../../artifacts/fixes/llama_checkpoint_spacing_verdict_20260729.json).

### Agotamiento de los últimos candidatos, 2026-07-29

La campaña continuó después del cierre anterior y volvió a exigir igualdad
semántica, órdenes A/B opuestos y servidor fresco por brazo:

- El solape G→V sí se promovió. En tres réplicas y 18 turnos, todas las salidas
  fueron exactas, V empezó y terminó antes de P en las nueve acciones y el p50
  de acción mejoró en las tres corridas. El ahorro agregado fue 0,765 s, unos
  85 ms por acción. El
  [veredicto](../../../artifacts/fixes/guard_count_overlap_verdict_20260729.json)
  acredita que el máximo siguió siendo tres inferencias concurrentes.
- V y C conservan el JSON Schema genérico. La compactación reducía el p50 de V
  aproximadamente 29,8 % y el de C 22,5 %, pero C perdió de forma estable
  `memory.forget` y `game.launch` en ambos órdenes. Al ampliar V a 72 casos,
  bajó su p50 34,8 %, pero convirtió cinco resultados antes correctos en
  incorrectos, incluidos conocimiento técnico y misiones compuestas. Se
  rechazó y se retiró del runtime; quedan el
  [gate de corpus](../../../artifacts/fixes/compact_validator_corpus_verdict_20260729.json)
  y la
  [ampliación](../../../artifacts/fixes/compact_v_expanded_corpus_ab_20260729.json).
- Pedir a P JSON minificado ahorraba 39–43 % de tokens y unos 0,29–0,30 s de
  p50 E2E, pero cambió 7/11 y 5/11 semánticas primarias en órdenes opuestos,
  alteró tres decisiones finales por réplica y perdió un modo esperado en
  ambas. La política conserva su prompt y schema; véase el
  [veredicto](../../../artifacts/fixes/primary_minified_prompt_verdict_20260729.json).
- Forzar `top_k=1` sólo en los validadores a temperatura cero tampoco es una
  equivalencia de greedy en este modelo. En un orden cambió P y dos V de
  `zero` a `multiple`, convirtió dos acciones en planes y omitió C/E. En el
  orden exacto inverso, el p50 E2E empeoró 48,9 ms. Producción no recibió ese
  sampler; véase el
  [veredicto](../../../artifacts/fixes/llama_structured_top_k1_verdict_20260729.json).
- `--kv-unified` conservó modos, decisiones y argumentos, pero cambió dos
  respuestas libres y empeoró p50 5,595→7,663 s, 37,0 %, y el total 39,9 %.
  Se mantuvieron buffers KV separados; véase el
  [veredicto](../../../artifacts/fixes/llama_kv_unified_verdict_20260729.json).
- La release oficial b10182 se descargó y verificó sólo en una carpeta
  temporal. Tres réplicas exactas frente a b9980 cambiaron de dirección:
  −3,72 %, +3,54 % y +6,14 % en p50. Sólo una de tres mejoró; no se instaló ni
  se cambió el manifest. Véase el
  [veredicto](../../../artifacts/fixes/llama_b9980_b10182_verdict_20260729.json).
- `GGML_CUDA_GRAPH_OPT=1`, opción experimental del backend CUDA, aceleró V y
  chat aislados, pero empeoró el p50 E2E en ambos órdenes. En 12 casos por
  perfil, p50 subió 1,25 % y el trabajo total 0,70 %; P/G/L fueron 3,62/4,30/
  5,37 % más lentos. No se añadió al entorno; véase el
  [veredicto](../../../artifacts/fixes/llama_cuda_graph_opt_verdict_20260729.json).
- Cuantizar K y V de Q8 a Q4 no conservó calidad ni produjo una ganancia
  repetible. En un orden pareció bajar el p50 E2E 245,9 ms, pero cambió tokens,
  contenido y decisiones; al invertirlo volvió a cambiar la salida y empeoró
  p50 526,3 ms, total E2E 3,443 s y trabajo estructurado 5,049 s. KV permanece
  en Q8; véase el
  [veredicto](../../../artifacts/fixes/llama_kv_q4_verdict_20260729.json).
- Forzar `CUDA_MODULE_LOADING=EAGER` conservó tokens, salidas y decisiones,
  pero empeoró el arranque frío en ambos órdenes. Frente a `LAZY`,
  startup→primera respuesta aumentó 1,701/0,308 s y
  startup→workload 2,416/0,468 s. El valor predeterminado `LAZY` permanece;
  véase el
  [veredicto](../../../artifacts/fixes/cuda_module_loading_verdict_20260729.json).
- `ngram-mod` se agotó con cuatro servidores frescos por perfil y órdenes
  opuestos. Los defaults 24/48/64 propusieron 613 tokens y aceptaron 123
  (20,1 %) por brazo, sólo en P; mejoraron el p50 E2E, pero cambiaron tokens de
  G y añadieron 2,104/1,971 s al trabajo estructurado. El único ajuste
  conservador para modelo denso, 24/4/16, aceptó 203/319 tokens (63,6 %) y
  redujo p50 264,0/259,1 ms, pero cambió contenido visible y tokens de P y
  todavía añadió 0,343/1,003 s al trabajo estructurado. No se hizo un barrido
  posterior ni se activó speculative decoding; véase el
  [veredicto conjunto](../../../artifacts/fixes/llama_ngram_mod_verdict_20260729.json).
- El cierre MTP sobre el binario temporal b10182 tampoco habilita una perilla
  neutral. El control `--spec-type none` cargó y completó el workload, pero
  `draft-mtp --spec-draft-n-max 1` terminó antes de `ready`: b10182 informó que
  el GGUF registrado no contiene capas MTP y no pudo crear el contexto draft.
  Por tanto no existe un par de latencia válido. Incorporar el assistant GGUF
  que documenta Google sería un activo nuevo, con hashes, memoria, packaging y
  certificación de calidad propios; no se descargó ni instaló. Véase el
  [veredicto](../../../artifacts/fixes/llama_b10182_mtp_verdict_20260729.json).
- El priming concurrente de los prefijos token-exactos P/G/L sí hizo más
  rápido el turno una vez pagado el priming: las medianas pareadas mejoraron
  0,367 y 0,266 s en órdenes opuestos. Sin embargo, preparar los tres slots
  costó unos 0,77–0,88 s. Al incluirlo, `ready`→respuesta empeoró 0,438 y
  0,539 s y el total frío desde startup empeoró 0,437 y 0,461 s. Los 12 pares
  conservaron salida, payload y total de tokens exactos; `cache_n` pasó de
  0/0/0 a 562/149/209 en P/G/L, de modo que la reutilización existió pero sólo
  trasladó más latencia al warmup. Quedan el
  [harness](../../../experiments/mind_router_spike/benchmark_first_turn_prefix_priming.py),
  el [A/B](../../../artifacts/fixes/first_turn_prefix_priming_ab_20260729.json)
  y su
  [orden inverso](../../../artifacts/fixes/first_turn_prefix_priming_ab_reverse_20260729.json).
- Persistir esos prefijos mediante `/slots/{id}?action=save|restore` tampoco
  habilitó un arranque más rápido. b9980 informó
  `n_restored=562/154/214` y leyó 5.192.260/1.512.700/2.101.900 bytes para
  P/G/L, pero el primer turno reutilizó `cache_n=0/0/0` tanto con selección
  automática como fijando P/G/L a los mismos slots 0/1/2. Incluso el probe
  fijado terminó frío 2,6 ms peor; cualquier diferencia caliente no procede
  de la caché porque los prompts se reprocesaron completos. Se rechazó el
  mecanismo, se borraron sus archivos temporales y no cambió producción,
  instalación ni manifest. Evidencia:
  [harness](../../../experiments/mind_router_spike/benchmark_first_turn_prefix_restore.py),
  [selección automática](../../../artifacts/fixes/first_turn_prefix_restore_mechanism_probe_20260729.json),
  [slots fijados](../../../artifacts/fixes/first_turn_prefix_restore_pinned_probe_20260729.json)
  y
  [veredicto conjunto](../../../artifacts/fixes/first_turn_prefix_cache_verdict_20260729.json).

Los providers también agotaron esperas artificiales sin abreviar sus
postcondiciones:

- `SpotifyDesktopAutomation.ps1` observa la ventana, el resultado y la
  postlectura antes de dormir, protege la identidad de la consulta y conserva
  los horizontes terminales. Sus gates son simulados; no se abrió Spotify.
- `SpotifyMediaControl.ps1` sustituye los mínimos fijos de 1.200, 200 y 400 ms
  por observación inmediata y polling de 50/25/100 ms dentro de los mismos
  límites. En el caso cálido puede evitar hasta 1,8 s de espera fija.
- La postlectura de Spotify Web API puede ahorrar 500 ms y SMTC hasta 350 ms;
  los casos idempotentes o ambiguos siguen esperando el horizonte original.
- Abrir carpeta y seleccionar todo observan antes del primer intervalo. Abrir
  archivo conserva los 350 ms de estabilidad de éxito, pero `WaitForExit`
  devuelve antes ante un fallo terminal. El único backoff de escritorio de
  400 ms sin un predicado barato observable se mantuvo.
- La mensajería de escritorio observa de inmediato únicamente donde ya existe
  la misma postcondición terminal: identidad del destinatario y borrador
  visible. Si el primer probe no basta, conserva los horizontes anteriores de
  900 y 350 ms; el ahorro máximo de espera fija es 1,25 s. La entrega conserva
  sus 900 ms: captura cambiada, texto visible y destino estable no distinguen
  de forma inequívoca una burbuja entregada de un draft que sigue visible
  durante una animación. Los waits de foco, apertura de buscador y limpieza del
  compositor también permanecen porque no tienen una postcondición equivalente
  barata.
- Tesseract drena `stdout` y `stderr` en paralelo antes de esperar la salida.
  Esto no promete un ahorro fijo: elimina el tail no acotado por saturación del
  pipe que podía impedir que una observación OCR terminara.
- No molestar consulta primero el toggle UIA exacto y sólo entonces cae en el
  calendario anterior de 900 ms más 20 intervalos de 250 ms. Después de
  `Toggle()` hace una postlectura inmediata y conserva el probe de 400 ms si
  todavía no converge. El caso ya materializado puede ahorrar hasta 1,3 s sin
  acortar el horizonte terminal.
- Los dos inventarios de periféricos pasan `kind` al script y omiten
  `Get-Printer`, WIA, USB o HID cuando la categoría no fue solicitada. `all`
  conserva las cinco fuentes y la misma forma de salida. El ahorro físico
  depende de drivers y dispositivos, por lo que no se publica una cifra sin
  una campaña aislada del hardware.
- No se añadió un sub-timeout a la lectura IPC de mpv. La llamada ya obedece la
  cancelación externa y no existe un deadline interno previo que permita
  demostrar equivalencia; cualquier número nuevo podría convertir una
  reproducción válida pero lenta en fallo.

Estas cifras de providers son ahorros máximos de waits eliminados y pruebas de
contrato, no una medición física de Spotify. Ninguna acción externa se ejecutó.
El cierre focal pasó 95/95 pruebas C# de `DesktopMessagingAdapterTests` y
`ExternalAdaptersTests`, además de 13/13 pruebas Python de scripts de
interacción y media.

### Presupuesto físico final

El artefacto
[`mind_budget_gate.json`](../../../artifacts/product/mind_budget_gate.json)
ejerció por perfil 30 decisiones, 10 extracciones y 5 narraciones, 45
solicitudes en total, con catálogo de 168 operaciones y cero errores:

| Métrica | GPU, 99 layers | CPU, 0 layers |
|---|---:|---:|
| solicitudes | 45/45 | 45/45 |
| `turn.decide` p50 / p95 / máximo | 4,728 / 17,716 / 18,035 s | 19,512 / 19,534 / 19,539 s |
| `arguments` p50 | 1,173 s | 10,725 s |
| `narrate` p50 | 0,248 s | 2,497 s |
| pico VRAM del árbol de procesos | 1.549,6 MiB | 109,5 MiB |
| pico RAM del árbol de procesos | 3.295,6 MiB | 4.152,2 MiB |

El catálogo quedó listo en 5,150 s GPU y 5,644 s CPU. Frente al gate anterior,
el p50 GPU bajó 5,362→4,728 s (−11,8 %), argumentos 1,248→1,173 s y narración
0,257→0,248 s. La cola no mejoró: el p95 actual es 17,716 s, frente a 10,598 s
en el corte anterior y 15,801 s en una réplica independiente. Se conserva como
límite medido y motivó un diagnóstico GPU por caso; no se infiere una mejora de
cola a partir del p50. Ambos perfiles cerraron `passed`, 90/90 solicitudes y
cero errores.

### Cola de reintentos, 2026-07-30

El diagnóstico por caso aisló los extremos `turn-06` y `turn-23`: P agotaba
sus tokens internos de pensamiento y devolvía contenido vacío con
`finish_reason=length`. El segundo intento repetía G y L ya validados y podía
iniciar otra V especulativa aunque esa V no tuviera consumidor.

La capa request-local conserva G/L válidos durante la misma solicitud y
desactiva el solapamiento G→V en un reintento lógico. No cambian prompts,
schemas, shortlist, sampler ni modelo. Una L especulativa se publica sólo
después de superar su cancelación; `begin_request` y `end_request` siguen
borrando esa capa. La LRU exacta entre solicitudes, promovida después, es otra
frontera: acepta sólo resultados validados y se invalida con el proceso del
modelo.

Dos órdenes A/B del candidato redujeron p95 1,4635/1,8253 s y máximo
0,3994/1,4003 s sin diferencias de proyección semántica. La medición posterior
del código de producto sobre 30 turnos fue:

| Métrica | baseline emparejada | producto | delta |
|---|---:|---:|---:|
| p50 | 4,7751 s | 4,8929 s | +0,1178 s |
| p95 | 17,3578 s | 15,8986 s | −1,4592 s |
| máximo | 17,7454 s | 17,1046 s | −0,6408 s |
| total de 30 turnos | 170,3081 s | 169,3441 s | −0,9640 s |

Hubo 30/30 respuestas válidas, cero diferencias de decisión y cero efectos
ejecutados. El p50 no se presenta como mejora: el cambio sólo actúa cuando P
entra en retry. Evidencia:
[producto](../../../artifacts/fixes/gpu_turn_tail_retry_reuse_product_20260730.json),
[baseline emparejada](../../../artifacts/fixes/gpu_turn_tail_retry_reuse_pair_baseline_after_20260730.json)
y
[órdenes A/B](../../../artifacts/fixes/gpu_turn_tail_retry_reuse_guard_language_full_20260730.json).

Se rechazaron tres atajos que reducían tiempo pero no conservaban el producto:

- GBNF directo sólo en el retry eliminó los reintentos completos y redujo la
  cola, pero cambió decisiones, respuestas o efectos;
- ampliar P/V de 160/24 a 256/64 tokens fue inestable entre órdenes, llegó a
  añadir un retry y aumentó el total en una réplica;
- b10182 con presupuestos de pensamiento 32/4 y 64/8 conservó los mismos dos
  retries; b8738 se verificó por SHA-256, pero no puede cargar el layout E2B
  actual y se descartó sin tocar la instalación.

Los corpus privados presentes conservaron sus identidades promovidas: 14.845
filas de oráculo, 14.845 de alcance lingüístico y 25.156 de evidencia. Sus
pruebas cerraron 38 + 163 subtests; las 292 pruebas focales de planner/política
cerraron con 37 subtests. La suite completa aprobó 1.383 + 382 subtests y dejó
un fallo ajeno ya existente: el test del launcher espera la antigua llamada
síncrona, mientras App usa el descubrimiento asíncrono vigente. No se presenta
esa ejecución completa como verde.

### Calidad y cierre de pruebas

El preflight físico paralelo de 16 casos por brazo devolvió `status=failed` por
su criterio absoluto. En la comparación pareada, evidence frente a baseline
conservó deltas cero en modo, macro-F1 y familia, no añadió acciones inseguras
y obtuvo una ganancia sin pérdidas; su p50 fue 5,4302 s. La réplica serial de
un slot también devolvió `status=failed`, reprodujo métricas y acciones
inseguras, obtuvo cero ganancias y cero pérdidas y dio p50 5,5807 s. Por tanto,
la concurrencia no explica esa pérdida absoluta, pero ninguno de los dos
artefactos es un gate verde:

- [preflight paralelo](../../../artifacts/fixes/turn_policy_gate_latency_final_preflight_20260729.json);
- [preflight serial](../../../artifacts/fixes/turn_policy_gate_serial_preflight_20260729.json).

El cierre Full del checkout aprobó **1.381 pruebas Python + 382 subtests**. En
.NET aprobó **2.232** con **18 omisiones ambientales**: Contracts 51; Kernel
97/2; Providers 429/5; Setup 464/8; Integration 1.191/3, donde cada par expresa
aprobadas/omitidas. Las compuertas de fuente Fast y Full quedaron verdes y el
build Release terminó con cero advertencias y cero errores. Esto acredita el
checkout y sus pruebas; no convierte el preflight físico en aprobado ni
sustituye `final39` como baseline exhaustiva del corpus.

El preflight físico final completó 32/32 llamadas sin errores. Evidencia ganó
un caso crítico, perdió cero y no añadió acciones inseguras ni violaciones de
autoridad, pero sumó 0,2305 s de media en esta muestra. El estado absoluto
quedó `failed` porque ambos brazos conservaron un falso positivo inseguro y
baja exactitud; no se presenta como certificación integral:
[reporte](../../../artifacts/fixes/turn_policy_gate_final_scheduler_preflight_20260729.json).

## Fuentes externas contrastadas

- La documentación de
  [`llama-server` b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md)
  define continuous batching, slots paralelos, prompt cache, `cache-reuse`,
  Flash Attention, KV cuantizado, GBNF y speculative decoding. BAXY midió cada
  opción relevante en su propio hardware en vez de asumir que aumenta la
  velocidad.
- La guía oficial de
  [speculative decoding de b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/docs/speculative.md)
  documenta que `ngram-mod` comparte un pool entre slots, ocupa unos 16 MiB y
  permite reducir `min/max` en modelos densos. Eso motivó el único perfil
  24/4/16; su mayor aceptación no superó el gate de salida exacta.
- La documentación oficial de
  [MTP para Gemma 4](https://ai.google.dev/gemma/docs/mtp/mtp)
  carga por separado el target y su modelo `-assistant`. La promesa de calidad
  se refiere a ese par de checkpoints; no implica que el GGUF target de BAXY
  contenga las capas draft. El probe b10182 verificó precisamente esa frontera
  y no justificó cambiar los activos atestados.
- NVIDIA documenta que
  [CUDA lazy loading](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/lazy-loading.html)
  aplaza la carga de módulos y que EAGER puede desplazar ese coste al
  arranque. BAXY midió el balance completo startup→respuesta y conservó LAZY
  porque EAGER aumentó el total frío en los dos órdenes.
- Las releases oficiales
  [b9980](https://github.com/ggml-org/llama.cpp/releases/tag/b9980) y
  [b10182](https://github.com/ggml-org/llama.cpp/releases/tag/b10182)
  identifican los commits y binarios CUDA 12 comparados. Que b10182 fuera la
  última revisión no sustituyó el A/B sobre el modelo y la GPU de BAXY.
- La documentación actual de
  [`llama-server`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
  define `--reasoning off` y el presupuesto de pensamiento. La discusión
  oficial
  [#21445](https://github.com/ggml-org/llama.cpp/discussions/21445)
  documenta `thinking_budget_tokens` por solicitud; BAXY lo midió en b10182.
  Los reportes Gemma 4
  [#21321](https://github.com/ggml-org/llama.cpp/issues/21321) y
  [#21338](https://github.com/ggml-org/llama.cpp/discussions/21338)
  explican por qué `reasoning off`, presupuesto cero y
  `enable_thinking=false` todavía pueden dejar drenaje de tokens en algunas
  combinaciones de modelo/build.
- La implementación opt-in de
  [`GGML_CUDA_GRAPH_OPT`](https://github.com/ggml-org/llama.cpp/pull/16991)
  publica ganancias dependientes del modelo y hardware. En esta RTX portátil,
  la mejora de V no compensó la regresión del camino P/G/L concurrente.
- La caché de prompts en RAM de b9980 proviene de
  [la implementación oficial #16391](https://github.com/ggml-org/llama.cpp/pull/16391);
  [#24190](https://github.com/ggml-org/llama.cpp/pull/24190) extendió la
  exportación de slots ociosos al modo multi-slot sin KV unificado. BAXY ya
  recibió esa ruta por defecto y rechazó checkpoints más densos porque no
  aumentaron `cache_n` ni `prompt_n` en sus prompts reales.
- La documentación de b9980 define
  [`--slot-save-path` y los endpoints save/restore](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md#post-slotsid_slotactionsave-save-the-prompt-cache-of-the-specified-slot-to-a-file).
  Los propios mantenedores aclaran que
  [restore repone KV pero no la representación textual del prompt](https://github.com/ggml-org/llama.cpp/discussions/9781).
  Por eso BAXY no aceptó `n_restored` como prueba: exigió `cache_n` en el POST
  real posterior, que quedó en cero aun con `id_slot` explícito.
- Los límites de keep-alive usados para el pool están fijados en el
  [`cpp-httplib` de b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/vendor/cpp-httplib/httplib.h#L23-L33);
  Python documenta la reutilización de la misma conexión después de consumir
  la respuesta en
  [`http.client`](https://docs.python.org/3/library/http.client.html).
- [XGrammar](https://arxiv.org/abs/2411.15100) respalda que una gramática
  compilada puede reducir el overhead de salida estructurada. BAXY no extrapoló
  esa ganancia: sólo promovió los dos enums cerrados que pasaron su A/B.
- Los mantenedores distinguen
  [batch lógico y ubatch físico](https://github.com/ggml-org/llama.cpp/discussions/6328);
  esa diferencia explica por qué no se promovió un valor por resultados de
  otro backend o GPU.
- [SGLang](https://arxiv.org/abs/2312.07104) respalda reutilización de prefijos y
  FSM comprimidas para salida estructurada; la implementación activa conserva
  llama.cpp porque cambiar de runtime/modelo exige una nueva certificación.
- El estudio
  [Decoding Speculative Decoding](https://arxiv.org/abs/2402.01528) demuestra
  que la ganancia depende fuertemente de la latencia del draft. BAXY no posee
  hoy un draft atestado que justifique memoria y activos adicionales.
- Una revisión sistemática reciente de
  [speculative decoding](https://arxiv.org/abs/2601.11580) separa el límite
  teórico de la ganancia real cuando verificación y runtime dominan. Los A/B de
  BAXY confirmaron que acelerar un decode aislado no garantizaba acelerar E2E.
- El algoritmo exacto de
  [Leviathan et al.](https://proceedings.mlr.press/v202/leviathan23a.html)
  conserva la distribución cuando existe un draft adecuado. Métodos actuales
  como [Medusa](https://arxiv.org/abs/2401.10774) y
  [EAGLE-3](https://arxiv.org/abs/2503.01840) necesitan cabezas o entrenamiento
  propios; sin esos activos atestados no son una perilla gratuita para Gemma.
- [Sarathi-Serve](https://arxiv.org/abs/2403.02310) muestra que mezclar prefill
  y decode crea un compromiso entre throughput y latencia. Eso concuerda con el
  cuarto slot y el MTP peores bajo contención, pero el veredicto procede del A/B
  local, no de extrapolar hardware de datacenter.
- [`numpy.partition`](https://numpy.org/doc/stable/reference/generated/numpy.partition.html)
  usa selección parcial pero no promete estabilidad; BAXY restaura de forma
  explícita el orden histórico de empates antes de aceptar el top-k.
- Microsoft recomienda procesar UTF-8 directamente con
  [`Utf8JsonReader`](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/use-utf8jsonreader)
  para el mejor rendimiento. Los microbenchmarks locales, no esa recomendación
  por sí sola, justifican los hot paths promovidos.
- El reporte de
  [multilingual E5](https://arxiv.org/abs/2402.05672) documenta el compromiso
  calidad/eficiencia de sus tamaños; por eso BAXY conserva E5 y elimina sólo
  recomputaciones exactas o consultas cuyo resultado no puede consumirse.
- Microsoft recomienda para
  [WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/performance)
  reutilizar el entorno/control, reducir IPC y medir contenido real. FieldUi
  ya usa una vista persistente y el pipe nativo no contiene un sleep de entrega.
- Microsoft documenta
  [eventos de UI Automation](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-eventsforclients)
  y
  [`WaitForInputIdle`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-waitforinputidle).
  Como no todos los providers exponen una señal fiable para cada cambio, BAXY
  usa observación inmediata con polling acotado y conserva el fallback
  terminal en vez de asumir que un evento siempre llegará.
- Microsoft documenta que un contador de tasa
  [PDH necesita dos valores](https://learn.microsoft.com/en-us/windows/win32/api/pdh/ns-pdh-pdh_raw_counter);
  ese segundo no se retiró porque cambiaría el significado de `gpu_usage`.
- sherpa-onnx recomienda 512 muestras y 500 ms en su ejemplo de
  [Silero VAD](https://k2-fsa.github.io/sherpa/onnx/c-api/html/vad.html), pero el
  perfil crudo de 500 ms no conservó la salida del baseline. El perfil
  500 ms + padding ASR conservó las muestras pequeñas, pero todavía carece de
  evidencia held-out con pausas naturales y ruido; BAXY retiene 700 ms.
- Como evidencia anecdótica, usuarios de Gemma/llama.cpp reportan que el tercer
  trabajo concurrente puede degradar mucho el rendimiento y que batch/ubatch
  debe ajustarse al hardware en la
  [discusión comunitaria #21112](https://github.com/ggml-org/llama.cpp/discussions/21112).
  El resultado local coincide: cuatro slots y ubatch manual fueron peores.
- Una discusión reciente con el
  [mismo Ryzen 7 5800H y una RTX portátil](https://github.com/ggml-org/llama.cpp/discussions/23147)
  muestra además que slots y presión de VRAM pueden hacer al servidor más lento.
  BAXY conservó tres slots porque los tres verificadores realmente se solapan,
  pero rechazó un cuarto después de medir la contención.

## Reapertura del límite E2B del 30 de julio de 2026

La objeción a una cola de 17 s reabrió la campaña aun después de promover la
reutilización de G/L en retries. La nueva descomposición separó el modelo E2B
del protocolo de turno:

- el chat exacto de BAXY, sin P/G/L/V, midió p50 **2,395 s** bajo el estado
  térmico vigente; el prompt crudo equivalente quedó en **3,908 s** porque tres
  de cuatro respuestas agotaron 128 tokens;
- P siguió siendo el camino crítico: el A/B instrumentado anterior registró
  p50 **4,111 s**, 84 tokens predichos de mediana y hasta **9,923 s** por POST;
  G, L, V y chat quedaron respectivamente en 1,628, 0,982, 1,728 y 0,604 s de
  mediana;
- `nvidia-smi` acreditó `SW Thermal Slowdown=Active`, P3 y reloj SM de
  **900 MHz** frente a **2100 MHz** máximos. No se cambió energía, reloj ni
  configuración del equipo. Este estado explica variación entre réplicas, pero
  no la brecha de aproximadamente cuatro veces entre chat E2B y turno completo.

Se agotaron variantes adicionales sin promoverlas:

- quitar descripciones candidatas, dar exclusividad GPU a P y retirar los
  campos redundantes `effect_count`/`response_language` empeoró la mediana o
  cambió acciones;
- `assistant prefill` conservó exactamente tres respuestas y redujo en una
  sonda p50 10,092→8,560 s y máximo 19,501→10,491 s, pero cambió el cuarto caso
  y en la corrida completa convirtió `audio.volume` en conversación;
- el GBNF directo totalmente compacto alcanzó p50 **2,340 s** y máximo
  **2,847 s**, demostrando que el rango E2B es físicamente alcanzable, pero
  4/4 objetos fueron inválidos y terminaron en clarificación;
- permitir espacio, salto sin sangría o sangría 0/2/4 recuperó sólo 1/4
  objetos. Gemma E2B necesita el rango de whitespace aprendido del schema
  generado; estrecharlo no es una optimización neutral.

La evidencia queda en
`raw_e2b_latency_20260730.json`,
`gpu_thermal_state_20260730.json`,
`gpu_turn_current_baseline_smoke_20260730.json`,
`gpu_turn_primary_minimal_prefill_four_20260730.json` y
`gpu_turn_primary_direct_compact_four_20260730.json`, todos bajo
`artifacts/fixes`. El resultado no autoriza afirmar que 8–17 s sea aceptable:
demuestra que, con el checkpoint y contrato actuales, acercarse a 2,4 s exige
un contrato compacto que todavía no conserva validez/calidad, o un nuevo
activo de draft/modelo con recertificación.

### Agotamiento final y reutilización exacta validada

La campaña continuó sobre el mismo manifest canónico y sin iniciar Core ni
ejecutar efectos. Se cerraron las alternativas que todavía podían parecer
neutrales:

- reducir P de 160 a 112 tokens conservó inicialmente las 30 proyecciones,
  pero el orden inverso cambió `turn-03` de conversación a plan, añadió retries
  en `turn-04` y `turn-06`, elevó p95 12,5219→19,5051 s y el total
  227,9156→252,5193 s. Se rechazó;
- el audit E5 completo evaluó 11.527 filas objetivo y unió 781 señales con
  baseline. La compuerta física de las 77 señales cuyo efecto esperado era una
  operación encontró a G respondiendo `no_effect/zero` para una acción
  canónica, reproducido dos veces. E5+G no puede cancelar P ni otorgar
  conversación;
- gramática P dinámica, `ngram` simple/map-k, MTP externo, gating o stagger de
  L, flags/control/corte de razonamiento, streaming P y retry especulativo se
  rechazaron por salida distinta, contrato inválido, mayor cola o ausencia del
  activo draft atestado. Sus seams SSE/control/gating se retiraron del runtime
  productivo y del transporte.

La única promoción nueva fue reutilizar inferencias cerradas y deterministas
G/L/V/C para una clave exactamente idéntica mientras vive el mismo proceso del
modelo. Los dos A/B principales, con servidores frescos y orden inverso,
conservaron decisión, proyección de efectos, respuesta semántica y texto
visible exactos; el p50 caliente bajó **3,2854 s** y **1,2851 s**, y el trabajo
caliente total **14,8237 s** y **9,7457 s**. La ampliación a conversación,
plan, aclaración y acción redujo el total **4,6039 s** y **5,9048 s**. Una
divergencia fría de `turn-18`, ocurrida antes de que existiera una entrada
reutilizable, motivó un miss sin lock; el caso aislado volvió a pasar exacto en
ambos órdenes y redujo el total caliente 3,2724/5,4245 s.

La promoción quedó respaldada por 241 pruebas focales, `Fast` verde y `Full`
verde: 1.388 pruebas Python + 382 subtests y 2.237 pruebas .NET, con 18
omisiones ambientales. Evidencia:

- [veredicto de reutilización](../../../artifacts/fixes/validated_inference_reuse_verdict_20260730.json);
- [audit E5 completo](../../../artifacts/fixes/turn_evidence_fastpath_full_audit_20260730.json) y
  [falso negativo físico de G](../../../artifacts/fixes/turn_evidence_guard_fastpath_operation_gate_20260730.json);
- [P=112 base inversa](../../../artifacts/fixes/gpu_turn_primary_max112_order2_baseline_20260730.json) y
  [P=112 candidato inverso](../../../artifacts/fixes/gpu_turn_primary_max112_order2_candidate_20260730.json).

Después de esta promoción, un turno nuevo y no repetido continúa dominado por
P. Acercarlo al chat E2B puro exige cambiar el contrato P/whitespace, incorporar
un draft/modelo compatible o modificar el estado físico de energía y
refrigeración. Las tres opciones cambian activo, autoridad de certificación o
hardware y quedan fuera de una optimización interna segura del checkout.

## Verificación independiente y funnel de modelos, segunda pasada del 30 de julio de 2026

Una revisión independiente reprodujo la baseline sin tocar producción:

- el workload congelado de 30 turnos terminó 30/30 válido, con cero efectos y
  un solo retry (`turn-23`): p50 **4,113 s**, p95 **7,348 s**, máximo
  **14,075 s**. Es claramente mejor que la corrida registrada la madrugada del
  mismo día (p50 4,893 / p95 15,899 s) porque la GPU no estaba bajo slowdown
  térmico sostenido durante la medición; en reposo conservaba P3 y 900 MHz.
  Esto confirma que las comparaciones sólo valen emparejadas en la misma
  sesión térmica;
- el probe chat aislado dio BAXY p50 **1,439 s** frente a 2,327 s del prompt
  crudo con techo de 128 tokens: el overhead de BAXY sobre el modelo aislado
  en chat caliente sigue siendo no separable de cero bajo estas condiciones;
- evidencia: `raw_e2b_latency_repro_20260730.json` y
  `gpu_turn_tail_product_repro_20260730.json` bajo `artifacts/fixes`.

El funnel documental de modelos con corte 2026-07-30 quedó en
`artifacts/fixes/model_research_funnel_20260730.json`:

- ~~el asistente MTP oficial `google/gemma-4-E2B-it-assistant` (~78M) es el
  único candidato con upside grande, pero su carga está rota en llama.cpp desde
  b9702 por la regresión abierta
  [#24795](https://github.com/ggml-org/llama.cpp/issues/24795); el runtime
  canónico b9980 está dentro del rango afectado y el único build que funciona,
  b9553, es anterior al certificado~~. **RETRACTADO el 2026-07-31**: el b9980
  certificado sí carga el drafter y sirve con él. La conclusión sobre MTP ya no
  depende de #24795 y pasó a ser un rechazo físico; ver «MTP de Gemma 4: rechazo
  físico sobre el runtime certificado» más abajo y
  `artifacts/fixes/model_research_funnel_20260731.json`;
- Qwen3.5-4B y la serie pequeña Qwen3.5 se descartan en fase 1: su
  arquitectura híbrida Gated DeltaNet no tiene soporte en el llama.cpp
  oficial, sólo en un fork comunitario;
- Ministral-3-3B-Instruct-2512 (Apache 2.0, GGUF oficial) queda en shortlist
  sin justificación de valor esperado: ~3B densos activos superan el cómputo
  activo de E2B y no hay evidencia primaria de ventaja en latencia ni en
  español; perseguirlo exigiría autorización de descarga y recertificación
  completa;
- Phi-5-Mini no está publicado; Phi-4-mini es anterior a la ventana y mayor;
  Gemma 4 26B A4B excede la VRAM del equipo canónico.

Ninguna promoción nueva salió de esta pasada. El criterio de cierre del
registro de mantenibilidad se mantiene: el cuello es P para texto nuevo y las
tres salidas (contrato compacto, draft/modelo, energía/refrigeración) siguen
requiriendo decisiones fuera del alcance interno seguro.

## Fase correctiva del 30 de julio de 2026

La revisión fue objetada por metodología de overhead no equivalente, retry sin
descomponer y escenarios sin medir. La fase correctiva cerró cada punto con
medición física; el reloj SM permaneció clavado en 900 MHz durante toda la
sesión, por lo que las comparaciones internas comparten estado térmico.

### Overhead con cargas byte-idénticas

`benchmark_equivalent_overhead.py` captura el wire payload exacto que produce
`LlmRuntime.chat` y lo reenvía por el mismo transporte sin el camino BAXY:
mismos mensajes, sampler, seed, budget y estado de slots, ABBA por ronda, 32
pares. Cero discrepancias de payload. Delta pareada BAXY−directo: p50
**−6,0 ms**, IC95 bootstrap [−72,6, +71,3] ms, sign test bilateral p=1,0;
TTFT proxy (derivado de timings del servidor; el protocolo no transmite
tokens) p50 −2,3 ms, IC95 [−82,6, +83,3] ms. El overhead de BAXY sobre el
modelo aislado **no es estadísticamente separable de cero**; la resolución de
la medición (±80 ms) la fija el nondeterminismo simétrico del servidor (2
salidas distintas por caso dentro de cada brazo con greedy). El overhead
Python+HTTP por llamada es 6,6 ms frente a 6,4 ms del POST desnudo. Evidencia:
`equivalent_overhead_ab_20260730.json`.

### Causa raíz de la cola de retry

`probe_turn_retry_decomposition.py` traza cada inferencia dentro del sidecar
real. La cola de 14–19,5 s de `turn-23` son cuatro intentos seriales de P que
drenan 160 tokens con `finish_reason=length` y contenido vacío o truncado
(5,9 + 4,0 + 4,2 + 2,6 s) más 2,5 s de la clarificación; la reutilización
promovida de G/L en retry funciona (no se repiten). El experimento decisivo
aisló la causa: **la composición del prompt de P depende de si el índice
asíncrono de evidencia terminó de construirse**. Con el índice frío,
`candidate_families` devuelve `()` y la shortlist léxica (5.805 chars, sha
`10700527…`) produce P válido en 4,7 s; con el índice asentado, la shortlist
preferida por evidencia (5.347 chars, sha `e18ff2be…`) hace drenar a Gemma de
forma determinista (issue clase llama.cpp #21321/#21338). Frecuencia sobre 30
corridas completas: turn-23 30/30 (siempre `clarify`), turn-06 27/30,
turn-04 15/30. El mismo texto produce `conversation` o `clarify` según el
momento: hallazgo de producto registrado en mantenibilidad. Correcciones
agotadas: presupuesto 320 sólo en el intento final se rechazó físicamente hoy
(el deadline de 19 s lo trunca tras dos drenajes); omitir el intento 0b es
indemostrable como equivalente (greedy no es numéricamente determinista entre
slots); menos intentos pierde recuperaciones demostradas. Evidencia:
`turn_retry_root_cause_verdict_20260730.json` y sus artefactos enlazados.

### Escenarios arquitectónicos completados

`architecture_scenarios_audit_20260730.json` cierra frío, caliente,
concurrencia, backpressure, cancelación, transporte, slots/KV, recursos y
soak: spawn→hello 0,49 s y catálogo listo 4,62 s; tres slots solapan a ~2,05×
de throughput efectivo con +46 % por petición bajo contención plena; el cuarto
POST encola acotado (~un decode) sin fallar; la recuperación tras cancelar a
mitad de decode cuesta +87 ms; el pipeline no-LLM completo (JSONL + router +
resolución explícita) cuesta 1–2 ms; el soak de 4 corridas (120 turnos, 0
errores) no degradó p50 (4,02→3,66 s), mantuvo 59–64 °C, 900 MHz constantes y
VRAM pico 2.418 MiB sin fugas; toda la cola provino de los casos de drenaje
conocidos.

### Tabla del contrato P

`primary_contract_component_table_20260730.json` cuantifica cada componente:
system prompt 549 tokens (prefijo constante cacheado, coste 0 caliente),
nombres de candidatos 131 tokens (~170 ms), descripciones 545 tokens
(~700 ms, precio medido de la calidad de decisión: names-only cambió
acciones), schema de salida sólo-gramática (0 tokens de prompt), texto 12
tokens. Prefill 708–859 tok/s; decode 25–40 tok/s bajo contención. Cada
alternativa de representación (orden de schema, IDs compactos, GBNF directo,
priming, save/restore, checkpoints, separación de constantes) está medida y
rechazada o pertenece a los límites que requieren otra decisión.

### Lote experimental autorizado (cuarta pasada)

Con autorización del usuario, el asistente MTP oficial de Gemma 4 E2B y
Ministral-3-3B se midieron físicamente en una carpeta aislada, sin tocar Git,
manifests ni la instalación. Ambos quedaron **rechazados**: el asistente MTP
acepta solo 28,3 % de drafts contra el target QAT (chat +33 %, P sin ganancia,
3/4 salidas cambiadas; `b9553_mtp_assistant_verdict_20260730.json`) y
Ministral pierde la fase 2 (decode −29 %, P real +51 %, VRAM +968 MiB;
`ministral_phase2_ab_v2_20260730.json`). La causa del hallazgo de readiness
quedó identificada como el diseño bifásico léxico→semántico
(`promote_planner_resources`, frontera a ~19–22 s del catálogo) y la variante
V-A que la elimina quedó medida y bloqueada por adjudicación en
`evidence_readiness_stability_verdict_20260730.json`.

### MTP de Gemma 4: rechazo físico sobre el runtime certificado (2026-07-31)

`artifacts/fixes/mtp_q4_abba_20260731.json`. Esta pasada corrige dos premisas
falsas de la anterior y llega al mismo veredicto con evidencia mucho más firme.

**Lo que estaba mal.** El funnel del 30 de julio decía que adoptar MTP obligaba a
degradar llama-server por debajo de la revisión certificada, hasta b9553, por
[#24795](https://github.com/ggml-org/llama.cpp/issues/24795). Es falso: el
**b9980 certificado carga** `mtp-gemma-4-E2B-it-Q4_0.gguf` y sirve con él bajo
los flags exactos del producto. La línea `Gemma4Assistant requires ctx_other to
be set`, que las sondas anteriores leyeron como fallo de carga, viene anotada por
la propia llama.cpp como `(this warning is normal during memory fitting)`: el
servidor continúa y responde. Además, la ficha QAT de Google exige que el
assistant de MTP sea **un checkpoint QAT con la misma precisión que el target**,
de modo que el Q8_0 medido antes contra un target QAT Q4 era una combinación que
el propio proveedor documenta como no soportada.

**Lo que se midió.** Drafter Q4_0 del mismo repositorio que el target
certificado (Apache 2.0, 59 235 648 B, sha256 `586f2460…`), ABBA sobre
instancias de servidor, flags del producto en ambos brazos, temperatura 0,
20 muestras por brazo:

| | baseline | con drafter | delta |
|---|---:|---:|---:|
| keystroke visible p50 | **1,3400 s** | **2,1192 s** | **+0,7792 s (+58 %)** |
| s por token generado p50 | 0,014271 | 0,015472 | +8,4 % |
| salidas idénticas al baseline | — | **0 de 5** | — |

Cada brazo es internamente determinista (una sola salida distinta por prompt en
cuatro repeticiones), así que la divergencia no es ruido de muestreo: con drafter
el modelo **dice otra cosa**. Ejemplo real: «hacer que la computadora arranque y
funcione» pasa a «hacer que tu computadora inicie y funcione».

Falla a la vez la puerta de salida exacta y la de latencia, sobre el runtime
certificado y con el activo que la documentación del proveedor prescribe. El
decoding especulativo de Gemma 4 queda **rechazado físicamente en este hardware**,
no aplazado detrás de un fallo de terceros.

### Reauditoría Qwen3.5 con fuentes oficiales

Corrección del funnel: llama.cpp oficial **sí** ejecuta los híbridos Gated
DeltaNet en builds recientes (GGUF oficiales publicados; la conversión está
soportada), pero los issues oficiales #21831 (abierto), #22746 y #25913
muestran que los modelos híbridos/recurrentes fuerzan re-procesamiento
completo del prompt entre solicitudes. BAXY reutiliza 554–1.214 tokens de
prefijo en cada llamada P/G/L/V: un re-prefill de ~1,2k tokens (~0,9–1 s) por
inferencia invertiría el signo de cualquier ganancia de decode. Descartado con
condición de reversión: #21831 corregido en release oficial soportada.

## Cómo medir sin confundir resultados

- Separar arranque frío, primer turno caliente y mediana caliente.
- Precalentar exactamente como el escritorio antes de aceptar entrada.
- Medir el mismo texto varias veces y registrar longitud de salida.
- No comparar una respuesta de diez tokens con otra de cien como si el modelo
  hubiera hecho el mismo trabajo.
- Para `llama-server`, registrar `prompt_n`, `predicted_n`, `cache_n` y sus
  timings cuando estén disponibles.
- Informar latencia crítica y trabajo total por separado: dos inferencias
  concurrentes pueden tardar más individualmente por contención y aun reducir
  el tiempo hasta que ambas terminan.
- Usar sólo lecturas inocuas en sondas end-to-end. Una acción externa sensible
  requiere contrato, simulación o autorización explícita.
- No presentar el tiempo de `turn.decide` como tiempo total de una acción: App,
  Core, provider y formulación todavía deben terminar.

Las cifras actuales y su alcance viven en
[`REGISTRO_DE_MANTENIBILIDAD.md`](../REGISTRO_DE_MANTENIBILIDAD.md).

## Primera respuesta visible (decidido 2026-07-30)

La entrega sigue publicando el mensaje completo, pero el turno ya no es mudo
mientras dura. El puente publica una **indicación honesta de progreso** sobre
el evento histórico `boot_stage` que el `dist` sellado ya interpreta: no cambia
un byte de `dist` y ningún lector puede malinterpretarla. El vocabulario es
cerrado (`starting`, `understanding`, `preparing_steps`, `acting`, `working`,
`awaiting_reply`, `unavailable`, más un `ready` terminal que la retira), el
texto es natural, se deduplica, se recalcula —nunca se reproduce— al
reconectar un socket, y nunca anticipa un éxito ni muestra JSON, schemas o
estado interno.

El **streaming de la prosa del modelo queda rechazado por contrato**: el texto
visible debe formularse bajo los contratos de BAXY y una acción no puede
mostrar éxito antes de la verificación del proveedor, de modo que publicar
prosa parcial antes de la decisión rompería ambas invariantes. La alternativa
promovida llega a la persona de inmediato y no cuesta tiempo total.

Medición del **tramo del shell** sobre el core real
(`tests/Baxy.Integration.Tests/VisibleResponsePathMeasurementTests.cs`):

| Hito | p50 | p95 | máx |
|---|---:|---:|---:|
| Primera indicación visible honesta | 0,278 ms | 457 ms | 457 ms |
| Texto publicado en la conversación | 66,97 ms | 578,8 ms | 578,8 ms |

**Estas cifras no son latencia productiva end-to-end.** El ensamblado de
integración activa `UserMessagePolicy.BypassLlmCompositionForTests` en
`TestAssemblySetup`, de modo que el texto final sale de la plantilla
determinista y **no** de `message.compose`, que es la composición real del LLM
en producción; además la decisión la fija un resolver de prueba en lugar de
P/G/L/V/C, y el tramo WebView2→DOM→primer paint queda fuera. Lo que la prueba
sí acredita es la propiedad por la que se hizo el cambio: la indicación honesta
precede al texto, no lo sustituye ni lo retrasa.

Las plantillas deterministas siguen siendo borrador/fallback. **No** se
promovieron como respuesta principal para ganar latencia: la respuesta
productiva la sigue formulando el LLM con hechos ya verificados.

### Descomposición de P/G/L/V/C: cómo NO medirla

`artifacts/fixes/pglvc_pipeline_20260731.json` quedó **retractado**. Correlaba
cada POST con un turno por solapamiento de ventana de reloj, y eso es inválido
en este sidecar: hay trabajo especulativo, trabajo retirado y calentamiento en
segundo plano, así que la misma inferencia cae dentro de varias ventanas. El
resultado atribuía **5,647 s de inferencia a un turno determinista de 0,0015 s**
(×3765) y daba a turn-03 y turn-06 exactamente los mismos 6,981 s: las mismas
llamadas contadas dos veces. Los 12 casos superaban su propio tiempo de pared.

La lección es general: **un POST sólo puede atribuirse a un turno por identidad
propagada desde su creación**, nunca por proximidad temporal.

Por eso `LlmRuntime.begin_request` publica ahora una identidad de petición
—puramente diagnóstica, sin efecto sobre prompts ni decisiones— y
`experiments/mind_router_spike/probe_policy_pipeline.py` atribuye cada llamada
por esa identidad, separando explícitamente el trabajo consumido por el turno
del trabajo de fondo o huérfano.

### Descomposición correcta de P/G/L/V/C (2026-07-31)

`artifacts/fixes/policy_pipeline_20260731.json`. **51 llamadas, 51 atribuidas,
0 huérfanas.** Corpus de 12 casos con conversación, acción, plan, clarify,
colas conocidas y textos con forma de efecto que el reconocedor determinista no
resuelve, para que el guard participe de verdad.

| Componente | Llamadas | prefill p50 | decode p50 |
|---|---:|---:|---:|
| **P** política primaria | 10 | 646,2 ms | **3 024,3 ms** |
| **G** guard semántico | 10 | 506,8 ms | 1 078,7 ms |
| **L** gramática de idioma | 10 | 523,5 ms | 272,6 ms |
| **V** verificación de cantidad | 5 | 177,0 ms | 1 072,0 ms |
| **C** compatibilidad | 3 | 263,0 ms | 337,6 ms |
| **S** selector de efecto único | 1 | 594,7 ms | 788,1 ms |
| chat / conocimiento | 11 | 153,0 ms | 467,0 ms |

Lecturas:

- **P domina y su coste está en el decode** (3,02 s), no en el prefill (0,65 s).
- **G se agenda una vez por cada turno de modelo** (10:10 con P), como implica
  el planificador: es la primera barrera de decisión.
- Los turnos ya deterministas registran **0 llamadas** y 1–7 ms, que es la
  comprobación de que la atribución por identidad no les presta trabajo ajeno.

Cuidado al clasificar: `_compact_structured_grammar` reescribe el schema de G a
GBNF y elimina su `response_format` en la copia de wire, de modo que sobre el
cable G y L se parecen. Sólo la gramática de idioma es literalmente
`_RESPONSE_LANGUAGE_GRAMMAR`; cualquier otra gramática compactada es el guard.
Confundirlos hace desaparecer G de la medición.

### Harness versionado del camino visible (2026-07-31)

Hasta ahora el camino tecla→pintado se medía con scripts sueltos del scratchpad:
imposible de repetir y de auditar. Ahora vive en el repositorio:
`scripts/measure_app_visible_path.ps1` mide y
`scripts/summarize_app_visible_path.py` resume, sobre
`artifacts/fixes/app_visible_path_v3.json` y las trazas crudas del directorio
del mismo nombre.

Lo que garantiza: identificadores de escenario estables y un SHA-256 del conjunto
congelado —dos corridas sólo son comparables si preguntaron lo mismo—; brazos
frío y caliente alternados en orden ABBA; relojes, throttle, temperatura y
potencia de GPU más los SHA-256 de la app, el core y llama-server, capturados
antes y después; valores individuales con dispersión, nunca sólo una mediana; y
atribución **por posición dentro del bloque** con los turnos de calentamiento
declarados, de modo que un bloque cuyo recuento de turnos no cuadre se reporta
sin atribuir en vez de correlacionarse por reloj de pared.

Corrida del 2026-07-31: 2 rondas, 8 bloques, 5 escenarios por bloque,
**40 de 40 muestras atribuidas, 0 bloques sin atribuir**.

| | frío | caliente |
|---|---:|---:|
| **primer turno del bloque** p50 | **4 814,1 ms** (n=4, sd 119,7) | **3 698,8 ms** (n=4, sd 264,3) |
| turnos posteriores p50 | 895,5 ms | 852,8 ms |
| mediana del brazo completo | 930,3 ms | 908,0 ms |

Lecturas:

- **El primer turno es lo que cuesta de verdad un arranque en frío**: ~1,1 s más
  que en caliente, con dispersión baja en ambos brazos. La mediana del brazo
  completo lo esconde por entero; por eso el primer turno se reporta aparte.
- **Aun un bloque caliente paga 3,7 s en su primer turno**, así que lo caro no es
  sólo cargar el modelo: es el primer turno después de una pausa.
- **El transporte y el pintado no son el coste**: tecla→submit 0,855 ms, cruce
  del puente 0,070 ms, cola 0,643 ms, publicación→DOM 18,0 ms y DOM→paint
  19,5 ms. Unos 39 ms de los ~926 ms que tarda un turno.
- `decision_ms` tiene p50 de **21,9 ms** sobre 40 turnos —el reconocimiento
  determinista haciendo su trabajo— pero un máximo de **15 119,9 ms**: una sola
  decisión de política del modelo todavía puede costar quince segundos, y ese
  valor atípico es el que produce el peor caso de 15 151,4 ms de toda la corrida.
- `arguments_grounding_ms` queda en **0,848 ms** de mediana, que es el scope
  determinista promovido: ese tramo costaba ~1,0 s.

`paint.observed` sigue siendo un proxy de doble rAF posterior a la mutación
dentro de WebView2, **no** una confirmación del compositor del sistema: acota
cuándo se entregó el cambio de DOM al renderizador, no prueba que los píxeles
llegaran al panel.

### Por qué un token de política cuesta más, y qué se hizo (2026-07-31)

`artifacts/fixes/policy_token_rate_20260731.json`. P emite pocos tokens y aun
así domina, así que la pregunta era por qué cada token cuesta de más. Medido con
los payloads reales sobre un servidor caliente, en orden ABBA:

| brazo | tokens | ms/token |
|---|---:|---:|
| chat libre | 14 | **9,34** ← tarifa propia del modelo |
| P sin `response_format` | 20 | 9,13 |
| P con schema completo | **76** | 14,64 |
| P con enums relajados | 76 | **14,34** |
| P con schema, contendido | 87 | 21,33 |

Dos conclusiones que corrigen intuiciones razonables pero falsas:

- **Los enums largos no cuestan.** Abrir los dos enums de 28/29 operaciones a
  `string` no movió la aguja (14,64 → 14,34). El término dominante del muestreo
  con gramática es el barrido del vocabulario, no cuántas ramas tiene la
  alternancia.
- **La contención no hay que atacarla.** `serial_vs_parallel_policy_20260731.json`:
  el grupo P+G+L tarda 1,7098 s en paralelo contra 1,7469 s en serie. Solapar es
  **37 ms más rápido**; G y L viajan a la sombra de P. Serializar empeoraría.

De los 930 ms que cuesta restringir a P, **el 88 % son los 56 tokens
estructurales de más** y sólo el 12 % la tasa por token. El arreglo por tanto no
es una gramática más barata: es **emitir menos estructura para la misma
decisión**.

#### Campos derivados retirados del schema primario

`artifacts/fixes/p_derived_fields_20260731.json`. El propio prompt declara dos
campos como funciones de otro, y el código ya actuaba en consecuencia:

- `effect_count` — `_canonical_turn_decision` **ya lo recalculaba** desde
  `len(effect_operations)` y descartaba el valor del modelo. Se le pagaba por
  escribir algo que se tiraba siempre.
- `operation` — `validate_turn_decision` **ya exigía** `operation ==
  effect_operations[0]` y rechazaba el turno si diferían. Derivarlo no puede
  cambiar una decisión aceptada; sólo elimina un rechazo que costaba un turno de
  política entero.

Ambos se retiraron del schema y BAXY los deriva. Medido con los timings propios
de P, 42 llamadas por brazo, sesiones alternadas en ABBA:

| | antes | después | delta |
|---|---:|---:|---:|
| tokens emitidos p50 | 82,0 | **61,0** | **−21** |
| decode p50 | 1 677,0 ms | **1 317,4 ms** | **−359,6 ms** |
| decode media | 1 904,8 ms | 1 551,0 ms | −353,8 ms |
| prefill p50 | 360,7 ms | 361,5 ms | sin cambio |

Puerta: **ninguna decisión nueva** que el baseline no produjera, en las 48
muestras por brazo del corpus congelado. `guard-01` sale no-determinista, pero en
ambos brazos con el mismo conjunto de resultados: es no-determinación del modelo
bajo batching continuo, no efecto de la variante.

**Cómo NO medir esto.** El tiempo de turno no sirve: esa distribución es bimodal
—turnos deterministas de ~0,001 s mezclados con turnos de modelo de varios
segundos, sd = 1,61 s— y el efecto buscado cabe entero dentro del ruido. La
misma métrica dio −115 ms, −2 ms y −134 ms en tres corridas del mismo
experimento. Hay que medir `predicted_n` y `predicted_ms` de P desde los timings
de llama-server. La primera corrida de este trabajo reportó −114,7 ms de ganancia
y **era ruido leído como victoria**; queda retractada.

### Brazo directo byte-idéntico: BAXY no cobra nada (2026-07-31)

`artifacts/fixes/policy_direct_replay_20260731.json`. La pregunta era estrecha:
para los payloads exactos que P, G, L, V y C envían, ¿pasar por BAXY cuesta algo
frente a publicar los mismos bytes contra el mismo llama-server? **No.**

| Componente | BAXY p50 | directo p50 | delta | tokens generados |
|---|---:|---:|---:|:--:|
| P política primaria | 1,6372 s | 1,6035 s | +0,0337 s | 76 / 76 |
| G guard semántico | 0,6205 s | 0,5962 s | +0,0243 s | 20 / 20 |
| L gramática de idioma | 0,1475 s | 0,1548 s | −0,0073 s | 6 / 6 |
| V verificación de cantidad | 0,9482 s | 0,9067 s | +0,0415 s | 23 / 23 |
| C compatibilidad | 0,3549 s | 0,3645 s | −0,0096 s | 15 / 15 |
| chat | 0,2395 s | 0,2351 s | +0,0044 s | 14 / 14 |
| argumentos aterrizados | 0,7038 s | 0,7125 s | −0,0087 s | 45 / 45 |

Ambos brazos generan **la misma cantidad de tokens**, así que el delta es
atribuible al camino y no al trabajo. La latencia de la política es decodificación
del modelo, no transporte ni orquestación de BAXY.

Dos cosas que hay que respetar para que la comparación signifique algo:

- **Los bytes tienen que ser literalmente los mismos.** BAXY publica
  `json.dumps(payload).encode("utf-8")` con los valores por defecto de la
  biblioteca estándar. Un primer intento serializó el brazo directo con
  `sort_keys=True` y `ensure_ascii=False`; no eran los mismos octetos y reportó
  un −0,336 s en los argumentos aterrizados que desapareció al igualar los
  bytes. Ese intento queda registrado como descartado dentro del propio
  artefacto.
- **Hay que contar los tokens generados.** Un delta de segundos sólo se lee como
  coste de transporte cuando ambos brazos decodificaron lo mismo.

Queda una asimetría conocida y anotada: BAXY publica sobre su pool de conexiones
persistentes y el brazo directo abre un socket por petición. En loopback es la
única diferencia restante y favorece a BAXY.

### Scope determinista de `system.status` (promovido 2026-07-30)

El grounding de argumentos era el cuello de la ruta de acción. El `scope` de
`system.status` es un enum cerrado del catálogo y el reconocedor ya sabe qué
dominios medibles nombra el texto, así que ahora lo aporta por el mismo seam
que el resto de argumentos explícitos (`_ground_explicit_arguments`), sin
preguntar al modelo por un valor que el texto ya contiene.

Condición que lo hace seguro: **o nombra el alcance correcto o no nombra
ninguno**. Se abstiene —y conserva el grounding actual— ante dos alcances que
el enum no mide de una vez, ante una petición de GPU que no dice si pregunta
identidad o uso, y ante toda la familia adversarial. Core sigue siendo la única
autoridad: el valor cruza `normalize_objective_arguments` y todas las
compuertas de schema, riesgo, confirmación y verificación.

Corpus: 52 casos cubriendo batería/carga, CPU/núcleos, RAM, disco/espacio,
GPU identidad y uso, Windows, resumen, combinaciones representables y no
representables, temperatura, atribución por proceso y por modelo,
pasado/futuro/hipótesis, otro dispositivo, conocimiento/consejo/compra/
diagnóstico, ámbito de aplicación y es/en/spanglish. Resultado: aporta scope en
37, **0 incorrectos y 0 abstenciones inesperadas**.

**A/B real, ambos brazos en la misma sesión física**
(`scope_abba_same_session_20260731.json`). El primer intento comparaba contra
una traza capturada horas antes, en otro proceso y con otro estado térmico:
eso no es un A/B y sobrestimaba el ahorro. Aquí baseline y candidato se
alternan en orden ABBA dentro del mismo sidecar, con prompts, calentamiento,
runtime y temperatura idénticos; el brazo baseline desactiva el atajo sólo para
esa petición.

| Brazo | p50 | n |
|---|---:|---:|
| Baseline (grounding con modelo) | **1,0126 s** | 6 |
| Candidato (scope determinista) | **0,0006 s** | 6 |
| **Δ** | **−1,012 s** | |

**`arguments_all_equal: true`**: los dos brazos produjeron argumentos idénticos
en los seis prompts, así que el ahorro no viene de decidir distinto.

El ahorro honesto es **≈1,01 s**, no los 1,37 s que sugería la comparación
entre sesiones. Regresión permanente en
`tests/test_system_status_scope_grounding.py` y
`tests/test_machine_status_scope.py`.

### Descomposición definitiva desde la pulsación real (2026-07-30)

Segunda pasada con todos los tramos separados —incluidos el grounding de
argumentos y la llamada al Core, que antes quedaban fundidos— y con la
pulsación real marcada en el documento. 12 turnos en orden ABBA: 6 de acción y
6 de conversación, runtime caliente
(`artifacts/fixes/app_keystroke_to_paint_v2_20260730.json`).

| Tramo | Acción p50 (n=6) | Conversación p50 (n=6) |
|---|---:|---:|
| Teclado → submit | 0,91 ms | 1,07 ms |
| Cruce del bridge | 0,08 ms | 0,08 ms |
| Despacho | 1,48 ms | 0,54 ms |
| Primera indicación honesta (desde la tecla) | 2,88 ms | 2,61 ms |
| Decisión | 2,41 ms | **5 048,9 ms** |
| **Grounding de argumentos** | **1 371,4 ms** (n=5) | — |
| Core + provider + verificación | 188,9 ms | — |
| Composición final del LLM | 460,4 ms | — |
| Publicación → DOM | 20,7 ms | 17,2 ms |
| DOM → proxy doble-rAF | 20,2 ms | 20,2 ms |
| **Teclado → proxy doble-rAF** | **2 200,5 ms** | **5 105,6 ms** |

**El cuello de la ruta de acción es el grounding de argumentos**, no el Core ni
la composición: 1,37 s de mediana frente a 189 ms de Core+provider+verificación
y 460 ms de composición. Sólo aparece cuando la operación tiene schema con
propiedades: `system.time` usa `EmptySchema` y por eso su turno no tiene ese
tramo (n=5 sobre 6 acciones) y baja a 1,56 s end-to-end.

En la ruta de conversación no hay ni Core ni composición: la mente formula la
respuesta dentro de la propia decisión, que cuesta 5,05 s de mediana.

Valores individuales de los 12 turnos, y no sólo percentiles, están en el
artefacto: con seis muestras por ruta un p95 no es una conclusión robusta y se
publica sólo como referencia.

**Qué mide exactamente el último hito.** `paint.observed` es el segundo
`requestAnimationFrame` posterior a la mutación del DOM: un **proxy de doble
rAF**, no una confirmación del compositor del sistema operativo. Acredita que
el motor de render pasó por dos vueltas de frame, no que el píxel llegó a la
pantalla. Llamarlo «primer paint físico» exigiría una observación externa
correlacionada que esta medición no tiene.

**Estado de esta medición**: es diagnóstica y reproducible a mano, no un
benchmark versionado. Le faltan identificadores estables de escenario, hashes
de fixture, arranque en frío, repeticiones suficientes y un parser versionado;
hasta tenerlos no debe usarse como baseline de promoción.

### Medición productiva completa (2026-07-30)

Sesión de escritorio interactiva real, runtime caliente, producto en ejecución
—no un host de pruebas—, con la mente real, el Core real y la composición real
del LLM. La pulsación entra por clic + teclado sobre el campo del FieldUi y el
último hito es el frame que entregó el compositor
(`artifacts/fixes/app_visible_path_endtoend_20260730.json`, 7 muestras).

| Turno | Decisión | Decisión (ms) | Core+provider+verificación+composición LLM (ms) | App→DOM (ms) | DOM→paint (ms) | Enter→paint (ms) |
|---|---|---:|---:|---:|---:|---:|
| t1 | action | 56,9 | 647,2 | 33,0 | 29,8 | **1 383,7** |
| t2 | action | 2,8 | 503,2 | 12,5 | 17,0 | **537,0** |
| t3 | action | 4,9 | 2 081,5 | 17,4 | 26,8 | **2 132,2** |
| t4 | action | 1,9 | 1 930,1 | 16,9 | 19,4 | **1 970,9** |
| t5 | action | 2,1 | 1 987,6 | 28,4 | 17,3 | **2 035,3** |
| t6 | conversation | 4 726,4 | 7,1 | 21,3 | 48,8 | **4 797,9** |
| t7 | conversation | 4 106,8 | 0,2 | 18,5 | 19,0 | **4 144,5** |

Resumen por tramo (p50 / p95 / máx, n=7): cruce del bridge 0,12 / 0,59 / 0,59;
despacho hasta iniciar el turno 1,59 / 504,3 / 504,3; primera indicación
honesta 2,16 / 505,6 / 505,6; decisión 4,87 / 4 726 / 4 726; Core + provider +
verificación + composición del LLM 647,2 / 2 081 / 2 081; App→DOM 16,9 / 28,4 /
28,4; DOM→primer paint 19,4 / 48,8 / 48,8; **Enter→paint 2 035 / 4 798 /
4 798**.

Lectura honesta de dónde está el coste:

- **Ruta de acción**: la decisión ya no pesa —1,9–4,9 ms gracias al resolver
  determinista; los 56,9 ms de t1 son el primer turno en frío—. El coste lo
  domina el bloque Core + provider + verificación + **composición del LLM**,
  entre 0,5 y 2,1 s. Ese bloque es exactamente el que la medición anterior del
  shell excluía, y por eso aquella cifra de 67 ms no describía la respuesta
  productiva.
- **Ruta de conversación**: el coste está en la decisión (4,1–4,7 s), porque el
  propio turno formula la respuesta; la composición posterior es ~0 porque el
  texto ya viene formulado por la mente.
- **Transporte y pintado**: App→DOM 17 ms y DOM→paint 19 ms de mediana. Juntos
  no llegan a 40 ms: el recorrido visible no es el cuello.

Para reproducirlo hay que lanzar `Baxy.exe` con `ProcessStartInfo` y
`UseShellExecute=false`, pasando un entorno explícito con `BAXY_APP_TRACE` y con
el .NET 10 privado. `Start-Process` de PowerShell usa ShellExecute y **no**
transporta un entorno modificado: con él la instrumentación queda muda y el
apphost puede mostrar su propia ventana de error, que es fácil confundir con una
ventana de BAXY que no termina de cargar.

**`DOTNET_ROOT` por sí solo no alcanza en esta máquina.** El entorno de máquina
exporta `DOTNET_ROOT` y `DOTNET_ROOT_X64` apuntando a `C:\Program Files\dotnet`,
cuyo runtime de escritorio más nuevo es 9.0. La forma específica de arquitectura
tiene prioridad sobre la genérica, así que fijar sólo `DOTNET_ROOT` deja ganar a
la heredada y el apphost vuelve a mostrar su ventana de error. Hay que fijar
`DOTNET_ROOT`, `DOTNET_ROOT_X64` y `DOTNET_ROOT(x64)` a la raíz privada. Y no se
debe preferir la variable ambiental sobre la privada: hay que elegir la raíz por
lo que contiene, comprobando que exista un `shared\Microsoft.WindowsDesktop.App`
con una versión 10.x, que es lo que hace `scripts/measure_app_visible_path.ps1`.
La prueba de que arrancó la app y no el diálogo de error es que aparezca el
archivo de traza: si no aparece, lo que se está midiendo no es BAXY.

Para instrumentar el camino completo, exporta `BAXY_APP_TRACE` con la ruta de
un archivo antes de lanzar la App: `src/Baxy.App/ShellTrace.cs` escribe una
línea JSON por hito, con reloj monotónico, correlación por petición y un
vocabulario cerrado de etiquetas; por diseño no puede escribir texto de la
persona ni prosa del modelo. El tramo WebView2→DOM→primer paint exige una
sesión de escritorio interactiva real.

## La envoltura social, 31 de julio de 2026

De los 30 turnos congelados del workload, 15 ya no llegaban al modelo, y por eso
`decision_ms` tiene una mediana de 21,9 ms. Cada turno que deja de cruzar P vale
más que cualquier micro-optimización de su schema, así que la pregunta era qué
familias seguían cruzándolo sin necesidad.

El reconocedor determinista no tenía una noción uniforme de **envoltura
social**, y de ahí salían dos huecos encadenados:

- un turno que es únicamente un acto social —`hola`, `buenas tardes`,
  `nos vemos`, `perfecto gracias`, `hi, how are you?`— pagaba un decode completo
  de P, porque sólo el agradecimiento a secas estaba reconocido;
- un acto social por delante bloqueaba una petición que el reconocedor sí sabía
  resolver, salvo que el saludo fuera exactamente `hola baxy`. `hola baxy,
  cuanta bateria queda` resolvía a `system.status`; `hola, cuanta bateria queda`
  no.

Esta página **afirmaba desde antes** que saludos y despedidas no ejecutaban E5.
Para el agradecimiento y el no-entendimiento era cierto; para saludos y
despedidas no lo era. La documentación describía el diseño previsto, no el
código. El cambio la vuelve verdadera.

### Medición física

ABBA de sesiones completas, mismo corpus dos veces por sesión, brazo baseline
restaurando los tres patrones anteriores dentro del mismo código de producto.
Las llamadas a P se atribuyen por identidad de petición, nunca por proximidad
temporal:

| Familia | P baseline | P candidato | p50 baseline | p50 candidato |
|---|---:|---:|---:|---:|
| acto social completo | 28 | **0** | 1,6582 s | **0,1735 s** |
| saludo + petición | 32 | **0** | 2,7044 s | **0,0009 s** |
| adversarias | 16 | 16 | 1,5743 s | 1,6822 s |
| continuidad congelada | 20 | 20 | 1,7771 s | 1,8835 s |

En total, 98 → 38 llamadas a P, 124,369 → 46,772 s de decode y 24,264 →
11,919 s de prefill. La prueba de que la variante surtió efecto no es que
corriera: es que un turno que el candidato no manda a P **no tiene fila de
telemetría**. El delta de p50 de turno (−1,0007 s) se publica sólo como
referencia: esa distribución es bimodal y no resuelve el efecto. Un turno social
sigue llamando a `chat` para formular su respuesta visible, así que el ahorro es
E5 más P, G y L, no el turno completo.

### Por qué la puerta no fue igualdad exacta contra el modelo

La igualdad exacta contra un baseline de P **sólo puede aprobarla una variante
donde P ya acertaba**: rechaza por construcción todo caso en que ampliar el
reconocedor *corrige* una respuesta. El acto social completo la aprobó tal cual
—7/7 casos `conversation` idéntica y deterministas en ambos brazos, y las cuatro
adversarias intactas con 4 → 4 llamadas a P—. El saludo delante de la petición
la falló en 2 de 4 casos, y los dos son P contradiciéndose a sí mismo:

- `buenos dias, cuanta bateria queda`: el baseline resolvía la forma desnuda a
  `system.status`, pero la envuelta la contestó con una aclaración 4 de 4 veces,
  gastando 16 llamadas a P;
- `hola, pon el volumen al 30 por ciento`: el baseline resolvía la forma desnuda
  a `audio.volume`, pero la envuelta la convirtió en un plan sobre
  `audio.volume.adjust`, un ajuste relativo donde la persona nombró un nivel
  absoluto.

Por eso esa mitad se cerró con la puerta que ya usaron R3 y R10: un **oráculo**,
no el modelo. Los 64 casos congelados de `tests/test_effect_intent.py` por 13
envolturas dan 832 comparaciones por brazo. Equivalentes 222 → 809, **cero
regresiones** contra el reconocedor anterior, **cero autoridad inventada** por
una envoltura en ninguno de los dos brazos y cero solapamiento entre el
vocabulario social y una operación. Se verificó además que, en los cuatro casos
de saludo + petición, la forma desnuda resuelve idéntica en ambos brazos: el
candidato nunca concede una operación que el reconocedor no concediera ya.

`guard-01` mostró decisiones nuevas y **no es atribuible** a este cambio: la
ruta determinista devuelve `None` bajo los dos juegos de patrones y P se llamó
4 veces en cada brazo. Ya estaba registrado como el único caso no determinista
de su corpus en `p_derived_fields_20260731.json`.

### Hallazgos registrados, no corregidos

- Una envoltura con dos puntos no se separa en cláusulas como sí lo hace una
  coma, así que `Hola baxy: Abre la calculadora` sigue yendo al modelo. Once de
  los 22 residuales comparten esta causa.
- `Hola baxy: Navega Opera a https://example.com/` resuelve a
  `browser.navigate` en vez de `browser.navigate.named`, es decir navegaría en
  el navegador por defecto y no en el que la persona nombró. **Los dos brazos
  producen exactamente ese único caso**, así que es un hallazgo de esta
  auditoría y no un efecto del cambio.
- `¿Está instalada la calculadora?` pierde su envoltura con cualquier forma,
  incluida `Baxy, `, que ya existía antes. Misma causa de anclaje.

Corregirlos exige ampliar `app.open`, `app.installed`, `capture.screenshot`,
`browser.navigate.named` y los planes compuestos que los contienen, que es otra
afirmación con su propio radio de impacto. No se hace aquí.

Evidencia: [veredicto](../../../artifacts/fixes/social_envelope_verdict_20260731.json),
[A/B físico](../../../artifacts/fixes/social_envelope_20260731.json),
[oráculo de equivalencia](../../../artifacts/fixes/social_envelope_equivalence_20260731.json),
[probe](../../../experiments/mind_router_spike/probe_social_envelope.py) y
[detector](../../../scripts/detect_social_envelope_equivalence.py).

## Calidad del tool calling: dónde se pierde de verdad, 2026-07-31

El reconocedor determinista no puede cubrir toda frase que una persona escriba,
así que el modelo carga la cola larga. Antes de intentar mejorarlo convenía
saber si el modelo es de verdad el eslabón débil. **No es el principal.**

La medición suspende el reconocedor dentro del sidecar del propio probe, de modo
que cada texto congelado lo decide P exactamente como lo haría una paráfrasis no
reconocida. El oráculo es el emparejamiento texto → operaciones ya congelado de
`tests/test_effect_intent.py`. 57 casos, 114 turnos, un brazo, código de
producto, sin efectos.

El acierto exacto final es **0,465**, pero ese número mezcla tres causas con
arreglos opuestos:

| causa | turnos | quién falla |
|---|---:|---|
| E5 nunca ofreció la operación esperada | **45 (39,5 %)** | recuperación |
| la operación estaba ofrecida y P falló | 23 (20,2 %) | modelo |
| P acertó | 46 (40,4 %) | — |

El enum del schema de la política **sólo admite operaciones del shortlist**, así
que en esos 45 turnos P no podía nombrar la correcta ni entendiendo el pedido a
la perfección. **Cuando la operación sí está ofrecida, el modelo acierta el
66,7 %.**

La evidencia es concreta:

- `Haz una captura de pantalla`: ninguna candidata de la familia `capture` entre
  las 21 ofrecidas. P respondió `audio.microphone.mute`, que parecía un fallo
  absurdo del modelo y es la opción menos mala de las que recibió.
- `¿Cómo está el Wi-Fi?`: se ofreció `wifi.ensure.connected` y no `wifi.status`.
- `Lista mis tareas pendientes`: la familia `task` entera ausente mientras la
  familia `note` aparece tres veces, lo que también explica que `Crea una tarea`
  resuelva a `note.create`.

**Hipótesis refutada.** Se sospechaba que los vetos posteriores a P estaban
suprimiendo el tool calling. No: sobre 114 turnos tumbaron una propuesta
correcta 0 veces en esta corrida y 1 en la anterior, y **repararon** una
equivocada 7 veces. Son netos positivos y no es ahí donde se pierde.

**Defecto del modelo sí confirmado como sistemático**: `Pon el volumen al 8 por
ciento` resuelve a `audio.volume.adjust`, un ajuste *relativo*, donde la persona
nombró un nivel *absoluto* y `audio.volume` estaba ofrecida. El mismo defecto
apareció de forma independiente en `hola, pon el volumen al 30 por ciento`.

Consecuencia para la planificación: la palanca mayor para que el LLM haga buen
tool calling es la **recuperación**, no el modelo. Esos 45 turnos se pierden
antes de consultarlo, y arreglar el shortlist además **sube el techo** de
cualquier mejora posterior de prompt o schema, porque ésas sólo actúan sobre los
turnos donde la candidata estaba presente.

Honestidad del alcance: esos 57 textos son las frases canónicas que el
reconocedor posee, así que en producción no toman la ruta E5; suspenderlo mide
esa ruta sobre ellos, que es el mejor proxy disponible de una paráfrasis no
reconocida pero no es una muestra fuera de distribución. Dos corridas dieron
0,447 y 0,465, de modo que el titular es estable a unos ±2 puntos y las
diferencias menores no se leen como señal. Evidencia:
[veredicto](../../../artifacts/fixes/policy_tool_quality_verdict_20260731.json),
[medición](../../../artifacts/fixes/policy_tool_quality_20260731.json) y
[probe](../../../experiments/mind_router_spike/probe_policy_tool_quality.py).

## El shortlist decide qué puede nombrar el modelo, 2026-07-31

El enum del schema de la política **sólo admite operaciones del shortlist**, así
que una operación que el shortlist omite es una que el modelo no puede nombrar
por más que entienda el pedido. La medición de tool calling encontró que en el
39,5 % de los turnos con respuesta conocida la operación esperada **nunca se
ofrecía**: el modelo perdía antes de ser consultado.

La causa no es E5 recuperando mal. Es que la **expansión de familias de
`turn_evidence`**, consultiva por contrato —su propio docstring dice *"never
predicts a turn mode or selects an operation"*—, **ordenaba por encima del
ranking propio del catálogo**. Devuelve hasta 12 etiquetas, cada una arrastra
hasta 3 familias relacionadas, y sus dos niveles de preferencia podían llenar las
diez plazas por sí solos. La mejor coincidencia semántica del catálogo quedaba en
el nivel inferior y no entraba nunca. En la práctica, el camino consultivo estaba
seleccionando qué operaciones existen.

Sobre los 57 casos del oráculo congelado: el catálogo por su cuenta ofrece la
esperada en **50**, el producto en **34**. **16 turnos perdidos por la expansión,
0 rescatados**. El 59,6 % offline coincide con el 60,5 % medido en vivo, así que
la reproducción sin modelo es fiel y las perillas se barren en minutos.

### La perilla se eligió con el coste delante

27 combinaciones de piso × ventana por familia × banda de relevancia, con el
**tamaño medio del shortlist** al lado del recall: cada operación añadida es
prefill, y esta misma campaña midió que meter el catálogo en el prefijo de
sistema empeoró el prefill de 369,5 a 420,9 ms.

| piso | ventana | banda | recall | shortlist medio |
|---:|---:|---:|---:|---:|
| 0 (anterior) | 3 | 0,035 | 34/57 | 20,84 |
| 5 | 3 | 0,035 | 48/57 | 20,42 |
| **8** | **3** | **0,035** | **50/57** | **20,60** |
| 8 | 3 | 0,15 | 54/57 | 27,25 |

Se promovió **piso 8 con ventana y banda intactas**: alcanza el techo del propio
catálogo sin agrandar el prompt. La banda 0,15 llega al mejor recall medido y se
**rechaza con mecanismo**: cuesta unas siete operaciones más por prompt contra un
tope de 28, y esas extra son hermanas casi sinónimas, justo la población que se
midió haciendo elegir mal al modelo.

Una reserva previa de este trabajo temía que un piso de 8 dejara la expansión
inerte. El barrido la desmiente: la expansión rescata **0 casos en todos los
pisos** y pierde casos en todos los pisos por debajo de 8.

### Medición física

ABBA de sesiones completas, 456 turnos, con el reconocedor determinista
suspendido para que cada texto lo decida P como lo haría una paráfrasis no
reconocida. El brazo baseline pone el piso en cero, que reproduce el orden
anterior exactamente.

| Métrica | baseline | con piso |
|---|---:|---:|
| operación esperada ofrecida | 60,5 % | **87,7 %** |
| acierto exacto | 44,7 % | **55,7 %** |
| shortlist medio | 21,3 | **21,0** |
| prefill p50 | 292,1 ms | **271,2 ms** |
| llamadas a P | 241 | 233 |

Diez casos mejoran y tres empeoran. El delta de decode (+23 ms) está dentro del
ruido de este workload y no se presenta como efecto.

### Las tres regresiones, nombradas

`Abre Opera` → `browser.navigate.named`, `Abre Spotify` →
**`media.play.query`** y `Crea un recordatorio…` → `notification.schedule`.

La segunda no es un punto de exactitud: es **poner música cuando la persona pidió
abrir la aplicación**, y se nombra como cambio de efecto, no como puntaje.

**No son fallo de recuperación**: la operación esperada estaba ofrecida 4 de 4
veces en **ambos** brazos. El piso cambió qué *otras* operaciones la acompañan y
el modelo prefirió una hermana casi sinónima. La hipótesis del orden se probó y
quedó refutada: en el caso del recordatorio la esperada subió a la posición 0 y
el modelo igual eligió la de la posición 9. El modelo es sensible al **conjunto**
de candidatas, no a su orden, así que ningún reordenamiento lo arregla.

Los tres textos los posee el reconocedor determinista en producción y no llegan a
P; la regresión es real para las paráfrasis que el reconocedor no cubre. Pertenece
al cubo del modelo —la candidata correcta estaba ofrecida y no fue elegida— y es
el siguiente objetivo.

Se promovió pese a ellas porque diez casos mejoran contra tres, con +27,2 puntos
de recuperación y sin coste de prompt ni de prefill, y porque retenerlo dejaría a
45 de 114 turnos perdiendo antes de consultar al modelo para evitar tres turnos
que el reconocedor ya posee. Además **sube el techo** de todo lo que venga
después: cualquier mejora de prompt o schema sólo actúa donde la candidata está
presente, y eso pasó del 60,5 % al 87,7 % del corpus.

Evidencia: [veredicto](../../../artifacts/fixes/shortlist_floor_verdict_20260731.json),
[barrido y oráculo](../../../artifacts/fixes/shortlist_recall_20260731.json),
[A/B físico](../../../artifacts/fixes/policy_tool_quality_20260731.json) y
[detector](../../../scripts/detect_shortlist_recall.py).

## Lo que le pasa a la persona cuando el camino determinista no la cubre

Todas las cifras de tool calling anteriores de esta campaña salen de las 57
frases canónicas de `tests/test_effect_intent.py`. Ésas son exactamente las que
el reconocedor determinista posee, así que **en producción no llegan al
modelo**: medirlas exigía suspender el reconocedor, y eso responde «¿qué haría
el modelo con estos textos?», no «¿qué le pasa a la persona cuando el camino
determinista no la cubre?».

Esta medición usa la segunda población. Del corpus histórico congelado se toman
las filas que son `user_mission`, en español o inglés, con una sola familia de
operación, con forma de enunciado y —el punto— **no resueltas por el
reconocedor**. Califican 1.002 textos; se congela dentro del artefacto una
muestra estratificada determinista de 147, y se ejercen 294 turnos.

| Métrica | corpus canónico | paráfrasis reales |
|---|---:|---:|
| operación esperada ofrecida | 94,7 % | **76,9 %** |
| acierto | 58,8 % (operación exacta) | **21,8 %** (familia) |

**R19 y R20 alcanzaron el 94,7 % sobre el corpus contra el que se eligieron sus
perillas.** Sobre la población real es 76,9 %. Ambos apuntan en la dirección
correcta y sus deltas pareados siguen valiendo, pero su **magnitud estaba
inflada por ese corpus**. Queda registrado aquí en vez de dejarlo para que lo
descubra producción.

### Dónde se pierde el efecto

| | turnos de 294 |
|---|---:|
| el modelo nunca propuso un efecto | 110 |
| **las compuertas de `__main__` lo retiraron** | **93** |
| el efecto se conservó | 91 |
| se perdió dentro de `decide_turn` | **0** |

El guard semántico G y el verificador de conteo V **no retiran nada**. Toda la
supresión ocurre en compuertas con nombre:

| compuerta | dispara | con el modelo acertando la familia |
|---|---:|---:|
| `apply_operation_domain_grounding_veto` | 37 | 22 |
| `apply_turn_action_grounding_gate` | 29 | 6 |
| `apply_compound_effect_conservation_veto` | 24 | 16 |

El gate de grounding de acción **está haciendo su trabajo**: 23 de sus 29
disparos atraparon una propuesta de familia equivocada. Los otros dos suprimen
mayoritariamente propuestas cuya familia era correcta.

**Corrección de una afirmación anterior de esta misma campaña.** El veredicto de
calidad de tool calling concluyó que la maquinaria posterior a P no es donde se
pierde el tool calling, con 0–1 anulaciones en 114 turnos. Eso es **cierto para
ese corpus y falso para la población real**: sobre 294 turnos reales las
compuertas retiran el efecto en 93. La afirmación anterior no se retira —era
correcta sobre lo que midió— pero no debe leerse como una afirmación sobre
producción.

### El veto «de compuestos» dispara sin nada compuesto

`apply_compound_effect_conservation_veto` **veta incondicionalmente** en cuanto
`unresolved_compound_contract` devuelve un contrato: nunca compara la propuesta
del modelo contra él. El propio código lo dice —«una propuesta del modelo de la
misma longitud no puede probar conservación»—. Reproducido sin modelo:

- `alarma para mañana 8am`: **una** cláusula, contrato min=1, vetado;
- `ponme un recordatorio en 2 minutos para tomar agua`: **una** cláusula, vetado;
- `Abre Notepad y luego cierralo`: dos cláusulas y el modelo propuso exactamente
  `[app.open, app.close]`, los dos pasos correctos, y se vetó igual.

La regla real no habla de compuestos: es «si alguna cláusula positiva tiene una
identidad de operación que el reconocedor no pudo resolver, no concedas
autoridad física». Su efecto neto es que **BAXY sólo actúa donde el reconocedor
determinista ya está de acuerdo**, que es lo contrario de que el modelo cargue
la cola larga. Coincide con su propio comentario interno, así que es una
decisión de diseño con alcance no buscado, no un descuido; lo que está mal es el
nombre y el docstring, que prometen una comprobación de conservación que el
código no hace.

### Honestidad de la medida

- La granularidad de familia **sobrestima** los vetos equivocados: `Borra la
  carpeta CarterTest` proponiendo `filesystem.folder.open` cuenta como «familia
  correcta» y ahí el veto acertó al impedir abrir una carpeta cuando pidieron
  borrarla. Todo recuento de «suprimió una propuesta correcta» es una **cota
  superior**.
- El corpus etiqueta como español filas en portugués y francés (`Abaixa o volume
  pra 30 por cento`, `tira uma captura de tela`) y como misión alguna pregunta
  de conocimiento (`how do I take a screenshot in Windows?`). Son 14 de 294
  turnos; limpiarlos mueve el titular un punto, así que el hallazgo no descansa
  en ello. Queda anotado como deuda del corpus.

### Por qué no se cambia aquí

Estas dos compuertas **conceden o niegan autoridad física**. Un error ahí no
cuesta un punto de exactitud: ejecuta algo que nadie pidió. Aflojarlas exige su
propio corpus que acredite que no se concede ni un efecto equivocado, su propio
A/B físico y su propia compuerta —la disciplina que usaron R3 y R10 para el
reconocedor, no el trato más liviano que admitió un ranking de shortlist—.

Evidencia:
[veredicto](../../../artifacts/fixes/paraphrase_tool_quality_verdict_20260731.json),
[medición](../../../artifacts/fixes/paraphrase_tool_quality_20260731.json) y
[probe](../../../experiments/mind_router_spike/probe_paraphrase_tool_quality.py).

## El modelo responde cada mensaje, 2026-07-31

BAXY no podía despedirse. `chat` sustituía por un texto fijo cualquier respuesta
cuyo texto normalizado coincidiera con el de la persona, pero **para una
despedida el espejo es la respuesta**: `¡Nos vemos!`, `¡Chau!`, `Bye!` y `Good
night!` se descartaban. `¡Adiós!` sobrevivía sólo por el accidente de su acento.
El guard existe para atrapar a un modelo que repite la pregunta; sobre una
despedida se disparaba al revés.

Un turno clasificado como acto social puede responder con un espejo; cualquier
otro `conversation_kind` conserva el guard exactamente igual. ABBA de sesiones
completas: respuestas producidas por una constante **20 de 48 turnos → 0 de 48**,
con saludo, agradecimiento y conocimiento como controles sin cambio. Como efecto
lateral, `nos vemos` pasó de ~2,4 s a ~0,09 s, porque el guard forzaba un
reintento correctivo —un decode entero— que el mismo check volvía a rechazar;
esas dos cifras vienen de sesiones distintas y no se presentan como delta ABBA.

Queda **una** constante visible en la ruta conversacional, para contenido
genuinamente vacío tras el reintento. No se alcanzó en 96 turnos medidos y no se
defiende como correcta: debería ser una disculpa escrita por el modelo. Está
registrada como pendiente.

La lección de método: la puerta del A/B de R16 comparaba `kind`, `operation`,
`effectOperations` y `question`. **Una puerta sobre la decisión contractual no ve
una respuesta visible rota**, y este defecto estaba en aquel artefacto desde el
principio. Evidencia:
[veredicto](../../../artifacts/fixes/farewell_reply_verdict_20260731.json),
[A/B](../../../artifacts/fixes/farewell_reply_20260731.json) y
[probe](../../../experiments/mind_router_spike/probe_farewell_reply.py).

## Límites que requieren otra decisión

Estas opciones pueden reducir más la espera, pero no son refactors internos:

- streaming de tokens de la respuesta: cambia el contrato público mente/App y
  la presentación de FieldUi, y choca con la formulación bajo contrato y con la
  prohibición de éxito anticipado (rechazado 2026-07-30, ver arriba);
- compactar el schema rico de la política primaria: altera el contrato interno
  con el modelo y necesita volver a pasar el corpus exhaustivo; los GBNF
  cerrados de idioma y guard ya se promovieron por gates independientes;
- otro modelo, draft model o speculative decoding: cambia activos, hashes,
  presupuesto y evidencia reproducible.

No se deben activar estas opciones por intuición. Primero se mide el beneficio,
después se valida calidad y recursos, y sólo entonces se promueve el cambio.
