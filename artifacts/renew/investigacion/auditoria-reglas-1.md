# Auditoría de reglas 1: todo baxy-renew (2026-10-15, notebook, sólo lectura)

La hicieron agentes de auditoría contra las `<reglas>` del goal y la identidad. El detalle, con archivo:líneas, cita
y arreglo mínimo de cada hallazgo, está en dos informes:

- `auditoria-reglas-kernel-providers.md`: Kernel, Core, Contracts, Providers.Windows y la mente con sus datos.
- `auditoria-reglas-app.md`: Baxy.App y FieldUi, auditados en el commit `b33a3e62d`.

**Lo que es honestidad permitida y se queda:**

- el catálogo tipado;
- el riesgo y la confirmación del kernel, incluido que `RiskPolicy` y `WorldActs` lean el rótulo exacto del clic;
- el journal;
- la verificación de los proveedores (post-lecturas, `SearchPageReader` sólo con direcciones públicas);
- el enmascarado de datos sensibles;
- los botones Sí/No;
- la pausa del latido mientras la persona juega o la GPU está ocupada (decisión del dueño).

## Recuento

| Parte | Violaciones | Zona gris | Permitido (se queda) | Código muerto o apilado |
|---|---|---|---|---|
| Kernel, Core y Contracts | 7 | 5 | 6 | 14 |
| Ruta `web.search` | 13 | 7 | 5 | 1 |
| Otros providers | 19 | 20 | 9 | 2 bloques grandes |
| Mente y datos | 0 | 3 | 2 | 3 |
| App y FieldUi | 16 | 16 | 15 | ~1077 líneas (inventario en `app-codigo-muerto.md`) |
| **Total** | **55** | **51** | **37** | — |

## Lo más grave, por regla

### Regla 3: la ventana de la persona y sus datos

1. **Las operaciones de entrada actúan en la ventana que la persona tiene al frente.** Es el caso de `input.*` sin
   `window`, `clipboard.copy` y `clipboard.paste`, `input.pointer.control` (hace clic donde esté el cursor),
   `input.select.all` e `input.keyboard.layout`. Un clic por rótulo sin ventana atada también va al frente.
   - Ninguna ruta comprueba que la ventana sea de BAXY: `LaunchProvenance` sólo lo consulta `app.close`.
   - Al modelo nunca le llega el hwnd de la vista, porque lo quitan `ScreenViewProjection` y `OperationVisibleFacts`.
   - `DesktopMessagingAdapter` selecciona todo y borra el borrador del chat que la persona tenía abierto.
   - Discord escribe Ctrl+K en la primera ventana `Chrome_WidgetWin_1` cuyo título diga «Discord», que puede ser el
     navegador de la persona.
   - **Arreglo:** una sola compuerta. Toda operación que actúa exige `window`, y su raíz tiene que ser una ventana
     que BAXY lanzó en la sesión (`LaunchProvenance`); si no, se rechaza antes de cualquier efecto.
2. **Se actúa en el navegador de la persona.** `browser.control` (atrás, recargar, cerrar hasta 50 pestañas) y
   `PagePlay` (escribe en el buscador de Disney+ o HBO, y elige con listas de palabras) lo hacen sin pedir nada.
3. **Las capturas pueden salir del equipo.** `CaptureVisionAdapter` y `WindowsVisibleVisionLocator` mandan la captura
   a un HTTPS remoto con una clave.
   - Hoy están apagados sólo porque falta `BAXY_VISION_ENDPOINT`, y además rechazan un modelo local en loopback.
   - **Arreglo:** borrarlos o aceptar sólo loopback.
4. **`nearby` sale por la red.** Pregunta la ciudad por IP a `ipwho.is` y a `http://ip-api.com` en HTTP plano, y
   añade la ciudad a la consulta (zona gris).

### Regla 1: el código que interpreta o sustituye

5. **`web.search` decide por la persona y por el modelo.**
   - Enruta según listas de palabras: divisas, deportes, lugares, enciclopedia, recetas y noticias.
   - Reescribe «este año» y juzga la pertinencia con `SearchPertinence`, `FigureWords` y `WeatherSynonyms`.
   - `answerWords`, `answerWordsNot` y `listing` llegan al modelo sin descripción.
   - **Arreglo:** devolver los resultados de la fuente tal cual, con argumentos tipados si hace falta elegir fuente,
     y que el modelo lea páginas con `web.fetch`.
6. **Se cambia lo que el modelo nombró por algo parecido.**
   - `app.open` resuelve por Levenshtein: «Motion» abre Notion.
   - El rótulo del clic pasa por alias y subcadenas: «ok» vale para «Aceptar» y encaja en «Bookmarks».
   - Destinatarios, red Wi-Fi, juego («Portal» por «Portal 2»), zona horaria (por población) y volumen por app
     resuelven por subcadena.
   - Los colores se traducen por diccionario, y `web.download` baja la `og:image` en vez de la página.
   - **Arreglo:** coincidencia exacta tras plegar mayúsculas y tildes. Si no coincide, se devuelven los candidatos
     al modelo.
7. **`ScreenStateLines` reescribe la pantalla** («Ethernet: Conectado») con una lista bilingüe de estados.

### Regla 2: honestidad

8. **`routine.*` nunca se ejecuta**, porque nadie lee `on_phrase`, pero la descripción promete que sí.
9. **Los resultados dan por hecho lo que no se comprobó.**
   - `winget` cuenta «instalando» como éxito verificado.
   - El `toggle` de Spotify siempre dice `paused`.
   - OCR informa `selected` cuando nada se seleccionó.
   - Un error después de pulsar se cuenta como «nada pasó», y la cascada puede pulsar otra vez.
10. **`WindowsInventoryAdapter` tapa fallos reales** con fallos enlatados. Es un duplicado: se borra.
11. **App: el modelo puede aprobar su propia llamada de riesgo.**
    - `confirm_pending` se acepta en cualquier paso, también dentro de un latido.
    - **Arreglo:** sólo desde un turno que la persona abrió después de la pregunta, o desde los botones Sí/No.
12. **App: cuatro herramientas de memoria fallan siempre.** `memory.enable`, `memory.disable`,
    `memory.sensitive.save` y `memory.session.clear` caen por una comprobación que dejó el analizador viejo.
13. **App: la interfaz muestra datos que nadie observó.**
    - El contexto aparece como 12288 en vez de 49 152: la App lee `BAXY_MIND_CTX` y la mente usa
      `BAXY_RENEW_CTX`.
    - Los modelos de voz figuran como «descargados» si hay micrófono.
    - El «/ 4k» de tokens no corresponde a nada que se envíe.
14. **Arreglado en este notebook.** El aviso de `schedule.alarms` no mostraba texto en Windows 11 Home (no existe
    `msg.exe`) y escribía su recibo antes de sonar. Commit `1f2f33fd8`.

### Regla 4: código muerto y capas apiladas

15. **`OperationVisibleFacts` le quita al modelo `noteId`, `deviceId`, `sha256`, el hwnd y el `processId`**, así que
    hay argumentos que nunca puede llenar.
16. **Catorce operaciones públicas están ocultas sólo por el prefijo «Paso interno»** en `mind.py`. Por eso
    `message.send` y `filesystem.trash.restore` son inalcanzables, y no hay ninguna herramienta para instalar
    programas.
17. **Código muerto:** la misión de pantalla, `MissionPlanValidator` (que dicta el orden de los pasos),
    `HonestyCorrection`, `MissionFrontSignal` (sin llamadores), siete mecanismos de primer plano solapados, el panel
    de ajustes heredado de Gemma 4 y unas 1077 líneas de la App.
18. **Variables de entorno:** la App fija siete que la mente no lee, y ninguna de las `BAXY_RENEW_*`.

## Reparto propuesto para arreglar

| Quién | Qué |
|---|---|
| NB | Los proveedores fuera de computer use: la ruta `web.search` (W1-W21), la resolución exacta por nombre (Wi-Fi, juego, zona horaria, volumen por app, navegador, diff), colores, `web.download`, `routine.*`, winget, Spotify, `WindowsInventoryAdapter`, la visión remota y `nearby`. |
| PC | Lo que toca computer use y la App: la compuerta de ventana propia en la entrada, el hwnd en la vista, rótulos y alias, `browser.control` y `PagePlay`, mensajería, `confirm_pending`, memoria, interfaz, variables de entorno, «Paso interno» y el código muerto de la App. |
