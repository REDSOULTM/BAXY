# Palancas del PC (fase A, goal «BAXY Renew al máximo»)

Base: `pc-system-one` 86991ca9d; desde las 14:3x `renew-maximo` = base + `hub/pc-cu` fusionado (c1177101d, decisión
del dueño). Áreas del PC: 1 bucle de la mente, 2 presentación, 4 System One, 5 kernel y riesgo, 8 honestidad,
9 velocidad percibida, 13 estado del arte. Cada área la investigó un subagente de sólo lectura (código entero más
fuentes 2024-2026, enlaces abiertos). «Medida» = cifra propia; «esperada» = estimación del investigador. Ninguna
ganancia de esta tabla está medida todavía salvo donde se dice.

## Línea base medida (PC, 2026-10-22, c2e1, temp 0,2, seed 0, catálogo `renew_v4\catalog-base.json`)

| Banco | S1 apagado | S1 encendido | Nota |
|---|---|---|---|
| decision2 (268) | 231 | 233 | sin los 9 ids que están en los datos de Laya: 223/259 → 225/259 |
| acciones equivocadas en decision2 | 25 | 19 | |
| p50 / p90 de decisión | 0,937 / 1,563 s | 0,875 / 1,795 s | |
| escenas de práctica (39) | 32 | 32 | idénticas; p50 4,37 s / 2,71 s |
| VRAM (notebook, measure_resources) | 3 902 MiB | **4 091 MiB** | Laya usa GPU sin `--device none` (NB) |
| RAM del producto (notebook) | 2 438 MiB | 2 719 MiB | |

Primera corrida de decision2 sin S1 cayó con «bad allocation» (RAM del PC: el dueño usa Ableton, 7 GB); se repitió
sola. Ruido: con la semilla fija, una corrida es una muestra; el ruido se mide con `BAXY_RENEW_SEED` (en curso) y con
réplicas por edición neutra (palanca 12.3 del NB).

## Tabla (columnas de MAXIMO.md)

Máquina dueña: PC = `src/baxy_mind`, App, Core, Kernel; NB = providers.

| # | Palanca | Área | Evidencia | Fuente | Ganancia esperada | Banco | VRAM / RAM / latencia | Riesgo | Esfuerzo | Medida o esperada | Máquina |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1.1 | Compactar los resultados de turnos ya cerrados (cuerpo → «omitido, míralo de nuevo»; quedan las llamadas y su línea de estado) antes de tirar turnos | 1 | `mind.py:318-324` (historial ≈3,3k tokens); un turno de 5+ llamadas ocupa 3,6k p50 (traza) | [Complexity Trap](https://arxiv.org/abs/2508.21433); [Anthropic context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing); [ACON](https://arxiv.org/abs/2510.00615) | de ~3 a 6-8 turnos recordados | falsedades (multi-turno), uso real | 0 / 0 / una relectura al compactar | pierde ids viejos (la regla 10 ya obliga a releer) | medio | esperada | PC |
| P1.2 | Si el turno abierto no cabe, quitar historial antes de forzar el final | 1 | `mind.py:834-845,869-875`; 15 `context_shrunk` en la traza, cada uno cerró la misión | Anthropic context editing | misiones largas del e2e | e2e | 0 / 0 / igual | nulo | bajo | esperada | PC |
| P1.3 | Contar el historial con `usage.prompt_tokens` y no con `json.dumps` tokenizado | 1 | `mind.py:724-730` | — | más historial por el mismo presupuesto | sesión larga | 0 / 0 / −5-20 ms | nulo | bajo | esperada | PC |
| P1.4 | Recortar con histéresis (al llenarse, bajar al ~60 %) y precalentar en ocioso | 1, 9 | `mind.py:711-722`: 28 % de los `turn.decide` releen >500 tokens (p50 761 / 701 ms; p90 2,5k / 1,6 s) | [PR #24176](https://github.com/ggml-org/llama.cpp/pull/24176) | −0,5 s p50 en ~19 % de los decide; −1,5-3,6 s en sesiones largas | sesión de 20 turnos (`prompt_n`) | 0 / 0 / − | menos turnos a ratos (P1.1 lo compensa) | bajo | esperada (cifras de traza) | PC (= NB 3.2) |
| P1.5 | Contexto 49 152 → 53 248 | 1 | 8 capas de atención × 4 cabezas KV × 256, q8 → ~17 KB/token | [config Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/config.json) | +4k tokens de historial | falsedades | +68 MiB / 0 / 0 | VRAM: sólo con 3.1 hecho | trivial | esperada | PC |
| P2.1 | Regla 2 del sistema en dos: «¿ya lo hiciste?» se contesta por la conversación; «¿cómo está X?» se mira | 2 | `mind.py:42-45`; holdout de ayudas: 26/30 errores de la familia falsedad = comprobar con herramienta en vez de contestar | [Anthropic, building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | falsedades; familia «falsedad» del holdout | falsedades ×6, decision2 | 0 / 0 / ~20 tokens (relee sólo el sistema) | texto entrenado | bajo | esperada | PC |
| P2.2 | Defectos de las descripciones (sólo datos): «mensaje normal» → `message_send`; `system_settings_set` 1 = encender / 0 = apagar; `placeValue` sólo con `results` y `game`; `newDocument`; `input_scroll` en vez de `input_pointer_control`; `browser_navigate` sin contradicción | 2 | `tool_descriptions.en.v1.json:107,49,85,142,7,28,29`; `ProductCatalog.cs:1471`; proveedores exigen 0/1 (`WindowsDeviceControlAdapter.cs:542,2180`) | [Anthropic, writing tools](https://www.anthropic.com/engineering/writing-tools-for-agents) | filas de mensajería, modo avión, búsquedas en apps | decision2 ×3 | 0 / 0 / relee el prefijo una vez | prefijo entrenado (cambios pequeños) | bajo | esperada | PC |
| P2.3 | Constantes del esquema como constantes: `version` 1..1 y `selector: null` (11 herramientas de memoria); `null` fuera de los `enum` (16 propiedades) | 2, 5 | `mind.py:408-422`; `ProductOperationSchema.cs:263-266` | [PA-Tool](https://arxiv.org/abs/2510.07248v1) | menos `invalid_arguments` en memoria | decision2 | −~150 tokens | prefijo | bajo | esperada | PC |
| P2.4 | Una sola ruta (`path` «como la dijo») en las herramientas de archivos | 2 | E006/E020 0/27 (`PROGRESO.md:2580-2588`); el proveedor ya resuelve rutas (`WindowsKnownFileAdapter.cs:763-790`) | [Anthropic, building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (poka-yoke) | E006, E020, E017, E024, E027: hasta +2 por semilla | e2e ×3, decision2 | −300 tokens | el más contrario al ajuste (180 `file.write` con `home`); retira la ayuda 3b | alto | esperada | PC + NB |
| P2.5 | Significado en el argumento y no en la prosa (file_find, window_resolve, web_search) | 2 | 300 de 352 propiedades sin `description` | [Trace-Free+](https://arxiv.org/html/2602.20426): Qwen3-4B RestBench 54,1 → 62,1 | argumentos | decision2, e2e | ~0 | prefijo | medio | esperada | PC |
| P2.6 | Quitar del prefijo 64 entradas de apps de ayuda/desinstalar/manuales y la copia doble de `{app_places}` | 2 | `mind.py:524,544` | [Less is More](https://arxiv.org/abs/2411.15399) | −0,6k tokens (≈10 MB, más historial) | decision2 | − | filtro que se lleve apps reales | bajo | esperada | PC |
| P4.1 | Candidatos de duda sin rollout: los nombres del catálogo que empiezan por el token rival (trie); fuera `complete_name` y `/apply-template` por rival | 4 | `mind.py:963-977`, `llm_server.py:106-114`; turnos con S1 1,9 s p50 frente a 0,9 s | [Apple, incertidumbre en function calling](https://arxiv.org/abs/2604.22985) | −0,8 s por turno dudoso, mismos aciertos | decision2 S1 on (latencia y acierto idéntico) | 0 / 0 / −0,8 s | nulo | bajo | esperada (traza) | PC (= NB 3.5) |
| P4.2 | Una pregunta por malentendido: tras contestar un `ask_user` o una pregunta de duda, la capa 0 no vuelve a frenar (va a Laya/«corrige») y Laya ve la pregunta | 4 | `mind.py:623-633,925-938` | [SAGE-Agent](https://arxiv.org/abs/2511.08798) | bucles de aclaración | e2e, escenas | 0 | bajo | bajo | esperada | PC |
| P4.3 | Laya v6: opción «ninguna de estas» y pérdida Gatekeeper; «corrige» sólo con p de Laya ≥ τ | 4 | `build_kev_data.py:107-110` añade siempre el oro (979) y al servir nunca (`mind.py:969-970`); en la franja de duda Laya elige otra equivocada 6 veces | [Gatekeeper](https://arxiv.org/html/2502.19335v3) | −3 a −6 acciones equivocadas con «corrige» | decision2 sin los 9, devmix, calib | 0 / 0,6 GB igual / 0 | fugas (canario y `fuga.py`) | medio (reajuste) | esperada | PC |
| P4.4 | Umbral de duda por riesgo, fijado con control conforme del riesgo sobre calib | 4 | `mind.py:932-934`; ECE 0,04 en decision2, 0,13-0,16 en massive (agregados del investigador) | [CRC](https://arxiv.org/abs/2208.02814) | menos preguntas en lecturas, más frenos en lo caro | decision2, falsedades | 0 | sobreajuste | bajo | esperada | PC |
| P4.5 | Duda de argumentos sólo en valores de texto libre que no están en el pedido | 4 | AUROC 0,84-0,89 dentro de acciones con la operación correcta; 32/53 errores de devmix son de argumento | Apple (arriba); SAGE | argumentos (devmix, sint) | decision2, e2e | 0 | más preguntas | bajo | esperada | PC |
| P5.1 | Hecho tipado de efecto en el catálogo (`window_input`, `network`) que excluye de «corrige» lo que toca la ventana de la persona o la red, y sustituye las listas por nombre `SendsInputToAWindow` / `ReachesTheNetwork` | 5 | `mind.py:349,953`; `NativeTurnLoop.cs:484-519` («the catalog has no typed fact for it yet») | [Anthropic, writing tools](https://www.anthropic.com/engineering/writing-tools-for-agents) | «corrige» seguro por construcción; menos código | decision2 S1, pruebas | 0 | nulo | medio | esperada | PC |
| P5.2 | Fusionar casi-duplicados del catálogo sin perder cobertura (`clipboard.copy/paste` y `input.select.all` frente a `input.key.press`; `wifi.ensure.connected`/`wifi.status`; `wifi.connect`/`.named`; `system.settings.adjust` ⊂ `.set`; `media.play.exact`/`.query`; `message.send.test` fuera de producción) | 5 | `ProductCatalog.cs:309,315,835,737,1724,1754,1697,1707,1442,1454,952,963,1132` | Anthropic; [Less is More](https://arxiv.org/abs/2411.15399) | −8 herramientas, ~3,5k caracteres | decision2, cobertura una a una | − | cobertura (regla del dueño) | medio | esperada | PC |
| P5.3 | Errores accionables: `invalid_arguments` con `argumentProblems` (argumentos aceptados, enum más cercano) en los 20 handlers que hoy lo dan pelado | 5 | `ProductOperationSchema.cs:538,557`; `WindowControlHandlers.cs:108-110` y otros | Anthropic, writing tools | reintentos en una vuelta | e2e | tokens sólo en error | nulo | medio | esperada | PC |
| P8.1 | Registro de la sesión en el mensaje del reloj (qué herramientas corrieron en la sesión y con qué estado; «ninguna» si ninguna) | 8 | `mind.py:584-597`; F015 = 5 de las 10 falsedades de B y «ninguna ayuda del resultado lo toca» (`PROGRESO.md:2603,2678`) | [Tool Receipts](https://arxiv.org/html/2603.10060); [A-CC](https://arxiv.org/abs/2512.00332) | F015 (la mayor clase restante) | falsedades ×6, decision2 ×3 | 20-80 tokens en el sufijo | nulo (hechos) | bajo | esperada | PC |
| P8.2 | Campo `verification` tipado desde el kernel (`readback`, `delivered_only`, `unchanged`, `output_only`, `none`) que retira la heurística de nombres de `_outcome`; `changed:false` deja de narrarse como cambio | 8 | `mind.py:106-146`; `ExternalCapabilityHandlers.cs:334-345`; `observedLimit:"omitted"` leído como «sin verificar» (`mind.py:139`) | Tool Receipts; Anthropic | F004, F013 | falsedades, sonda | 0 | nulo; retira una heurística | medio | esperada | PC |
| P8.3 | Releer el estado tras un fallo ambiguo cuando hay lector barato (papelera, ventana, volumen) | 8 | `WindowsRecycleBinAdapter.cs:41-42`; `ExternalJson.cs:66-73` | [VeriSafe](https://arxiv.org/html/2503.18492v1) | falsedades de «vacié/cerré» | falsedades | 50-300 ms sólo en fallos | nulo | medio | esperada | NB (providers) |
| P8.4 | La mirada dice primero lo seleccionado/activo | 8 | `ScreenViewProjection.cs:107-115,239-245` | [A11y-Compressor](https://arxiv.org/pdf/2605.00551) | «leyó mal la vista» (1 → 3 en ayudas) | e2e E015, sonda F019 | ~0 | nulo | bajo | esperada | PC (App) |
| P9.1 | Pasos de Supertonic 10 → 6-8 | 9 | `make_baxy_voice.py:23`; voz → primer sonido 1 544 ms p50 / 2 701 p90 (traza; Piper era 138-365 ms) | [Supertonic ONNX](https://huggingface.co/onnx-community/Supertonic-TTS-ONNX) (5 por defecto) | −250 a −550 ms por respuesta hablada | `sound_ms` en la traza | 0 / 0 / − | calidad de la voz: **juicio del dueño** | trivial | esperada | dueño |
| P9.2 | Señal no verbal temprana (sonido corto a ~1,2-1,5 s si no sonó nada) en vez de «Un momento.»; el aviso se cierra al sonar y no al publicar | 9 | `mind.py:31` (texto fijo: viola el invariante), `SilenceNotice.cs:95-103` | [LiveKit latency](https://livekit.com/blog/understand-and-improve-agent-latency) | `first_audio_over_3s` → ~0 | e2e (latencia) | 0 | que moleste | bajo | esperada | PC |
| P9.3 | Primera frase sintetizada sola (`JOIN_CHARS=120` junta el 84 % de las respuestas) | 9 | `voice_output.py:55,259-262` | [Pipecat metrics](https://docs.pipecat.ai/pipecat/fundamentals/metrics) | −300-700 ms en respuestas de dos frases | `sound_ms` | 0 | prosodia | trivial | esperada | PC |
| P9.4 | Final en streaming con presíntesis de la primera frase (nada suena antes de publicar) | 9 | `llm_server.py:92-104` | [PR #12379](https://github.com/ggml-org/llama.cpp/pull/12379) | −100-250 ms p50; −0,5-0,8 s en respuestas largas | `sound_ms` | 0 | parser en streaming | medio | esperada | PC (= NB 3.7) |
| P9.5 | `top_logprobs` sólo en `turn.decide` | 9 | `mind.py:859` | [server-common.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/server-common.cpp) | −20-100 ms por llamada de continuación | latencia | 0 | traza de duda en continue | trivial | esperada | PC |
| P9.6 | El latido cancelable cuando habla la persona, y precalentar tras el latido | 9 | `__main__.py:100-158`; 78 decide releen tras un latido (p50 668 ms) | — | −0,5 s en ~9 % de los decide | traza | 0 | aborto de llama-server (sin verificar) | medio | esperada | PC |
| P13.1 | Pista de herramientas candidatas DESPUÉS del prefijo («soft masking»), sin recortar el catálogo | 13 | la lista corta ya existe (`scripts/renew/system_one/shortlist.py`, recall@16 98,6 %) | [DTDR](https://arxiv.org/html/2512.17052v3) (Qwen3-4B 59,6 → 80,7 recortando); [TinyAgent](https://arxiv.org/html/2409.00608v3) (el recall manda) | +2 a +5 en decision2 | decision2 (primero con pista oráculo = cota) | 0 / +~100 MB / 5-20 ms + 30 tokens | el modelo ajustado nunca vio pistas; parecida a la 9 descartada | medio | esperada | PC |
| P13.2 | Repetir la petición de la persona al final del turno | 13 | — | [Prompt Repetition](https://arxiv.org/abs/2512.14982v1) | 0 a +2 | decision2 | 20-50 tokens | formato no visto | trivial | esperada | PC |
| P13.3 | Enums del catálogo en la gramática (nombres y valores) | 13, 2 | llama.cpp no restringe enums de texto en el XML de Qwen ([qwen3-coder.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/b11609/common/parsers/qwen3-coder.cpp)) | [function-calling.md](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) | +1 a +2 | decision2 (primero medir enums inválidos) | 0 | convierte un rechazo honesto en un valor equivocado; fork | alto | esperada | PC |

## Defectos confirmados de la revisión (fase B adelantada; cada uno se arregla con su prueba)

Arreglos en marcha en worktrees: `fx-mente` (mind.py y compañía), `fx-voz` (voz Python); App y Core/Kernel cuando
haya RAM. B-SYS-1 lo arregla el notebook.

**Seguridad e invariantes (primero):**
- **B-SYS-1** `file.write`/`file.edit` con `folder:home` pueden escribir `%LOCALAPPDATA%\BAXY\1\confirmation-mode` =
  `bypass` sin preguntar (y System One podría «corregir» hacia ellas): `ConfirmationModeStore.cs:540-562`,
  `LocalFilesystemProvider.ResolveIn`. → NB.
- **K-1** `input.pointer.control {click}` hace un clic ciego en la ventana bajo el puntero sin regla
  (`RiskPolicy.cs:148-156`; corregible por S1).
- **K-2** Enter/Espacio sin `target`/`onto` nunca preguntan (`RiskPolicy.cs:254-255,284-285`): `message.draft` +
  Enter manda un mensaje sin el sí que `message.send` exige.
- **K-3** Bypass sólo pregunta por `message.send`; `email.send`, `email.latest.reply` y escribir+Enter van directos
  (`RiskPolicy.cs:59`). Decisión del dueño de 2026-10-21 (un mensaje a otra persona pide el sí también en Bypass).
- **M-1** Una llamada en cola se ejecuta aunque la anterior falló (`mind.py:810-811`).
- **A-1** Sesiones en claro con secretos y resultados de memoria; sobreviven a «olvida todo»
  (`FieldSessionStore.cs:74`, `mind.py:610`). = NB B-SYS-2.
- **A-2** El Sí/No de una tarjeta se pierde con `ok:true` durante otro turno y no va atado a la tarjeta pulsada
  (`FieldProductChannel.cs:138-144`).
- **A-3** «Bypass · hecho sin preguntar» se publica aunque la llamada falló, y es prosa escrita en C#
  (`FieldProductChannel.cs:306-311`).
- **M-6 / A-9** Textos visibles fijos: `NOTICE = "Un momento."` (`mind.py:31`) y textos de la App (decidir con el
  dueño qué es adorno de interfaz).
- **M-4** La traza guarda lo deducido de la memoria en el latido y el texto de `doubt_ask` de memoria.

**Robustez:**
- **M-2** Si llama-server muere, la mente no se reinicia por la vía de `decide` y deja pedidos viejos en la
  conversación. **M-17** plazos: la App corta a 30 s, la mente espera hasta 120 s.
- **M-3** `ref:rN` no se exportan ni se vacían: tras relanzar apuntan a otra URL.
- **M-5** Duda mal calculada con texto antes de la llamada (`doubt.py:32-39`).
- **M-7** Llamada mal formada como texto crudo visible en un paso no final.
- **C-1** `task.create` con 512 documentos tumba el core (exit 70) (`TaskHandlers.cs:34-68`).
- **C-2** Un resultado reintentable llega al modelo como `failed` y no `pending` (`OperationVisibleFacts.cs:79-96`).
- **C-3** Modo accesible: «no pude leer» se toma como «apagado» (`ExternalCapabilityHandlers.cs:177-203`).
- **C-4/C-5** `app.open` con lugar: el fallo no dice que la app sí se abrió; el éxito no dice que el lugar no se
  verificó si las ayudas están apagadas (`AppOpenHandler.cs:121-143`).
- **C-7** `windowHandle` llega al modelo (`OperationVisibleFacts.cs:551-558`; confusión E007).
- **K-5** Una cadena con surrogate suelto tumba el core (`RequestFingerprint.cs:54`).
- **A-4..A-8** carreras de sesión en la App (abrir sesión sin tomar el turno, dos arranques de la mente, nueva
  conversación sin esperar a la mente, mente relanzada sin su sesión, confirmación vencida contada como «otra cosa»).
- **V-1..V-3** voz: candado retenido durante la transcripción, `speak` rechazado con efectos, cierre del stream desde
  otro hilo; `voice.start` tardío abre el micrófono; `voice.release` espera detrás de un turno.

**Pruebas que no prueban:** el Sí/No de la mente, los umbrales 0,4/0,6 en el borde, el apagado de la capa 2,
«corrige» con riesgos no corregibles, `SystemOne` y `fill_call` sin ninguna prueba; la App no tiene proyecto de
pruebas; pruebas de providers que leen el código fuente como texto (`X1EnvioBusquedaTests.cs:108-131` y 4 más).

## Descartadas en la investigación, con su porqué

- **Lista corta dinámica en el prompt de Qwen**: la plantilla de Qwen3.5 pone las herramientas antes del sistema;
  cambiarlas relee el prefijo entero (3-7 s por decisión frente a 0,19 s) y el modelo ajustado nunca vio 16
  herramientas ([chat_template](https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/chat_template.jinja)).
- **Pensamiento (aunque sea sólo en duda)**: el brazo THINK de la decisión 20 dio −43 en decision2, 3× más lento y
  falsedades en cadena (buzón NB 2026-10-16 14:19); [The Reasoning Trap](https://arxiv.org/abs/2510.22977).
- **Best-of-n con verificador**: la ganancia publicada pide n=32 y un RM de 14B ([ToolRM](https://arxiv.org/html/2509.11963v2)).
- **Decodificación especulativa MTP**: desactiva `--cache-reuse` y el GGUF ajustado no trae cabeza MTP.
- **Calibrar una sola puntuación (Platt, temperatura)**: es monótona, no cambia ninguna decisión con umbral fijo
  (agregados del investigador del área 4); **subir el umbral de Laya a 0,7** (+1 equivocada frenada por +1 correcta en
  decision2); **multiplicar duda de nombre por duda de argumento** (empeora la cola).
- **Bajar `--ctx-checkpoints` sin cuidar el del final del prefijo**: es el que evita releer 42k tokens (~25 s) tras
  un latido o un recorte (área 1) — choca con la 3.3 del NB: se verifica cruzado.
