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
| Voz que habla | Piper como antes |
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
| Reparto según rendimiento | **PC:** el arnés nuevo, computer use (las apps reales del dueño), el latido, la integración y la medición final. Con 16 GB caben dos llama-server a la vez, así que puede correr dos bancos en paralelo. **Notebook:** la voz que habla (Piper, CPU), las herramientas de agente, la limpieza de código muerto, el banco de escenas y la investigación. Con su GPU cerca del límite de 4 GB, mide el perfil de 4 GB (IQ4_XS con un hueco) en hardware real |

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
3. **Voz que habla, con Piper como antes** (decisión del dueño):
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
  - Desde que el texto de una orden llega a la mente hasta que Piper empieza a sonar, ≤ 2,5 s.
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
