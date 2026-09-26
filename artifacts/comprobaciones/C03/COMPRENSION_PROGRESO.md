# Fase 3.5b «comprensión natural» — progreso (fuente de verdad ante un corte)

Goal: [`PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md`](PROMPT_OPUS_COMPRENSION_NATURAL_2026-09-25.md). Decisiones sin
el dueño: [`DECISIONES_COMPRENSION_2026-09-25.md`](DECISIONES_COMPRENSION_2026-09-25.md). Rama `codex/kiro-goal-c03`.

## Punto de partida

- Tag local `opus-cn-inicio` = `4f510ee7` (informe de la verificación encima de `b34c3f39`; `src` idéntico a
  `b34c3f39`).
- Al empezar seguía corriendo la segunda verificación completa de la sesión anterior (`verify_chain2.sh` sobre
  `b34c3f39`: 742, capas, reserva MASSIVE, guion y held-out, cien-103, tandas 1–10 en la ventana). Mide el mismo `src`
  que el punto de partida: es la base del conjunto de regresión (D2).

## Estado por fase

| Fase | Estado | Cifra |
|---|---|---|
| F0 etiqueta y ficheros | hecho | — |
| F1 conjuntos DEV-A / DEV-B / FINAL + puntuador + base | **hecho** | DEV-A 59,6 %, DEV-B 69,2 % |
| F2 diagnóstico por camino + modelo libre | **hecho** | Qwen3.5-4B libre: DEV-A 70,0 %, DEV-B 77,5 %, seguimientos B 84,8 % (`DIAGNOSTICO_F2_2026-09-25.md`) |
| F3 torneo de modelos | **hecho**: gana Qwen3.5-4B | 393/513 (76,6 %), seguimientos 112/134; ninguno lo desplaza (`DIAGNOSTICO_F2_2026-09-25.md` §F3) |
| F4 mecanismos | **M8 entra** (D18); falta retirar el camino viejo de la suite (ley 2) | producto DEV-B 78,3 %, seguim. B 80,3 %, capa A 96,4 %, reserva 84,0 %, VRAM 3 804 MiB |
| F5 ventana oficial con DEV-B | pendiente | — |
| F6 cierre (FINAL una vez) | pendiente | — |

## Dónde está cada cosa

- Conjuntos (privados, fuera de git): `%LOCALAPPDATA%\BAXY\comprension-2026-09-25\sets\` (D3). Scripts que los
  construyen y encargos de los subagentes: `comprension-f1/` (junto a este fichero).

## Conjuntos de F1 (cerrados 2026-09-25 12:40)

| conjunto | turnos | sueltos | en conversación (conv.) | seguimientos que dependen | SHA-256 |
|---|---|---|---|---|---|
| DEV-A (se miran sus fallos) | 260 | 125 | 135 (35) | 68 | `cffb39cd90ba378c92902401f48da8330712a0d0233f0d89985d0c7ad7044e75` |
| DEV-B (sólo su cifra) | 253 | 125 | 128 (35) | 66 | `5f7eda2a1602c4b7e6cb9c0b5a17c0dad8c37bbf7e04d66f6c93b469b26462c9` |
| FINAL (sellado, sólo lectura) | 202 | 100 | 102 (27) | 57 | `e05cf27e8af6dca7d38f77689d866d0a94ddf19bd8bf203d5b9e2bc71323d993` |

- Sueltos por fuente en cada conjunto (por 125): MASSIVE val es 18 / en 10, MTOP test+eval es 14 / en 8, CLINC150 12,
  OVOS-ILENIA 12, CSTOP (spanglish) 20, PRESTO test es 14 / en 7 (code-mixing, disfluencias, auto-correcciones),
  oasst2 es 10. Ninguna frase ya vista (D4: 79 464 textos + 13 371 hashes).
- Conversaciones: públicas (PRESTO humano con contexto, SGD test, oasst2 es) + 54 escritas en sala limpia por tres
  subagentes (chileno, rioplatense, mexicano, colombiano, España, inglés EE. UU., spanglish; dictado, erratas,
  muletillas, cortés, seco, largo), repartidas por hablante entre los tres conjuntos (D6).
- Oro: escritores (sus conversaciones) y tres etiquetadores con ids opacos mezclando los tres conjuntos, según
  `comprension-f1/brief/REGLAS_ORO.md`. Auditoría a ciegas del 10 % (71 turnos): **acuerdo 70/71** (DEV-A 25/26,
  DEV-B 25/25, FINAL 20/20); el desacuerdo de DEV-A se resolvió a `limit`/`ask`.
- Base del conjunto de regresión: salidas de `verify_chain2.sh` en el scratchpad de la sesión anterior
  (`…\6f29a6a5-…\scratchpad\`: `lit-fin2.jsonl`, `layers-fin2.jsonl`, `uso\hold-fin2.jsonl`, `finc2\`, `cien-103`,
  `uso\fin2-NN.out`).

## Base de F1 en DEV (HEAD de partida, sólo decisión, `scripts/comprension_eval.py`, 14:28–14:48)

| | total | sueltos | en conversación | seguimientos que dependen | decisión p50 / p90 |
|---|---|---|---|---|---|
| DEV-A (260) | **59,6 %** (155) | 62,4 % | 57,0 % | 51,5 % (35/68) | 1,97 / 4,09 s |
| DEV-B (253) | **69,2 %** (175) | 77,6 % | 60,9 % | 53,0 % (35/66) | 1,98 / 4,03 s |

## Base del conjunto de regresión (HEAD de partida, `src` = b34c3f39)

| medida | base | cómo |
|---|---|---|
| capa A (768) | **96,5 %** (741) · registro real 90,1 % · 742 97,3 % | `semantic_corpus.py score` sobre `lit-fin2` + `layers-fin2`, referencia S8 |
| capa B (20) / capa C (1 000) | 45,0 % / 54,2 % | ídem |
| 742 sólo-decisión contra S8 | **14** decisiones distintas | `semantic_replay.py diff lit-s8 lit-fin2` |
| reserva MASSIVE (2 757) | **82,2 %** (2 265; decisión p50 0,93 s) | `score_big.py big-hold hold-fin2` |
| guion del dueño (60) / held-out (30) | **46/60** (+6 por revisar) / **24/30** — ambos bajo el «sin retroceder» del goal (53, 29): hay que recuperarlos | `semantic_replay.py summary --out finc2` |
| cien-103 | **95/100** (94 iguales + 1 mejor; mal: 008, 027, 096 pedido sin referente → límite falso, 037 «no lances Steam», 084 memoria tras session.new) | conductor; adjudicación contra cien-101 |

## F4 — mecanismos (regla D12 para M1; cifras estrictas de `comprension_eval.py`)

| mecanismo | DEV-B total | seguim. B | DEV-A | capa A (registro real) | reserva | 742 distintas de la base | veredicto |
|---|---|---|---|---|---|---|---|
| base | 69,2 % | 53,0 % | 59,6 % | 96,5 % (90,1 %) | 82,2 % | — | — |
| M1: decisor en contexto (V2) + Qwen3.5-4B, 12 288/ranura | 75,5 % | 87,9 % | 70,0 % | **93,5 % (70,3 %)** | 81,5 % | 24 | **no entra**: el registro real cae (quejas y charla con historial convertidas en acciones: «baxy, cierra baxy» → cerrar todas las ventanas) |
| M1b: V5 — con historial deciden los lectores de conversación (charla, quejas, social, límites) y el decisor el resto | 73,9 % | 80,3 % | 70,4 % | **94,9 % (82,4 %)** | — | 24 | **no entra** (capa A): catálogo opaco («ponme daredevil en disney» → límite, «tirame cuánta memoria tengo» → «no tengo acceso»), «buscá recetas de pizza» como charla |
| M2: + catálogo del decisor en lenguaje llano (dato de sala limpia, 204 líneas) + lo que el catálogo sí hace se hace + «buscar» es web.search | **77,1 %** | **86,4 %** | 72,7 % | 95,4 % (83,5 %) | — | 21 | no entra todavía (capa A 95,4 < 96,0): quejas con historial largo convertidas en acción; argumentos: 7–8 turnos por conjunto con la decisión bien (lector de lugar del clima, recordatorios) |
| M3: + política «un comentario o una queja no es un pedido», «las opiniones se buscan sin preguntar de dónde», «parar» en media.control | 76,7 % | 86,4 % | 71,5 % | 95,2 % (82,4 %) | — | 22 | **retirado**: no mueve nada (ley 2) |
| V6 (simulado): con historial, los mensajes autónomos según `dialogue.dependency` por la tubería vieja | 180/253 | 46/66 | 179/260 | registro real 84/95 (M2: 80) | — | — | **descartado**: el detector da por autónomos 57–70 seguimientos reales |
| M4: M2 + el decisor ve los últimos 4 mensajes (no 12) | 77,1 % | 86,4 % | 72,7 % | 95,6 % (84,6 %) | — | 21 | se queda (igual en DEV, +1 en el registro real, menos prompt); capa A aún a 4 filas del umbral |
| M5: M4 + guarda de forma sobre acciones del decisor en mensajes autónomos con historial | 76,3 % | 83,3 % | 71,9 % | 95,4 % (83,5 %) | — | 21 | **retirado**: peor en todo |
| M6: M4 + segunda elección sobre la elección del decisor y 10 recuperadas para el pedido reescrito | 73,1 % | 77,3 % | 70,0 % | 95,6 % (85,7 %) | — | 23 | **retirado**: la lista corta vuelve a cambiar elecciones buenas (ley 1) |
| M7: M4 + argumentos: el lector del clima ya no toma «Denver»/«para Rosario» por un infinitivo; la extracción omite el opcional no dicho (vacío o no literal) en vez de abstenerse de todo | argumentos sólo (turnos con decisión bien y oro de argumentos): DEV-A 31→33/40, **DEV-B 33→34/41** | | | | | | se queda (0 rotos; pytest de extracción y clima: las mismas fallas con y sin el cambio, todas de la ruta M4). Resto: servicio de streaming perdido en la reescritura, archivos por referencia, pedido reescrito en otro idioma («airport» → «aeropuerto») |
| **M8: M7 + LoRA del decisor (`full1`, D17) sólo en la llamada del decisor** | **78,3 %** (sólo decisión 206) | 80,3 % | **82,7 %** | **96,4 % (92,3 %)** | **84,0 %** | 20 (8 mejor, 4 peor, 8 igual) | **entra** (D18): cumple toda la regla de D12; VRAM 3 804 MiB |
| M9: M8 + el decisor decide también los primeros mensajes que un lector prueba | 79,1 % | 80,3 % | 82,7 % | **70,3 %** (84,6 %) | — | 248 | **retirado**: en los comandos del dueño el LoRA vuelve planes una acción (48) o charla (23), y acciones charla (48); faltan planes en sus datos |
| M10: M8 + el decisor lee los mensajes largos que hoy se toman por conversación ajena (`overheard_speech`) | 78,3 % | 80,3 % | 83,8 % | **94,4 %** (84,6 %) | — | 30 | **retirado**: el registro real del dueño sí trae conversación ajena |
| M12: M8 + los reintentos del compositor muestrean (Qwen: T 0,7, top_p 0,8, top_k 20, semilla fija; el primer intento sigue greedy) + la pista de «missing_name» nombra el nivel observado | (no toca decisiones) | | | | | | **se queda**: en la app real, guion 46/60 (+8 por revisar), held-out 21 → **23/30**; Qwen3.5 repetía tres veces el mismo borrador rechazado («He bajado el volumen a 15» por 15 → 55) |
| M11: el camino viejo del modelo (lista corta, selector nativo, `llm.decide_turn`, re-decisión por familia) se retira; todo turno sin lector lo decide el decisor | 78,3 % | 80,3 % | 82,7 % | 96,1 % (90,1 %) | 84,0 % | 20 | **entra** (ley 2): igual que M8 dentro del ruido (±2 filas del registro real entre corridas); ningún turno de DEV, 742, registro real ni reserva pasaba ya por ese camino |
| M13: la re-lectura canónica también sobre los límites del decisor (sólo lo que los lectores prueban en la reescritura) | 78,3 % | 80,3 % | 82,7 % | 96,2 % (91,2 %) | 84,0 % | 20 | **entra**: arregla la tanda 3 del dueño («Pausa el speaker.» → media.control, micrófono y cámara → micrófono, «añadir una nueva lista…» → pregunta los ítems) sin mover ningún conjunto |

### Revisión de las 21 decisiones de las 742 que M4 cambia frente a la base

- **Mejor (7):** H0059 «NO te preocupes si se abrió steam» → charla; H0080 «funciona mi internet» y H0732 «tengo internet» →
  lee la red; H0142 «responde con un chiste» → lo escribe; H0253 «°F de 100 °C» y H0367 «100 dividido 4» → lo calcula;
  H0607 «y disco?» → estado del sistema.
- **Peor (6):** H0091 «ahí que me abre este» → límite falso; H0139 «¿de dónde es esto?» (letra) → «no tengo
  información»; H0313 «They are P Games.» → juego instalado; H0407 «nunca cierres spotify» → pregunta; H0506 «guardá que
  mi cumpleaños es el 5 de mayo» → crea un recordatorio; **H0711 «abrí mi carpeta de descargas» → fondo de escritorio**
  (el decisor reescribe bien «Abrir la carpeta de Descargas» y elige mal la operación: motiva M6).
- **Equivalente (8):** fragmentos sin contexto y preguntas equivalentes (H0173, H0271, H0353, H0354, H0414, H0513,
  H0582, H0604).

### Revisión de las 742 con M8 (20 distintas de la base)

- **Mejor (8):** H0059 «NO te preocupes si se abrio steam» → charla; H0080 «funciona mi internet» y H0732 «tengo
  internet» → `network.status`; H0139 dictado sin referente → pregunta (no busca); H0142 «responde con un chiste» →
  charla; H0253 °F/°C y H0367 «100 dividido 4» → se contestan; H0711 «abrí mi carpeta de descargas» →
  `filesystem.folder.open`.
- **Peor (4):** H0313 «They are P Games.» → charla que inventa un dato; H0407 «nunca cierres spotify» → pregunta;
  H0506 «guardá que mi cumpleaños es el 5 de mayo» → nota (lo propio va a memoria); H0604 «Como me llamo» → límite
  («no llamo»).
- **Igual (8):** H0271, H0353, H0354, H0373, H0414, H0513, H0607, H0623 (fragmentos y pedidos de ayuda: charla ↔
  pregunta).

### Guion del dueño y held-out en la app real (2026-09-26 06:42–07:19, runtime M8, audio 70 y devuelto a 61)

| | base (b34c3f39) | M8 | M8 + M12 |
|---|---|---|---|
| guion del dueño (60) | 46 (+6 por revisar) | 47 (+6) | 46 (+8) |
| held-out (30) | 24 | 21 (+1) | **23** (+1) |

- La primera corrida no arrancó la mente: el build **Release** de la App era del 25-09 y su lectura del manifiesto no
  conocía `decider_adapter` (rechazo del manifiesto entero). Release recompilado 06:41; los servidores de
  compilación de dotnet bloquean la compuerta de `semantic_replay conv` (`dotnet build-server shutdown`).
- Cambios del guion frente a la base: +4 (03, 11, 17, 42) y −3 (08 «Me gusta como se desenvuelven» → pregunta, 16
  y 26 ya recuperado por M12). Held-out: siguen mal 10–12 (el bloc de notas no se verifica: la lista de ventanas no
  se leyó, cadena de cierre), 14 y 16 (el compositor no publica la reseña hallada: «search_report_page_voice», ya
  mal en la base), 17 («tengo ganas de escuchar reggaetón» → Spotify sin resultados; la base iba a YouTube).
- El audio del dueño estaba en 61 sin silenciar (no 0 silenciado como decía el goal): se devolvió así.

### App real tras M13 (2026-09-26 11:45–11:51, runtime M8 + M11–M13; audio del dueño en 100 sin silenciar, devuelto)

- Guion del dueño **47/60** (+8 por revisar); held-out **26/30** (+1). Las subidas del held-out son de entorno (el
  bloc de notas se verificó y se cerró, Spotify encontró reggaetón); siguen mal 14 (el primer borrador copia el lema
  de la página, «nuestro destino», y el veto de voz de la página lo rechaza: termina en «No lo encontré»), 16 (esta
  vez la búsqueda misma falló; con resultados, el informe no nombraba la serie) y 18.
- Latencia visible (mensaje → primera respuesta, resolución 1 s): **p50 2,0 s**, p90 6 s, 10/90 sobre 5 s.
- Probado y retirado (ley 2): una instrucción para que el informe de búsqueda nombre de qué trata; en la corrida el
  caso que la motivó no llegó a redactarse, así que no hay efecto demostrado.

### Retirada del camino viejo (ley 2, plan tras M8)

Con M8, el camino viejo del modelo (lista corta, selector nativo, `llm.decide_turn`, vetos y verificadores del
efecto retirado) sólo sigue vivo dentro de la re-lectura de la superficie servida (`_served_surface_reread`), que
corre cuando un lector da un límite. La suite tiene ~165 pruebas en rojo que fijan ese camino para turnos que hoy
decide el decisor (LLM falsos sin `decide_in_context`). Plan M11: la re-lectura también la decide el decisor sobre
la reescritura; el camino viejo queda muerto y se retira con sus pruebas (y con ellas las que fijan guardas sobre el
decisor viejo). Los invariantes de seguridad (lo que borra, instala, paga o envía nunca actúa sin confirmación)
siguen en la App (riesgo del catálogo, confirmación ligada a la invocación). Se mide con la regla de D12.

### Retirada hecha (M11 + M13, 2026-09-26)

- `src`: `__main__` +55/−300 (rama del modelo tras la ruta, evidencia, selección nativa, `selector_declined`, veredicto
  por familia de la superficie servida, `_turn_evidence_query`, `_compound_clause_shortlist`,
  `_recogniser_identity_holds`); `llm.py` −1 243 (`decide_turn`, `_decide_turn` y los 10 ayudantes que sólo usaba él,
  `_reading_of`, `_greeting_is_the_whole_request`). Ninguna regla nueva.
- Pruebas: ~120 funciones que fijaban el camino viejo o el motor retirado se retiraron (turnos que hoy decide el
  decisor, medidos en DEV y en las capas); 8 nuevas fijan el contrato del decisor (`tests/test_context_decider_route.py`).
  Re-fijadas con cita: presupuesto de la reparación en JSON 160 (44e683ad), contexto por ranura 12 288, pregunta de
  reserva inválida descartada, sellos de identidad del programa.
- Pendiente de la misma línea: la prueba de la tanda 3 «inactiva la alarma de la casa» sigue siendo acción del decisor
  (dato para el próximo ajuste del LoRA).

## LoRA del decisor (D13, en curso)

- Datos: 9 escritores de sala limpia (`comprension-f1/brief/ENTRENAMIENTO.md`), 900 conversaciones, **1 991 ejemplos de
  entrenamiento + 111 de validación** (acción 66 %, charla 25 %, límite 5 %, pregunta 4 %; 257 mensajes de operar dentro
  de aplicaciones para computer use); 2 frases que coincidían con DEV/FINAL descartadas. Cada ejemplo lleva un catálogo
  parcial de 50 operaciones (las correctas, sus hermanas de familia y distractoras): el decisor aprende a leer el
  catálogo que tiene delante, así las operaciones nuevas del motor de computer use no piden reentrenar.
- Entorno aislado `D:\BAXYRuntime\python\c03-decider-lora-v1` (torch 2.8 cu126, transformers 5.17, peft 0.21,
  bitsandbytes 0.50, triton-windows 3.4 + flash-linear-attention 0.5.2 para las capas DeltaNet); base HF
  `Qwen/Qwen3.5-4B@851bf6e8`; QLoRA nf4, r 16, pérdida sólo en la respuesta. Medido: 7,9 s por ejemplo, pico 5,76 GB
  (sin flash-linear-attention: 20 s; con el catálogo entero no cabe en 6 GB).
- Conversor: llama.cpp b9980 (el mismo del servidor) en `D:\BAXYRuntime\build\llama.cpp-b9980`.
- Plan: piloto de 360 ejemplos (1 época) medido con `lora/decider_eval.py` (el decisor del producto aislado, con y sin
  adaptador) en DEV-A; si mejora, entrenamiento completo y medición con la regla de siempre.
- El dueño pidió (2026-09-25 ~21:00) que sirva a BAXY completo y a la fase de computer use: escritor 9 dedicado a operar
  dentro de apps; adaptador sólo en la llamada del decisor (no toca redacción ni el paso a paso del motor); riesgo
  anotado: el paso a paso del motor (rama `fable/computer-use-engine`) está ajustado sobre Qwen3-4B y el cambio de modelo
  base le afecta; medirlo al unir esa rama.

### Entrenamiento en el PC principal (redpc) por SSH (dueño, 2026-09-25 ~22:20)

El dueño ofreció su PC principal (RTX 4060 Ti, 16 GB) para la receta bf16 que Unsloth recomienda. Su agente abrió SSH
sólo por la tailnet y sólo con una clave de esta laptop; desde aquí se montó `D:\BAXYTrain` (mismas versiones,
Qwen/Qwen3.5-4B@851bf6e8, datos de entrenamiento) y se lanzó el piloto bf16 (400 ejemplos, igual que el QLoRA local)
como tarea programada oculta. Nada del repositorio de BAXY se toca en ese PC.

- **Piloto 1** (23:05): DEV-B ciego sólo decisión 201/253 frente a 208/253 de la base (DEV-A 199 frente a 198): arregla
  operaciones hermanas y convierte límites y preguntas en acciones. Causas y receta de datos v2 en D15 (negativos
  difíciles w10–w13, catálogo por familias al azar). **Piloto 2** (800 ejemplos de los datos v2) lanzado 23:50 con
  conversión y evaluación encadenadas (`lora/pilot_chain_redpc.ps1`).
- **Deriva de idioma del decisor** (2026-09-26 00:25): Qwen3.5-4B reescribe en español el 22–28 % de los pedidos de
  acción en inglés («max it» → «Maximizar la ventana de Steam»); M4 tomaba de ahí el idioma de la respuesta. Arreglado
  en el producto: el idioma sale de las palabras de la persona (`_read_reply_language`) y sólo si no lo dicen, de la
  reescritura. El LoRA del piloto 1 ya baja la deriva de 22/100 a 2/133 en DEV-A (sus datos traen el pedido en el
  idioma de la persona); el prompt del decisor no se toca mientras se entrena con él.
- **Piloto 2** (01:05): DEV-B ciego 210/253 (base 208), DEV-A 203/260 (base 198), p50 0,66 s; sobran límites (D16).
  **Completo** (`full1`, 2 654 ejemplos, irrelevancia 10 %) lanzado 01:19 en redpc, ~3,5 h + evaluación encadenada.
- **Integración lista para medir** (sin commit): `baxy_mind/decider_adapter.py` (binding por hash al GGUF base, como
  el adaptador de prosa de CPU, con el que comparte `read_bound_adapter`/`verify_neutral_adapter`); el servidor lo
  carga sin aplicar (`--lora-init-without-apply`, escala global 0 verificada al arrancar) y `decide_in_context` lo
  enciende por petición en su ranura reservada. Harness: `--decider-adapter` en `comprension_eval.py run` y
  `semantic_replay.py literals` (`gate.decider_adapter_environment`). Humo con el piloto 2 en `turn.decide`: 12/12 sin
  error, A-s006/A-s007 con la elección del LoRA. Falta el lado C# (manifiesto → variable) si el completo entra.

## Bitácora

- 2026-09-25 12:0x — F0: tag, ficheros de estado. Verificación anterior en curso (capas A/B/C).
- 12:40 — conjuntos DEV-A/DEV-B/FINAL cerrados y auditados; FINAL sellado. Esperando GPU (verificación anterior) para
  la base DEV y F2.
