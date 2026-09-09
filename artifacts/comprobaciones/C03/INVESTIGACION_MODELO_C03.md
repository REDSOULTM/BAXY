# C03 — investigación específica del modelo

Revisión: 2026-09-06, tramo33. Contraste documental y comparación controlada
completados para las capas de chat y la primaria estructurada descritas abajo.
No se ha promovido un nuevo sampler ni cambiado el modelo en esta revisión.

## Actualización 2026-09-07 — Qwen3.5, tramos75–77

El [template oficial Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja)
rechaza cualquier system salvo el primero.75 reproduce esa restricción con
HTTP400 en nueve paquetes reales del producto; no es inferencia desde otra
familia ni un rechazo semántico del modelo.76 conserva cada texto y el diálogo,
agrupa sólo las instrucciones al inicio y elimina9/9 errores de servidor.
Con2507, que admite varios system, las respuestas principales de causa UTF8,
checksum y aclaración del volumen se mantienen. Una pregunta de recuperación
cambia y añade reasoning_content: no afirmar equivalencia token a token.

Fuente77 serializa el prefijo system en el owner de envío, sin cambiar prompts,
historial, samplers ni selector.1149 pruebas dueñas pass/0 skips; Fast verde.
Producto files77-template7/10 útil; los vetos de rol corregidos en78 elevan9/10.
No promoción de Qwen3.5 ni aceptación integral. PRUEBAS_TEMPLATE75_76.md y
TRAMO75_76_PINS.json fijan evidencia nativa; PRUEBAS_TEMPLATE77.md y
PRUEBAS_ROLES78_Y_ENUMERACION79_80.md registran el producto.
Esta restricción específica actualiza la fila histórica de chat del tramo33;
no cambia su conclusión para el2507 entonces probado.

## Actualización 2026-09-08 — razonamiento y muestreo399–400

Los RESULT/PINS de `astra-thinking399/` y `astra-thinking400/` comparan ocho
payloads fijados (dos lecturas privadas, cuatro conversaciones y dos consultas
de cuentaWindows). Qwen3.5-4B Q4_K_M, backendb9980; mismo historial y catálogo,
max_tokens1024.399 compara off0 con on512 aT0:3/8→3/8+un parcial.400 cambia sólo
al perfil general de thinking de la ficha oficial: temperatura1, top_p0,95,
top_k20, min_p0, presence_penalty1,5, repeat_penalty1; seed0 conservada.
400 produce5/8 útiles, pero estropea el recuerdo de sesión que399 resolvía.
Ambos perfiles thinking agotan la lectura inglesa y dejan texto interno en
content; sujetoLina sigue incorrecto. No se promueven ni se siguen variando semillas.

Fuentes contrastadas el2026-09-08: [ficha Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B)
y [servidor b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md).
El servidor local confirma reasoning on/off y presupuesto positivo; el campo
HTTP se llama repeat_penalty.512 es nuestro límite diagnóstico, no una garantía
de calidad del fabricante. El2507 registrado es otro modelo, no-thinking.
GPU3175,56MiB; RAM3880,71/3906,91/3905,92MiB;8,015/40,86/48,578s respectivamente.
Sin infracciones de recursos ni cambio del manifiesto; esto no acredita voz conjunta.

## Fuentes y alcance

- [Ficha oficial Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507):
  variante exclusivamente sin pensamiento. Recomienda temperatura 0,7, top-p 0,8,
  top-k 20 y min-p 0. Penalización de presencia opcional entre 0 y 2; aumentarla
  puede mezclar idiomas y reducir calidad. Su recomendación general de salida
  amplia no obliga a gastar ese presupuesto en cada interacción de BAXY.
- [generation_config oficial](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/generation_config.json):
  confirma do_sample y temperatura/top-k/top-p. No asumir que llama.cpp importa
  este archivo del repositorio Hugging Face al cargar el GGUF.
- [Qwen3 Technical Report, mayo de 2025](https://arxiv.org/html/2505.09388v1):
  documenta perfiles diferentes para thinking y non-thinking. Es anterior a la
  revisión 2507; sus resultados no certifican esta cuantización ni BAXY.
- [Tokenizer/template oficial](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/blob/main/tokenizer_config.json):
  formato ChatML, mensajes system/user/assistant y formato específico de tools.
  Contrastar el render del GGUF local; no sustituirlo por una plantilla genérica.
- [Servidor llama.cpp b9980](https://github.com/ggml-org/llama.cpp/blob/b9980/tools/server/README.md):
  defaults documentados top-k 40, top-p 0,95 y min-p 0,05; dispone de
  `/apply-template` para inspeccionar el prompt renderizado. Comprobar defaults
  efectivos de la instancia antes de atribuirlos a una generación concreta.
- [Experiencia reproducible, issue 20809](https://github.com/ggml-org/llama.cpp/issues/20809):
  usuario reporta en b8429/Vulkan detección de pensamiento incorrecta y llamadas
  a tools desviadas a reasoning_content; muestra mejora con `--reasoning off`.
  Es un reporte con etiqueta bug-unconfirmed, no prueba de fallo en b9980/CUDA.

## Comparación con código y evidencia local

Modelo registrado: Qwen3-4B-Instruct-2507 Q4_K_M base, sin LoRA, llama.cpp b9980.
Registro SHA256: 13b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed.
Fuente inspeccionada: `src/baxy_mind/llm.py` en el WIP del tramo32.

| Aspecto | BAXY observado | Qué demuestra |
|---|---|---|
| Servidor | `_server_command`: --jinja, --reasoning off, --reasoning-budget 0, KV q8_0 | No necesitamos añadir el workaround citado; falta inspeccionar template renderizado. |
| Muestreo | Varias rutas fijan temperatura 0; `_public_compose_sampling` sólo especializa Granite | El perfil de conversación recomendado para Qwen no está aplicado uniformemente. No demuestra causalidad por sí solo. |
| JSON | `_post_schema_object` reemplaza temperatura por 0 o 0,1 según intento | Cambiar sólo el payload inicial no cambiaría ese perfil efectivo. |
| Chat | Políticas e idioma se añaden como mensajes system; seed estable para presentación | Hay que comparar roles/render e instrucciones aplicables, sin asumir que varios system son inválidos. |
| Salida | En la ablación previa de Steam hubo respuesta útil truncada y reintento vacío | No demuestra desconocimiento de Steam. El límite y finish_reason importan. |

Herencia: `biblioteca/carter/legacy/Carter_v4/audit/runs/gemma_vs_qwen_report.md`,
2026-05-08, reporta 26/30 para Qwen y errores de routing/multilingüismo. Su
evaluador penalizaba nombres de operaciones y lenguaje: no trasladar la cifra al
contrato actual. ASTRA-TRAMO-32 registra ablaciones recientes sin variante verde;
la llamada denominada bare todavía usaba wrapper/guardas/límites de BAXY.

## Resultado medido del contraste

`astra-qwen-documented-profile/`: 69 llamadas, 84,89 s; GPU 3497,56 MiB;
RAM 3612,91 MiB; registro intacto. PREREG y probe.py permiten reproducirlo.
PROPS confirma top-k 40, top-p aproximadamente 0,95, min-p aproximadamente 0,05,
penalización de repetición 1 y de presencia 0; contexto 4096 por slot, tres slots.
El perfil actual fija temperatura 0 en las llamadas comparadas. El perfil
documentado se probó con dos semillas fijadas de antemano, 0 y 17.

El template GGUF incorpora lógica de historial thinking ausente en el tokenizer
oficial de revisión `cdbee75f17c01a7cc42f958dc650907174af0554`. Se guardó la diferencia
exacta y ambos templates. Los renders user-only y mensajes BAXY comparados son
idénticos; no atribuir estos errores a esa diferencia ni declarar equivalencia
para cualquier secuencia de tools/historial de pensamiento sin probarla.

La recomendación de muestreo no arregla la negación de audio ni la selección de
volumen absoluto contextual. Con mensajes BAXY incluso afirma haber bajado el
volumen sin observación en un caso. No se promueve. La fecha se interpreta bien
en primaria y el veto posterior sigue siendo la causa localizada en el tramo32.
Steam sin wrapper responde extensamente y agota 512 tokens; algunos desarrollos
incluyen afirmaciones incorrectas. No se considera al modelo solo libre de fallos.

Se corrigió una causa de BAXY demostrada: una petición de conocimiento ya no se
convierte en afirmación del usuario por empezar con un adverbio. La prueba normal
de chat recuperó la explicación de Steam; el muestreo quedó intacto. Ver
[respuestas literales](PRUEBAS_MODELO_DOCUMENTADO_C03.md) y ASTRA-TRAMO-33.md.
Persisten las causas pendientes: no repetir esta comparación sin hipótesis nueva.

## Actualización 2026-09-08 — RAM del servidor,420–425

Backend exacto b9980 admite --cache-ram (8192MiB por defecto;0desactiva) y
--no-mmap. [PR16391](https://github.com/ggml-org/llama.cpp/pull/16391) distingue
la caché de prefijos en RAM del contexto activo. [PR15293](https://github.com/ggml-org/llama.cpp/pull/15293)
documenta checkpoints aparte; no se desactivaron. No es cambio del modelo.
La ayuda y logs exactos prevalecen sobre defaults actuales de master.

Con Qwen3.5-4B Q4_K_M,4096tokens×3slots,KVq8_0,ngl99, mismas8peticiones:
422no-mmap conserva cache8192 y corta con5303,99MiB RSSárbol;
423no-mmap+cache0 completa con3173,43MiB;
424mmap+cache0 completa con5207,20MiB. GPU3177,56MiB en los tres.
423/424dan8finalesidénticos,4útiles;fallos de conducta siguen abiertos.
No se certifica voz conjunta, mínimo global ni regresión integral.
425propone cache0 y no-mmap con GPU; CPU conserva mmap por falta de beneficio
medido sin offload. No nueva variable de usuario ni promoción del4Bdiagnóstico.
RESULT/PINS en cada carpeta; estado de adopción/validación en astra-host-memory425.

## Actualización 2026-09-08 — backend y perfiles por modelo,448–451

Mensajes directos19–20: revisar versiones y medir perfiles adecuados por modelo,
sin limitarse a lo descargado. Una comparación causal con parámetros iguales
no es un ranking global. Las siguientes fuentes se consultaron el2026-09-08.

448 verifica y descarga la distribución oficial de
[llama.cpp v0.4.0](https://github.com/ggml-org/llama.cpp/releases/tag/v0.4.0),
publicada el4 de septiembre; su paquete Windows CUDA12.4 enlaza b10809,
commit5266f24da. El tag de la versión y el commit del binario enlazado son
distintos y quedan registrados. BAXY usaba b9980/8014d2cf9 del13 de julio.
Archivos y huellas en astra-backend-audit448; instalación separada, no promoción.

La [corrección27483](https://github.com/ggml-org/llama.cpp/pull/27483) reduce
crecimiento temporal de buffers de repacking durante carga. No demuestra por
sí sola ahorro en BAXY. La [28183](https://github.com/ggml-org/llama.cpp/pull/28183)
afecta al asistente MTP de Gemma; los diagnósticos actuales no usan ese drafter.
Las correcciones del parser Qwen y presupuesto por petición se registran en448;
no se atribuye una mejora de prosa o routing sin medir esa ruta concreta.

449 conserva el render y4096 tokens por cada uno de tres slots entre versiones.
450 completa44 respuestas, sin truncamiento ni errores: Qwen6/11 con ambas;
Gemma9/11→8/11 por omisión de protección en el caso mixto. La actualización sola
no resuelve el bloqueo. Ninguno de estos resultados descarta un modelo bajo
otros perfiles justificados. Fuente436 y registro2507 siguen intactos.

Perfiles no thinking de451, para composición breve de hechos verificados:

| Candidato exacto | Temperatura | top-p | top-k | min-p | Presencia | Repetición |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3.5-4B Q4_K_M |0.7|0.8|20|0|1.5|1|
| Qwen3-4B-Instruct-2507 Q4_K_M |0.7|0.8|20|0|0|1|
| Gemma4-E2B base y publicado, por separado |1|0.95|64|0|0|1|

[Qwen3.5](https://huggingface.co/Qwen/Qwen3.5-4B) distingue modo y tarea;
se usa la recomendación general no thinking, no la de coding. Dos apartados
discrepan en el perfil de razonamiento no thinking; no se mezclan sus valores.
La ficha advierte que presencia alta puede mezclar idiomas. Para
[2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), estrictamente no
thinking, presencia es opcional y queda0. No es la misma revisión que Qwen3.5.

[Gemma](https://huggingface.co/google/gemma-4-E2B-it) y su
[generation_config](https://huggingface.co/google/gemma-4-E2B-it/blob/main/generation_config.json)
especifican T1/p0.95/k64. min-p0 evita añadir el filtro0.05 predeterminado de
llama.cpp, ausente de esa receta. La ficha oficial no certifica la calidad del
checkpoint publicado de BAXY. Base y publicado se miden por separado.

El [informe Gemma4](https://arxiv.org/html/2607.02770v1) distingue parámetros
efectivos y embeddings por capa, QAT y drafter MTP. Sus cifras de cuantización
móvil no equivalen al GGUF Q4_K_M actual ni al consumo de todo BAXY. Sus mejoras
de thinking en razonamiento no prueban que cada respuesta breve lo necesite.
El [estudio Qwen4B de cuantización y drafter](https://arxiv.org/html/2607.04244v1)
usa una competición con A10G de24GB y un drafter entrenado; sus aceleraciones no
son transferibles como un flag gratuito al presupuesto4GB de BAXY.

La [discusión27115](https://github.com/ggml-org/llama.cpp/discussions/27115)
orienta a enviar muestreo por petición; se contrasta con el
[README del commit exacto](https://github.com/ggml-org/llama.cpp/blob/5266f24da/tools/server/README.md).
El cambio de modo no modifica automáticamente el sampler. Se registran payloads
y parámetros de slots activos. La ventana de penalización permanece64;
por tanto no se afirma igualdad total con Transformers. La
[guía oficial Qwen](https://qwen.readthedocs.io/en/latest/run_locally/llama.cpp.html)
también pide adaptar el muestreo al caso, no copiar defaults sin medir.

451 fija semillas0/17 antes de generar, cuenta todas las88 respuestas y conserva
inputs444. Máximo1024 tokens para variación no thinking; los44 resultados450
pararon naturalmente antes de256. Agotamiento o timeout se etiqueta como tal,
no como fallo de una respuesta completa. Thinking requiere otro presupuesto si
el diagnóstico lo justifica. No se prueba hasta que salga bien ni se elige la
mejor semilla. Todavía no hay perfil declarado óptimo ni promoción.


## Resultados453–464 y recursos específicos de Gemma

453thinking completo: Qwen5útiles/2fallos/4censuras3072tokens; Gemma base5/11,
publicado9/11. 456b10865 no corrige memoria: QwenT0 6/11, perfilesdocumentados
4/11+5/11;Gemma8/11 idéntico a estable. CorrecciónGDN28068 y límites de
aplicabilidad en astra-nightly-audit454. Descarga455verificada, no promoción.
Phi oficialgreedy500/templateverificado4579/11; typedredaction4582/3protección,
aún un falloES. No rechazo global de familia; no seguir variando ese formato.

460 conserva guardas reales: baseline10/11→11/11 con único valor público
obligatorio en caso mixto. No lista ilimitada: dosrequiredFacts activaban
scaffold de misión en459offline; la ruta actual402no los exige. No fuenteadoptada.

461integración se corta por RAM libre antes de medir el perfil. b10809ya incorpora
[PR27794](https://github.com/ggml-org/llama.cpp/pull/27794) y
[PR27837](https://github.com/ggml-org/llama.cpp/pull/27837): PLE bajo demanda,
independiente del no-mmap general. Auto sólo para tablasmayores4GiB; la deeste
Gemma es1837,5MiB y exige --lazy-mode on para medir el ahorro. El benchmark del
autor conE4B advierte coste potencialdevelocidad; no trasladarlo aWindows/E2B.
462misma docena del compositor460:12textos idénticos/13calls,RAM2832,90→1005,51MiB,
VRAM1695,79→1692,18MiB.45,859vs49,859s totales;no óptimo ni velocidad universal.
El log463confirma CUDA_Host315MiB+CPU_Mapped1837,5MiB. Con todoelproducto,
464mide2653,13MiB RAM y1694,18MiB VRAM,7/8útiles;vozfísica pendiente.

Trampa de configuración verificada: [server-common.cpp5266f24da](https://github.com/ggml-org/llama.cpp/blob/5266f24da/tools/server/server-common.cpp#L1366)
interpreta request.reasoning_budget_tokens=-1 como herencia del servidor. 463tenía
servidor0 yno reprodujo thinking460.464servidor-1/deepseek, otrosrequestsfalse/0,
confirma reasoning_content sóloenperfilmemoria. T1confirmación aún omite explicar
el permiso de activar memoria.465debe medir perfil de esa responsabilidad con
hechos/prompt/guardasactuales. Actualización2026-09-08; evidencia privada local.


## 465–480 — confirmaciones, E4B y precisión de pesos

Fuente466 conserva destino y posibilidad de sync que se perdían antes de inferir;
1404ownerpass/0skips/Fast.467 recibe estos hechos pero no los conserva en finales.
468 usa el perfil documentado2507: memoria8/11+11/11, confirmaciones2/6+2/6;
la variante de único valor público añade cifrado inventado conQwen, por lo que no
se adopta universalmente pese al resultadoGemma460.

470/471: nuevo GemmaE4BQ4, revisiónUnslothbfc15c38, SHA85a896... verificado. Se
cargan43/43capas y PLE1848MiB CPU_Mapped bajo lazyon. PicoGPU3278,29/RAM1137,65MiB.
Dos modos oficiales:2/4sin-thinking,3/4thinking, exportación incompleta enambos;
protectedENthinking3intentos23,156s. No asumir que mayor modelo es mejor candidato.

472/473 cambian únicamente obligación de explicar causa/consecuencias: mejora
cobertura parcialQwen, pero prosa interna; Gemma inventa riesgos.474 protocolo
nativo recupera activaciónES pero no advertencias.476 combinación exacta conserva
fallos y pierde naturalidad. No adoptar ni seguir variantes de esos factores.

478 abre contraste de precisión DEL MISMO checkpoint2507 (no nuevas instrucciones).
RepositorioUnsloth/revisióna06e946bb6b655725eafa393f4a9745d460374c9 coincide conQ4
registrado. Q8_0:4280405600bytes, SHA391c1e410fd9f4cf2de2b510273b56a84c19ce18f4fa3bfb3774031dac4ef068.
Los antiguos astra-native-*-q8/PREREGISTRO conservaban pesosQ4: sólo cambiabanKV.

Herencia:03_Optimizacion_Ollama_qwen3_ultimo_10_porciento.md:195–215 proponeQ6/Q8,
pero sus cifras son previsiones no medidas con4060Ti16GB. No tomar su opinión
comunitaria como reproducción. [Qwen llama.cpp cuantización](https://github.com/QwenLM/Qwen3/blob/main/docs/source/quantization/llama.cpp.md)
distingue mezclas de pesos y señala límites de usar perplexity para Instruct.
[Estudio Qwen3](https://arxiv.org/abs/2505.02214) es de mayo2025 y no estudia2507GGUF;
[estudio llama.cpp/Llama8B](https://arxiv.org/abs/2601.14277) incluye tareas semánticas
y coste de recursos, pero usa otra familia/hardware. Son motivos para contrastar,
no pruebas de que Q8 corrija BAXY. Receta2507 oficial .7/.8/k20/min0/neutral,
no-thinking, semilla0/17 preservada. No llamar óptimo a la recomendación inicial.

479: NGL26 AMBOS,4096×3/KVq8/b2048/ub256/b10809. Q4completa16 con2/6confirmaciones
porseed;Q8corta enGPU3800,535MiB antesdeinferir. Es margen de diagnóstico, debajo
4096MiB; no resultado semánticoQ8. Buffers Q8CUDA2951,28pesos+637,5KV+94,73compute;
CPUHost1519,27pesos+280,5KV. Offload26/37 incluye25bloques+salida (no suponer salida
siempreCPU enparcial).480 reduce ub256→128 paraambos, sin trasladarmáspesos aCPU,
con fuente/registro/guardas intactos. Revisar susresultados antesdedecidir promoción.

## 481 — precisión de pesos comparada, sin adopción
Q8 pudo completar con NGL24/microbatch128; Q4 se midió con esos mismos ajustes.
Los32 primeros payloads conservaron fuente466 y perfil oficial2507.32 stop naturales,
sin reintentos. Ambos2/6 confirmaciones en cada semilla;4/4 controles memoria.
Q8 recupera destino/algún objeto, no irreversibilidad/sync/activaciónES. Su pico fue
3578,934MiB GPU/2509,336MiB RAM,65,516s frente2457,613/1848,004MiB/34,953s Q4.
No adoptar ni barrer precisiones intermedias: coste mayor sin resolución del bloqueo.
Esto no prueba inferioridad general de Q8 ni recursos de BAXY completo. Ver RESULT.md,
ADJUDICATION.json y PINS.json en astra-qwen-precision481. Sin cambios fuente/registro.

## 482 — Qwen3.5-9B con perfil propio y backend corregido
Se heredan388/390/441 y se aplica el perfil general no-thinking de
https://huggingface.co/Qwen/Qwen3.5-9B; informe oficial https://qwen.ai/blog?id=qwen3.5.
Reproducción de mantenedor https://github.com/ggml-org/llama.cpp/pull/28068: mecanismo
GDN aplicable, cifras en otros pesos/tamaños no extrapolables. b10865 ya auditado454/455.
NGL14/no-mmap/cache0,4096×3/KVq8, perfiles efectivos y template guardados.16composiciones,
19stop naturales,3reparaciones;4/6+2/6confirmaciones,2/4memoria. GPU2901,383MiB,
RAM3838,629MiB/170,328s. Sin promoción: intercambia fallos y conserva error de sujeto.
Es calificación con versión/perfil actualizados, no atribución a un solo factor ni
conclusión global contra9B. Fuente/registro intactos. Ver astra-qwen9b-profile482.

## Cierre de las pruebas nativas 491–497

Los contratos completos y la polaridad explícita de audio.mute (491/492) mejoraron unas respuestas y empeoraron otras. El campo de entrada real es state: true silencia y false reactiva; muted pertenece a observaciones. No se adoptaron las variantes.

Gemma E2B publicado, con perfil Google y thinking/lazy-on/b10809 (493), repitió operaciones. 494 comparó generación cruda y llamadas parseadas: eran iguales, por lo que el parser no insertó esas llamadas. 495 falló HTTP antes de generar; no es un resultado del modelo. 496 cambió únicamente gramática, grammar_lazy y disparadores en cuatro pares con parámetros efectivos iguales: quitarla eliminó extras, pero introdujo una operación no declarada y prosa de éxito previa a ejecución. No se adoptó.

497 comparó el Gemma E2B-it original Q4 (SHA740185...) con el publicado, ambos bajo gramática nativa y perfil Google T1/top_p.95/k64/min0, thinking y lazy-on. Tres prompts renderizados coincidían exactamente con494. El original evitó extras en14 respuestas, pero invirtió el silencio en3 respuestas contextuales y violó la interfaz sin argumentos en4. RAM1030,965/GPU1681,988MiB,62,719s; sólo nativo. No promoción ni conclusión global sobre toda una familia.

Fuentes primarias del mecanismo: documentación específica de Gemma4 sobre function calling y formato de prompts (https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4 y https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4); fuente llama.cpp5266f24da archivada en privado494/495. Los reportes de usuarios21375 y22786 tienen otras versiones/condiciones y no prueban por sí solos la causa de BAXY. RESULT, ADJUDICATION y PINS de491–497 conservan perfiles, fallos y límites.

## Reparación del producto y comprobación 502

498 protege las cláusulas con pero/but y el texto citado;500 comparte ponle entre lectura y delimitación;501 conserva una respuesta numérica sólo frente a un pedido previo del usuario con contrato de nivel incompleto, y prueba nivel/polaridad en la materialización. No cambia modelo ni sampler. Siete suites:3377 pass y121 subtests,0skips; Fast verde.

502, con runtime registrado, entrega12/14 propuestas/aclaraciones correctas y10/10 bindings correctos. Owner51 pasa de error6,188s a turno0,484s y plan con level100/statefalse. RAM1773,180/GPU3497,559MiB,45,297s; mente y conductor, sin UI/voz/efectos. Persisten owner46 y definición defectuosa. Es comparación de regresión del código, no una clasificación de capacidad de modelos a partir de defaults. 503 trabaja sobre la pérdida del marco de petición y la familia desilenciar; aún en validación. CHECKPOINT.md manda para el estado vigente.

## 503–508: separar fallos de fuente y configuración de conversación

503 resuelve la petición explícita tras asentimiento y la familia desilenciar.504:13/14propuestas,11/11bindings correctos.505 demuestra que initial_reply salta la generación con identidad/idioma y publica la prosa del selector; retirarlo mejora4/7→5/7 en conversación.506 elimina la ruta completa, sin nuevos prompts/modelos:3404pass+121subtests,0skips/Fastverde.507 integrado:18/20útiles y11/11bindings; siguen definición inexacta y recuerdo que prioriza una afirmación del asistente sobre la del usuario.

508 aísla el perfil oficial exacto de Qwen2507 (https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507):T0,7/top-p0,8/k20/min0/presence0/repeat1 frente al registrado, semillas0/17. Ambos5/7 porsemilla.28/28generaciones con perfil efectivo auditado;84respuestasHTTPstop; máximos87salida/2223total, sin cortes. RAM1770,398/GPU3497,559MiB,74,313s. No promoción ni otro barrido de parámetros sin causa nueva. Fuente506 permanece.

Siguiente509 contrasta una regla de procedencia de hechos personales con historial íntegro, mismo perfil propio en ambos brazos. https://arxiv.org/abs/2602.24287v2 documenta contaminación por respuestas propias y filtrado selectivo; no se extrapolan sus ahorros ni se borra todo historial. Carter LLM_CONTEXT_MEMORY_AUDIT.md13/54–63 distingue fuente, pero su propuesta de prioridad OS contradice la identidad vigente y no se adopta. La prueba local decidirá, con controles de corrección humana, otra persona y referencia a palabras del asistente. No confundir este diagnóstico con aceptación de un modelo.


### Actualización 508–518: distinguir perfil, historial y pérdidas de código

La adjudicación508 v2 prevalece sobre el recuento preliminar: ambos perfiles de Qwen2507 obtuvieron5/7 con semilla0 y6/7 con semilla17. Se corrigió una expectativa demasiado exhaustiva de la definición de desmutear; las acepciones de salida de audio y recepción de contenido son válidas. No se cambió el criterio para favorecer un perfil.509 confirmó que una instrucción de procedencia aislada no corrige el nombre errado del historial; los controles nuevos ya pasaban en el brazo original.

510 conservó literalmente todo el historial y sus autores como datos, con el pedido actual separado. Corrigió el nombre del usuario en ambos ensayos y conservó la capacidad de citar lo que había dicho el asistente.511 aisló sólo temperatura0 en22 payloads emparejados con510:22/22 útiles.512 adoptó la representación acotada de conocimiento y su reparación; los lectores, historial almacenado, otras formas de presentación y perfil registrado se conservaron.3406 pruebas Python y121 subpruebas pasaron, sin skips, más Fast.513 verificó24/24 conversaciones y planes de desarrollo y11/11 bindings con el registro real, sin tratamiento privado. Esto no es una nueva comparación universal de modelos ni aceptación fresca.

514 verificó memoria sintética y conversación en el conductor real:7/8 finales útiles.515 comparó la vista original con retirar metadatos redundantes de éxitos privados: ambos7/9; la prosa siguió hablando como un reporte interno. No se adoptó. La deshabilitación añadida no alcanzó la operación porque el parser sólo reconocía ciertas frases exactas. Ese rechazo se había convertido ya en outside what I do antes de llegar al redactor; no se atribuye al modelo ni se intenta arreglar con muestreo.516 reemplaza esos alias con gramática acotada de la misma memoria privada;36 controles focales y1962 pruebas de memoria pasan, cero skips, más Fast.517 se ejecuta con fuente516 para verificar el efecto real y enabled=false, sin el filtro rechazado.

La auditoría518, sin inferencia, resolvió las raíces de tres fuentes FunctionGemma referidas por el extractor histórico.15510 filas estables y0malformadas;92 de204 candidatos se solapan con campos o líneas exactas/normalizadas.112 quedan sin coincidencia en ese cruce,101 con original completo. No es certificado de frescura: falta contexto, otras fuentes y exposiciónC03 posterior a483; quedan0casos congelados o ejecutados. Los textos de reserva no se usan para estas reparaciones.
