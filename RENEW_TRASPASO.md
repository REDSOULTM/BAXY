# BAXY Renew — traspaso a un chat nuevo (2026-10-15)

Rama `baxy-renew`, worktree `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew`. Último commit al escribir esto:
`6eba9dfb` (voz conectada). La transcripción completa del chat anterior está en
`C:\Users\usuario\.claude\projects\c--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo\3b9a0154-01df-432e-b70a-2765d76906d6.jsonl`.

## La misión, en palabras del dueño

BAXY = el modelo puro (Qwen3.5-4B) + las herramientas y el ecosistema de BAXY, optimizado al máximo para ese modelo.

- **Sin código que ayude al modelo:** nada de regex, reglas semánticas, guardias, vetos ni sobreingeniería.
- **Las mejoras vienen sólo de** la presentación (prompt del sistema, descripciones de herramientas, formato), el
  protocolo y la inferencia.
- **Límite honesto:** lo que el modelo no logre se acepta como límite; BAXY nunca dice algo falso.
- **Regla vital:** antes de implementar cualquier cosa, investigarla con papers, documentación oficial y experiencia
  de usuarios. Nunca improvisar.
- **Ciclo:** lanzar subagentes que auditen, arreglar, medir y re-auditar, hasta que no encuentren nada.
- **Recursos:** como máximo 4 GB de VRAM y 4 GB de RAM.

Decisiones del dueño, tomadas con casillas de opciones:

| Tema | Decisión |
|---|---|
| Multipaso | Bucle nativo |
| Pedido imposible | Decir que no lo hace |
| Volumen sin cantidad | Que decida el modelo |
| Voz | Primero «después»; el 2026-10-15 pidió conectar la wake word y la transcripción (hecho, ver abajo) |
| Voz que habla | Piper como antes; el 2026-10-17 el dueño la cambió por una voz propia en Supertonic 3 (ver «Voz de BAXY») |
| Computer use y herramientas genéricas | Lo que recomienden los papers, la documentación, los usuarios y la evidencia de BAXY |
| Meta final | Metas medibles: holdout nuevo ≥ 85 %, cero falsedades en banco automático, ≤ 4 GB + 4 GB; si no llega, límite honesto y cierra |

### El BAXY que se construye (segunda ronda de decisiones, 2026-10-15)

**Referencia:** OpenClaw, pero en 4 GB de VRAM. Es un asistente personal que vive en el PC: el modelo, herramientas y
el bucle, con memoria, skills y latido. El código queda limpio, sin ningún truco para el modelo, y a la vez optimizado
al máximo para Qwen3.5-4B.

| Tema | Decisión del dueño |
|---|---|
| Herramientas | Skills a demanda (un índice corto en el prompt y la skill completa cuando hace falta), o lo que recomiende la evidencia. Se mide contra «todas en el prompt» con Qwen3.5-4B |
| Memoria | El almacén cifrado actual de BAXY; el modelo lo lee y escribe con herramientas |
| Proactivo | Latido como OpenClaw: actúa por instinto, conociendo al usuario y lo que puede necesitar en el momento |
| Riesgo por instinto | Por instinto hace lo de bajo riesgo. Lo de alto riesgo (borrar, enviar mensajes, apagar, pagar) siempre lo propone y espera el «sí» |
| Qué observa el latido | Hora, apps y ventanas abiertas; la memoria y el historial con BAXY; el contenido de la pantalla; el estado del PC |
| Frecuencia del latido | Cada 5 min y ante cambios (se abre una app, termina una descarga). Se pausa si el dueño juega o la GPU está ocupada |
| Avisos | Según lo que haga el dueño: habla en voz alta si está libre; si juega, está en llamada o viendo algo, sólo una notificación en pantalla |
| Canales | Ventana más voz en el PC; sin Telegram, WhatsApp ni Discord |
| Confirmaciones | Botones Sí/No en la ventana. Por voz, el modelo interpreta la respuesta con una herramienta. La lista de palabras (regex) de `ConfirmationReplyParser` se va |
| Código | Se reescribe sólo el arnés, la capa App↔mente. Se conservan el kernel, los proveedores, el journal y la seguridad |
| Pruebas | Se borran las heredadas. Quedan pocas pruebas, del contrato (arnés nuevo, kernel, proveedores), más el banco y el holdout |
| Tono | Breve y cercano, en el idioma en que le hablen (español o inglés), sin relleno |
| Destino | Queda como rama aparte; no se fusiona a main |
| Modo de trabajo | `/goal` autónomo: lanza agentes, investiga, mide y hace commits en `baxy-renew`. Pregunta con opciones sólo ante una decisión del dueño |
| Ritmo | **Lo más rápido posible, sin perder calidad**: hay que entregarlo pronto. Agentes en paralelo y nada de esperas inútiles |
| Dos máquinas | Dos sesiones de Claude Code, una por máquina, cada una con su propia cuenta (las dos en el plan de 200 dólares). Se coordinan con un buzón por SSH (vía Tailscale) y con git |
| Quién dirige | **El PC** (redpc): integra las ramas en `baxy-renew`, decide el reparto y hace la medición final. El notebook (rednote) apoya con las piezas que corren aparte |
| Uso de las máquinas | **Las dos quedan dedicadas por completo** (el dueño no las usa mientras se trabaja). Cada agente usa toda la CPU, GPU y RAM de su máquina sin esperar, y abre o maneja apps cuando lo necesite. Se sigue pidiendo confirmación antes de borrar fuera del worktree, cerrar apps con trabajo sin guardar o enviar algo fuera |
| Decisiones del dueño | Pregunta con opciones y además le manda una notificación push al celular. Mientras espera, sigue con lo que no depende de la respuesta |
| Uso agotado | Un recordatorio cada hora retoma el goal si quedó parado. Las dos sesiones quedan abiertas |
| Hardware | **PC (redpc):** RTX 4060 Ti 16 GB, i9-12900HX, 32 GB de RAM, modelos en el M.2 `F:`. **Notebook (rednote):** RTX 3060 Laptop de 6 GB, Ryzen 7 5800H, 16 GB de RAM |
| Reparto según rendimiento | **PC:** el arnés nuevo, computer use (las apps reales del dueño), el latido, la integración y la medición final. Con 16 GB caben dos llama-server a la vez, así que puede correr dos bancos en paralelo. **Notebook:** la voz que habla (Supertonic, CPU), las herramientas de agente, la limpieza de código muerto, el banco de escenas y la investigación. Con su GPU cerca del límite de 4 GB, mide el perfil de 4 GB (IQ4_XS con un hueco) en hardware real |

## Qué es Renew hoy

- **Mente (`src/baxy_mind/`):** quedan `__main__.py`, `llm_server.py`, `mind.py`, `protocol.py`, `voice.py` y `data/`.
  Se borraron 142 módulos.
- **Servidor del modelo:** `llama-server` b11609 con `--jinja --reasoning off`, dos huecos (0 = decidir,
  1 = redactar) y `-kvu`.
- **Catálogo:** prefijo de unos 38,9k tokens. Las descripciones van en inglés, en
  `data/tool_descriptions.en.v1.json`, con el formato «Use when / Do not use when / Examples».
- **Bucle nativo:** `turn.continue`, con los resultados como mensajes `role:"tool"`, hasta 6 pasos, y el texto final
  lo escribe el modelo.
- **Lo que se queda en la App (honestidad):** el catálogo tipado, el kernel (riesgo y confirmación), el journal, la
  verificación del proveedor y el enmascarado de datos sensibles.
- **App:** sin atajos, vetos ni redacciones fijas. La lógica del bucle está en `MainWindowViewModel.cs`, en
  `RunNativeToolLoopAsync`, `CaptureLoopStepAsync`, `NextLoopDecisionAsync` y `ResumeAfterConfirmationAsync`.

**Arranque:** `scripts\run_renew.cmd`. Fija las rutas de este PC, compila si hace falta y lanza la App.

- Los modelos están en el M.2 `F:`, no en el HDD `D:`.
- El registro de turnos de la mente está en `%LOCALAPPDATA%\BAXY\renew\turns.jsonl`.

**Banco:** `F:\BAXYeval\renew_bench\bench.py` (90 casos en `cases.json`).

| Corrida | Resultado | p50 de la decisión |
|---|---|---|
| Mejor de práctica, `en02v2` | 85/90 | 0,74 s |
| `HOLD-final` | 53/60 | 0,77 s |

El holdout (`holdout.json`, 60 casos) **ya se usó**: no se ajusta nada mirándolo. La ronda 1 (`bd6a4ba3`) **no se
midió todavía**; corre `py -3.12 -X utf8 bench.py r1 --desc en --temp 0.2`.

## Voz (hecho el 2026-10-15)

**Qué hace `src/baxy_mind/voice.py`:**

- Cadena: micrófono → wake word k4 (`WakewordBaxy/models/final/baxy-wake-k4`, umbral 0,5) → Parakeet Ultra int8
  (`D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli`). Todo en CPU, en un hilo propio.
- La segmentación es la de `WakewordBaxy/probar_baxy.py`.
- La llamada «Baxy» se quita **por tiempo, no por texto**: se descartan las palabras de Ultra que empezaron más de
  0,25 s antes del disparo. Medido con las grabaciones del dueño: «Baxy» empieza entre 0,5 y 0,75 s antes del disparo.
- Hace falta quitarla porque la confirmación de riesgo de la App sólo acepta un «sí» limpio.

**Protocolo:**

- La mente atiende `voice.start` (modos `wake` o `direct`), `voice.stop`, `voice.status` y `voice.cancel`.
- Envía `voice.transcript` y los eventos `voice.event` `wake_detected`, `partial` y `state`.
- **No hay TTS:** el hello no ofrece `voice.speak` y la App no le pide hablar.
- `protocol.write_message` escribe con un lock.

**Verificado:**

- Con las grabaciones reales del dueño, pasadas como si fueran el micrófono:
  - «Baxi, abre Steam.» → «abre Steam.»
  - «Hola. Maxi. Abre Spotify and Pause.» → «Abre Spotify and Pause.»
  - Un «Baxi» suelto → no envía nada.
  - El modo directo transcribe una orden y vuelve a esperar «Baxy».
- La App lanzada publica `wake_listening: true`, `mic_available: true` y `mind_ready: true`. La mente usa unos 1,05 GB
  de RAM privada con Ultra cargado.

**Falta:**

- La prueba en vivo del dueño con el micrófono.
- Medir la RAM total contra el límite de 4 GB: llama-server marcó 5,7 GB privados; hay que ver cuánto es RAM real.

**Dependencias:**

- `kaldi-native-fbank==1.22.3` se instaló en el Python del runtime (`%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1`).
  Ese Python es compartido con BAXY Definitivo.
- `pylock.runtime-win-x64.toml` todavía no la incluye.

## Lo primero para el chat nuevo (encargo afinado con el dueño el 2026-10-15)

**Meta:** BAXY como un agente nativo del PC, al estilo de Cursor, OpenCode o Claude Code: el modelo, un buen juego de
herramientas y el bucle nativo, y el modelo decide todo. Debe quedar completo (escucha, habla, ve y maneja la
pantalla), pero nativo. Cada paso se investiga antes de implementarlo (papers, documentación, usuarios), como pide la
regla vital.

**Orden:**

1. **Falsedades vistas en uso real (2026-10-15, 01:52–01:55).** Siguen el orden de `conversation.v1.jsonl`, en
   `%LOCALAPPDATA%\BAXY\dev-mente-v2\conversation`:
   - BAXY dijo «¡Listo! Ya he abierto Steam… Doom Eternal» sin haber ejecutado nada (ruta `conversation`). Esto rompe
     «BAXY nunca dice algo falso». Hay que investigar por qué el modelo cuenta acciones que no llamó y arreglarlo con
     presentación o protocolo.
   - Con una confirmación pendiente, «cierra chrome» recibió «No puedo cerrar Chrome porque mi última orden pendiente
     era cerrar la ventana 18titans». Hay que revisar cómo se reemplaza un plan pendiente.
2. **Medir la ronda 1** (`r1`) y comparar con `en02v2`.
3. **Voz que habla, con Piper como antes** (decisión del dueño; hecho, y el 2026-10-17 cambiado por Supertonic: ver
   «Voz de BAXY»):
   - Es la voz es_MX que usaba BAXY Definitivo; su ruta está en `tts_model` del manifiesto.
   - Se porta de Definitivo (`src/baxy_mind/voice_output.py`, `voice_aec.py` y lo que use `voice.py`) sólo lo
     necesario: `voice.speak`, `voice.cancel`, la interrupción al hablar encima, y la cancelación de eco y la bajada de
     volumen si la evidencia las pide.
   - El hello vuelve a ofrecer `voice.speak`.
   - El torneo TTS (BAXY-098) sigue aparte; aquí no se cambia la voz.
4. **Computer use nativo.** La forma la decide la investigación junto con la evidencia que juntó BAXY Definitivo.
   - **Investigación:** papers como OSWorld, Windows Agent Arena y UFO, la documentación oficial y la experiencia de
     usuarios.
   - **Evidencia de BAXY:**
     - la memoria `c03-computer-use-engine`;
     - el contrato `documentacion/computer-use/CONTRATO_VISTA_ACCION.md`, en la rama `fable/computer-use-engine`;
     - las lecciones de sus sondas.
   - **Lo que ya hay:** el catálogo de Renew ya tiene las primitivas `input.visible.controls`, `input.visible.click`,
     `input.key.press` e `input.scroll`. Falta que el modelo las encadene solo en el bucle nativo; puede hacer falta
     subir el límite de pasos.
   - **Lo que no entra:** el motor viejo dictaba los pasos obvios con código (`deterministic_step`) porque el 4B agotaba
     el tiempo. Eso es código que ayuda. Si el 4B no llega, queda como límite honesto.
   - **Recursos:** todo dentro de 4 GB de VRAM. Sumar visión (capturas) sólo si la evidencia lo justifica y cabe.
5. **Herramientas genéricas de agente** (terminal, archivos, leer la web, lista de tareas propia…). Entran las que la
   investigación recomiende para un modelo local de 4B, y todas pasan por el riesgo y la confirmación del kernel.
6. **Ciclo de re-auditoría con agentes:**
   - Código muerto: unas 7 200 líneas de la App, 27 JSON huérfanos, 508+8 pruebas de Python y 32 pruebas .NET de
     integración.
   - `bootstrap.ps1` todavía importa `baxy_mind.voice`; ahora existe, pero hay que revisar qué espera.
7. **Optimizaciones pendientes:**
   - Hora local en avisos y recordatorios: el modelo no convierte a UTC (`dueUtc`), así que conviene que el catálogo
     acepte la hora local.
   - Sacar del prompt la lista de 522 apps.
   - Guardar y restaurar el hueco en disco.
   - Perfil de 4 GB: IQ4_XS con un solo hueco.
   - Redactar dentro del bucle.

## Cuándo termina (metas medibles, fijadas por el dueño)

- **Holdout nuevo y sellado, con ≥ 85 % de aciertos.**
  - Se escribe antes de ajustar nada y no se mira mientras se ajusta; el viejo ya está gastado.
  - Cubre también voz, computer use y las herramientas nuevas.
- **Cero falsedades en un banco automático** de turnos con guion, que el chat corre solo.
  - Cada turno se audita contra el journal: no puede decirse como hecho nada que no se haya ejecutado y verificado.
- **≤ 4 GB de VRAM y ≤ 4 GB de RAM**, medidos con todo cargado: modelo, voz que escucha y que habla, y computer use.
- **Instinto: banco de escenas, con ≥ 80 % de aciertos.**
  - Cada escena trae hora, apps abiertas, pantalla, historial y estado del PC. Un acierto es actuar cuando conviene y
    callarse cuando no.
  - Cero acciones de riesgo hechas solas.
  - Como máximo una acción molesta cada 20 escenas.
- **Velocidad (p50):**
  - La decisión, en ≤ 1 s.
  - Desde que el texto de una orden llega a la mente hasta que la voz empieza a sonar, ≤ 2,5 s.
- **Alcance de la medición (decisión del dueño):** sólo se mide y optimiza el arnés.
  - La wake word k4 y la transcripción Parakeet Ultra son piezas fijas: no se miden, no se ajustan y sus errores no
    cuentan. Los bancos entran como texto.
  - La meta de 4 GB de VRAM y 4 GB de RAM es para llama-server y la mente, sin k4 ni Ultra. Se anota también el total
    con la voz.
- **Si una meta no se alcanza por el límite del modelo:** se documenta como límite honesto, con su evidencia, y se
  cierra. Nunca se parchea con código.

## Trampas de este entorno

- **Git Bash:** un heredoc pierde las barras invertidas dobles. Para editar con Python, escribe el script en un `.py`
  y usa rutas con `/`.
- **Saltos de línea:** git guarda LF y los `.cs` tienen BOM. Conserva los dos al editar.
- **Compilación:**
  - `vswhere.exe` no está en el PATH; `run_renew.cmd` lo agrega.
  - Si Baxy.exe tiene tomados los archivos, `main.py` cierra la ventana antes de copiar.
- **Manifiesto compartido:** `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` es de BAXY Definitivo; no se edita.
  Renew usa sus propias variables `BAXY_RENEW_*` y las de `BAXY_MIND_*` que fija el lanzador.

## Voz de BAXY (2026-10-17, elegida por el dueño de oído)

La voz que habla ya no es Piper: es una voz propia hecha con **Supertonic 3** (sherpa-onnx INT8, CPU, en el mismo
proceso de la mente; el runtime ya traía sherpa-onnx 1.13.4 y scipy, sin dependencias nuevas).

- **Por qué:** el dueño encontró artificiales todas las voces Piper y Kokoro. `es_MX-claude-high` es femenina (~180 Hz)
  y de tamaño medium aunque diga «high»; bajarle el tono no da un hombre natural (formantes). Supertonic fue el motor
  más natural que cabe en CPU sin entrenar.
- **La voz «G»:** mezcla de estilos 50 % M1 (sid 5) + 30 % M2 (sid 6) + 20 % M4 (sid 8), +0,5 semitono, 10 pasos,
  velocidad 1,0, semilla 7. La construye `scripts/voice/make_baxy_voice.py` en
  `%LOCALAPPDATA%\BAXYRuntime\assets\voice\baxy-supertonic` (`BAXY_RENEW_TTS_DIR`), con `baxy-voice.json` (la receta).
  **En el notebook** hay que copiar esa carpeta a `D:\BAXYRuntime\assets\voice\baxy-supertonic`.
- **Personaje:** la mascota es un robot pequeño hecho de constelaciones, curioso y cálido; la voz es de chico joven,
  seria y con cuerpo (el dueño rechazó las versiones infantiles por chillonas).
- **Texto hablado:** `src/baxy_mind/speech_text.py` pasa números (con género), horas, fechas, dinero, porcentajes,
  unidades y abreviaturas a palabras, y reescribe las marcas en inglés como se dicen (`data/speech_respellings.v1.json`).
  Supertonic no normaliza nada y sherpa no cambia de idioma dentro de una frase.
- **Medido en el PC:**
  - Fuera de la app: 231 MB de RAM al cargar; la primera frase tarda 0,92 s con 8 pasos, 1,16 s con 10 y 1,31 s con
    12. Con 2 hilos tarda lo mismo que con 4, y con 8 es más lenta. Con Parakeet, 5,8–8,1 % de palabras mal según la
    semilla (incluye los errores del propio Parakeet).
  - En la app (`measure_resources.py voz-supertonic`): mente 311 MB USS, frente a 38 + 103 MB de mente y Piper en
    `final`. Desde que la respuesta está escrita hasta que suena: 0,6–1,4 s (con Piper, 0,05–0,3 s).
  - En esa corrida la GPU ya tenía 8,9 GB ocupados por otras sesiones, y llama-server marcó 3,8 GB USS y respuestas
    más lentas. Hay que repetir la medición del arnés con la GPU libre antes de compararla con la meta de 2,5 s.
- **Salida de audio:** la voz abre el «Asignador de sonido Microsoft» (MME) y no el dispositivo que era el
  predeterminado cuando arrancó PortAudio: el dueño cambió su salida predeterminada y no oía a BAXY. Verificado que el
  asignador abre a 91 ms; falta oírlo en uso real.
- **Licencia:** el modelo es OpenRAIL-M. Para distribuirlo hay que incluir la licencia y avisar que la voz es
  sintética. El repositorio de Supertonic está archivado.
- **Arreglos del 2026-10-20 (quejas del dueño en uso real):**
  - **Idioma y semilla nunca se aplicaban:** `config.extra[...] = ...` se pierde (pybind11 devuelve una copia), así
    que BAXY hablaba con la etiqueta «en» y una semilla al azar. Ahora `config.extra = {...}`.
  - **Silencios:** cada toma traía 0,35–0,67 s de silencio por lado; se recorta a la voz (-40 dB) y la pausa es
    0,35 s (0,45 s tras una pregunta). Volumen medido sólo sobre la voz; velocidad según el largo de la frase;
    respuestas cortas en una llamada; «…» y rayas pasados a lo que se dice.
  - **«Un momento»:** se sintetiza una vez al cargar (suena en 0,05–0,14 s); si llega la respuesta antes de que
    suene, no se dice; lo cancelado (la persona habla encima) ya no se sintetiza y no retiene la respuesta siguiente
    (esperaba 2,8–5,7 s). El dueño puede apagarlo: Ajustes → Voz → «Decir «Un momento»» (`waitNotice`); con la voz
    silenciada tampoco se dice.
  - **Palabra de activación:** 4 copias desfasadas del detector k4 (`StaggeredWake` en `voice.py`): «BAXY» se oye a
    0,28 s p50 (0,46 s máx.) tras la palabra, antes 1,18 s (1,36 s); falsos en 99 palabras parecidas 35 frente a 32.
  - **Subtítulos:** el anterior ya no reaparece ni se re-anima cuando BAXY vuelve a hablar.
  - Pasos de cálculo: el dueño eligió quedarse en 10 por ahora (empieza a hablar en 1,68 s p50; 6 pasos: 1,08 s).

## Interfaz v4 (2026-10-17, encargo del dueño con `design_handoff_baxy`)

La vista `src/Baxy.FieldUi` es ahora el rediseño v4, conectado a datos reales (ver su README y ORIGIN.md).

- **Decisiones del dueño:** chips con un título corto en español por operación (`Baxy.App/Assets/operation-labels.v1.json`)
  y los hechos del proveedor tal cual como «lo que observó»; dos niveles de confirmación (Normal = «lo arriesgado»,
  Bypass = «nada»); construir todo el backend que pide el diseño.
- **Backend nuevo:** `FieldTranscript` (conversación con pasos y tarjetas, la guarda el host), `FieldStepProjection`
  (`ok` sólo completado y verificado), `FieldSessionStore` (sesiones con la conversación de la mente:
  `session.export/load`), `FieldSettings` (arranque con Windows, bandeja, voz muda, sonido al despertar, web/clima/
  pantalla, «no me interrumpas», silencio), triggers = `schedule.alarms`, temperatura por D3DKMT y memoria de la
  mente y su llama-server (`WindowsModelResourceReader`), transcripción en vivo y soltar-para-hablar en `voice.py`.
- **Aceptación:** `scripts/test_field_ui.ps1` (Playwright por CDP contra la app real): 17/17 el 2026-10-17.
- **Propuestas en silencio:** notificación de Windows con Sí/No (`ProposalToast`, AUMID en HKCU); no se probó con un
  clic real (sin acceso a la pantalla); si Windows la rechaza sale la de la bandeja.
- **Pendiente:** adjuntar archivos (sin contrato tipado; el botón se quitó, era un punto muerto); mostrar datos
  sensibles (el almacén no los devuelve).
- **Revisión de botones (encargo del dueño, 2026-10-17: «que todos funcionen y nada lleve a un punto muerto»):**
  se pulsó cada control en la app real y se leyó el host por sus rutas. Arreglado:
  - «Recordar cosas sobre ti» (Memoria) llamaba a `/memory/enabled`, que no existía: ahora usa `memory.enable` y
    `memory.disable` del catálogo (el interruptor es el «sí» de encender, como el «Olvidar» de dos pasos).
  - «Cancelar» en Triggers mandaba la fecha completa y `schedule.alarms` cancela por la hora: siempre fallaba.
  - Elegir el modo del micrófono mientras BAXY arranca o está en reposo se rechazaba y se perdía; ahora se guarda y se
    aplica al terminar de arrancar o al activar.
  - «Arrancar con Windows» decía «No se pudo leer el inicio de Windows»; es una copia de desarrollo que no puede
    registrarse (regla de `WindowsAutostartRegistration`), y ahora lo dice. Decidir si Renew debe arrancar con Windows
    (registrando `run_renew.cmd`) es del dueño.
  - Reposo/Activar avisa al instante (tras un arranque espera a que cargue la voz).
  - Los comandos de voz del host (`SetWakeVoiceAsync`) van en fila (SemaphoreSlim) en vez de rechazar el que llega
    mientras otro espera.
  - Verificado a mano el mismo día: tarjetas Sí/No (botón y Enter), pasos del chat, enviar texto, cancelar un
    recordatorio, olvidar un recuerdo, mantener para hablar (ratón y espacio), pulsar la cara, minimizar y cerrar a la
    bandeja y volver con «Abrir BAXY».
  - **Abierto (rojo):** `scripts/test_field_ui.ps1` da 23/24. Falla `controls.spec.ts › micrófono` en una app recién
    arrancada: tras «Siempre activo», «Apagado» no deja la voz en `off` en 8 s y «Mantener para hablar» no se aplica
    (el botón sigue en «Siempre activo»), y el espacio no escucha. Con la app ya asentada, los mismos pasos pasaron
    (50/50 a mano). La fila de comandos de voz no lo arregló; sospecha: la primera orden tras el arranque espera a
    `AwaitStartupVoiceAsync` y la vista no la ve terminar. Probablemente es lo que vio el dueño («no me funcionó
    ninguno»). Se investiga abriendo la app cuando el dueño libere la GPU.
- **Adaptado a lo que BAXY es (pedido del dueño):** donde el diseño prometía algo que BAXY no hace, la vista dice lo
  real. La tarjeta espera lo que dura el token del kernel (2 min, `ConfirmationLifetime.Challenge`) y la propuesta del
  latido 10 min (`NativeTurnLoop.ProposalLifetime`); los dos plazos los informa `GET /confirmation`. Hay dos niveles,
  Normal («lo arriesgado») y Bypass («nada»), y ningún texto menciona un tercero. El arranque ya no promete «12 a 18 s»:
  muestra cuánto tardó la carga anterior en este PC.

## Interfaz v5 (2026-10-21, `Baxy Design (2).zip`)

Sólo lo que cambió de la v4; el detalle está en `src/Baxy.FieldUi/ORIGIN.md`. BAXY es ahora el avatar en vídeo de
Higgsfield (37 clips en `src/Baxy.FieldUi/public/clips`, en Git por decisión del dueño) con la red viva dibujada
encima; en tema claro, con `?avatar=live` o sin fotograma, se dibuja la cara en código. Icono nuevo, fondo de
nebulosa, chat que baja solo salvo que la persona suba a mano, arreglos de la ronda 2.

- **Trampa que ya mordió:** la App sirve una copia de `dist/` en su `bin` (`FieldUi\`), no `dist/` directo. Recargar la
  vista no basta: tras `pnpm build` hay que relanzar con `scripts\run_renew.cmd` (el fingerprint incluye `dist/` y
  recompila). Se vio al dueño con la vista vieja mientras `dist/` ya tenía la nueva.
- **Fallo corregido:** el avatar a veces no se veía. React volvía a poner la clase `nf` (sin fotograma) en cada cambio
  de estado y el vídeo quedaba en opacidad 0 mientras la cara dibujaba sólo la red. Ahora `AvatarVid` es dueño de sus
  clases y `avatar.spec.ts` comprueba en cada muestra que BAXY se ve (vídeo con fotograma o cara entera).
- **Aceptación:** `scripts\test_field_ui.ps1` 34/35 en una corrida y las 3 restantes del avatar en la siguiente
  (sin cambios de la vista entre ellas): 35/35. `controls.spec.ts › micrófono` pasó también en la app recién lanzada.
- **Hallazgos fuera de la vista (no tocados):** con «Sí», mover a la papelera tardó 101 s y 74 s; la primera vez el
  sistema no respondió y BAXY lo dijo («No pude confirmar que se borró…»), la segunda quedó en la papelera
  (comprobado). La frase dice «el papelera» (concordancia, la compone la mente).
- **Lip-sync (2026-10-21):** la boca del avatar sigue al sonido real (detalle y medidas en
  `src/Baxy.FieldUi/ORIGIN.md`). Cadena: `voice_output.py` (evento `lip`: volumen cada 40 ms + hora en que suena) →
  `MainWindowViewModel.VoiceLip` → `FieldProductChannel` → `lip.ts` → bocas recortadas de los clips en `AvatarVid`.
  `e2e/lipsync.spec.ts` lo mide con `scripts/tools/loopcap` (loopback de proceso: sólo el sonido de BAXY, con o sin
  otros sonidos en el PC); necesita la voz sin silenciar.
