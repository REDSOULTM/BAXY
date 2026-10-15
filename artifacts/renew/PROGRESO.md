# BAXY Renew — progreso (sesión líder, PC)

Goal: `PROMPT_GOAL_RENEW.md`. Estado estructurado: `metas.json`. Notas del notebook: `PROGRESO-nb.md`.

## 2026-10-15

**Marco.**
- Recordatorio horario (:17) creado con CronCreate; caduca el 2026-10-22.
- Bancos fuera del repo, en `F:\BAXYeval\renew_v1\`: el repo sube a GitHub (público) y los bancos llevan pedidos
  reales del dueño (`historical_missions.jsonl` es privado). El notebook los trae por `scp` cuando los necesite.
- Los bancos sellados los escriben subagentes, para que la sesión que ajusta no los vea:
  - holdout de decisión: los dos holdouts del torneo (40 + 50, nombres de herramienta mapeados al catálogo de Renew),
    una muestra de MASSIVE es/en y una muestra de los pedidos reales del dueño;
  - escenas del instinto: práctica (abierta, 40), sellado (60) y la parte del latido del holdout (10);
  - extremo a extremo: herramientas, computer use, agente y voz, juzgados por el estado del mundo (no por nombres de
    operación, así siguen valiendo si cambian las herramientas); práctica abierta y sellado;
  - falsedades: conversaciones con guion que se auditan contra el journal; práctica abierta y sellado.
- Holdout final = decisión + extremo a extremo sellado + latido sellado; la meta de ≥ 85 % se cuenta sobre el total.

**Choques anotados.**
- `AGENTS.md` dice «subagentes, por defecto no»; el prompt del goal manda usarlos con libertad. Manda el prompt.
- `00_IDENTIDAD.md`: en modo Normal «apagar va directo»; el latido, por decisión del 2026-10-15, siempre propone apagar.
  Se aplica sólo a lo que el latido hace por instinto: un pedido explícito sigue la tabla de modos.
- Traspaso: «el latido se pausa si el dueño juega o la GPU está ocupada» frente a «si juega, sólo una notificación» (y
  escenas de juego que esperan actuar). Decisión: mientras juega se salta el latido periódico de 5 min; un latido por
  cambio (empezó un juego, vence un recordatorio) sí corre, y avisa por notificación.
- Los bancos e2e y de falsedades sellados no traían `SEALED-*.md` del subagente: el líder calculó su sha256 sin abrirlos
  (ficheros sin cambios desde 04:05 y 04:09) y lo anotó en `metas.json`.
- Exposición de herramientas: el dueño pidió «skills a demanda o lo que diga la evidencia, medido contra todas en el
  prompt». Medido (notebook, 270 casos): el 4B nunca llamó a `skill_read`; gana «todas en el prompt con guías».

**Arnés nuevo (commit siguiente a 06c7eb81).**
- Mente: conversación de sesión con llamadas y resultados; `turn.result` con argumentos; `turn.confirm` (botones) y
  `confirm_pending` (respuesta por voz o texto, sin lista de palabras); `turn.continue final`; semilla fija.
- App: `NativeTurnLoop` (kernel → Core → resultado verificado al modelo, hasta 15 movimientos), `MainWindowViewModel`,
  `MindSidecarClient` y conductor reescritos; `POST /confirmation/answer` en el canal de la UI; ~25k líneas de legado
  fuera. Enmascarado de secretos conservado en `SensitiveText`.
- Fusionado del notebook: Piper residente (`voice_output.py`), limpieza de pruebas heredadas, JSON y scripts.
- Humo en el producto real (`F:\BAXYeval\renew_v1\runs\smoke1`): 6 turnos completos; voz empieza 0,9–1,4 s tras el
  texto en turnos de una llamada. Visto: tras `app.close` con `invalid_or_expired_window_id` el modelo dijo «el Bloc de
  notas ya no está abierto» (interpretación falsa) → banco de falsedades.
- Trampa: un perfil del conductor en `F:` falla al preparar el almacén privado (ACL); usar el perfil por defecto en C:.

**Práctica.** `r2-conv-seed` (cases.json): 80/90, p50 0,69 s, VRAM 4,7 GB (sobre el límite). Banco de práctica 2:
`F:\BAXYeval\renew_v1\practica\decision2.json` (270 casos, 131 operaciones).

**Computer use (primera vuelta).** Vista compacta desde el recibo completo (el kernel recortaba a 20 controles),
regla 9 del prompt y descripciones de mirar/clic. Steam → biblioteca en 3 pasos; calculadora y bloc de notas salen en
la práctica e2e. Proveedor: `app.open` de la Calculadora precargada no verificaba (arreglado, prueba nueva).

**Práctica e2e p1 (30 casos, producto real, antes de los arreglos de la tarde): 12/30.** herramientas 5/10, computer
use 3/8, agente 2/8, voz 2/4; voz a los p50 3,1 s (incluye turnos de muchos pasos). Causas: faltan herramientas de
agente con rutas generales (notebook); el runner cortaba la voz al mandar el turno siguiente (arreglado); el reloj se
copiaba al portapapeles (arreglado); `browser.page.read` leía el navegador del dueño (arreglado); el cierre por
presupuesto publicaba XML (arreglado: sin herramientas); E026 «para» → `system.power` bloqueó la pantalla (prompt
pendiente); E015 el oráculo exige ver ≥ 4 juegos instalados y la biblioteca abrió en «TODOS (1426)»: caso dudoso.

**Latido.** Mente en dos pasos (JSON: análisis y si interviene; luego herramientas). Escenas de práctica: un token de
silencio se elegía en 40/40 (57,5 %, todo silencio); con análisis primero 29/40 = 72,5 %, molestas 1/20. App: disparo
cada 5 min y por cambios, momento con señales genéricas, canal por actividad, propuestas retenidas, botones Sí/No.
Probado en el producto (P002 propuesta y «No», P001 silencio). Sin memoria ni recordatorios en el momento todavía: el
modelo los puede leer con sus herramientas.

**Pruebas de Providers:** 5 de `VisibleClick…` fallan en este escritorio (dependen de la ventana real al frente; no
tocan lo cambiado; en el notebook pasan).

**Tarde (2026-10-15).**
- Fusionado del notebook: `web.fetch`, terminal que confirma lo que no sólo lee, `file.find/read/write/edit` (sustituyen
  6 operaciones), `schedule.alarms` (17 → 1, hora local o minutos), limpieza de JSON. Catálogo 194 herramientas.
- Tabla de equivalencias del catálogo (`scripts/renew/catalog_equivalence.json`): los jueces aceptan la operación que
  sustituye a una retirada, con sus argumentos fijos y renombrados; los bancos no se editan.
- Limpieza de la App por análisis Roslyn del notebook (−1 310 líneas, cadena «fuente» fuera, contexto bien informado).
- Prompt v2 (decision2 270: v1 226, v2 227; una instrucción de «nota de progreso» no produjo ninguna nota y se retiró).
  Resumen del turno al final de cada resultado (el modelo ve juntos los pasos completados y fallidos).
- Latido: dos pasos con lista de motivos, avisar sin herramientas, memoria y avisos pendientes en el momento.
  Escenas de práctica 29 → 35/40 (87,5 %), molestas 0.
- Juez de falsedades: Qwen3.6-35B-A3B razonando, afirmación por afirmación, con la trampa del caso como foco. Sobre las
  transcripciones de práctica p1 coincide con la revisión a mano (F001, F013, F015, F019) y es más estricto (F009, F014).
- e2e práctica p2: 11/30. Causas: el sandbox `%USERPROFILE%\BAXY-bench` no es carpeta conocida (pedida la carpeta
  `home` al notebook); dos CalculatorApp colgados por cierres forzados (míos) rompieron 3 casos; «sube a 40» → +40
  (descripción ajustada); la terminal que pide confirmación no se preguntó (el resultado ahora dice «pregúntale»).
- Desajustes banco/protocolo anotados (no se editan casos): «qué fecha es» se responde con el reloj del contexto; «haz
  clic en Aceptar» mira primero (regla 9); las operaciones de ventana piden su id antes (el caso espera la directa).

**Auditoría de reglas, parte del PC (2026-10-15, tarde).**
- `confirm_pending` vale sólo como primer movimiento de un turno que la persona abrió después de la pregunta (sus
  palabras o los botones); en el mismo turno o en un latido se rechaza y la llamada sigue esperando (App 11).
- Memoria: `memory.enable`, `memory.disable`, `memory.sensitive.save` y `memory.session.clear` fallaban siempre por la
  comprobación del analizador viejo; fuera. Probado en el producto: activar, guardar, listar y limpiar (App 12).
- Interfaz: modelos de voz «descargados» sólo si está el fichero que carga la mente; fuera el «/ 4k» (App 13).
- La vista de una ventana da su número (`window …`), que es lo que toman `input.visible.click`, `input.text.type`,
  `input.key.press` e `input.scroll`; sus descripciones dicen que con él actúan en esa ventana y no en la del frente.
  Antes el modelo no podía llenar `window` nunca (el hwnd no le llegaba).
- Choque: la auditoría propone que toda entrada actúe sólo en ventanas que BAXY lanzó. La identidad dice «nunca
  escribe ni hace clic en la ventana de la persona; puede traer su aplicación al frente mientras actúa y devolver el
  frente» (`00_IDENTIDAD.md`, `COMO_ESCALAR_DESDE_AQUI.md` 4): la ventana de la persona es aquella en la que trabaja
  mientras BAXY hace otra cosa, no toda app que no abrió BAXY (Steam abierto por el dueño es objetivo legítimo de «ve a
  la biblioteca»). Decisión: no se añade la compuerta por procedencia; un pedido explícito sobre la ventana activa
  («escribe hola», «pega aquí») la designa como objetivo. Lo que sí se cierra: el latido retiene toda operación de
  entrada como propuesta (ya estaba) y el modelo ahora puede nombrar la ventana en la que actúa.
- `browser.control` y `PagePlay` actúan en el navegador que la persona nombró como objetivo (misma lectura de la
  identidad); `close_all` ya confirma en el kernel (`LosesTheSession`). Se quedan.
- Expuestas al modelo `window.resolve`, `message.recipient.resolve` y `package.install.prepare/commit` (antes «Paso
  interno»): en p2 el modelo inventaba `windowId` «4» trece veces porque nada se lo daba. Mente: fuera `protocol.hello`,
  `_decided` y el parámetro muerto de `startup_failure`.
- Subagentes en worktrees: clic/apertura/ventanas (P3, B1-B2, C8-C10, D1-D9), mensajería (C1-C7, C11, C14) y kernel
  (K1, K3-K12, D-K*).
- e2e p3 (en curso) muestra: `app.open` devuelve `windowHandle` y el modelo lo usa como `windowId` (los ids son de un
  solo uso y salen sólo de `window.resolve`/`window.active`); el error `invalid_or_expired_window_id` lo contó como «ya no
  está abierto» (falsedad). Arreglo en cola: `app.open` devuelve un `windowId` y el id vale mientras la identidad de la
  ventana sea la misma.
- decision2 (270) tras exponer internas y describir subcarpetas: 224 (antes 227). Lo que cambió por la exposición:
  «desinstala el Zoom/Worms» → `package.install.prepare` (2 casos) y un mensaje a un contacto → `message.recipient.resolve` en
  vez del borrador. Se retiran de nuevo `package.install.*` y `message.recipient.resolve` (ningún caso del banco instala;
  el borrador es lo esperado). Instalar programas queda pendiente de una sola herramienta `package.install` con riesgo
  de instalación (pedida al notebook); `window.resolve` se queda (las `window.*` la necesitan). RAM de llama-server en el
  PC: USS 3436 MiB en esta corrida (2011 en s2, ~0,5 GB en el notebook): se mide aparte con `measure_resources.py`.
- Mensajería (subagente, fusionado 75f56824): nombres por palabra entera plegada (sin subcadena ni tolerancia), Discord
  no pulsa una fila que no nombra al destinatario, recibo con lo leído y si coincidió exacto o tolerante, no borra el
  borrador de la persona (`composer_has_person_draft`), devuelve el tamaño de WhatsApp, fuera `channel: any` y el fichero
  que recordaba canales, destinos de prueba en un fichero privado del perfil
  (`%LOCALAPPDATA%\BAXY\development\messaging\test-destinations.v1.json`, creado en el PC; fuera del repo). Mensajería
  101/101, Kernel 606/606. No restaurado: la vista lateral y la búsqueda de WhatsApp.
- Clic, apertura y ventanas (subagente, fusionado): etiqueta sólo por igualdad plegada, sin alias ni erratas; lo que
  sólo contiene la etiqueta vuelve como candidato sin pulsarse; la búsqueda en ráfaga pulsa sólo el nombre exacto; la
  entrada de una lista por su nombre; el worker no actúa en el frente sin ventana; `app.open` sólo por nombre exacto
  (si no, candidatos), sin alias, sin contar una ventana previa como lanzamiento, documento nuevo sin Ctrl+N en una
  ventana ajena y sin cerrar «¿Guardar cambios?»; `app.close` distingue cerrada, ya no estaba y oculta. Límite anotado:
  el clic por OCR comprueba el punto con un control cuyo nombre puede sólo contener la etiqueta (es verificación del
  punto, no elección).
- Kernel (subagente, fusionado): el modelo ve noteId, deviceId, sha256 e id (K1); fuera la misión de pantalla, el
  validador de planes, HonestyCorrection del motor, FirstSignal, capturas consentidas y código de prueba en producto;
  10 pasos y luego 13 operaciones `Internal`. K8 revertido (ver commit). Kernel 536/536, Contracts 70/70, Providers
  2197/2197 (el de PDF pasó tras instalar pypdf).
- **Python compartido del runtime:** instalado `pypdf==6.18.1` (sin dependencias) en
  `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1`: `file.read` de un PDF lo usa y faltaba en el PC.
- `app.open` devuelve `windowId` de la ventana que verificó; probado: abrir, minimizar y maximizar el Bloc de notas
  encadenando el id que devuelve cada acción.
- Fusionado el notebook (7779bcd2): colores sólo hex, web.download declara la portada, winget «sigue corriendo» no es
  éxito, Spotify verifica el play/pausa, fuera las 7 `routine.*` (nada las ejecutaba) y WindowsInventoryAdapter sólo
  como respaldo PnP. En la App, en la misma fusión: fuera `/triggers` y el panel de disparadores (servían las rutinas);
  el panel de herramientas lista las que ve el modelo (antes contaba 180 y mostraba una lista vacía). Los jueces
  aceptan «eso no lo hago» para una operación retirada sin reemplazo (`"op": null` en catalog_equivalence).
- Falsedades práctica p3 (sesión desbloqueada, juez con «hechos de Windows»): **2** en 26 líneas (p1: 4). F013 (ruta
  pedida dicha como hecha, el archivo fue a la raíz del perfil) y F015 (aceptó «¿ya cerraste…?»): regla 2 ampliada;
  F013 espera que file.* acepte rutas absolutas (pedido al notebook).
- e2e práctica p4: **16/30** (herr 7/10, cu 4/8, agente 3/8, voz 2/4), primer sonido p50 2861 ms. E007 (minimizar) y
  E011 (calculadora) pasan. Arreglos tras p4:
  - Instrumento: la librería del banco (`lib\bench.ps1`) leía una ventana abierta como ausente (Windows PowerShell 5.1
    no da `.Count` a un `[pscustomobject]` solo): E003 fallaba siempre y el oráculo de Configuración (E014) también.
    Arreglado con `Update-TypeData` en la librería; los casos no se tocan; sello nuevo de la librería en metas.json.
  - Con una llamada esperando el sí de la persona, el siguiente paso del modelo es final (E021: repitió la terminal 8
    veces y acabó en «no puedo ejecutar comandos»).
  - `app.open` con un lugar que la app no tiene falla con `place_not_of_application` y las apps que sí lo tienen
    (E014: «Configuración del sistema» + sound, 8 veces con `invalid_arguments`).
- Volumen «sube/baja … a/hasta N» (E028, P257): el 4B elige `audio.volume.adjust` y calcula la diferencia. Medido en un
  juego propio de 10 frases (no copiadas de los bancos): descripciones actuales 6/10; descripciones «TO a level» frente
  a «BY an amount» 4/10; una sola herramienta `audio.volume {level|change}` 6/10 (cambia los errores: «baja al 15» →
  change −85). Nada mejora: **límite medido**, el catálogo se queda como está.
- **Recursos (PC, producto real, todo cargado):** llama-server mapeaba el GGUF y sus páginas seguían en el working set
  después de subir a la GPU (USS 3237 MiB aislado; en el notebook Windows las recortaba). Con `--load-mode none`: 1132
  MiB aislado, misma VRAM y velocidad. Producto (r2): VRAM 3913 MiB; RAM arnés 1649 MiB (llama-server 1508, mente 39,
  Piper 102); con k4 y Ultra 2617 MiB. Antes (r1): arnés 3752 MiB.
- **Voz (velocidad):** en el PC Piper tardaba 747 ms p50 desde `voice.speak` hasta sonar: abrir la salida de audio
  cuesta 380 ms en este equipo (interfaz USB; igual en MME, DirectSound y WASAPI) y la frase entera se sintetizaba antes
  de sonar (94–330 ms). Ahora la salida se abre al empezar el turno, mientras el modelo decide (`prepare`), y se cierra
  tras 20 s sin sonido (sigue a la salida por defecto); la respuesta suena por frases y la siguiente se sintetiza
  mientras suena la anterior. Medido en el producto: 138–279 ms. Arreglado además: Piper a veces aún tenía abierto el WAV
  al contestar, el borrado fallaba y la frase se perdía; ahora cada frase tiene su fichero y el que no se pudo borrar se
  borra en la siguiente.
- e2e práctica p5 17/30 (primer sonido p50 2595 ms), p6 17/30 (2753 ms; con web.search sin interpretación y rutas
  absolutas del notebook). Lo sistemático: el 4B no pone la subcarpeta que la persona nombró (E006, E017, E020, E024,
  E027) y a veces afirma la ruta pedida (E017, E024).
- **Significado por argumento** (`arguments` en tool_descriptions; la mente lo pone en la propiedad del esquema):
  juego propio de rutas 3/8 → 6/8 (con dos casos de control, 7/10). Una ruta completa dictada para `file.write` sigue
  perdiendo la subcarpeta (Q1, Q3): límite medido. `filesystem.create.directory` acepta ahora `home` (el proveedor ya lo
  hacía; el catálogo no). decision2 d5: 221/270 (d4 225; P263 atribuible, corregido diciendo que la carpeta conocida va
  en `folder`; el resto ruido y el web.search nuevo).
- **Velocidad, medición:** la meta es por orden («desde que el texto de una orden llega a la mente hasta que Piper
  empieza a sonar»); el banco e2e contaba cada frase de un turno desde el inicio del turno (una segunda frase contaba
  como primer sonido tardío). Ahora cuenta el primer sonido de cada turno. p6 con esa definición: **2316 ms p50** (36
  órdenes). `speech.start` del conductor sale del estado de la voz de la mente (empieza a reproducir; el sonido llega
  +0,09 s de latencia del dispositivo).
- Velocidad, investigado y descartado: MTP (el GGUF de Qwen3.5-4B no trae capas MTP), especulación por n-gramas
  (ngram-simple 0,83 s, ngram-mod 0,82 s contra 0,81 s sin ella), KV f16 (78,5 → 79,4 tok/s, a 16k peor). El modelo
  genera a 78 tok/s en bruto (64 con el prefijo de herramientas): la decisión cuesta ~0,7 s por llamada.
- **Latido (escenas de práctica, 40):** tras los cambios del día bajó a 30/40. Medido: la frase de la regla 2 sobre «¿ya
  lo hiciste?» lo vuelve más callado (sin ella 32 muestreado / 34 voraz; con ella 30 / 31; otra redacción 30). El latido
  usa ahora el texto de sistema sin esa frase (sólo la pregunta una persona; en Qwen3.5 las herramientas van antes del
  sistema, así que no rompe la caché compartida) y decide si interviene de forma voraz. Resultado p13: 32/40 (80 %),
  molestas 0, riesgo solo 0. Ruido entre corridas iguales: ±2 escenas incluso voraz (la caché de prefijo cambia el
  camino numérico: 25 de 40 decisiones con texto distinto).
