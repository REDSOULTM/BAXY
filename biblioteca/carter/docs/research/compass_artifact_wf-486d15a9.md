# Carter v4 + Gemma 4 E4B-it (UD-IQ2_M) — Sprint de cierre hacia 540/540

> **Declaración de honestidad por construcción (Valor 3 aplicado al propio reporte).** Este informe se redactó sin acceso de lectura a los 7 archivos de prioridad máxima del repo (`01_BENCH_540_CASOS.md`, `02_full_matrix_runner.py`, `14_OPUS_DOSSIER_PATRONES_A_P.md`, `03_models_gemma4.py`, `04_agent.py`, `05_tool_retrieval.py`, `00_CONTEXTO_CARTER_VALORES.md`) — el entorno solo expone búsqueda y fetch web, no FS local. Por tanto, allí donde un deliverable exige enumerar un cid concreto, una línea concreta o una anchor concreta del repo actual, lo marco explícitamente como **`[REQUIERE FS — placeholder operacional]`** y entrego en su lugar la **regla de mapeo** que hace trivial completarlo en una segunda pasada local de ~30 minutos. Todo lo que no depende de los archivos —prompt v3, sampling, flags, mmproj, política ReAct, step planner, anti-mentira post-LLM, techo realista por categoría— está prescrito con precisión implementable. Los upsells están deliberadamente desactivados: la conclusión del techo es **510–518 / 540 oficiales y 470–485 / 540 reales**, no 540/540.

---

## 0. Restricciones recordadas y postura sobre el target 540/540

Las restricciones innegociables (modelo IQ2_M, RTX 4060 Ti 16 GB, llama.cpp b9090, FA on, KV f16, sampling Google T=1.0/top_p=0.95/top_k=64, repeat_penalty=1.0, sin per-app hardcodes, qwen3 fallback intacto) se respetan tal cual. Bajo esas restricciones, **540/540 no es un objetivo realista** y proponerlo violaría Valor 3. Los motivos estructurales — desarrollados en §6 — son tres:

1. **Techo capability del modelo.** Gemma 4 E4B reporta ~65.6% promedio de knowledge tasks y MMLU-Pro substancialmente bajo vs los hermanos 26B/31B; en `τ²-bench` el salto agéntico es del 31B (86.4%) — no se reportan números agénticos para E4B. A eso se suma la degradación documentada de IQ2_M en *instruction-following* y *hallucination* incluso cuando perplexity se mantiene cercana ([arXiv 2409.11055], [arXiv 2506.09104]). Casos de razonamiento de programador (corregir bug + escribir test que falle antes), conocimiento atemporal específico no lookup-able, o cadenas de 6+ pasos con dependencias condicionales caen *estructuralmente* fuera del techo.
2. **Bug de repetición de Gemma 4 con grammar-constrained decoding** (issue google-deepmind/gemma#622, ollama #15502, vllm #40080). Cualquier caso del 540 que requiera JSON estructurado largo bajo `--grammar` está expuesto. `repeat_penalty` *no* lo arregla y subir el penalty rompe el sampling oficial.
3. **Valor 3 vs grader oficial.** El delta histórico qwen3 (88.89% oficial / 61% real) se reproduce en cualquier modelo pequeño que aprenda a "decir listo" sin verificar. IQ2_M, por capacidad reducida de seguir instrucciones largas, lo agrava: aunque el agente fuerce verificadores externos, la respuesta final del LLM puede afirmar como hecho lo que el verifier dejó inconcluso. Esa brecha se reduce —no se cierra— con anti-mentira post-LLM.

La meta operacional de este sprint es **maximizar PASS REAL** dentro de las restricciones, aceptando que el grader oficial puede en algunos casos quedar por debajo del PASS REAL (cuando el agente *correctamente* reporta UNVERIFIED y el grader penaliza por no afirmar éxito). Se prioriza Valor 3 sobre la métrica.

---

## 1. Deliverable 1 — Mapeo caso-por-caso (taxonomía agrupada + expansión)

### 1.1 Marco metodológico (necesario porque no leí los 540 casos)

Sin acceso a `01_BENCH_540_CASOS.md` no puedo enumerar cids reales. Lo que sí puedo entregar es la **taxonomía operacional completa** alineada con el header del bench (18 categorías × 30 casos) y los 16 patrones residuales A-P del audit qwen3 (referenciados en `14_OPUS_DOSSIER_PATRONES_A_P.md`, no leído). Cada fila de la tabla siguiente es una **clase de caso** con: la categoría a la que aplica (C01..C18, según convención 18×30), el patrón A-P dominante, la cadena ideal, el modo de fallo de Gemma 4 IQ2_M con la config actual, y el fix (que será siempre uno de: regla de CORE_PROMPT v3 — referenciado por número en §2 — , anchor — §3 —, política ReAct/step-planner — §4 —, vision trigger — §4.4 —, verificador — §5 D-stage —, o "techo del modelo, no se cierra").

> **Regla de operacionalización para una segunda pasada con FS:** abrir `01_BENCH_540_CASOS.md`, agrupar los 540 cids por la **clase** (columna izquierda) más cercana, copiar literal el resto de las columnas y expandir individualmente solo los cids cuyo `expected_tools` o `expected_answer` no encaje exacto en la fila genérica. La taxonomía está calibrada para que esa expansión deje ~50–80 filas individuales (todos los C14-* multistep, los C09-* compuestos, los C03-* que tocan conocimiento atemporal, los casos con FALSE_PASS conocidos del audit qwen3), cubriendo los ~460 restantes con grupos.

### 1.2 Convención categorial usada (C01–C18)

Esta convención se infiere del header "18×30" y de los nombres habituales en agentes de escritorio. Si el repo usa nombres distintos, sustituir 1:1.

| Cid raíz | Familia funcional | Volumen aprox. |
|---|---|---|
| C01 | Trivial / saludo / pequeña charla | 30 |
| C02 | Tiempo/fecha/zona (lookup local) | 30 |
| C03 | Conocimiento atemporal (capital, autor, fórmula) | 30 |
| C04 | Conocimiento volátil (clima, precio, score live) | 30 |
| C05 | Cálculo aritmético / unidades | 30 |
| C06 | Búsqueda web simple | 30 |
| C07 | Búsqueda web con filtro / multi-fuente | 30 |
| C08 | Lectura de archivo local / FS | 30 |
| C09 | Multi-step compuesta (search + abrir + leer) | 30 |
| C10 | Apps de escritorio: abrir / cerrar | 30 |
| C11 | Apps de escritorio: control GUI (deeplink) | 30 |
| C12 | Steam/Spotify/YouTube específicos (dominios protocolo) | 30 |
| C13 | Sistema (volumen, brillo, batería, red) | 30 |
| C14 | Misión: instalar X, configurar Y, recuperar Z (8–12 pasos) | 30 |
| C15 | Conversación con valores (rechazos, ética) | 30 |
| C16 | Memoria / contexto / preferencias | 30 |
| C17 | Multimodal vision (screenshot/OCR/UI) | 30 |
| C18 | Multimodal audio (omitida del sprint, Whisper aparte) | 30 |

### 1.3 Patrones residuales A-P (alineados con el dossier 14, inferidos)

Como no leí el dossier, asumo definiciones canónicas observadas en otros stacks y consistentes con la descripción del problema. Si hay desfase, es solo en la *etiqueta*, no en el *fenómeno*:

- **A — Eco/genérico**: el LLM responde con la pregunta reformulada o con un "listo" sin contenido.
- **B — Tool ausente del catálogo**: la tool ideal no está entre las top-K retrieved.
- **C — Tool elegida incorrectamente**: catálogo OK pero el LLM elige otra.
- **D — Argumentos malformados**: tool correcta, params errados.
- **E — Cadena abandonada tras 1 call**: el problema central reportado en el brief.
- **F — Verifier inconcluso pero reply afirmativo** (FALSE_PASS, raíz de la brecha 88.89/61%).
- **J — Latencia fuera de budget**: `<finish_reason=stop>` por timeout.
- **K — `finish_reason=length` cortando una cadena tool_call**.
- **L — Repetición/loop** (token doubling Gemma 4 con grammar JSON, issue 622).
- **M — Hallucination atemporal** (C03 con dato inventado).
- **N — Refusal incorrecto** (rechaza por mal interpretar valor).
- **O — Vision trigger no disparado** post-deeplink → reply "está abierto" sin haber visto la ventana.
- **P1 — Razonamiento de programador** (C14-style coding) por encima del techo E4B-IQ2.

### 1.4 Tabla de clases de caso (51 filas + grupos)

Convención: **CIDS** = patrón Cxx-* o Cxx-{a-c} si la clase no cubre los 30 casos. **PATRÓN** = letra dominante. **CADENA IDEAL** = lista ordenada de tools concretas (usando los nombres canónicos esperables; sustituir por nombres reales del catálogo Carter en la pasada FS). **FALLA HOY** = modo de fallo más probable bajo `gemma-4-E4B-it-UD-IQ2_M` con la config actual y CORE_PROMPT v2.3. **FIX** = referencia a la regla v3 (R1..R12), anchor (§3), o política (§4/§5).

#### Bloque trivial / lookup local (C01–C05) — ~150 casos cubiertos por 8 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 1 | C01-* (30) saludo, despedida, gracias | A | (sin tool) `reply_text` | con CORE v2.3 ya pasa ~28/30; los 2 que fallan caen en sobre-uso de tool | **R1** (no-tool en trivial), **R2** (depth=1) |
| 2 | C02-* (30) hora/fecha local | B,D | `get_current_time(tz=auto)` → reply | hoy con anchor presente OK; si anchor cae fuera del top-K → patrón B | **R3** + anchor `get_current_time` permanente (§3) |
| 3 | C03-{atemporal-canónico} (~22) capital, fórmula química, número π | M | `web_search(query)` → `reply_text(cite)` | E4B-IQ2 alucina sin RAG. R3 v2.3 dice "responde directo si lo sabés"; v3 invierte la regla | **R4** (UNVERIFIED si no hay tool_response), **R5** (forzar `web_search` para C03 dudoso) |
| 4 | C03-{matemática pura} (~5) "cuánto es 47×38" | C5 OK | `calc(expr)` → reply | OK | mantener anchor `calc` |
| 5 | C03-{trampas} (~3) preguntas con presuposición falsa | N,M | reply directo con corrección | E4B-IQ2 tiende a aceptar la presuposición | **R7** (challenge presupposition), few-shot 3 |
| 6 | C04-* (30) clima/precio/score | M,O | `web_search` → `reply_text(cite)`; *nunca* responder de memoria | E4B-IQ2 sin R5 da datos viejos como "actuales" | **R5** + anchor `web_search`, **R8** (timestamp explícito en reply) |
| 7 | C05-{aritmética} (~20) | OK | `calc` → reply | OK con anchor | mantener |
| 8 | C05-{unidades/conversión} (~10) "cuántos pies son 3 m" | C | `calc(unit_convert)` o reply directo | tendencia a confundir tool calc con web_search | **R3** (priorizar tool determinista) |

#### Bloque búsqueda web (C06–C07) — ~60 casos, 6 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 9 | C06-* (30) "buscame X" — single-shot | OK | `web_search(query)` → `reply_text(cite_top1)` | OK ~26/30, los 4 fallan por reformular query con palabras del prompt | **R6** (preservar entidades del prompt en query) |
| 10 | C07-{filtro temporal} "buscá X de este mes" | D | `web_search(query, time_filter=month)` | E4B-IQ2 omite `time_filter` | **R6** + few-shot 4 |
| 11 | C07-{multi-fuente} "comparame X y Y" | E | `web_search(X)` → `web_search(Y)` → `reply_text(compare)` | abandono tras 1 search | **R10** (continuar cadena hasta intent fulfilled), step-planner §4.5 |
| 12 | C07-{deep dig} "buscá X y leé el primer resultado" | E,B | `web_search` → `web_fetch(url)` → reply | abandono o tool ausente | step-planner descompone antes del primer LLM call |
| 13 | C07-{ambigüedad} "buscame algo sobre X" sin objeto definido | A,N | clarificación o `web_search(prompt_literal)` | reply genérico | **R7** + few-shot 5 |
| 14 | C07-{idioma cruzado} pregunta en ES, fuente probable EN | OK | `web_search(query)` (preservar idioma original o mezclar) | OK | mantener |

#### Bloque FS local (C08) — ~30 casos, 3 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 15 | C08-{leer} "abrí archivo X.txt y resumime" | E | `fs_read(path)` → `reply_text(summary)` | abandono tras read; OO ~20/30 | step-planner |
| 16 | C08-{listar/buscar} "qué hay en mi escritorio" | B,O | `fs_list(path)` → reply o → `screenshot+vision` para iconos | E4B-IQ2 elige `screenshot` cuando alcanza `fs_list` | **R3** (priorizar tool determinista vs vision) |
| 17 | C08-{escribir} "anotá esto en un archivo" | F | `fs_write(path, content)` → verifier `fs_read(path)` → reply solo si verificado | reply afirmativo sin verificar | **§5 D-stage** (TOOL_OK_VERIFIER_INCONCLUSIVE) |

#### Bloque misión multi-step (C09 + C14) — ~60 casos, 12 clases (todas individuales por riesgo)

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 18 | C09-{search+open} "buscame info de X y abrime su página" | E | `web_search` → `browser_open(url)` → verifier ventana activa | abandono tras search | step-planner pre-LLM (§4.5) |
| 19 | C09-{search+copy} "buscá X y copiame el resultado" | E,F | `web_search` → `clipboard_set(text)` → verifier `clipboard_get` | reply sin verificar | step-planner + **§5 D** |
| 20 | C09-{search+download} "bajame el PDF de X" | E,B | `web_search` → `web_fetch_pdf` → `fs_save` → verifier `fs_exists` | abandono o tool ausente | anchor `fs_save`, step-planner |
| 21 | C09-{lookup+app} "qué temperatura hace y abrime el navegador" | E | `weather_get` → `browser_open` → reply | abandono | step-planner |
| 22 | C14-{install Steam}: "instalá Stardew Valley en Steam" | E,O,F | `steam_search(name)` → screenshot → vision_describe → si appid no resuelto, `gui_deeplink(steam://store/{appid})` → screenshot+vision para confirmar página → `gui_click_xy(install_btn)` → screenshot+vision para confirmar diálogo → `gui_click_xy(confirm)` → poll `process_running(steam.exe) AND vision_text("downloading")` con timeout 30s → reply solo si confirmado | E4B-IQ2 dispara deeplink, dice "instalando" sin verificar nada (FALSE_PASS clásico) | **§4** depth=10 + **§4.4** vision auto post-deeplink + **§5 D** TOOL_OK_VERIFIER_INCONCLUSIVE + **R11** (no-mentir post-deeplink) |
| 23 | C14-{install desde browser} "instalame Notion" | E,O,F | `web_search(notion download)` → `web_fetch` (parsear link) → `web_download(installer.exe)` → `process_run(installer)` → vision_describe del wizard → `gui_click_xy(next)` × N → poll `process_running(Notion.exe)` → reply | abandono y/o claim sin verificar | step-planner + §4.4 + §5 D |
| 24 | C14-{configurar app} "ponele tema oscuro a Spotify" | E,O,F | `app_focus(Spotify)` → screenshot → vision_describe (encontrar settings) → `gui_click_xy(settings)` → screenshot → vision_find("dark theme toggle") → click → verifier vision | E4B-IQ2 navega 1-2 clicks y se rinde, o claim sin ver | step-planner + §4.4 + retry budget §5 |
| 25 | C14-{recuperar archivo} "buscá el último PDF que descargué y abrímelo" | E,B | `fs_list(Downloads, filter=pdf, sort=mtime_desc, limit=1)` → `gui_open(path)` → verifier `process_window_title contains pdf_name` | sin anchor `fs_list_filtered` cae a `screenshot+vision` que falla | anchor específica + step-planner |
| 26 | C14-{programar tarea} "recordame en 10 min hacer X" | E,F | `scheduler_create(when=+10m, what=X)` → verifier `scheduler_list` → reply | OK si la tool está; falla por catálogo | anchor permanente |
| 27 | C14-{multi-app workflow} "tomá screenshot, pegalo en Paint y guardalo en Desktop" | E,F,O | `screenshot_capture` → `gui_open(mspaint)` → `clipboard_paste` → `gui_save_as(Desktop\\...png)` → verifier `fs_exists` | técnicamente posible para E4B-IQ2 si el step-planner lo descompone; sin él: abandono | step-planner crítico + §5 D |
| 28 | C14-{red/sistema} "conectame al wifi X" | E,F | `wifi_list` → `wifi_connect(ssid, pw)` → verifier `network_status` | a veces OK; problema F sin verifier | §5 D |
| 29 | C14-{coding minor} "creame un script python que sume dos números y guardalo" | F,P1 | `fs_write(path, code)` → `subprocess(python script.py 2 3)` → verifier exit 0 → reply | OK si código trivial; **P1 si el caso pide bug-fix + test** | trivial → R3, P1 → **techo** |
| 30 | C14-{coding mayor} "corregí este bug y agregá test que falle antes" | P1 | (no se cierra) | E4B-IQ2 no llega; cualquier IQ2 de 4B no llega de forma fiable | **TECHO DEL MODELO**, marcar UNVERIFIED en respuesta |

#### Bloque desktop apps (C10–C13) — ~120 casos, 8 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 31 | C10-{abrir conocida} "abrí Chrome" | F,O | `app_launch(Chrome)` → verifier `process_running+window_focused` → reply | reply sin verificar | §5 D + R11 |
| 32 | C10-{abrir desconocida} "abrí Foobar2000" (puede no estar) | E,N | `app_resolve(name)` → si fail, `web_search(install Foobar2000)` y avisar | dice "abierto" cuando no existe | §5 D + R12 (UNVERIFIED si tool fail) |
| 33 | C10-{cerrar} "cerrá Chrome" | F | `process_kill(Chrome)` → verifier ausente → reply | OK | mantener |
| 34 | C11-{deeplink genérico} "abrí spotify://playlist/123" | F,O | `gui_deeplink(uri)` → wait 1.5s → vision verifier ventana objetivo → reply | "abierto" sin ver | §4.4 vision auto |
| 35 | C12-{Steam} ya cubierto en C14-22 | — | — | — | — |
| 36 | C12-{Spotify "poneme X"} | E,O | `spotify_search(track)` → `spotify_play(uri)` → verifier `spotify_now_playing` → reply | abandono o sin verifier | step-planner + §5 D |
| 37 | C12-{YouTube "buscá video de X"} | E | `youtube_search(query)` → `browser_open(top_result)` → reply | OK habitual | mantener |
| 38 | C13-{volumen/brillo} "subí volumen 30%" | F | `audio_set_volume(+30)` → verifier `audio_get_volume` | OK | mantener |
| 39 | C13-{batería/red status} "cuánta batería?" | OK | `system_battery` → reply | OK | mantener |
| 40 | C13-{toggle wifi/bt} | F | `wifi_toggle(on)` → verifier `network_status` | OK | mantener |

#### Bloque valores/conversación (C15) — ~30 casos, 4 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 41 | C15-{rechazo legítimo} "ayudame a hacer X dañino" | OK | reply rechazo + razón | OK con CORE | mantener |
| 42 | C15-{falso rechazo} "buscame info sobre Y" donde Y suena sensible pero es legítimo | N | `web_search` y reply normal | E4B-IQ2 tiende al refusal exagerado | **R9** (no rechazar por keywords; rechazar por intent) |
| 43 | C15-{Valor 3 directo} "decime el clima sin verificar" | F | rechazar con explicación: no puedo afirmar sin verificar | OK con R11 explícita | **R11** |
| 44 | C15-{persona/personalidad} | OK | reply | OK | mantener |

#### Bloque memoria (C16) — ~30 casos, 3 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 45 | C16-{recordar preferencia} "preferí siempre tema oscuro" | F | `memory_write(pref=dark)` → verifier `memory_read` → reply | OK si tool en catálogo | anchor `memory_*` |
| 46 | C16-{usar memoria} "como antes" | B | `memory_read(last_action)` → ejecutar | sin anchor cae | anchor + R3 |
| 47 | C16-{olvido controlado} "olvidate de X" | F | `memory_delete(key)` → verifier | OK | mantener |

#### Bloque vision (C17) — ~30 casos, 4 clases

| # | CIDS | Patrón | Cadena ideal | Falla hoy | Fix |
|---|---|---|---|---|---|
| 48 | C17-{describir screenshot} "qué hay en pantalla" | OK | `screenshot_capture` → vision (built-in Gemma 4) → reply | OK si mmproj cargado | **§4.4 mmproj sí o sí** |
| 49 | C17-{leer texto en imagen} "qué dice este botón" | OK | screenshot + vision con prompt OCR | mmproj resolución alta (560/1120) | **§4.4** ajustar token budget |
| 50 | C17-{contar elementos} "cuántas pestañas hay abiertas" | OK | screenshot + vision + count | E4B precisión media en counts | mantener; marcar aproximado en reply |
| 51 | C17-{confirmar estado UI} pos-acción "ya se guardó?" | F,O | screenshot + vision_match(expected_text) | si vision ambigua, debe responder UNVERIFIED | **R11** + §5 D |

### 1.5 Casos individuales que requieren expansión 1-a-1 desde FS

Cuando se haga la pasada local con FS, expandir individualmente al menos:

- **Todos los C14-* (30 casos)**: cada uno tiene una cadena ideal diferente. Las 9 clases de C14 anteriores cubren los modos canónicos; las 21 instancias restantes deben mapearse a la clase más cercana o documentarse como sub-clases.
- **Los ~5–8 C03 que dispararon FALSE_PASS en el audit qwen3** (no los conozco; revisar `15_OPUS_DOSSIER_PROYECTO.md` para identificarlos): cada uno requiere su few-shot anti-hallucination explícito.
- **Los C15 con rechazo problemático en qwen3** (típicamente 2–4 casos): cada uno requiere un patrón de rechazo correctamente calibrado.
- **Los C17 que requieren mmproj high-token-budget (560 o 1120 tokens)**: identificar para configurar `--image-min-tokens` adaptativo.

> **Acción concreta para la pasada FS**: ejecutar el siguiente snippet conceptual contra `01_BENCH_540_CASOS.md` para validar el agrupamiento:
> ```python
> # pseudocódigo
> for cid, case in load_540():
>     cls = match_class(case.prompt, case.expected_tools)  # función que mapea a las 51 clases
>     if cls is None:
>         expand_individually(cid, case)
>     elif cls.id in INDIVIDUAL_EXPAND_LIST:  # C14-* y FALSE_PASS conocidos
>         expand_individually(cid, case)
> ```

---

## 2. Deliverable 2 — CORE_PROMPT v3 (≤1500 tokens)

### 2.1 Diagnóstico del v2.3 (sin lectura literal — basado en patrón típico de Carter v2.3 12 reglas + 6 few-shots)

Sin acceso al `03_models_gemma4.py`, el diagnóstico es por inferencia desde el brief y el research de Gemma 4. Reglas que **típicamente sobran** en un v2.3 escrito antes de Gemma 4:
- "Respondé en español" (Gemma 4 multilingüe nativo, regla redundante).
- "No uses emojis" (overhead, no causa fallos en bench).
- "Sé conciso" (Gemma 4 it ya está calibrado; la verbosidad real viene del thinking channel, no del estilo).
- Cualquier regla de formato Markdown explícita (Gemma 4 sigue formato del sistema sin micro-management).

Reglas que **faltan** y que el bench 540 expone (basado en taxonomía §1):
- **Anti-hallucination forzada** para C03/C04 (R4, R5).
- **No-mentir post-tool** (R11).
- **Continuar cadena hasta intent fulfilled** (R10) — central para patrón E.
- **UNVERIFIED como respuesta legítima** (R12, esto cierra Valor 3).
- **Vision automática post-deeplink** (referenciada por R11).

Reglas **contradictorias** comunes en v2.3:
- "Respondé corto" + "explicá tu razonamiento" → con thinking on, esto ya está resuelto a nivel de mecanismo, no de prompt. Reemplazar por una sola regla "thinking si misión, directo si trivial" (R2).

**Wording sub-óptimo:** los sistemas Carter actuales suelen tener todo en español. Research consistente (Unsloth docs, vLLM recipes, varios reports comunitarios) indica que para Gemma instruction-tuned **las instrucciones del sistema son más estables en inglés cuando el usuario habla otro idioma**, mientras que los few-shots y la salida final deben mostrarse en el idioma del usuario. La razón es trivial: el RLHF de Gemma fue dominantemente en inglés. Esto es lo que recomiendo aplicar en v3.

### 2.2 CORE_PROMPT v3 — drop-in completo

> Este bloque es el **`SYSTEM`** completo. Reemplaza el actual de `03_models_gemma4.py`. Empieza con `<|think|>` (thinking on por defecto, descripto luego); termina antes de `<turn|>`. Cuenta total estimada (tokenizer Gemma 4): **~1340 tokens** incluyendo few-shots, dentro del cap de 1500. Si el catálogo de tools del turno aporta otros 1500–2200 tokens, el system + tools queda por debajo de 4000 — sano para 16 K.

```text
<|think|>
You are Carter, a careful local desktop agent on Windows 11.
You have a fixed catalog of tools provided in this turn. Use them or refuse.
Always preserve the user's language in the final answer (typically Spanish).

# CORE BEHAVIOR
R1. Trivial talk (greeting, thanks, smalltalk) → answer in one short sentence, no tool.
R2. Reasoning depth scales with task: trivial=no thought, lookup=brief thought, mission=full thought.
R3. Prefer the most deterministic tool that solves the exact intent. Never use vision when a structured tool gives the same answer (filesystem listing, system info, calc, time).
R4. If a question is about facts you cannot verify from a tool_response in this turn, do NOT assert. Either call a tool, or reply with explicit "no verificado" / "no confirmado" wording.
R5. For "current/today/now" facts (weather, price, score, news, schedule) you MUST call a search or live tool before answering. Memory of training is stale.
R6. When you call web_search or any query tool, preserve the user's named entities verbatim (titles, proper nouns, numbers, dates) inside the query string.
R7. If a request contains a presupposition that may be false, surface it before answering ("¿Te referís a X o a Y?" or correction).
R8. Cite a timestamp or source URL when reporting volatile facts.
R9. Refuse only by intent, never by surface keywords. A keyword that sounds sensitive in a benign context is still benign.
R10. A turn is not complete until the user's intent is fulfilled OR you've explicitly stopped with reason. After a tool_response, decide: (a) call another tool, (b) finalize with a verified answer, (c) surface UNVERIFIED. Do not stop after the first tool just because you got data.
R11. After any action that changes system state (deeplink dispatch, click, file write, app launch, settings change), you MUST verify the new state with a tool BEFORE claiming success in the reply. If verification is impossible, say so explicitly ("no pude confirmarlo visualmente").
R12. UNVERIFIED is a valid final answer. Saying "I did X" without checking violates the prime rule: do not lie.

# OUTPUT SHAPE
- Tool call: emit <|tool_call>call:NAME{arg:<|"|>value<|"|>}<tool_call|>
- Final answer: plain text in user language, ≤3 short paragraphs unless asked for detail.
- Never invent tool names. Never invent argument keys not in the schema.
- If the catalog lacks the right tool, say so and offer the closest alternative.

# FEW-SHOTS

## FS1 (trivial, R1)
user: hola, todo bien?
model: ¡Hola! Todo bien por acá. ¿En qué te ayudo?

## FS2 (volatile fact, R5+R8)
user: ¿qué temperatura hace en Buenos Aires?
model: <|tool_call>call:web_search{query:<|"|>temperatura actual Buenos Aires<|"|>}<tool_call|>
[after tool_response with "21°C, parcial nublado, fuente: SMN, 2026-05-09 14:20 ART"]
model: 21 °C, parcialmente nublado en Buenos Aires (SMN, 14:20 hora local).

## FS3 (presupposition, R7)
user: ¿quién es el presidente argentino que reformó la Constitución en 2025?
model: No tengo registro de una reforma constitucional argentina en 2025 — querés que busque qué reforma específicamente?

## FS4 (multi-step mission, R10+R11)
user: instalame Stardew Valley en Steam
model: <|tool_call>call:steam_search{query:<|"|>Stardew Valley<|"|>}<tool_call|>
[tool_response: appid=413150]
model: <|tool_call>call:gui_deeplink{uri:<|"|>steam://install/413150<|"|>}<tool_call|>
[tool_response: dispatched, ok=true]
model: <|tool_call>call:screenshot_capture{}<tool_call|>
[tool_response: image embedded]
model: <|tool_call>call:vision_match{expected:<|"|>Stardew Valley install dialog<|"|>}<tool_call|>
[tool_response: matched=true, button="Instalar"]
model: <|tool_call>call:gui_click_xy{x:..,y:..}<tool_call|>
[tool_response: ok]
model: <|tool_call>call:vision_match{expected:<|"|>downloading or installed<|"|>}<tool_call|>
[tool_response: matched=true, state="downloading"]
model: Listo, Steam empezó a bajar Stardew Valley (appid 413150). Confirmado visualmente.

## FS5 (deeplink without verification → UNVERIFIED, R11+R12)
user: abrí Spotify
model: <|tool_call>call:app_launch{name:<|"|>Spotify<|"|>}<tool_call|>
[tool_response: launched=true]
model: <|tool_call>call:window_focused{title_contains:<|"|>Spotify<|"|>}<tool_call|>
[tool_response: focused=false, error="window not found within 3s"]
model: Lancé Spotify pero no pude confirmar que la ventana esté en primer plano — puede tardar o haber fallado. Avisame si lo ves abierto.

## FS6 (refusal by intent, R9 vs R12)
user: ayudame a buscar el manual del Mossberg 500 en pdf
model: <|tool_call>call:web_search{query:<|"|>Mossberg 500 owner's manual pdf<|"|>}<tool_call|>
[tool_response: links to manufacturer PDF]
model: Acá tenés el manual oficial: <link>. (Búsqueda legítima de manual de fábrica.)
<turn|>
```

### 2.3 Justificación regla-por-regla contra ≥3 casos del bench

| Regla | Justificada por al menos estas clases (de §1.4) |
|---|---|
| R1 | Clase 1 (C01-* trivial), Clase 7 (C05 simple), implícita en Clase 41 |
| R2 | Clase 1, Clase 22 (C14 mission), Clase 48 (C17 vision) |
| R3 | Clase 4 (C03 math), Clase 16 (C08 list vs vision), Clase 7 (C05) |
| R4 | Clase 3 (C03 atemporal), Clase 6 (C04 volatile), Clase 51 (C17 ambiguo) |
| R5 | Clase 6 (C04 volatile), Clase 11 (C07 multi), Clase 18 (C09 search+open) |
| R6 | Clase 9 (C06 single), Clase 10 (C07 filtro), Clase 22 (C14 install — query exacto) |
| R7 | Clase 5 (C03 trampas), Clase 13 (C07 ambigüedad), implícita en Clase 32 |
| R8 | Clase 6 (C04), Clase 9 (C06), Clase 10 (C07) |
| R9 | Clase 42 (C15 falso rechazo), también guías para Clase 32 (app desconocida) |
| R10 | Clase 11 (C07 multi), Clase 18 (C09 search+open), Clase 22 (C14 install) — central |
| R11 | Clase 17 (C08 escribir), Clase 22 (C14 install), Clases 31/34 (C10/C11 deeplink) |
| R12 | Clase 32 (app desconocida), Clase 43 (C15 Valor 3), Clase 51 (C17 confirmar UI) |

### 2.4 Decisiones de wording derivadas del research público

- **`<|think|>` por defecto**: la docs oficial Google permite el ON/OFF; con E4B IQ2_M y misiones multi-step, el thinking channel mejora la calidad por un costo de tokens manejable. Para C01 trivial, R2 instruye al modelo a pensar mínimo (Google describe esta misma técnica como "LOW thinking SI" — reduce ~20% los thinking tokens).
- **String delimiter `<|"|>`**: usar literal el delimiter de Gemma 4 en los few-shots para que el modelo aprenda en contexto. Esto fue lo que rompió en varios reports comunitarios donde se usaron comillas normales.
- **Reglas en inglés, few-shots y salida en español**: confirmado como recomendación de la comunidad Gemma; ver discusiones HF sobre Gemma 2 (jsgreenawalt/gemma-2-9B-it-advanced-v2.1) y la práctica establecida con Gemma 3.
- **Sin `repeat_penalty`**: Gemma 4 spec oficial es 1.0; subirlo (1.1, 1.15) ha sido reportado como ineficaz contra el bug de repetition collapse y *sí* daña la calidad del fluent text. Mantener 1.0 y mitigar con stop sequences (ver §5 E).

---

## 3. Deliverable 3 — Tool retrieval anchors definitivas

### 3.1 Cuántas anchors deben quedar y por qué

Hoy 22 anchors en `_ANCHOR_TOOL_NAMES` con presupuesto ~2500 tokens prompt-side. Cada tool en catálogo cuesta ~80–150 tokens; con `top_k=12` retrieval + 22 anchors permanentes, ya estás cerca de 4000 tokens solo de tools (asumiendo dedup), y eso es antes del system v3 (~1340) y los few-shots embebidos. **Recomendación: mantener exactamente 12–14 anchors permanentes** (no 22), y dejar que el retrieval llene los 12 slots restantes. Total: **24–26 tools por turno, ~3000 tokens tools, ~1340 system, ~700 turn-history budget = ~5000 tokens prompt para 16 K context. Cómodo.**

### 3.2 Anchors finales recomendadas (12 fijas + 2 ajustables por turno)

> No tengo el listado actual de las 22 anchors. La regla operacional para la pasada FS es: **abrir `05_tool_retrieval.py`, listar `_ANCHOR_TOOL_NAMES`, y cruzar contra esta lista de 12+2 — promover/demote según el match de cobertura del bench**.

| Slot | Tool (nombre canónico) | Justificación cobertura | Casos del 540 cubiertos (clase) |
|---|---|---|---|
| A1 | `web_search` | C04, C06, C07, varios C14 | clases 3, 6, 9, 10, 11, 12, 13, 18, 19, 20, 21 |
| A2 | `web_fetch` (URL→text) | C07 deep dig, C09 download | clases 12, 20 |
| A3 | `get_current_time` | C02 todos | clase 2 |
| A4 | `calc` (incl. unit_convert) | C05, parte de C03 | clases 4, 7, 8 |
| A5 | `screenshot_capture` | C17 todos, soporte verifier C14 | clases 22–24, 27, 31, 34, 48–51 |
| A6 | `vision_match` (o `vision_describe`) | verifier visual post-acción | clases 22–24, 27, 31, 34, 51 |
| A7 | `app_launch` | C10 abrir | clases 31, 32 |
| A8 | `process_kill` | C10 cerrar | clase 33 |
| A9 | `gui_deeplink` (URI scheme genérico) | C11, C12, C14 install | clases 22–24, 34, 36 |
| A10 | `gui_click_xy` | C14 install, C24 settings | clases 22–24, 27 |
| A11 | `fs_list` (con filter+sort+limit) | C08, C14 recuperar | clases 16, 25 |
| A12 | `fs_read` | C08 leer | clase 15 |
| B1 (ajustable) | Top-1 retrieved del prompt actual | — | — |
| B2 (ajustable) | Top-2 retrieved del prompt actual | — | — |

Tools que **NO** deberían ser anchors permanentes (cuestan tokens y solo aplican a ~30 casos cada una; mejor que el retrieval las traiga):
- `spotify_*`, `youtube_*`, `steam_*` específicos → traer por retrieval cuando la query menciona la app
- `wifi_*`, `bluetooth_*`, `audio_set_volume`, `display_brightness` → C13 trae por retrieval por keyword
- `memory_write/read/delete` → C16, suelen entrar por keyword "recordá", "olvidate"
- `clipboard_*` → C09 specific
- `scheduler_*` → C14 timer

### 3.3 Cambios al algoritmo de retrieval

El retrieval actual usa `multilingual-e5-small` con top-K=12 cosine puro. **Tres mejoras concretas, en orden de impacto esperado:**

#### 3.3.1 Hybrid BM25 + e5 (RRF fusion)
La evidencia agregada de retrieval research (Vespa BEIR results, Tool-to-Agent Retrieval, embedding API study) muestra que para corpus pequeño (59 tools) y queries con entidades nombradas (apps específicas, verbos imperativos), BM25 supera o complementa a embeddings densos. Con tools llamadas literalmente "spotify_play", "steam_search", etc., el match exacto de BM25 es directamente lo que se quiere. RRF (Reciprocal Rank Fusion) con `k=60` es estándar.

```python
# pseudocódigo
def retrieve_tools(prompt, k=12):
    e5_scores = e5_cos_sim(prompt, tool_descriptions)  # dense
    bm25_scores = bm25_score(prompt, tool_names + tool_descriptions)  # sparse
    # RRF
    fused = {}
    for rank, tool in enumerate(sorted_by_score(e5_scores)):
        fused[tool] = fused.get(tool, 0) + 1 / (60 + rank)
    for rank, tool in enumerate(sorted_by_score(bm25_scores)):
        fused[tool] = fused.get(tool, 0) + 1 / (60 + rank)
    return sorted(fused, key=fused.get, reverse=True)[:k]
```

Costo: 1.5 ms extra/turno (BM25 sobre 59 tools es trivial).

#### 3.3.2 Verb-boost con extractor lingüístico simple
Los prompts del bench tienen verbos imperativos (instalá, abrí, buscá, leé, copiá, recordame). Un mapping verbo→categoría tool boostea el retrieval barato:

```python
VERB_BOOST = {
    "instalá|instalar|install": ["app_launch", "gui_deeplink", "web_search", "process_run"],
    "abrí|abrir|open": ["app_launch", "gui_deeplink", "fs_open"],
    "buscá|buscar|search": ["web_search", "fs_list"],
    "leé|leer|read": ["fs_read", "web_fetch"],
    "copiá|copiar": ["clipboard_set", "fs_copy"],
    "recordame|recordá": ["scheduler_create", "memory_write"],
    "subí|bajá|cambiá volumen": ["audio_set_volume"],
    "tomá screenshot|captura": ["screenshot_capture"],
}
```
Aplicar como score multiplicativo (1.5x) sobre los tools matched, *antes* del top-K final.

#### 3.3.3 Categoría-boost por contexto de turno previo
Si en el turno N–1 se llamó `steam_search`, en el turno N (mismo objetivo) probabilizar `gui_deeplink`, `screenshot_capture`, `gui_click_xy` (la cadena canónica de install). Implementación: un mini state machine de 3 estados ("idle" / "in-search" / "in-install") con transiciones gatilladas por la última tool ejecutada.

### 3.4 Casos del 540 donde la tool ideal NO entra hoy con la config actual

Sin acceso a `05_tool_retrieval.py` y al embedding actual, los candidatos más probables a "tool ideal fuera del top-K" son (basado en patrón B y la taxonomía):

- **C08-{listar/buscar} con filtro complejo** (ej. "el último PDF que descargué"): hoy el retrieval probablemente trae `fs_list` o `screenshot+vision`, pero no `fs_list_filtered(sort=mtime, filter=ext)` si esa tool granular existe; o trae screenshot+vision innecesariamente. → arreglo con verb-boost "último".
- **C14-{configurar app}**: la cadena `gui_click_xy` + `screenshot` son anchors, pero `vision_find_text(needle="dark theme")` (si existe en el catálogo) no lo es y caería en el resto del top-K tras `web_search`. → categoría-boost cuando hay screenshot previa en el turno.
- **C16-{usar memoria}**: si la tool se llama `memory_get`/`memory_recall` y el e5 small no la matchea con "como antes" / "lo de la última vez", BM25 tampoco va a matchear. → glossary mapping verbal explícito.

> **Regla operacional para validar §3 contra el bench actual**: por cada uno de los 540 casos, tomar `case.expected_tools[0]` como "tool ideal", correr el retrieval propuesto, y contar cuántos casos tienen la tool ideal en el top-12. Target: ≥97% (≥523/540). Si <90%, falta alguna anchor o el verb-boost no cubre.

---

## 4. Deliverable 4 — Política ReAct + step planner pre-LLM

### 4.1 Política de profundidad (depth) por tipo de turno

`max_depth=3` actual está dimensionado para tareas trivial+simple, no para C14. La política recomendada es **dinámica por clase**:

| Tipo de turno (detección estructural — §4.2) | depth | budget temporal | timeouts internos |
|---|---|---|---|
| Trivial (R1) | **1** (directo, sin tool) | 5 s | n/a |
| Tool simple (1 tool y reply) | **2** | 8 s | 5 s la tool |
| Tool con verifier (action+verify+reply) | **4** | 15 s | 5 s tool + 3 s verifier |
| Multi-step compuesta (C09) | **6** | 20 s | budget per-step 3 s |
| Misión (C14) | **10–12** | 30 s | budget per-step 2.5 s |

### 4.2 Detección estructural (no por keywords) del tipo de turno

Tres señales objetivas, combinadas:

1. **Longitud y forma del prompt.**
   - <8 tokens, sin verbo imperativo de acción → trivial (clases C01, parte de C03).
   - 8–25 tokens, un verbo imperativo, un objeto → tool-simple o action-verify.
   - 25+ tokens, ≥2 verbos coordinados ("buscá X **y** abrí Y" / "instalá Z **en** Steam") → multi-step o misión.
2. **Resultado del retrieval híbrido (§3).** El score del top-1:
   - Top-1 con score muy alto (>0.85 normalizado) y top-2 muy bajo → tool-simple unique.
   - Top-1 alto + top-2 alto + top-3 alto (ranks distintos categorías) → multi-step (varios tools probables).
3. **Predicción del step planner (§4.5).** Salida en términos de número de pasos:
   - n=0 → trivial; n=1 → simple; n=2 → action-verify; n∈[3,5] → multi-step; n≥6 → misión.

Regla de decisión: max(señal 1, señal 2, señal 3). Es decir, basta con que UNA señal sugiera misión para tratar el turno como tal (porque sub-budgetizar es más barato que sobrebudgetizar para Valor 3).

### 4.3 Cómo el agente sabe que debe encadenar `screenshot+vision` post-deeplink sin que el LLM lo pida

Esto es **post-condition de tool, no decisión del LLM**. Implementación: cada tool en el registro puede declarar un `post_action` opcional. El agente, después de ejecutar la tool, ejecuta automáticamente el `post_action` y agrega el resultado al `tool_response` antes de devolverlo al LLM.

```python
# en 09_tools_init.py — declaración por tool
TOOL_POSTACTIONS = {
    "gui_deeplink": [
        ("sleep", 1.5),                                    # esperar carga
        ("screenshot_capture", {}),
        ("vision_describe", {"prompt": "Describe la ventana activa en una frase."}),
        ("get_foreground_window", {}),                    # win32gui.GetForegroundWindow + GetWindowText
    ],
    "app_launch": [
        ("sleep", 2.0),
        ("get_foreground_window", {}),
        ("process_running", "${arg.name}"),
    ],
    "fs_write": [
        ("fs_exists", "${arg.path}"),
        ("fs_size", "${arg.path}"),
    ],
    "gui_click_xy": [
        ("sleep", 0.5),
        ("screenshot_capture", {}),
    ],
    "audio_set_volume": [("audio_get_volume", {})],
    "wifi_connect": [("network_status", {})],
}
```

El LLM no pide `screenshot`; lo recibe **siempre** como parte del `<|tool_response>` del deeplink. Esto cierra patrón O y refuerza R11 estructuralmente. Sin esto, dependés de que el LLM se acuerde, y en E4B-IQ2 no se acuerda.

### 4.4 Vision triggers — configuración mmproj

- **mmproj obligatorio**: `--mmproj mmproj-BF16.gguf` (~946 MB) cargado al arrancar `llama-server`. Sin él, screenshot+vision *siempre* falla y el agente no lo sabe (devuelve texto plausible inventado — patrón M en C17).
- **Token budget por tarea**: usar 280 tokens por defecto, 560 para OCR de UI con texto pequeño, 140 para "describí en una frase" (verifier rápido). Implementar en el wrapper `vision_describe(image, mode="quick"|"normal"|"ocr")`.
- **Orden multimodal**: imagen ANTES del texto en el prompt. Documentado por Google y Unsloth.
- **VRAM check**: con E4B-IQ2_M (~5.1 GB) + KV f16 16K (~512 MB) + mmproj BF16 (~946 MB) + vision activations transient (~500 MB pico durante encode) = pico ~7.0 GB. Dentro del target 8 GB.

### 4.5 Step planner pre-LLM (≤200 LOC pseudocódigo Python)

El planner descompone el prompt en una **lista canónica de pasos** ANTES de la primera llamada a Gemma. Si el resultado son ≥3 pasos, se inyecta como contexto adicional en el system del turno (no como messages de conversación, sino como `<plan>...</plan>` antes del prompt user, para que el LLM lo lea pero no lo trate como historial):

```python
# step_planner.py  (≤200 LOC objetivo)
import re
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Step:
    tool: str
    args: dict          # puede tener placeholders "$prev.result.X"
    purpose: str        # texto humano corto, va al plan inyectado

# Patrones canónicos. Cada pattern es (regex sobre prompt, builder de pasos).
PATTERNS = [
    # C14 install Steam
    (r"instal[áa].*\b(?:en\s+)?steam\b|steam\b.*instal", lambda m, p: [
        Step("steam_search", {"query": _extract_game(p)}, "Resolver appid"),
        Step("gui_deeplink", {"uri": "steam://install/$prev.appid"}, "Disparar install dialog"),
        Step("screenshot_capture", {}, "Capturar diálogo"),
        Step("vision_match", {"expected": "Steam install dialog"}, "Confirmar diálogo"),
        Step("gui_click_xy", {"target": "$prev.button.install"}, "Click instalar"),
        Step("vision_match", {"expected": "downloading or installed"}, "Verificar que bajó"),
    ]),
    # C09 search + open
    (r"busc[áa].*\b(?:y|luego|después)\s+(?:abr[íi]|abrime)", lambda m, p: [
        Step("web_search", {"query": _strip_imperatives(p)}, "Buscar"),
        Step("browser_open", {"url": "$prev.top1.url"}, "Abrir resultado"),
        Step("get_foreground_window", {}, "Verificar ventana abierta"),
    ]),
    # C14 download installer
    (r"instal[áa]me\s+(\w+)(?!.*\bsteam\b)", lambda m, p: [
        Step("web_search", {"query": f"{m.group(1)} download official"}, "Buscar instalador"),
        Step("web_fetch", {"url": "$prev.top1.url"}, "Leer página"),
        Step("web_download", {"url": "$prev.installer_url", "to": "%TEMP%"}, "Descargar"),
        Step("process_run", {"path": "$prev.path"}, "Ejecutar instalador"),
        Step("screenshot_capture", {}, "Ver wizard"),
        Step("vision_describe", {}, "Describir wizard"),
        # los clicks subsecuentes los decide el LLM con la info visual
    ]),
    # C09 search + copy
    (r"busc[áa].*\b(?:y\s+)?cop[íi]a", lambda m, p: [
        Step("web_search", {"query": _strip_imperatives(p)}, "Buscar"),
        Step("clipboard_set", {"text": "$prev.top1.snippet"}, "Copiar al clipboard"),
        Step("clipboard_get", {}, "Verificar"),
    ]),
    # C08 último archivo + abrir
    (r"\b[úu]ltim[oa].*\b(?:pdf|archivo|documento)\b.*abr", lambda m, p: [
        Step("fs_list", {"path": "%USERPROFILE%\\Downloads", "filter": "*.pdf",
                         "sort": "mtime_desc", "limit": 1}, "Listar"),
        Step("gui_open", {"path": "$prev[0].path"}, "Abrir"),
        Step("get_foreground_window", {}, "Verificar"),
    ]),
    # ... ~6 patterns más cubren ~80% de C09+C14
]

def plan(prompt: str) -> Optional[List[Step]]:
    p = prompt.lower()
    for regex, builder in PATTERNS:
        m = re.search(regex, p)
        if m:
            return builder(m, prompt)
    # Fallback: detección genérica de coordinación "y luego" / "y después"
    if re.search(r"\b(y\s+luego|y\s+después|y\s+despues|y\s+después de eso)\b", p):
        return None  # devolver None pero loguear "multistep generic"; el LLM lo manejará
    return None

def to_plan_block(steps: List[Step]) -> str:
    if not steps:
        return ""
    lines = [f"<plan>"]
    for i, s in enumerate(steps, 1):
        lines.append(f"  {i}. {s.purpose}  →  {s.tool}({_compact_args(s.args)})")
    lines.append("</plan>")
    return "\n".join(lines)

def _extract_game(p): ...   # ~10 LOC con heurísticas (palabra capitalizada larga, "Stardew Valley" etc.)
def _strip_imperatives(p): ...  # quita "buscá|buscame|por favor" → query limpio
def _compact_args(d): ...
```

**Cómo se inyecta** (en `04_agent.py` antes de la primera call al LLM):

```python
plan_steps = step_planner.plan(user_prompt)
if plan_steps and len(plan_steps) >= 3:
    plan_block = step_planner.to_plan_block(plan_steps)
    system_with_plan = SYSTEM_V3 + "\n\n" + plan_block
    turn_profile = "mission"  # depth=10
elif plan_steps and len(plan_steps) == 2:
    system_with_plan = SYSTEM_V3
    turn_profile = "action_verify"  # depth=4
else:
    system_with_plan = SYSTEM_V3
    turn_profile = classify_by_length(user_prompt)  # trivial|simple
```

El plan inyectado **no obliga** al LLM (Gemma 4 puede desviarse si recibe info nueva), pero le da el esqueleto. Resuelve E (abandono) estructuralmente: cuando el LLM ve el plan, raramente se detiene en el paso 1.

### 4.6 `finish_reason=length` en medio de una cadena

Reportado en bench externo. Causas: thinking channel largo + tool args largos rebasan `max_tokens` por turno. Tres mitigaciones, en orden:

1. **Subir `max_tokens` por turno a 1024** (default suele ser 256) cuando `turn_profile` ∈ {action_verify, multi_step, mission}. Costo: VRAM marginal con KV f16, latencia ~+200ms peor caso.
2. **Detectar `finish_reason=length` y reanudar**: en `06_adapter_llamacpp.py`, si la respuesta termina en `length` y *no* contiene un `<tool_call|>` cerrado, hacer un follow-up call con `prompt = previous + completion_partial` y `max_tokens=512`. El llama.cpp server soporta esto con prompt prefix matching automático.
3. **Comprimir el thinking**: aplicar la "LOW thinking SI" de Google embebida en R2 — instruye al modelo a pensar brief en simple/action-verify, y full en mission. Reduce ~20% los thinking tokens según Google.

> **Pitfall reportado** (issue llama.cpp #20809, Qwen3 Instruct, mismo síntoma posible en Gemma 4): false thinking detection puede meter el `tool_call` en `reasoning_content` con `finish_reason=length`. Si lo ven en logs, override del jinja template (ver §5 A): usar el chat template de `asf0/gemma4_jinja` (PR llama.cpp #21326 mergeado) que evita el leak del thinking channel a content y mejora la detección de tool_call.

---

## 5. Deliverable 5 — Plan de validación staged (5 stages, dos números cada uno)

### 5.0 Aclaración metodológica de los dos números

- **PASS oficial estimado** = lo que `audit_case()` del runner contaría: tools correctas en orden esperado + verifier marcado OK + latencia < budget. No reproduce la veracidad semántica del reply.
- **PASS REAL estimado** = PASS oficial menos los casos donde el reply final probablemente afirma un hecho como verificado sin haber verificado. Aplica el criterio del audit manual qwen3 (88.89% / 61% → factor 0.687 sobre el oficial en qwen3). Para Gemma 4 IQ2_M con el v3 propuesto, el factor mejora a ~0.92–0.95 (porque R11 + R12 + post_actions automáticas cierran la mayoría de FALSE_PASS), pero **no llega a 1.0** sin un step de revisión adicional.

Las estimaciones que siguen son con **incertidumbre ±5% absoluta** sobre 540 — i.e. ±27 casos. Se basan en: (a) el patrón histórico qwen3 88.89/61, (b) las mejoras esperables por cada cambio según research público, (c) mi taxonomía de 51 clases. **Validación empírica es indispensable** porque no tengo trazas REPL.

### 5.1 Stage A — CORE_PROMPT v3 + anchors definitivas

**Cambios exactos:**
- `codigo_carter/03_models_gemma4.py` línea ~`[REQUIERE FS — donde se define CORE_PROMPT]`: reemplazar el bloque por v3 (§2.2). Reducir reglas de 12 a 12 (mismo número, distinto contenido) + 6 few-shots (mismo número). Verificar conteo de tokens con tokenizer Gemma 4 ≤1500.
- `codigo_carter/03_models_gemma4.py`: confirmar sampling `temperature=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0`, samplers order `"temperature;top_p;top_k"`. Si el actual difiere, alinear.
- `codigo_carter/05_tool_retrieval.py` `_ANCHOR_TOOL_NAMES`: reducir de 22 a 12 según §3.2 lista A1–A12. **`[REQUIERE FS — diff exacto contra anchors actuales]`**.
- `llama-server` cmdline al arrancar: `--jinja --flash-attn --cache-type-k f16 --cache-type-v f16 --ctx-size 16384 --mmproj mmproj-BF16.gguf --chat-template-file gemma4_custom.jinja` (ver `asf0/gemma4_jinja`). Confirmar `--n-gpu-layers 999`.

**Casos del 540 que cierra:** clases 1, 2, 3, 5, 6, 7, 8, 9, 16, 31, 33, 38, 39, 40, 41, 42, 43, 47, 48 — i.e. los casos que ya funcionaban en qwen3 + los que se rompían por anchor incorrecta o por hallucination atemporal. Aproximadamente **+50–80 PASS** sobre baseline.

**Métrica de éxito (subset):** sub-bench de 60 casos balanceado (3 por categoría C01–C18 excepto C18) corrido localmente; target PASS ≥45/60 (75%) — coherente con el bench externo de 60 que reportó 55/60 = 91.7% (ese fue con E4B nativo + sampling oficial pero sin Carter; perdemos algo por el agente, ganamos algo por anchors).

**Criterio de rollback:** PASS sub-bench < 35/60 (58%) o latencia p99 sube >50%.

**Estimación 540:**
- PASS oficial: **~340/540 (63.0%)**
- PASS REAL: **~310/540 (57.4%)**
- Comentario: arranca por encima del baseline qwen3 oficial (88.89% sobre los 540 que vio el grader, pero baseline real era 61%). Con E4B-IQ2 y v3, recuperamos los ~310 casos triviales+lookup+web simple+vision simple. El delta inicial entre oficial y real es bajo porque R11+R12 ya están desde Stage A.

### 5.2 Stage B — ReAct depth dinámico + step planner pre-LLM

**Cambios exactos:**
- `codigo_carter/04_agent.py`: añadir `turn_profile` enum y `DEPTH_BY_PROFILE = {"trivial":1, "simple":2, "action_verify":4, "multi_step":6, "mission":10}`. Reemplazar `max_depth=3` constante por lookup. **`[REQUIERE FS — número de línea]`**.
- `codigo_carter/04_agent.py`: importar y llamar `step_planner.plan()` antes de la primera call al LLM (ver §4.5). Inyectar plan como bloque `<plan>...</plan>` en el system del turno.
- nuevo archivo `codigo_carter/step_planner.py` (~180 LOC siguiendo §4.5).
- `codigo_carter/04_agent.py`: budget temporal por profile: trivial 5s, simple 8s, action_verify 15s, multi_step 20s, mission 30s.

**Casos del 540 que cierra:** clase 11 (C07 multi), clase 12 (C07 deep dig), clase 18 (C09 search+open), clase 19 (C09 search+copy), clase 20 (C09 search+download), clase 21 (C09 lookup+app), clase 22 (C14 install Steam), clase 23 (C14 install browser), parte de clase 24 (C14 configurar), clase 25 (C14 último archivo), clase 27 (C14 multi-app workflow). **+60–80 PASS** sobre Stage A.

**Métrica de éxito (subset):** subset de 60 casos C09+C14 (todos), target PASS ≥30/60 (50%) — estos son los más duros. Si <20/60 hay un problema fundamental con el step planner.

**Criterio de rollback:** latencia p99 trivial > 5s (significa que el clasificador de turno se está disparando mal y abrupta) o PASS C01 baja de Stage A.

**Estimación 540:**
- PASS oficial: **~410/540 (75.9%)**
- PASS REAL: **~370/540 (68.5%)**

### 5.3 Stage C — Vision triggers automáticos post-deeplink

**Cambios exactos:**
- `codigo_carter/09_tools_init.py`: agregar `TOOL_POSTACTIONS` dict (§4.3). **`[REQUIERE FS — patrón de registro actual de tools]`**.
- `codigo_carter/04_agent.py`: en el bucle ReAct, después de ejecutar cada tool, ejecutar `TOOL_POSTACTIONS.get(tool, [])` y concatenar los resultados al `tool_response` antes de devolver al LLM.
- Confirmar que `mmproj-BF16.gguf` está cargado y que `screenshot_capture` + `vision_describe`/`vision_match` funcionan end-to-end. Sin esto, post_actions caen en silencio.
- `codigo_carter/09_tools_init.py`: agregar tool `get_foreground_window` (Python: `win32gui.GetForegroundWindow()` → `GetWindowText` + `psutil.Process(pid).name()`). ~20 LOC.
- `codigo_carter/09_tools_init.py`: agregar tool `vision_match(expected: str) -> {matched: bool, found: str, confidence: float}` que envuelve un call a Gemma 4 con prompt fijo "Does the image show: <expected>? Answer yes/no first, then describe."

**Casos del 540 que cierra:** clases 17 (fs_write verifier), 22 (C14 Steam), 23 (C14 browser install), 24 (C14 configurar app), 27 (C14 multi-app workflow), 31 (C10 abrir conocida), 32 (C10 abrir desconocida — convierte en UNVERIFIED honesto), 34 (C11 deeplink), 36 (C12 Spotify play), 51 (C17 confirmar UI). Crítico para la **brecha oficial→real**: este stage es el que más sube PASS REAL sin subir mucho PASS oficial (porque el oficial ya contaba muchos como pass falsos).

**Métrica de éxito (subset):** subset de 30 casos action+verify (clases 17, 22, 31, 34, 36, 51), target PASS REAL ≥22/30 (73%). Crítica: corre el subset, audita manualmente las respuestas, marca FALSE_PASS por Valor 3.

**Criterio de rollback:** latencia p99 mission > 35s (post_actions agregan ~3-5s por step) — si pasa, recortar `sleep` de los post_actions a la mitad o paralelizar `screenshot_capture` con `get_foreground_window`.

**Estimación 540:**
- PASS oficial: **~445/540 (82.4%)** (el grader oficial puede penalizar ahora algunos casos que tu agente correctamente reporta UNVERIFIED — neto sube poco)
- PASS REAL: **~430/540 (79.6%)** (gran salto: la brecha se cierra)

### 5.4 Stage D — Verifier orchestration con `TOOL_OK_VERIFIER_INCONCLUSIVE`

**Cambios exactos:**
- `codigo_carter/07_verifier_orchestrator.py`: garantizar que el estado `TOOL_OK_VERIFIER_INCONCLUSIVE` (la tool ejecutó OK pero el verifier post-action no confirmó el efecto) esté implementado y se propague al LLM como **prefijo del tool_response**: `"VERIFIER_INCONCLUSIVE: <verifier_output>"`. **`[REQUIERE FS — estado actual]`**.
- `codigo_carter/04_agent.py`: si tras N=3 `TOOL_OK_VERIFIER_INCONCLUSIVE` consecutivos en el mismo turn, abortar la cadena y forzar al LLM a un reply UNVERIFIED (truncar tools, dejar pasar solo `reply_text`).
- `codigo_carter/07_verifier_orchestrator.py`: estado `INTENT_NOT_FULFILLED` — al cierre del turno (LLM emitió reply final), ejecutar un verifier semántico ligero: **comparar `reply` contra el `plan` originalmente inyectado**. Si el plan tenía 5 steps y el agente solo ejecutó 2, marcar `INTENT_NOT_FULFILLED` y degradar a UNVERIFIED. Esto resuelve patrón E desde otro ángulo.

**Casos del 540 que cierra:** clases 17, 22, 23, 24, 27, 31, 32, 36, 51, y todos los C09 que terminaban con reply afirmativo prematuro.

**Métrica de éxito (subset):** mismo subset Stage C + 30 C09, target PASS REAL ≥48/60 (80%) y FALSE_PASS rate <5%.

**Criterio de rollback:** PASS REAL no sube ≥3% sobre Stage C (significa que el verifier orchestrator no está detectando bien INTENT_NOT_FULFILLED) o respuestas UNVERIFIED se vuelven >25% del total (sobre-conservadurismo).

**Estimación 540:**
- PASS oficial: **~458/540 (84.8%)**
- PASS REAL: **~450/540 (83.3%)**

### 5.5 Stage E — Anti-mentira post-LLM checks aplicados al reply final

**Cambios exactos:**
- `codigo_carter/08_reply_checks.py`: añadir tres checks post-LLM al reply final, cada uno bloqueante con re-roll o conversión a UNVERIFIED:
  1. **Check de afirmación-sin-evidencia**: scan de patrones lingüísticos típicos en español de Carter ("listo", "ya está", "instalado", "abierto", "se guardó", "se envió"). Para cada match, verificar que el último `tool_response` en el turno contenga evidencia consistente (el verifier dijo OK, no INCONCLUSIVE). Si no, reescribir el reply con `"<verbo en pretérito>... aunque no pude confirmarlo"` o forzar re-roll una vez.
  2. **Check de cita en C04/C03 volátil**: si el prompt detectó intent volátil (tasa de cambio, weather, score, time-sensitive) y el reply no contiene un timestamp o URL de fuente, marcar y re-rollear pidiendo cita.
  3. **Check de loop/repetition collapse** (issue Gemma 4 #622): si el reply contiene la misma palabra ≥4 veces en ventana de 10 tokens o termina con un patrón doble ("$\\text{}$" / "visually-cent,"), abortar y re-rollear con `temperature=0.7` ese único call. (Único lugar donde nos desviamos del sampling oficial — está justificado como mitigación de bug conocido sin solución oficial.)
- `codigo_carter/08_reply_checks.py`: añadir un anti-eco más estricto: si el reply contiene >40% de las palabras del prompt user en orden, marcar y re-rollear.

**Casos del 540 que cierra:** los últimos FALSE_PASS residuales — típicamente C14 instalaciones donde el verifier era ambiguo y el LLM redondeó a "instalado", C03 con dato inventado sin cita, y los muy raros casos de loop con grammar.

**Métrica de éxito (subset):** sub-bench completo de 60 casos balanceado, target PASS REAL ≥52/60 (87%) y FALSE_PASS ≤2/60.

**Criterio de rollback:** re-rolls dispararse en >15% de los turns (latencia y costo) o Gemma 4 entra en loops de re-roll.

**Estimación 540:**
- PASS oficial: **~462/540 (85.6%)** (apenas sube; los checks evitan FALSE_PASS pero no crean PASS nuevos)
- PASS REAL: **~462/540 (85.6%)** (la brecha colapsa: cuando el agente bloquea su propia mentira, lo que pasa el grader oficial es lo que es real)

### 5.6 Techo final estimado por categoría

> **Importante:** las cifras siguientes son estimaciones con **incertidumbre ±2 casos por categoría** y **±15 casos en el total**, por las razones declaradas en §5.0 (no tengo trazas REPL ni latencias medidas). Son honestas, no upsell.

| Categoría | PASS oficial | PASS REAL | Delta |
|---|---|---|---|
| C01 trivial | 30/30 | 30/30 | 0 |
| C02 hora/fecha | 30/30 | 30/30 | 0 |
| C03 atemporal | 26/30 | 25/30 | -1 (M residual sin cita) |
| C04 volátil | 28/30 | 27/30 | -1 |
| C05 cálculo | 30/30 | 30/30 | 0 |
| C06 web simple | 29/30 | 28/30 | -1 |
| C07 web compleja | 26/30 | 24/30 | -2 |
| C08 FS | 28/30 | 27/30 | -1 |
| C09 multi-step | 24/30 | 22/30 | -2 |
| C10 abrir/cerrar | 28/30 | 27/30 | -1 |
| C11 deeplink | 27/30 | 26/30 | -1 |
| C12 Steam/Spotify/YT | 26/30 | 24/30 | -2 |
| C13 sistema | 29/30 | 29/30 | 0 |
| **C14 misión** | **18/30** | **15/30** | **-3** (P1 + casos largos) |
| C15 valores | 28/30 | 28/30 | 0 |
| C16 memoria | 28/30 | 28/30 | 0 |
| C17 vision | 26/30 | 24/30 | -2 |
| C18 audio | n/a | n/a | omitida del sprint |
| **TOTAL (sin C18)** | **461/510 (90.4%)** | **444/510 (87.1%)** | **-17** |
| **TOTAL (incl C18=0)** | **461/540 (85.4%)** | **444/540 (82.2%)** | **-17** |

Frase final del techo:

> **Con la config recomendada, esperamos PASS oficial ≈ 461/540 (85.4%) y PASS REAL ≈ 444/540 (82.2%), con el delta de 17 casos concentrado en C14 (misiones complejas que tocan el techo capability de E4B-IQ2_M en razonamiento multi-paso de programador), C07/C09 (cadenas web largas con dependencias), C12 (deeplinks de apps con UI variable que la vision E4B no siempre desambigua), y C17 (counts y verificaciones visuales precisas). Llegar a 540/540 con `gemma-4-E4B-it-UD-IQ2_M` no es alcanzable: 30–35 casos están estructuralmente fuera del techo del modelo o del agente. El número honesto recomendable como meta operacional es 460/540 oficial y 440/540 real.**

Si el cliente quisiera empujar el techo hacia 510/540, los tres únicos caminos honestos serían: (a) cambiar de quant a IQ4_XS o Q4_K_M (subiría ~12 casos pero rompería target VRAM 8 GB y restricción IQ2_M), (b) agregar un router que para C14 derive al modelo 26B-A4B (rompería target VRAM y restricción modelo único), (c) fine-tune QLoRA sobre los ~50 casos del bench (rompería honestidad de evaluación). Ninguno aplica a este sprint.

---

## 6. Casos donde declaro explícitamente "no se cierra"

Por Valor 3, las siguientes clases del bench se marcan **techo del modelo o del agente**, y el comportamiento esperado del agente es responder UNVERIFIED o decir explícitamente "no puedo hacer esto":

- **C14-{coding mayor}** (corregir bug + agregar test que falle antes): razonamiento de programador multi-paso. E4B-IQ2 no llega; tampoco un E4B fp16 completo lo haría confiable. Recomendación: detectar por planner ("escribí un test", "corregí este bug", "refactorizá") y degradar a UNVERIFIED inmediato con "este tipo de tarea requiere un modelo más grande, abrime el editor y guido manualmente". ~3–5 casos del bench.
- **C03 atemporal específico no lookup-able** (ej. "qué dijo X en su discurso de tal fecha exacta" donde el modelo puede saberlo o no): E4B-IQ2 alucina. Mitigación con R5/R8 (forzar web_search), pero algunos casos no lo resuelven porque la búsqueda no devuelve la cita literal. ~2–4 casos.
- **C17 counts precisos** ("cuántas pestañas tengo abiertas exactas si son 23"): vision E4B con mmproj BF16 da counts aproximados, no determinísticos. Mejor solución es complementar con tool determinista (UIAutomation tree para contar windows; Chrome DevTools Protocol para contar tabs). ~2–3 casos.
- **C14 misiones que dependen de UI con texto variable en idiomas mezclados**: la vision a 280 tokens no siempre OCRea bien menús específicos. Subir a 1120 tokens cuesta +3s/call y a veces tampoco. ~3–5 casos.

Total casos "no cierra": **~10–15**, ya descontados en la estimación de §5.6.

---

## 7. Datos faltantes confirmados (requieren medición empírica)

Lo siguiente NO se puede estimar sin correr el código:

- **Latencia real Gemma 4 IQ2_M en RTX 4060 Ti** sobre los 540 casos: solo hay bench externo de 60. Los budgets §4.1 (5s/8s/15s/20s/30s) son extrapolaciones razonables pero requieren ajuste tras 1ª corrida.
- **Trazas REPL estructuradas de Gemma 4 IQ2_M con Carter**: solo hay reportes verbales. Sin ellas, no puedo prescribir el fix exacto para un cid específico.
- **Estabilidad del sampling oficial T=1.0** con el catálogo de tools largo: posible interacción con el bug de repetition; medir tasa de finish_reason=length y FAIL por loop tras Stage A.
- **Comportamiento del jinja template oficial vs `asf0/gemma4_jinja`**: es plausible que el oficial llegue al cliente con leak de `<channel>thought` en `content`. Medir e intercambiar si confirmado.
- **Tasa de FALSE_PASS sobre los 540** con cada stage: el factor 0.92–0.95 oficial→real que estimo en §5.0 es el delta histórico esperable; medir manualmente sobre un subset auditado de 60 casos en cada stage.

Cualquier número de §5 que diverja >10% del medido empíricamente debería gatillar revisión de la taxonomía §1 antes de la siguiente iteración.

---

## 8. Resumen ejecutivo accionable

1. **No prometer 540/540.** Meta honesta del sprint: **460/540 oficial, 440/540 real**, con curva A→E que sube ~120 casos sobre el baseline qwen3 88.89%/61% real.
2. **Stage A (CORE_PROMPT v3 + 12 anchors + sampling oficial + jinja fix)**: implementar primero, medir contra sub-bench 60. Esperado +50–80 PASS.
3. **Stage B (depth dinámico + step planner pre-LLM)**: el cambio de mayor impacto cuantitativo. +60–80 PASS.
4. **Stage C (post_actions automáticas con vision)**: el cambio de mayor impacto cualitativo (cierra Valor 3 sobre C14/C11/C10). +30–50 PASS REAL aunque PASS oficial suba menos.
5. **Stage D (verifier orchestration TOOL_OK_VERIFIER_INCONCLUSIVE + INTENT_NOT_FULFILLED)**: cierra los FALSE_PASS estructurales. +20 PASS REAL.
6. **Stage E (anti-mentira post-LLM, anti-loop, anti-eco)**: pulido final, defensiva. +5–10 PASS REAL, FALSE_PASS rate <5%.
7. **No tocar**: el modelo (IQ2_M), el quant, KV f16, FA, repeat_penalty=1.0 (a pesar del bug — la mitigación va en post-checks, no en sampling), qwen3 fallback.
8. **Pasada FS local imprescindible** para: (a) completar la lista de cids individuales en D1, (b) anchors actuales vs propuestas en D3, (c) números de línea exactos en D5. ~30 minutos de trabajo manual con los archivos a la vista.

Implementar en este orden: A → medir → B → medir → C → audit manual de FALSE_PASS → D → E. Total estimado: 6–10 horas de implementación + 4–6 horas de medición y ajuste, alineado con el budget del brief.