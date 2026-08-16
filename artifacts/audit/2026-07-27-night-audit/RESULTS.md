# Resultados de la auditoría

## Sincronización

- `git rev-parse --show-toplevel`: `D:/BAXY/source`.
- Árbol de trabajo inicial: limpio.
- `git ls-remote --heads origin codex/baxy-rebuild-v3`:
  `f23b23f064211154e954d82883ba6bee5c2c466c`.
- `HEAD`: `f23b23f064211154e954d82883ba6bee5c2c466c`.
- Resultado: el repositorio ya estaba en la última versión publicada.
- Observación de infraestructura: `git fetch --prune origin` no pudo recorrer
  una referencia interna corrupta bajo `refs/codex/turn-diffs`; no se borró ni
  se modificó esa referencia porque no pertenece al producto auditado.

## Ejecuciones

- 00:55 — Primer intento de `pytest`: error de arnés antes de la colección
  completa porque faltó `PYTHONPATH=src`. No es un defecto de BAXY; se relanzó
  con el entorno correcto.
- 00:57 — Primer intento de smoke del catálogo instalado: el arnés eligió una
  raíz aislada fuera de `%LOCALAPPDATA%\BAXY`; el core cerró en fail-closed
  antes de publicar catálogo. Se corrigió solo el arnés y se repitió.
- 00:59 — Suite Python aislada con `PYTHONPATH=src`: 611 pruebas y 350
  subtests aprobados en 237,28 s; cero fallos.
- 00:59 — Primera corrida .NET concurrente: 2.090 totales, 2.051 aprobadas,
  17 omitidas y 12 fallidas. Corrida no concluyente porque coincidió con
  `pytest` y un segundo core instalado; queda pendiente replay aislado y
  serial antes de clasificar la señal como defecto.
- 00:59 — Smoke del catálogo instalado alcanzó 59/168 antes de que
  `game.install.prepare` terminara el core con `InvalidDataException`.
  Reproducción focalizada posterior: 8/8 cierres para
  `game.install.prepare`/`game.install.status`, instalación/desarrollo.
  Registrado como `BAXY-AUD-001` (P1) con causa raíz.
- 01:09 — Los 12 fallos .NET se reprodujeron al ejecutar solo
  `CoreNotesEndToEndTests`, pero quedaron explicados por el arnés: los tests
  crean el hijo mediante `dotnet` y el `PATH` resolvía el host global sin
  .NET 10. Al anteponer `C:\Users\usuario\.dotnet`, los mismos 12/12 aprobaron.
  No se registró defecto del producto.
- 01:12 — Suite .NET completa, serial y con toolchain fijado: 2.080 casos,
  2.063 aprobados y 17 omitidos; cero fallos.
- 01:13 — Barrido instalado de las 168 operaciones completado. Todas las
  fronteras públicas rechazaron argumentos inesperados sin efectos. Las 11
  operaciones de memoria devolvieron correctamente
  `invalid_private_envelope`; deben probarse desde la ruta autenticada del
  producto, no mediante JSONL desnudo. Se alcanzaron 59 providers `read_only`;
  52 respondieron terminalmente, tres operaciones de memoria quedaron
  protegidas por sobre privado, y cuatro señales requirieron reproducción.
- 01:14 — `package.install.prepare` con un paquete real y schema-válido
  reprodujo 4/4 cierres del core cuando `winget.exe` no está en `PATH`.
  Registrado como `BAXY-AUD-002` (P1); no se intentó instalar nada.
- 01:15 — `bluetooth.device.list` reprodujo el bloqueo 5/5 en instalación y
  desarrollo. La consulta PowerShell equivalente terminó en 1,57 s, pero el
  primer adaptador WinRT nunca cedió al fallback. Registrado como
  `BAXY-AUD-003` (P1).
- 01:20 — La compuerta de comportamiento con el modelo local aprobó 24/25
  casos, con máximo de 0,437 s. Falló solo el caso de confusión: devolvió
  `¿Qué quieres saber?` en vez de reconocer explícitamente que no había
  entendido.
- 01:24 — Un saludo desde la interfaz real devolvió metadiscurso en tercera
  persona. Se reprodujo 3/3, aislando como disparador la bienvenida incluida en
  el historial contextual. Registrado como `BAXY-AUD-004` (P2).
- 01:30 — Calculadora se abrió y verificó correctamente en dos ciclos. El
  cierre posterior falló 2/2 porque la ventana UWP ignoró `WM_CLOSE`; el
  verificador lo informó honestamente y la ventana se limpió manualmente al
  terminar cada sonda. Registrado como `BAXY-AUD-005` (P2).
- 01:36 — Peticiones inequívocas para abrir Opera y Bloc de notas fueron
  desviadas a aclaraciones sobre URL/Explorer. Una orden en inglés para
  Notepad sí alcanzó `app.open`, pero el efecto falló y queda pendiente aislar
  esa segunda señal en la compuerta física oficial.
- 01:42 — `Que hora es?` no ejecutó `system.time`: la interfaz pidió una
  aclaración innecesaria y la sonda contextual afirmó que no tenía acceso a la
  hora. Registrado como `BAXY-AUD-007` (P2).
- 01:43 — `Abre Spotify` preguntó qué buscar y no creó proceso ni ventana.
  Junto con Opera y Bloc de notas confirma `BAXY-AUD-006` (P1): el objetivo
  inequívoco se mezcla con argumentos de otra intención.
- 01:47 — La misión compuesta de Spotify sí construyó un plan y pidió
  confirmación. Tras confirmarla, el core abrió Spotify, buscó la pista
  correcta y certificó `media.play.query` en 21,73 s. La interfaz agotó su
  timeout de 20 s, afirmó que la acción falló y dejó la invocación en el
  outbox. La aplicación quedó sin aceptar la cancelación del plan. Registrado
  como `BAXY-AUD-008` (P1). Spotify quedó pausado y se cerró limpiamente; el
  launcher preexistente no se tocó.
- 01:55 — La compuerta física oficial de `app.open` abortó antes del efecto:
  limita una línea JSONL a 65.536 bytes, mientras el catálogo actual mide
  73.493 bytes en el build. Registrado como `BAXY-AUD-010` (P2, arnés).
- 01:58 — `app.open` directo con el argumento crudo `notepad` reprodujo
  `app_not_found`, confirmando que el extractor de la interfaz no normaliza al
  identificador `windows.notepad`. Registrado como `BAXY-AUD-009` (P2).
- 02:00 — Siete aperturas canónicas y aisladas de Bloc de notas: seis
  terminaron verificadas y una primera corrida abrió una ventana real pero
  devolvió `verification_failed/effectMayHaveOccurred:true`. Todas las ventanas
  creadas por la auditoría se cerraron y ninguna quedó activa. Registrado como
  `BAXY-AUD-011` (P2, intermitente de arranque frío).
- 02:00 — Tras reiniciar BAXY, la recuperación durable detectó correctamente
  el plan de Spotify, aceptó `cancelar`, eliminó plan y outbox y no repitió el
  efecto. Caso aprobado.
- 02:01 — La misión `Abre Opera y navega a https://example.com/` falló antes
  de emitir cualquier operación. La sonda del modelo muestra inestabilidad:
  según el historial propone `browser.navigate.named` o un DAG genérico
  `browser.navigate` + `browser.page.read`.
- 02:07 — La petición más explícita `Navega Opera a https://example.com/`
  alcanzó el core, que pidió confirmación sin efecto. La interfaz perdió esa
  confirmación, mostró primero fallo y luego afirmó falsamente que había
  navegado. No hubo proceso ni journal de efecto y quedó una entrada en el
  outbox. Registrado como `BAXY-AUD-012` (P1).
- 02:08 — Control positivo directo: el mismo core y el mismo provider
  `browser.navigate.named`, con handshake de confirmación completo, abrió su
  Opera CDP privado y verificó exactamente `https://example.com/`. El proceso
  terminó con el core aislado. Esto descarta instalación/provider como causa
  del fallo de interfaz.
- 02:12 — Reinicio de control con la identidad de navegador aún en el outbox:
  BAXY mostró solo la bienvenida; no anunció ni permitió reconciliar/cancelar
  la entrada. Tras documentarlo, se cerró el producto y se retiró
  exclusivamente la entrada creada por la auditoría, restaurando el outbox
  vacío sin tocar datos previos.
- 02:15 — Cadena CDP nombrada: Opera navegó y verificó `example.com`, pero
  `browser.page.read` falló inmediatamente porque las operaciones posteriores
  pertenecen a una sesión CDP genérica distinta. Registrado como
  `BAXY-AUD-013` (P1).
- 02:16 — Control positivo del navegador genérico: 7/8 operaciones verificadas
  (navigate, read, tabs, scroll, reload, navigate y back). El cierre de la
  última pestaña sí eliminó la sesión, pero devolvió
  `web_adapter_unavailable`. Registrado como `BAXY-AUD-014` (P2).
- 02:18 — Audio físico: baseline 3 %, set a 7 % verificado, ajuste -2 a 5 %
  verificado. La restauración directa a 3 % fue omitida como «ya satisfecha»
  por la tolerancia de ±2 y se reportó éxito con final 5 %. Registrado como
  `BAXY-AUD-015` (P2). Se restauró exactamente el 3 % mediante un paso puente
  a 0 %, y la postlectura final confirmó 3 %, audio activo.
- 02:19 — Portapapeles físico: escritura de marcador y doble lectura
  verificadas. El contenido anterior se mantuvo solo en memoria y se restauró
  al finalizar, sin imprimirlo ni guardarlo. Caso aprobado.
- 02:20 — Captura completa + OCR local encadenados: ambos
  `completed/verified:true`. La captura privada se eliminó con el data root y
  el texto OCR se sustituyó por hash/conteo en la evidencia. Caso aprobado.
- 02:20 — Cuatro búsquedas web reales. La estructura RSS fue válida, pero
  consultas específicas/únicas devolvieron resultados ajenos y aun así
  `verified:true`. Registrado como `BAXY-AUD-016` (P2).
- 02:21 — Compuerta integral de voz con salida física: dependencias, entrada,
  loopback, SAPI, cancelación, AEC (61,01 dB) y ducking/restauración aprobaron.
  La compuerta global falló por wake manifest ausente y porque la muestra
  histórica perdió la entidad Spotify. Registrados como `BAXY-AUD-017` y
  `BAXY-AUD-018` (P1).
- 02:23 — Diagnóstico redacted de la muestra: STT no vacío, dos tokens; el
  término de corrección Spotify sí está presente, pero la hipótesis queda a
  distancia de edición 3 y no hay alternativa n-best que habilite la rama
  fonética. No se almacenó el transcript.
- 02:29 — Cadena de datos locales instalada: 30/30 operaciones verificadas
  sobre notas, tareas, recordatorios y rutinas, incluyendo CAS, búsquedas,
  completar/reabrir, papelera y restauración. El almacén sintético aislado se
  eliminó al terminar. Caso aprobado.
- 02:32 — La cadena de archivos aprobó creación, escritura y lectura, pero
  `filesystem.hash` cerró el core 3/3 (dos corridas instaladas y una de
  desarrollo), siempre con código 70 e `InvalidOperationException`. La causa
  es el objeto JSON singular mal construido por `FilesystemResultJson.Entry`.
  Registrado como `BAXY-AUD-019` (P1); no se cambió código del producto.
- 02:33 — Rodeando únicamente `filesystem.hash`, el resto del ciclo aislado
  aprobó 22/22: CAS de escritura, lista, búsqueda, copia, backup,
  verificación, restauración, movimiento, papelera y recuperación. Caso
  aprobado; el sandbox completo fue eliminado.
- 02:42 — `input.select.all` falló en Notepad, WinForms y WPF. El diagnóstico
  exacto mostró que la ruta WPF llega a una selección completa pero el script
  no cargó el ensamblado que contiene `TextPatternRangeEndpoint`; WinForms
  tampoco tiene fallback sin `TextPattern`. Registrado como
  `BAXY-AUD-020` (P1).
- 02:45 — La cadena sintética de ventanas completó entrada, layout, teclado
  en pantalla, movimiento, tamaño, foco, puntero y cierre. Sin embargo,
  maximizar/minimizar/restaurar devolvieron fallo 7/7 sobre WPF y WinForms,
  mientras una postlectura a 500 ms observó 7/7 efectos correctos. Registrado
  como `BAXY-AUD-021` (P1). Las dos ventanas, los dos teclados en pantalla y
  el puntero quedaron cerrados/restaurados.
- 02:47 — BAXY abrió y resolvió su teclado en pantalla, pero `app.close`
  devolvió `action_failed`. El HWND aceptó enseguida el comando de sistema
  `SC_CLOSE`, usado solo para la limpieza. Registrado como `BAXY-AUD-022`
  (P2); no quedó ningún teclado de auditoría abierto.
- 02:50 — Control UIA positivo: botón WPF sintético, foco, click visible,
  postcondición deshabilitada y cierre aprobaron 5/5. Caso aprobado.
- 02:51 — Recordatorio físico de Windows programado dos horas al futuro y
  cancelado inmediatamente: 2/2 verificadas y la identidad exacta quedó
  ausente. No sonó ni quedó tarea o script pendiente.
- 02:58 — Wi-Fi confirmó desconectado sin exponer perfil; correo alcanzó el
  adapter y falló limpiamente por Outlook no configurado. Brillo aprobó
  0→5→0 con postlectura final en 0. Micrófono aprobó mute y restauración al
  estado activo.
- 03:00 — Terminación de proceso con confirmación: BAXY cerró exactamente el
  único `ping.exe` sintético, certificó identidad original ausente y no quedó
  proceso. Replay/idempotencia aprobó creación única, respuesta replayed y
  conflicto fail-closed para payload distinto.
- 03:04 — Matriz del modelo real: aceptando acción o plan equivalente, solo
  21/60 órdenes conservaron la intención. Hubo negativas falsas de capacidad,
  confusiones entre familias y 5/5 misiones compuestas finales incompletas o
  erróneas. Sin historial, 18/20 fallos persistieron; la shortlist E5 contenía
  la operación correcta en 18/20. Registrado como `BAXY-AUD-023` (P1) con
  causa raíz en autoridad LLM sin rescate semántico determinista.
- 03:08 — Compuerta oficial LLM→DAG→grounding→core: 3/9 misiones aprobaron,
  6/9 fallaron y seis pasos se ejecutaron verificados. Nota roundtrip, catálogo
  Steam+estado y web+navegación aprobaron; cinco DAG perdieron o sustituyeron
  efectos y calendario falló limpiamente por Outlook no configurado. Refuerza
  `BAXY-AUD-023`; no quedó navegador, Spotify ni documento de auditoría.
- 03:17 — Flujo de memoria privada desde la interfaz instalada y un data root
  aislado: habilitar/confirmar, guardar, consultar, listar,
  borrar/confirmar, verificar ausencia, deshabilitar y consultar estado
  aprobaron. Con la memoria deshabilitada, `memory.save` y `memory.recall`
  conservaron `memory_disabled` en el core, pero la interfaz mostró dos veces
  el fallback opaco `500: accion_no_completada`. Registrado como
  `BAXY-AUD-024` (P2). La app, core, modelo y procesos Python aislados cerraron
  limpiamente; se guardó evidencia y se eliminó solo el data root sintético.
- 03:25 — Cobertura adicional del core instalado: DOCX/XLSX crear+leer 4/4;
  clipboard copy/read/write/paste sobre controles WPF 4/4; sandbox nombrado
  5/5 efectos verificados y 2/2 rechazos fail-closed; eliminación absoluta
  recuperable 1/1. Se restauró el portapapeles previo y se eliminaron las dos
  ventanas, dos documentos Office y todos los roots/archivos sintéticos.
- 03:30 — Memoria privada ampliada desde la UI: corrección, dato de sesión,
  limpieza de sesión, guardado sensible, exportación, borrado total,
  listado vacío y deshabilitación terminaron verificados. El secreto sintético
  nunca apareció en UIA, journal ni outbox; el export confirmó el valor
  corregido, excluyó el secreto y el dato de sesión ya borrado, y fue eliminado
  exactamente. Sin embargo, 2/2 consultas de preferencia y 1/1 listado con un
  registro ocultaron `label:value` y respondieron solo «Encontré esta memoria
  local». Registrado como `BAXY-AUD-025` (P1): la reformulación LLM no exige
  preservar los hechos de la proyección segura.
- 03:34 — `audio.mute` aprobó mute/unmute con postlectura final en 3 % y audio
  activo. `network.ip.list` aprobó con confirmación y doble lectura; la
  evidencia conserva solo esquema y conteo (una dirección), no el valor
  privado.
- 03:36 — `streaming.navigate` verificó YouTube, pero
  `browser.page.read` inmediato falló 3/3 con snapshot inválido. La misma
  secuencia con 5 s de espera aprobó navegar, leer, listar pestañas y recargar
  4/4. Registrado como `BAXY-AUD-026` (P1): navegación certifica URL antes de
  que el documento alcance el estado requerido por el siguiente paso.
- 03:39 — Recordatorio local sintético pasó a vencido, apareció en
  `notification.list.due`, fue descartado por identidad+versión y desapareció
  del listado: 4/4 verificadas, store aislado eliminado.
- 03:40 — Cadena musical física directa: `media.play.query`, `media.status`,
  `media.seek.relative +10`, `media.control pause` y postestado aprobaron 5/5.
  El audio permaneció en 3 %, Spotify quedó pausado, todos los procesos creados
  por la auditoría se cerraron y el launcher preexistente siguió vivo.
- 03:49 — Cinco ciclos limpios de `media.play.exact` con `Beat It`: tres
  aprobaron reproducción exacta + estado + salto + pausa + postestado (5/5);
  dos fallaron de forma segura, pero tras unos 27 s, con
  `spotify_exact_play_control_not_found`. Registrado como `BAXY-AUD-027` (P1,
  2/5 fallos). La búsqueda no exacta conserva su control positivo 5/5. Spotify
  quedó pausado y solo permanece el launcher que ya existía antes de auditar.
- 03:50 — `filesystem.folder.open` abrió y verificó físicamente Descargas. Una
  postlectura independiente de Shell confirmó exactamente una ventana nueva en
  `Downloads`; se cerró por su HWND y no se tocó la ventana de Explorer que el
  usuario ya tenía abierta. La cobertura funcional queda en 143/168 operaciones
  públicas; 25 quedan
  deliberadamente fuera, en su mayoría por comunicación externa, privacidad,
  instalación, dinero o pérdida de trabajo.
- 03:52 — Sobre Steam ya abierto por el usuario, BAXY consultó el estado de un
  componente local instalado y preparó su instalación: ambos
  `completed/verified:true`, el segundo respondió `already_installed` y
  `requiresInstall:false`. No se lanzó juego, descarga ni diálogo. Con estos
  controles, 130 operaciones del catálogo tienen al menos un éxito verificado.
  La prueba prolongada cumplió su primera hora con 687 llamadas, cero anomalías
  y recursos estables (50,77 MiB RSS, 21,73 MiB privados).
- 03:54 — Estrés de arranque: 100/100 cores instalados publicaron el catálogo
  completo de 168 operaciones, versión 1.0.8, salieron con código cero y
  produjeron el mismo `hello` al excluir únicamente el PID. P95 0,297 s,
  máximo 0,343 s. No quedó core ni data root de la ráfaga; el único core vivo
  sigue siendo el de la prueba prolongada.
- 03:56 — Estrés de interfaz instalada: 10/10 aperturas produjeron una ventana
  visible y su core hijo, con 1,038 s de media y 1,124 s máximo. Diez cierres
  por `WM_CLOSE` terminaron con código cero, sin descendientes ni data roots
  aislados restantes. No se envió ninguna orden desde estas interfaces.
- 03:57 — Ráfaga JSONL de 240 consultas seguras en un solo core: 240/240
  `completed/verified:true` en 11,47 s (20,92 respuestas/s), sin respuestas
  perdidas, duplicadas, cruzadas o fuera de identidad. El escritor no se
  bloqueó, el core salió con código cero y el root aislado fue eliminado.
- 04:00 — Cadena navegador + click visible: tras la confirmación normal, BAXY
  navegó a una página sintética servida solo en `127.0.0.1`, encontró
  `BAXY audit web button` mediante UI Automation, lo invocó y verificó que
  quedó deshabilitado. `browser.page.read` confirmó después el texto
  `Clicked and disabled`: 3/3 operaciones verificadas. Servidor, Edge, perfil
  y core de auditoría quedaron cerrados.
- 04:01 — `media.play.youtube` buscó `Beat It Michael Jackson`, siguió la
  confirmación normal y verificó reproducción real mediante
  `yt-dlp` + `mpv` en 5,85 s. Al cerrar el core no quedó `mpv`, `yt-dlp` ni
  Edge; Spotify siguió limitado a su launcher preexistente. La postlectura de
  audio confirmó exactamente 3 % y sin mute. Cobertura: 144/168 ejercitadas,
  131 con éxito verificado.
- 04:02 — `streaming.play.named` llegó a Netflix con un título sintético de
  prueba, siguió la confirmación y falló explícitamente con
  `netflix_authentication_required`, el resultado correcto para el perfil CDP
  aislado sin sesión. No se intentó iniciar sesión; Edge y el perfil se
  eliminaron. Cobertura funcional: 145/168. El soak continúa con 803 llamadas,
  cero anomalías y recursos en su rango estable.
- 04:03 — La radio Bluetooth estaba activa; BAXY recibió el mismo estado
  (`true`) y aprobó con postlectura de Windows, `changed:false` y una radio.
  El adaptador siguió `OK`, por lo que la prueba no desconectó ni alteró ningún
  dispositivo. Cobertura: 146/168 ejercitadas, 132 con éxito verificado.
- 04:04 — `filesystem.file.open.latest` seleccionó exactamente un TXT
  sintético recién creado en Descargas, abrió Bloc de notas y devolvió
  `completed/verified:true`. Windows transfirió después la ventana del PID
  bootstrap al proceso UWP real; se cerraron ambos por PID/título exactos.
  El TXT fue eliminado y una postlectura confirmó archivo ausente y cero
  Notepad. Cobertura: 147/168 ejercitadas, 133 con éxito verificado.
- 04:09 — Iniciado un segundo soak, sin efectos, contra `turn.decide` y
  `plan` del modelo Gemma real hasta las 12:52. Alterna conversación, acciones
  simples y cuatro planes, puntúa conservación de intención, mide latencia y
  reinicia el worker cada dos horas. La prueba corta previa aprobó protocolo y
  limpieza; el proceso largo inició con una decisión correcta y seis procesos
  aislados (2,18 GiB RSS agregados). Ninguna decisión de este soak se ejecuta.
- 04:14 — Revalidación de actualización e integridad: HEAD local y punta
  directa de `origin/codex/baxy-rebuild-v3` siguen en
  `f23b23f064211154e954d82883ba6bee5c2c466c`; la instalación activa sigue en
  1.0.8 y 36/36 entradas de `SHA256SUMS` coinciden, sin faltantes.
- 04:18 — Recuperación de protocolo instalada: 11/11 tramas malformadas
  (vacía, truncada, valores JSON no objeto, tipo desconocido, campos ausentes,
  NUL escapado y una línea de 66.001 bytes) fueron rechazadas con
  `protocol.error`. Tras cada una, `system.time` aprobó con identidad exacta:
  11/11 recuperaciones, salida cero, sin root residual.
- 04:22 — Primera vuelta completa del soak LLM: 4/13 decisiones conservaron
  exactamente la intención y 9/13 no, sin anomalías de proceso/protocolo.
  Los cuatro planes fallaron: navegador omitió `browser.page.read`; captura +
  OCR, volumen + postestado y Spotify exacto + pausa acabaron en aclaración sin
  pasos. Refuerza `BAXY-AUD-023`; no se ejecutó ninguna propuesta. El soak del
  core alcanzó 1.024 llamadas y 90 min, aún con cero anomalías.
- 04:25 — `game.install.named` sobre un título ya instalado siguió la
  confirmación, resolvió AppID 420 y devolvió `already_installed` desde el
  manifest local. El PID y hora de inicio de Steam no cambiaron; no se abrió
  diálogo, juego ni descarga. Cobertura: 148/168 ejercitadas, 134 con éxito
  verificado; las 20 restantes conservan exclusión explícita por riesgo.
- 04:27 — `filesystem.known.trash.named` movió un TXT sintético único de
  Descargas a la papelera privada aislada, verificó ausencia y publicó un hash
  correcto. El arnés lo restauró desde ese recibo, confirmó el mismo hash,
  eliminó la copia privada y después borró exactamente el marcador. Cero roots
  residuales. Cobertura: 149/168 ejercitadas, 135 con éxito verificado.
- 04:52 — Primer corte de dos horas del soak del core: PID 22520 salió con
  código cero y stderr vacío; PID 28764 arrancó en el mismo perfil aislado,
  publicó nuevamente 168 operaciones y continuó. 1.371 llamadas, cero
  anomalías. RSS regresó de ~52 MiB a 38,64 MiB al iniciar el segmento 2,
  sin proceso ni lock residual del segmento 1.
- 04:53 — Segunda ráfaga JSONL con Gemma cargada: 240/240 consultas
  `completed/verified:true`, sin pérdida, duplicación o cruce de identidad.
  20,54 respuestas/s frente a 20,92 sin el soak LLM (−1,8 %), diferencia
  pequeña; el core de la ráfaga salió cero y el core largo continuó intacto.
- 05:52 — Soak del core supera tres horas: 2.063 llamadas, dos segmentos,
  cero anomalías, 56,1 MiB RSS y 27,3 MiB privados. El soak LLM alcanza
  103 decisiones en 102,5 min: 39/103 intenciones exactas (37,9 %), cero
  anomalías de protocolo, 6,05 s de latencia media y 14,05 s máxima.
- 06:10 — Primer corte de dos horas del soak LLM: worker 15168 salió cero,
  stderr vacío y sin descendientes; worker 1860 inició un servidor CUDA nuevo
  (PID 20600), reconfiguró las 168 operaciones y continuó. 121 decisiones:
  46 exactas, 75 incorrectas, cero anomalías de protocolo. El soak del core va
  por 2.262 llamadas y 3,32 h, también sin anomalías.
- 06:53 — Segundo corte del core / cuatro horas: PID 28764 salió cero, stderr
  vacío; PID 20656 reabrió el mismo journal y continuó. 2.750 llamadas, tres
  segmentos y cero anomalías. El arranque con 2.750 identidades retenidas usa
  56,48 MiB RSS frente a 35,12 MiB con journal vacío. Es crecimiento
  deliberado de replay exacto, acotado por el límite documentado de 64 MiB y
  rechazo fail-closed; se conserva como métrica, no como defecto.
- 07:52 — El soak del core supera cinco horas: 3.422 solicitudes, tres
  segmentos y cero anomalías. El soak LLM suma 223 decisiones: 84 conservaron
  la intención exacta y 139 no (37,7 % de acierto), sin fallos de proceso o
  protocolo. La repetición prolongada confirma `BAXY-AUD-023`; no se ejecutó
  ninguna propuesta del modelo.
- 07:53 — El registro Application de Windows no contiene eventos críticos,
  errores ni advertencias relacionados con BAXY, `baxy-core`, `Baxy.App`,
  `llama-server`, .NET Runtime, Application Error o WER desde el comienzo de
  la auditoría.
- 08:10 — Segundo corte de dos horas del soak LLM: worker 1860 salió con
  código cero, stderr vacío y sin descendientes. Worker 3884 levantó un
  `llama-server` CUDA nuevo (PID 17168), reconfiguró las 168 operaciones y
  retomó el ciclo. 241 decisiones: 91 exactas, 150 incorrectas y cero
  anomalías de protocolo.
- 08:12 — Arranque de la UI instalada bajo carga simultánea de core y Gemma:
  20/20 ciclos mostraron ventana visible, observaron su hijo `baxy-core` y
  cerraron limpiamente con código cero, sin hijos ni roots aislados residuales.
  Tiempo a ventana: 1,215 s de media, 1,540 s máximo (frente a 1,038 s y
  1,124 s en los diez arranques previos sin esta presión).
- 08:14 — Ráfaga concurrente extendida: 1.200/1.200 solicitudes de solo
  lectura terminaron `completed/verified:true` en 60,69 s (19,77 respuestas/s),
  sin pérdidas, duplicados, cruces de identidad, errores de escritor/lector,
  stderr ni root residual. El core largo siguió en paralelo con 3.667 llamadas
  y cero anomalías.
- 08:15 — Arranque paralelo del core instalado: tres rondas de 12 instancias
  simultáneas (36/36) publicaron las 168 operaciones, respondieron
  `system.time` con identidad exacta y salieron cero. Hello medio 0,828 s,
  máximo 0,898 s; respuesta verificada media 0,904 s, máximo 0,967 s. No hubo
  locks, contaminación cruzada, stderr, procesos ni roots residuales.
- 08:17 — Trazabilidad del backlog validada: 27/27 defectos tienen sección de
  evidencia y sus 103 referencias de evidencia resuelven a artefactos
  presentes (incluido el rango abreviado de reproducciones 3–7 de Bloc de
  notas). No hay defectos huérfanos ni archivos citados ausentes.
- 08:24 — Recuperación tras caída abrupta: 20/20 perfiles aislados confirmaron
  una respuesta comprometida, encolaron solicitudes concurrentemente y
  terminaron el core por fuerza antes de recibir respuestas de la cola. En
  20/20 reinicios el catálogo volvió con 168 operaciones, la identidad
  comprometida fue recuperada con `replayed:true`, una sonda posterior aprobó
  y el proceso recuperado salió cero. Sin corrupción ni roots residuales.
- 08:25 — Control de calidad intermedio: 139/139 archivos JSON de evidencia
  parsean correctamente, los 39 scripts Python del directorio de auditoría
  compilan y `git diff --check` no encuentra errores de whitespace.
- 08:52 — Tercer corte del core / seis horas: PID 20656 salió con código cero
  y stderr vacío; PID 2284 reabrió el journal, publicó el catálogo y continuó.
  4.100 solicitudes, cuatro segmentos y cero anomalías. El perfil ocupa
  7,69 MB; la nueva instancia arrancó con 47,45 MiB RSS y 28,63 MiB privados.
- 08:56 — Ráfaga máxima: 5.000/5.000 respuestas
  `completed/verified:true` en 236,65 s (21,13 respuestas/s), sin pérdidas,
  duplicados, cruces de identidad, errores de lectura/escritura, stderr ni
  root residual. Los soaks largos siguieron en paralelo sin anomalías.
- 08:58 — UI instalada aislada bajo los dos soaks: recibió físicamente
  `¿Qué hora es?`, pero respondió «No pude formular una respuesta segura…» y
  no invocó `system.time`. Reproduce `BAXY-AUD-007` con una tercera salida
  incorrecta. La UI cerró de forma ordenada, sus tres hijos terminaron y el
  root fue eliminado; el portapapeles quedó restaurado por el arnés.
- 09:01 — Fuzzing de recuperación JSONL: 500/500 entradas adversarias fueron
  rechazadas de forma controlada (464 `malformed_json`, 36
  `invalid_message_size`) y las 500 solicitudes válidas inmediatamente
  posteriores aprobaron con identidad exacta. Salida cero, stderr vacío y sin
  root residual.
- 09:12 — Stress visual extendido: una sonda inicial de 100 ciclos vio 99/100
  hijos core al muestrear solo 0,5 s después de la ventana. La repetición
  diagnóstica, con observación de hasta 5 s, aprobó 200/200: hijo observado en
  1,465 s de media, p95 1,661 s, máximo 1,963 s; cierre cero y sin procesos o
  roots residuales. Se clasifica como carrera del arnés, no defecto de BAXY.
- 09:53 — Soak del core supera siete horas: 4.793 llamadas, cuatro segmentos y
  cero anomalías. El soak LLM suma 343 decisiones, 137 exactas y 206
  incorrectas (39,9 %); latencia media 5,931 s, p95 11,067 s y máximo
  15,461 s, sin anomalías de proceso/protocolo.
- 10:11 — Tercer corte de dos horas del soak LLM: worker 3884 salió cero, con
  stderr vacío y sin descendientes; worker 4132 configuró nuevamente las 168
  operaciones y continuó. 361 decisiones (144 exactas, 217 incorrectas), cero
  anomalías. El core largo alcanzó 4.994 llamadas, también limpio.
- 10:52 — Cuarto corte del core / ocho horas: PID 2284 salió cero y con stderr
  vacío; PID 468 reabrió el journal y continuó. 5.467 solicitudes, cinco
  segmentos y cero anomalías. El perfil ocupa 10,26 MB; el nuevo core arrancó
  con 53,66 MiB RSS, 32,04 MiB privados y 405 handles.
- 10:55 — Segunda suite Python completa, ahora bajo ambos soaks: 611 pruebas y
  350 subtests aprobados en 153,23 s, cero fallos. No apareció flakiness ni
  interferencia tras ocho horas de ejecución.
- 11:00 — Segunda suite .NET completa, serial y bajo ambos soaks: 2.080 casos,
  2.063 aprobados, 17 omitidos y cero fallos. Coincide exactamente con la
  corrida serial inicial; no apareció flakiness tras ocho horas.
- 11:53 — Soak del core supera nueve horas: 6.151 llamadas, cinco segmentos y
  cero anomalías. El soak LLM suma 463 decisiones: 182 exactas y 281
  incorrectas (39,3 %), cuatro segmentos y cero anomalías de
  proceso/protocolo.
- 12:11 — Cuarto corte de dos horas del soak LLM: worker 4132 salió cero, con
  stderr vacío y sin descendientes; worker 12588 configuró las 168 operaciones
  y continuó. 481 decisiones (189 exactas, 292 incorrectas), cinco segmentos
  y cero anomalías. El core largo alcanzó 6.360 llamadas, también limpio.
- 12:52 — Cierre exacto de la ventana de doce horas. El soak del core completó
  10,019 h, 6.826 llamadas sobre 26 operaciones, seis segmentos y cero
  anomalías/finalError. Hubo 6.442 respuestas `completed`; los 384 fallos
  fueron ambientales esperados (`media_session_not_found` 373 y
  `outlook_profile_not_configured` 11). Latencia ponderada 0,347 s y máxima
  10,687 s; RSS 35,12–74,59 MiB, privados 16,18–42,84 MiB.
- 12:52 — El soak LLM completó 8,713 h, 522 decisiones y cinco segmentos, con
  todos los workers cerrados en cero, stderr vacío, sin descendientes, cero
  anomalías/finalError. Conservó 205/522 intenciones (39,27 %); 317 fallaron
  semánticamente. Latencia media 5,998 s, p95 11,138 s y máxima 15,461 s.
  Refuerza `BAXY-AUD-023`.
- 12:52 — Limpieza automática verificada: no quedan roots `audit-*`, procesos
  BAXY/core/llama/browser/Bloc de notas/multimedia creados por la auditoría, ni
  hijos de los soaks. Steam, SpotifyLauncher y Configuración preexistentes
  conservan sus PID y hora de inicio.
- 12:55 — Integridad final: HEAD y la rama remota siguen en
  `f23b23f064211154e954d82883ba6bee5c2c466c`; la instalación activa sigue en
  1.0.8 y 36/36 entradas de `SHA256SUMS` coinciden, sin ausentes ni cambios.
- 12:56 — Estado final del equipo: audio de salida 3 % y activo, micrófono
  activo, brillo 0, batería 98 % en corriente. El registro Application de
  Windows conserva cero eventos críticos/errores/advertencias relacionados
  con BAXY, core, .NET, llama-server o WER durante toda la ventana.
- 12:57 — Validación de entrega: 152/152 JSON parsean, 41/41 scripts Python
  compilan, 27/27 defectos conservan sus 106 referencias de evidencia y no
  falta ninguna; `git diff --check` aprueba.
