# Palancas del notebook (fase A, objetivo «BAXY Renew al máximo»)

Base: `pc-system-one` 86991ca9d (= `renew-maximo` al empezar). Áreas del notebook: 3 inferencia, 6 providers, 7 computer
use, 10 latido, 11 memoria y privacidad, 12 medición y holdout nuevo. Cada área la investigó un subagente de sólo lectura
(código entero del área más fuentes de 2024-2026); yo verifiqué en el código lo que aquí se marca «verificado». Ninguna
cifra de ganancia está medida todavía salvo donde dice «medida»: son esperadas.

Columnas como las pide `MAXIMO.md`. **Máquina autor** según los archivos que toca: portátil = providers
(`src/Baxy.Providers.Windows`, datos `app_places`); PC = mente (`src/baxy_mind`), App, Core y Kernel. Es una propuesta;
decide el líder.

## 0. Antes de todo: la base no tiene «CU rápido» (verificado)

`hub/pc-cu` (a0b103cb1, 51 commits, 18/18 casos de computer use con sus variantes) **no está** en 86991ca9d
(`git merge-base --is-ancestor hub/pc-cu HEAD` → no). Faltan `office.format.apply`, `clipboard.paste.into`,
`game.store.search/page`, `client.microphone.set`, `startsBehindSignIn`, la salida de pantalla completa (C13) y dos
arreglos de robustez y seguridad: `@($found).Count` sobre `List[object]` en PowerShell 5.1
(`DesktopUiaWorker.ps1:2684`, deja a Word y Excel sin árbol) y `visible_settings_switch_refused` (un clic volvió a
conmutar la radio Wi-Fi en C02). `git merge-tree` da 4 conflictos: `WindowsVisibleControlAdapter.cs`,
`tool_descriptions.en.v1.json`, `ProductCatalogTests.cs`, `ComputerUseWindowIdentityTests.cs`.
**Propuesta: fusionar pc-cu en renew-maximo como palanca 0, antes de medir las demás** (aviso al líder 2026-10-22 14:3x).

## Las que más prometen por su costo (mi orden propuesto)

1. **0 — fusionar pc-cu** (banco CU 18/18 medido allí; dos arreglos de seguridad).
2. **3.1 — Laya con `-dev none`**: hoy S1 deja la VRAM a 5 MiB del techo (medido); una línea.
3. **3.3 — `-ctxcp 8 -cram 0`**: −1,2 GB de pico de RAM en sesiones largas; dos flags.
4. **3.2 — historial con histéresis**: −1,5 a −3,6 s en sesiones largas (cifras de traza).
5. **R10.1 + R10.2** (errores del latido): ajustes del sistema solos en un latido (modo avión visto en traza) y las
   reglas del latido metidas en la conversación de la persona.
6. **7.7/R7.2 — repetición que compara contenido** y **6.3 — pistas de recuperación** en apps y juegos.
7. **12.1-12.3 — medir bien**: semillas que de verdad cambian, pareo por ítem, réplicas por edición neutra. Sin esto,
   las ganancias de <3 puntos de la fase B no se pueden decidir.
8. **10.1/10.2 — latido calibrado y con forma** (0 a +3 escenas; primero sólo traza).
9. **7.1 — vista de después en el recibo del acto** (un paso de modelo menos por acto en computer use).
10. **11.4/11.5 — privacidad**: sesiones cifradas y borrables; freno de salida a la red con datos de memoria.

## Tabla

| # | Palanca | Área | Evidencia | Fuente | Ganancia esperada | Banco | VRAM / RAM / latencia | Riesgo | Esfuerzo | Medida o esperada | Máquina |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Fusionar `hub/pc-cu` | 7 | ver §0 | CU_CASOS.md en a0900861b | banco CU ~9/18 → 18/18; casos Word/Excel/Steam/pegar del e2e | CU 18, e2e, decision2 s0 | 0 / 0 / 0; +~5 descripciones en el prefijo | prefijo se mueve (d2 229/268 en pc-cu) | bajo (4 conflictos) | medida en pc-cu | ambas |
| 3.1 | Laya fuera de la GPU de verdad: `-dev none` (o `--no-op-offload`) | 3 | `system_one.py:73-75` (`-ngl 0` sin `-dev none`; `:59` dice «no VRAM»); **medido hoy**: VRAM S1 off 3902 MiB, S1 on **4091 MiB** (+189), RAM del producto 2438 → 2719 MiB | [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) («`-dev none` = don't offload», «op-offload default: true») | hasta −189 MiB de VRAM (hoy a 5 MiB del techo); Laya deja de competir con Qwen en la GPU | recursos; latencia de Laya; decision2 S1 on idéntico | −189 MiB / ≈0 / Laya algo más lenta (medir) | ninguno | trivial | VRAM medida; ganancia esperada | PC (mente) |
| 3.2 | Recortar el historial con histéresis (al pasar de 8 turnos, bajar de golpe a 4) | 3 | `mind.py:711-722`, `HISTORY_TURNS=8` (`:318`): desde el 9.º turno cada orden relee todo el historial; 18 `turn.decide` releyeron 1,5k-4,4k tokens (1,5-3,6 s) en la traza | [b11609 server-context.cpp](https://github.com/ggml-org/llama.cpp/blob/fcac19079/tools/server/server-context.cpp) (borra los checkpoints tras la divergencia; sin `--cache-reuse` en estado recurrente) | −1,5 a −3,6 s de primer sonido en 3 de 4 órdenes de una sesión larga | sesión larga de 20 turnos (`prompt_n`, `prompt_ms`) | 0 / 0 / − | menos contexto a veces | bajo | esperada (cifras de traza) | PC (mente) |
| 3.3 | `-ctxcp 8 -cram 0` (tope de checkpoints; la caché de prompt en RAM nunca guarda con el latido) | 3 | `llm_server.py:47-51`; defectos de b11609 `-ctxcp 32`, `-cms 8192` ([common.h](https://github.com/ggml-org/llama.cpp/blob/fcac19079/common/common.h) l.637-640); ~50 MiB por checkpoint (24 capas DeltaNet) → ~1,6 GiB en sesión larga | [#21690 RAM de checkpoints hasta OOM](https://github.com/ggml-org/llama.cpp/issues/21690); [PR #15293](https://github.com/ggml-org/llama.cpp/pull/15293), [PR #16391](https://github.com/ggml-org/llama.cpp/pull/16391) | −1,2 GB de pico de RAM en sesiones largas; guardar/restaurar de visión más corto | recursos en sesión larga; decision2 | 0 / −1,2 GB / ≈0 | releer más si se pierde un checkpoint útil | trivial | esperada | PC (mente) |
| 3.4 | Pre-calentar la GPU cuando empieza a hablar la persona (`chat` con `max_tokens:1`, como `warm()`) | 3 | traza: `turn.continue` sin hueco 148 ms p50; tras 3-8 s de hueco 367 ms; todo `turn.decide` llega tras un hueco (388 ms para <50 tokens) | sólo anecdótica ([foro PyTorch](https://discuss.pytorch.org/t/first-batch-after-idle-between-workloads-is-much-slower-even-with-preloaded-data/224902)) | ~−0,25 s de primer sonido por orden | e2e (latencia), script de huecos con `nvidia-smi pstate` | 0 / 0 / − | nulo (no propone ni ejecuta) | medio (App avisa a la mente) | esperada (cifras de traza) | PC |
| 3.5 | Renderizar y tokenizar una sola vez por decisión dudosa (hoy `complete_name` re-aplica la plantilla y re-tokeniza ~44k tokens por rival, hasta 3 veces) | 3 | `mind.py:974`, `llm_server.py:110-113`; sobrecarga fija 106-138 ms p50 por petición | — | −100-200 ms en decisiones con S1 (confianza <0,6) | decision2 S1 on (latencia) | 0 | ninguno | bajo | esperada | PC |
| 3.6 | Latido con idéntico texto de sistema que el turno (la frase de la regla 2 pasa al mensaje de reloj) | 3 | `mind.py:63-71`; cada latido relee 1058-1073 tokens (0,93-1,27 s) en el único slot | — | −0,7 s por latido; una orden durante un latido espera menos | decision2, escenas (ruido ±6) | 0 | cambia el prompt del turno | bajo | esperada | PC |
| 3.7 | Respuesta final a la voz en streaming (sólo el paso `final`, que ya prohíbe `<tool_call>`) | 3 | `mind.py:860-866`; la voz ya va por frases (`voice_output.py:11`) | — | −0,2-0,4 s de primer sonido | e2e (latencia) | 0 | medio (cambia el protocolo) | medio | esperada | PC |
| 3.8 | Reserva de VRAM: `-ub 256`, o c2e1 en IQ4_XS con imatrix | 3 | IQ4_XS base: mismos aciertos, −254 MiB (`PROGRESO-nb.md:245`) | — | margen de VRAM si 3.1 no basta | los 4 bancos | − / 0 / ? | recuantizar el ajustado | medio | IQ4_XS medida sobre el base | portátil |
| 6.1 | `media.status` da todas las sesiones (`otherSessions`), no sólo la «actual» | 6 | `WindowsMediaSessionAdapter.cs:591-625`; el esquema de `media.control.sourceApp` admite que el modelo no puede conocer otro id (`tool_descriptions.en.v1.json:215`) | [Anthropic, writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) | «qué suena» y «pausa Spotify» ciertos con dos reproductores | falsedades, vivo (el e2e no tiene medios) | 0 / 0 / +30-80 tokens | ninguno (lectura) | bajo | esperada | portátil |
| 6.2 | `app.open` con lugar dice si la ventana cambió (`placeWindowChanged`), dato que hoy se tira | 6 | `ApplicationPlaceOpener.cs:64-84` (`SameSurface` :76, «Nothing is said from it»); `AppOpenHandler.cs:129-148` | mismo | E015, F019, «leyó mal la vista» (1 → 3 en ayudas) | e2e, falsedades | 0 / 0 / 0 | «cambió» no prueba el lugar: el campo dice sólo eso | bajo | esperada | portátil (+ ayuda 1c: PC) |
| 6.3 | Pistas de recuperación en fallos de apps y juegos (hechos, apagables como `ModelAids`): `launchIssued`, `place_not_opened` con su `windowId`, `steam_title_not_resolved` con candidatos y «sin red» aparte, pista a `game_entitlement_named` | 6 | `AppOpenHandler.cs:84-91,118-123`; `SteamLocalAdapter.cs:262,537-544,779` | [Fission-GRPO, ACL 2026](https://doi.org/10.48550/arXiv.2601.15625); Anthropic (arriba) | F001, F006, F016; E015 | falsedades ×6 semillas, e2e | 0 / 0 / tokens sólo en fallos | ninguno si es hecho, no orden | medio | esperada | portátil |
| 6.4 | `game.launch`: juego ya abierto → `alreadyRunning`; leer el exe con `QueryFullProcessImageName` en vez de `MainModule` | 6 | `SteamLocalAdapter.cs:787,888`; `WindowsInstalledApplicationOpenProvider.cs:~2095-2108` | [MainModule](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainmodule), [QueryFullProcessImageName](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew) | quita 35 s y un fallo falso (error R2) | vivo, prueba unitaria | 0 / 0 / −35 s en ese caso | bajo | bajo | esperada | NB |
| 6.5 | Apps empaquetadas por `IApplicationActivationManager::ActivateApplication` (HRESULT y PID inmediatos), con la ruta actual de respaldo | 6 | `WindowsInstalledApplicationOpenProvider.cs:2120-2143` (explorer `shell:AppsFolder`, un AUMID roto cuesta 30 s) | [ActivateApplication](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationactivationmanager-activateapplication); [UFO2](https://doi.org/10.48550/arXiv.2504.14603) | latencia en Calculadora, el Bloc de notas y la Configuración (E003, E007, E010-E012, E014) | e2e, 10 aperturas por app | 0 / 0 / − | medio (`FileActivation.cs:8`: `ActivateForFile` falló con empaquetadas aquí) | medio | esperada | NB |
| 6.6 | Catálogo de apps: usar el vencido si resuelve y refrescar detrás | 6 | `ReadCatalogAsync` `:613`, `CatalogLifetime` `:27` (PowerShell cada 5 min en el camino) | sin fuente externa | primer `app.open` tras una pausa | latencia | 0 / 0 / − | ninguno (la ventana se verifica igual) | bajo | esperada | portátil |
| 6.7 | Presupuesto único (~60 s) para `media.play.youtube` con mpv | 6 | `YouTubeMpvAdapter.cs:168,234,250` suman más que la espera de la App (`CoreProcessClient.cs:19`) | sin fuente externa (límite propio) | evita reinicios del núcleo (como M89) | prueba con resolver lento | 0 | bajo | bajo | esperada | portátil |
| 6.8 | Juegos de Epic por su protocolo (datos en `app_places` + lector de `.item` que ya existe) | 6 | `SteamLocalAdapter.cs:397` ya lee `AppName` e `InstallLocation` | sólo comunitarias: [jayd.ml](https://jayd.ml/games/2020/05/19/epicgamesstore-uri.html) | F016 («lanza Fortnite»), hoy imposible | falsedades, vivo | prefijo + / 0 / 0 | medio (formato no oficial) | medio | esperada | portátil |
| 7.1 | El recibo de un acto (clic, escribir, tecla) trae la vista de después como diferencia y pasa a ser la última vista; sale la regla «vuelve a mirarla» | 7 | `mind.py:56-58`; `Do-Postread` `DesktopUiaWorker.ps1:3183` sólo da banderas; `same_call_next` `mind.py:781-791` | [Anthropic computer use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool); [reflexión sobre la diferencia, +5,94 OSWorld-V](https://doi.org/10.48550/arXiv.2608.24015) | un paso de modelo menos por acto (1-3 s); menos «afirmar sin mirar» | CU 18, e2e multipaso, falsedades | 0 / 0 / +0,3-1,3 s de lectura, −1 decisión | índices viejos si no reemplaza a la última vista | medio | esperada | portátil (adaptador) + PC (regla de la mente) |
| 7.2 | Vista sin OCR que repite el nombre de un control listado (se dice cuántas líneas se omitieron) | 7 | `ScreenViewProjection.cs:174-200`; `WindowsVisibleControlAdapter.cs:1791,1909-1949` | [A11y-Compressor](https://doi.org/10.48550/arXiv.2605.00551); [AgentOccam tabla 10](https://doi.org/10.48550/arXiv.2410.13825) | pequeña-media; menos contexto en turnos largos | replay offline de vistas, luego CU | 0 / 0 / − tokens | un aviso igual a un botón (por eso se cuenta) | bajo | esperada | PC (App) |
| 7.3 | Zona gruesa por control (arriba/centro/abajo) en la vista | 7 | el worker ya tiene `rect`; `WindowsVisibleControlAdapter.cs:2026-2043` no lo escribe; `ScreenViewProjection.cs:227-255,2246` | A11y-Compressor; [OSWorld](https://doi.org/10.48550/arXiv.2404.07972); [UFO2](https://doi.org/10.48550/arXiv.2504.14603) | desambiguar dos «Buscar», «el primer resultado» | CU 18 | 0 / 0 / +~5 % tokens de vista | bajo | bajo | esperada | portátil + PC |
| 7.4 | Más lugares `ms-settings:` y de apps en `app_places.v1.json` (sólo datos) | 7 | 28 lugares de Configuración hoy; el texto de `app.open` sale de los datos (`mind.py:193-207`) | [ms-settings URIs](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings-app) | «abre la sección X de ajustes» (E014 y parecidos) | decision2 s0, e2e | prefijo + / 0 / 0 | ruido de prefijo ±2 | bajo | esperada | NB |
| 7.5 | Operación genérica de ruta de etiquetas `input.visible.path {window, labels[]}` (menú → submenú → orden), cada paso con `Find-Named`, postlectura y RiskPolicy | 7 | patrón de CU rápido: operaciones con nombre y argumentos obligatorios mueven al 4B | [GOI](https://doi.org/10.48550/arXiv.2510.04607); [UFO2](https://doi.org/10.48550/arXiv.2504.14603); [MCPWorld](https://doi.org/10.48550/arXiv.2506.07672) | menús y cintas (C02, C10v, C11), menos pasos | CU 18, decision2 s0 | +~150 tokens / 0 / − pasos | que el 4B no la elija | medio | esperada | portátil + PC |
| 7.6 | Visión en CPU bajo demanda (mmproj, `--no-mmproj-offload`) sólo cuando UIA, OCR y tooltip no encuentran la etiqueta; retira `WindowsVisibleVisionLocator` | 7 | `DECISION_VISION_V3.md:216,300-304` (aprobada, no construida) | UFO2; [ficha Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) | íconos sin texto (Steam, Epic); pocos casos | banco offline de capturas | 0 / +672 MB / 1,3-10 s por mirada | precisión con pocos tokens de imagen | alto | esperada | PC/portátil |
| 7.7 | La repetición compara también el contenido del resultado (hash de la observación) | 7 | `TurnClosing.cs:37-42`; `mind.py:106-146,784-791` (una mirada siempre «completado») | — (error R2 de §errores) | no cortar esperas legítimas ni decirle al modelo algo falso | prueba unitaria, CU | 0 | ninguno | bajo | esperada | PC (+ Core) |
| 11.1 | El código de E4 llega al modelo (`memory_recall_all_takes_no_selector` a la lista blanca) y `next` para `memory_conflict`, `memory_disabled`, `memory_capacity_reached` | 11 | `PrivateOperationBoundary.cs:12-27`; `MissionEngine.cs:171`; `MemoryHandlers.cs:581`; USO_REAL fila 24 | [Mem0](https://doi.org/10.48550/arXiv.2504.19413) | memoria en e2e; falsedades | e2e, prueba de `MissionEngine` | 0 | ninguno | bajo | esperada | PC (Core) |
| 11.2 | `scope=exact` sin coincidencia lo dice (`exactMatch:false`) en vez de devolver 20 recuerdos como un acierto | 11 | `MemoryHandlers.cs:619-636`; proyección `:541` | — | menos falsedades por atribuir otro recuerdo | prueba nueva, falsedades | 0 | ninguno | bajo | esperada | PC (Core) |
| 11.3 | Las lecturas de memoria no reescriben el almacén (persistir el reloj sólo si avanzó >1 h o hubo purga) | 11 | `LocalMemoryStore.cs:963-981` (cada recall/list/status hace un commit con fsync) | — | decenas de ms por `memory.*` (sin medir) | prueba que cuenta `Seal` | 0 / 0 / − | antirretroceso con resolución de 1 h | bajo | esperada | PC (Core) |
| 11.4 | Sesiones guardadas cifradas (DPAPI) y borrables; «olvida todo» ofrece borrarlas | 11 | `FieldSessionStore.cs:74` JSON en claro con argumentos de cada llamada (`mind.py:904-907`); sin ruta de borrado (`FieldProductChannel.cs:158-165`) | [OpenAI memory FAQ](https://help.openai.com/en/articles/8590148-memory-faq); [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) | hace cierta «se puede borrar entera» | prueba nueva | 0 / 0 / ms | ninguno | medio | esperada | PC (App) |
| 11.5 | Freno de salida a la red en turnos normales: pide el sí si una URL o consulta lleva un valor de memoria leído o el turno ya leyó contenido de fuera; texto de `web.fetch` marcado como datos (spotlighting) | 11 | `web.fetch` es ReadOnly (`ProductCatalog.cs:1651-1663`); el freno de red sólo existe en el latido (`NativeTurnLoop.cs:446`) | [lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/); [OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/); [Spotlighting](https://doi.org/10.48550/arXiv.2403.14720); [CaMeL](https://doi.org/10.48550/arXiv.2503.18813) | invariante 6 (nada sale) con contenido hostil | prueba de inyección, falsedades | 0 | alguna confirmación de más | medio | esperada | PC (App) |
| 11.6 | `turns.jsonl` con tope y en la carpeta privada; el JSON del latido y el `doubt_ask` sin texto de memoria en claro | 11 | `__main__.py:34`, `mind.py:667,900,1015,1040` | — | privacidad | prueba nueva | 0 | menos diagnóstico | bajo | esperada | PC (mente) |
| 11.7 | Ejemplos de las descripciones de memoria sin un valor que conteste la pregunta de otro | 11 | PROGRESO.md:1276 (dos pedidos contestados con el valor del ejemplo de `memory.save`) | — | falsedades de memoria | decision2 s0 (ruido ±2), falsedades | 0 | prefijo | bajo | esperada | PC |
| 11.8 | `memory.save` con `kind`, `retention`, `sensitivity`, `tags` opcionales (hoy 7 obligatorios) | 11 | `ProductCatalog.cs:1980-2000`; 114 tokens de salida (`mind.py:402`) | — | ~40 tokens (~0,5 s) y menos `invalid_arguments` | decision2 | 0 / 0 / −0,5 s | bajo | bajo | esperada | PC (Kernel) |
| 11.9 | Bloque «lo que recuerdas» (~300 tokens) en el mensaje del reloj cuando cambió la memoria o tras recortar el historial (requiere 11.4) | 11 | el latido ya recibe 20 recuerdos (`Heartbeat.cs:149`) | [Letta](https://docs.letta.com/guides/agents/architectures/memgpt); [LongMemEval](https://doi.org/10.48550/arXiv.2410.10813) | «¿cómo me llamo?» sin llamar | decision2 + banco nuevo | 0 / 0 / +~0,1 s prefill | historial más largo | medio | esperada | PC |
| 10.1 | Umbral calibrado sobre P(`intervenir`=true) del paso 1 del latido (logprobs, primero sólo en la traza como la capa 0); muestreo k=3 sólo en el margen | 10 | `mind.py:648-655` voraz y binario; todos los fallos de decisión del latido son hacia callar (P012, P016, P024, P035), silencios 92/92 | [PRISM, ICLR 2026](https://doi.org/10.48550/arXiv.2602.01532); [Kadavath 2022](https://doi.org/10.48550/arXiv.2207.05221); [Horvitz CHI99](https://www.interruptions.net/literature/Horvitz-CHI99-p159-horvitz.pdf) | 0 a +3 escenas (la fase de traza dice si hay margen, sin costo) | escenas ×4 con ediciones neutras + ROC | 0 / 0 / +20 ms; ~2 s en ~10 % de latidos | sobreajustar τ a práctica; no toca retenciones | bajo | esperada | PC (mente) |
| 10.2 | La decisión del latido dice la forma (`avisar`/`hacer`); con «avisar» el paso 2 va sin herramientas (mismo mecanismo que `final`) | 10 | `say` 14/24 en práctica y 0/6 en el holdout (`PROGRESO.md:2734`); P026 actúa 5/6 (brillo, modo avión), P035/P023 llaman `confirmation.answer`/`message.draft` | [Horvitz, dos umbrales](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/6553358) | +1 a +2 en práctica, más en el «decir» | escenas ×4 | 0 / 0 / ~5 tokens | puede bajar escenas act (P007, P027, P028); esquema distinto al del FT | bajo | esperada | PC (mente) |
| 10.3 | Pasar los motivos (no sólo `analisis`) al paso 2 del latido | 10 | `mind.py:675`; P002 `say` 6/6, P023 propone borrador | [Let Me Speak Freely?](https://doi.org/10.48550/arXiv.2408.02442) | 0 a +1 | escenas ×4 | ~20 tokens | silencios intactos (sólo corre si interviene) | bajo | esperada | PC |
| 10.4 | Tiempos relativos («hoy 10:00, en 20 min») y ausencia legible en el mensaje del latido | 10 | `mind.py:284,309`; `HeartbeatMoment.cs:81` (ISO) | [Test of Time](https://doi.org/10.48550/arXiv.2406.09170) | 0 a +2 (P024, P035, P008) | escenas ×4 | 0 | fuera de la distribución del FT | bajo | esperada | PC |
| 10.5 | Juntar y limitar latidos por evento (≥30 s entre latidos, ≤5/min) | 10 | `Heartbeat.cs:124`: cada cambio dispara un latido de ~2,4 s en el único slot y la persona espera (`MainWindowViewModel.cs:553`) | [Need Help?, CHI 2025](https://doi.org/10.48550/arXiv.2410.04596); [Microsoft notificaciones](https://learn.microsoft.com/en-us/WINDOWS/APPS/develop/notifications/app-notifications/app-notifications-ux-guidance) | latencia del turno de la persona | vivo | 0 / 0 / − | ninguno | bajo | esperada | PC (App) |
| 10.6 | El banco de escenas usa sólo señales que la App produce (`trabajando`→`libre`, vocabulario de eventos de `Heartbeat.cs:169-232`); reetiquetar P023 (say), P025 (`message.draft`) | 10/12 | `HeartbeatMoment.cs:18-24` nunca da `trabajando`; escenas con `download finished`, `battery critical`, `call started`… que la App no emite | — | que el banco mida el producto | escenas | 0 | rompe comparabilidad (re-correr base) | bajo | — | portátil (banco) |
| 10.7 | Definiciones de los motivos del latido («pedido», «se cumple») medidas frase a frase | 10 | P012: `"pedido": "ninguno"` con «avísame si me responde…» a la vista; `mind.py:81-84,94` | estudio-latido-nb.md A1/B | +1 a +2 | escenas ×4 | 0 | texto entrenado: un motivo añadido costó −5 (`PROGRESO.md:389`) | bajo | esperada | PC |
| 12.1 | Parche de semilla robusto (regex `"seed": 0[,}]`, abortar si el conteo ≠ 1) | 12 | `mind.py:857` dice `"seed": 0,` desde c7abe77ed; `e2e_aid*.sh:16`, `ab_e2e.sh:21` (portátil) y `e2e_pc2/3.sh:21`, `make_arms_d20.py:146` (PC) ya no cambian la semilla | — | que «3 semillas» sean 3 | e2e, decision2 | 0 | ninguno | bajo | verificado (mis copias de hoy sí cambian) | ambas |
| 12.2 | Comparación pareada por ítem (McNemar exacto / bootstrap, Holm) también en decisión y escenas, con un `pareado.py` genérico | 12 | hoy sólo `pareado_ab.py` para e2e; regla «±3 a ojo» | [Miller 2024, Adding Error Bars to Evals](https://doi.org/10.48550/arXiv.2411.00640); [Bowyer, ICML 2025](https://doi.org/10.48550/arXiv.2503.01747) | IC por comparación; evita victorias falsas | todos | 0 GPU | ninguno | bajo | — | portátil |
| 12.3 | Réplicas por edición neutra (no por semilla) en decisión y escenas | 12 | `PROGRESO.md:1141` (un espacio mueve escenas ±2); caché de prefijo ±3 (`PROGRESO.md:1128`, `PROGRESO-nb.md:249`) | [llama.cpp server README, cache_prompt no determinista](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md); [2510.05152](https://doi.org/10.48550/arXiv.2510.05152) | ruido real (las semillas lo subestiman) | decision2, escenas | ×3-4 corridas | ninguno | bajo | — | ambas |
| 12.4 | Puntaje continuo por ítem con la probabilidad de la operación correcta (ya en la traza de `doubt.py`) | 12 | `top_logprobs` en `mind.py:858-859` | Miller 2024 (probabilidad del siguiente token) | IC ~1,5-2× más estrecho (estimado) | decision2 | 0 | ninguno | bajo | — | portátil |
| 12.5 | pass^3 junto a la media en el e2e | 12 | E011, E017, E024 fallaban «a veces» | [τ-bench](https://doi.org/10.48550/arXiv.2406.12045) | mide la fiabilidad que siente el autor | e2e | 0 | ninguno | bajo | — | portátil |
| 12.6 | Juez de 4 clases en decision2 (acción, pregunta, respuesta, «no puedo») con `reply_re` en text; «¿algo más?» no es pregunta | 12 | `bench_decision.py:87-98`: una respuesta con «?» aprueba ask y text a la vez; 42 text sin `reply_re` | [When2Call](https://doi.org/10.48550/arXiv.2504.18851) | hace visible la «pregunta de más» de S1 | decision2 (re-juzgar jsonl) | 0 | rompe comparabilidad | bajo | — | portátil |
| 12.7 | Banco de latencia: primer sonido desde el envío por tipo de turno, IC agrupado por caso | 12 | `bench_e2e.py:177` mide desde `turn.start`, no ve la cola del conductor | — | latencia honesta | nuevo | ~15 min | ninguno | bajo | — | portátil |
| 12.8 | Precondiciones VOID dentro de `bench_e2e.py` (frente limpio, home limpio, pestañas, `setup_fallido` no es fallo) | 12 | `bench_e2e.py:210-217,79`; GameInputSvc (`PROGRESO.md:2105-2115`), restos en el home (`:2370-2376`) | — | quita ±1-2 casos de ruido de entorno | e2e | 0 | ninguno | bajo | — | portátil |
| 12.9 | Juicio de voz y de falsedades sin agujeros: turno callado = fallo, cleanup siempre, observación completa al juez, juez sin la trampa del caso | 12 | `bench_e2e.py:241-247,271-277`; `bench.ps1:612`; `bench_falsedades.py:69-71,114,230` | — | menos falsos positivos/negativos | e2e, falsedades | re-juzgar (35B ~1 h) | ninguno | bajo | — | portátil |
| 12.10 | Guardas anti-fuga hacia Laya: canario en el holdout v4, `build_kev_data`/`assemble_laya`/`teacher` rechazan `renew_v4` y el canario, oráculo de fuga ciego | 12 | 9 textos de decision2 en `kevdata-v4` (P045, P047, P048, P050, P053, P054, P189, P250, P254); umbrales 0,4/0,6 fijados en decision2 | [Dwork 2015](https://doi.org/10.48550/arXiv.1506.02629); [CapBencher](https://doi.org/10.48550/arXiv.2505.18102) | S1 medido sin inflar | holdout v4 | 0 | ninguno | bajo | — | PC (scripts S1) |
| 11.10 | Preguntar en el primer arranque si se enciende la memoria (hoy apagada por defecto, `LocalMemoryStore.cs:514`) | 11 | e2e con `memory_disabled` (PROGRESO 1370, 2197) | [ChatGPT memory controls](https://help.openai.com/en/articles/11146739) | la identidad dice «recuerda preferencias» | — | 0 | decisión de diseño | bajo | — | autor |

## Errores reales vistos en la fase A (se verifican y arreglan con prueba en la fase B)

Cada uno con la prueba que fallaría hoy. Los marco con su área; «verificado» = lo leí yo en el código.

**Providers (6)**
- **R6.1** `media.control` sin `sourceApp` actúa sobre la sesión «actual» de Windows aunque esté en pausa y otra suene
  (`WindowsMediaSessionAdapter.cs:285-300`, `:500`, `:576`): «pausa la música» con Edge pausado al frente y Spotify
  sonando dice «paused» y Spotify sigue. Prueba: dos sesiones (actual Paused, otra Playing), `pause` → hoy éxito sobre
  la pausada. Fuente: [GetCurrentSession](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssessionmanager.getcurrentsession).
- **R6.2** `game.launch` de un juego ya abierto falla a los 35 s (`SteamLocalAdapter.cs:787`: `before` excluye su
  proceso). Prueba: snapshot con el exe antes y después → hoy `steam_launch_process_not_verified`.
- **R6.3** Tiempo agotado de yt-dlp o de la conexión a mpv lanza `OperationCanceledException` sin capturar
  (`YouTubeMpvAdapter.cs:168-169,234-235`; catch en `:100,107`): no pasa al navegador y yt-dlp queda vivo. Prueba:
  resolver falso que duerme >45 s → debería dar `youtube_stream_not_resolved`.
- **R6.4** Valor mal formado para un lugar que existe se dice como «lugar de otra app» (`ApplicationPlaces.cs:72-91`,
  `AppOpenHandler.cs:54-65`). Prueba: `app.open{Steam, place:game, placeValue:"Rocket League"}` ≠
  `place_not_of_application`.
- **R6.5** (menor) `media.play.exact` con `SingleOrDefault(…Contains("spotify"))` lanza con dos sesiones y nombra una
  app en código (`WindowsMediaSessionAdapter.cs:345`).
- **R6.6** (menor) `file.open` con aplicación pierde los `candidates` de `app_not_found`
  (`WindowsFileToolsAdapter.cs:287-289`).

**Computer use (7)**
- **R7.1** = §0 (falta pc-cu, con el arreglo PS 5.1 y `visible_settings_switch_refused`).
- **R7.2** «Mismo resultado» falso: `TurnClosing.AfterCall` (`TurnClosing.cs:37-42`) y `same_call_next`
  (`mind.py:784-791`) no comparan el contenido; tres miradas iguales con vistas distintas (ventana cargando) cortan el
  turno y le dicen al modelo «mismo resultado». Prueba: `AfterCall` ×3 con resultados distintos → hoy `true`.
- **R7.3** En la tercera repetición seguida coinciden `SAME_CALL_NOTE` y el cierre «no admite más herramientas»
  (`mind.py:787-791,804-809`). Prueba: tres `continue_turn` iguales con `final=True`.
- **R7.4** «Foco: []» sin índice cuando el control enfocado no entró en la vista (`ScreenViewProjection.cs:230`).
- **R7.5** Docstring contra código sobre el foco (`WindowsVisibleControlAdapter.cs:1875` frente a `:2012-2022`).

**Latido (10)**
- **R10.1** `system.settings.set` corre solo en un latido (`RiskPolicy.cs:92` deja pasar Sensitive;
  `NativeTurnLoop.cs:502` sólo retiene `do_not_disturb`): traza `nb-beat-none-pC`, P026, modo avión encendido con
  batería al 8 %, sin pedido. Prueba: latido con `system.settings.set {airplane_mode}` → debería `needs_confirmation`.
- **R10.2** El mensaje entero del latido (con `BEAT_RULES` y «Responde en JSON…») entra a la conversación de la
  persona (`mind.py:694`): ~600 tokens de reglas ajenas por latido no silencioso en el historial de 24k caracteres.
  Prueba: latido que interviene, `end_beat()`, `decide("hola")` → los mensajes no deberían contener `BEAT_DECIDE`.
- **R10.3** «y 3 más sin listar ()» con paréntesis vacíos (`MainWindowViewModel.cs:795-798`, `mind.py:309`).
- **R10.4** El banco de escenas usa actividades y eventos que la App no produce (palanca 10.6).
- **R10.5** El saludo al volver no tiene motivo (R1 rechazado) y el banco etiqueta el regreso como silencio (P005,
  P037), contra la decisión 10 del autor. Decisión de diseño.

**Memoria (11)**
- **R11.1** El código de E4 nunca llega al modelo: `MemoryHandlers.cs:581` → `MissionEngine.cs:171` lo cambia a
  `memory_operation_failed` (no está en `PrivateOperationBoundary.cs:12-27`).
- **R11.2** Los recibos de idempotencia nunca se borran (tope de por vida 4096, `LocalMemoryStore.cs:21,1045`): tras
  ~4096 guardados la memoria queda «llena» con 0 recuerdos (estado falso). Prueba: `maximumReceipts:2`, enable, save,
  forget all, save → hoy `MemoryCapacityException`.
- **R11.3** Olvidar deja el `Selector` en los recibos (`LocalMemoryStore.cs:269-277,426-434`).
- **R11.4** Cada lectura reescribe el almacén (`:963-981`).
- **R11.5** Copias en claro de lo que la memoria cifra: sesiones (`FieldSessionStore.cs:74`, sin borrado),
  `turns.jsonl` (sin tope, fuera de la carpeta privada), `conversation.v1.jsonl` (sólo `SensitiveText`).
- **R11.6** El latido escribe en claro lo deducido de la memoria (`mind.py:667`); `doubt_ask` escribe el texto de una
  llamada de memoria (`mind.py:900`, el `private` se pone en `:1015`).
- **R11.7** Fuga a la red en turnos normales (palanca 11.5).
- **R11.8** (probable, sin comprobar) `CapturedAtUtc = now` en el digest de save/correct (`MemoryHandlers.cs:293,333`):
  reintentar tras una caída daría `memory_invocation_conflict` con el efecto ya hecho.

**Medición (12)**
- **R12.1** Parche de semilla (palanca 12.1).
- **R12.2** `bench_decision.py:87-98` (ask y text a la vez), `:62` subcadena laxa («up», «all»), `catalog_equivalence.json:2-7`
  (la hora de un recordatorio remapeado nunca se comprueba), `:194` p50/p90 con excluidos y errores, `:190` el
  resumen no anota `BAXY_S1_*`.
- **R12.3** `bench_escenas.py:135` (una pregunta cuenta como say), `:161` (retenida de lectura → falla aunque la clase
  acierte).
- **R12.4** `bench_e2e.py:210-217` (`setup_fallido` cuenta como fallo), `:271-277` y `bench.ps1:612` (callarse aprueba
  la regla de voz), `:241-247` (segunda confirmación sin respuesta escapa a la voz), `:177` (latencia desde
  `turn.start`), `:37` (stderr pegado a stdout del oráculo), un perfil para toda la corrida (memoria y notas pasan de un
  caso a otro).
- **R12.5** `rescore_e2e.py:30` busca `turn.start` por texto desde el inicio de toda la corrida (toma otro caso con «sí»
  o «para»; `StopIteration` sin capturar).
- **R12.6** `bench_falsedades.py:69-71` (sin cleanup si falla el setup), `:114` (observación cortada a 1500 caracteres
  → falsedad falsa), `:230` (la trampa del caso sesga al juez).
- **R12.7** `measure_resources.py:71-83` muestrea 5 s después de los turnos (no en inferencia); `:38` el llama-server
  de Laya sólo cuenta si su ruta contiene «evaluacion».

## Diseño del holdout v4 (área 12)

Lo escribe y sella un subagente aislado del líder; yo no lo veo. Potencia por la fórmula de Connor para McNemar
(α=0,05 a dos colas, potencia 0,8, [SAS](https://support.sas.com/documentation/cdl/en/statug/66103/HTML/default/statug_power_details55.htm)):
con discordancia p_d=0,06 un Δ de 3 puntos pide ~520 ítems; con p_d=0,10, ~870; Δ de 2 puntos, >1.100 (imposible en
e2e).

| Banco | Casos | Detecta (80 %) | GPU |
|---|---|---|---|
| Decisión | 720 | ≈3,0 puntos (p_d=0,08) | ~11 min × 3 configuraciones × 3 réplicas ≈ 1,7 h en dos GPUs |
| Escenas | 90 (silence 50, act 15, propose 12, say 13 con `reply_re`; 8 de «volvió») | ≈10 puntos (guarda de regresión) | ≈1,2 h |
| E2E | 72 | ≈10 puntos con media de 3 | ≈4 h (notebook) |
| Falsedades | 36 conversaciones | descriptivo, a mano | 1 corrida por configuración |

**Familias de decisión (720):** comunes del autor 120 · pares mínimos entre operaciones que se confunden 100 · riesgo
(mala lectura irreversible) 60 · preguntar 60 · «no puedo» 50 · texto o conocimiento con `reply_not_re` 50 ·
multi-turno con referencias 80 · «¿ya lo hiciste?» con resultados en el historial 40 · confirmación pendiente 40 ·
larga cola del catálogo 80 · primer paso de multipaso 40.

**E2E (72):** comunes 18 · computer use 12 · archivos con subcarpetas y rutas dictadas 10 · confirmación sí/no/
reemplazada/doble 8 · multi-turno con recuperación tras error 10 · «¿ya lo hiciste?» tras fallo inducido 4 ·
imposibles 4 · voz (barge-in, «para», respuesta larga) 6. Se reporta media, pass^3 y latencia.

**Idiomas:** decisión 50 % español (con chileno) / 15 % inglés / 15 % spanglish / 20 % dictado con errores de
reconocimiento; e2e 60/15/15/10. El dictado va como **gemelo** de un caso limpio (medida pareada de robustez; error
estándar agrupado por pareja). Nada de MASSIVE: Laya se entrenó con su train y dev.

**Sellado:** (1) el subagente lee sólo `renew_v4\catalog-base.json`, los README y el formato de las prácticas; (2) deja
generador, validador (operaciones, argumentos y enums existen; `judge` acepta cada expectativa; `bench.ps1` parsea y
pasa la autoprueba en mundo intacto) y comprobación de casi-duplicados contra decision2, escenas, e2e de práctica,
`kevdata-v*`, `massive_*`, `ft_v1/datos`, `sint_nb`; (3) GUID canario en cada archivo; (4) cifrado 7z AES-256 en
`<evaluacion>\renew_v4\holdout\` (un grep no lee texto), copia por scp a `D:`, clave fuera de evaluacion; (5) sha256 del
cifrado y de cada JSON, y conteos por familia sin textos, en `metas.json` y `SEALED-v4.md`; (6) análisis
pre-registrado (script con hash, métrica primaria, comparaciones S1 off / on / renew-maximo con McNemar y Holm, regla de
equivalencias, env de S1 de cada configuración); (7) se abre una vez, sobre el HEAD congelado, 3 configuraciones
intercaladas.

**Anti-fuga hacia Laya:** los constructores de datos de Laya rechazan `renew_v4` y el canario; oráculo de fuga ciego
(devuelve ids, nunca textos); Laya (sha) y umbrales 0,4/0,6 congelados antes de abrir; trazas del holdout sólo en
`renew_v4\runs`; reajustar Laya después de abrir exige un v5 ([Dwork 2015](https://doi.org/10.48550/arXiv.1506.02629),
[CapBencher](https://doi.org/10.48550/arXiv.2505.18102)).

## Detalle por área
<!-- DETALLE -->
