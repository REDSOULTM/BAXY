# Auditoría final independiente del notebook (sólo lectura)

Código auditado: `hub/baxy-renew` en `bde62d76c` (congelado a las 15:33), en una copia aparte. Cinco agentes, uno por
área, con las mismas reglas y el mismo formato: R1 sin ayudas al modelo en código, R2 honestidad de los recibos,
R3 nada del dueño sale y nunca en su ventana, R4 cero código muerto o apilado, R5 confirmación del dueño. Cada
hallazgo cita líneas que el agente leyó; los más graves se releyeron. Sirve para cruzar con la ronda final del líder,
que en paralelo ya está arreglando lo suyo.

| Área | Violaciones | Zonas grises | Muerto | Permitido-dudoso |
|---|---|---|---|---|
| Kernel, Core, Contracts, Security | 5 | 8 | 8 | 2 |
| Computer use, apps y ventanas | 9 | 7 | 6 | 6 (con permitidos) |
| Otros proveedores | 15 | 20 | 12 | 2 |
| App, FieldUi, Setup | 8 | 17 | 12 | 3 |
| Mente, datos y jueces de los bancos | 1 | 7 | 8 | 3 |

**Un hallazgo es del propio notebook** (verificado): `WindowsKnownFileAdapter.Locate` reduce una ruta completa a un
archivo de la raíz de la carpeta a su nombre suelto y lo busca en subcarpetas (`0075c505f`). Arreglo de tres líneas
propuesto al líder; el código está congelado.

## Kernel, Core, Contracts y Security


Copia congelada `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew-audit` (bde62d76c), sólo lectura. Rutas relativas a `src/`. Para comprobar si algo se usa o qué hace el proveedor se leyeron también Baxy.App, Baxy.Providers.Windows y baxy_mind, pero los hallazgos son de mi área.

Hechos de partida, verificados en el código:
- El catálogo tiene 184 operaciones: 175 `Public` y 9 `Internal`. La mente recibe sólo las públicas (`ProductCatalog.ToolDescriptors`, OperationRegistry.cs:34-43 y Program.cs:379). La exposición ya la decide `ToolExposure`, no el prefijo «Paso interno».
- Lo que el modelo lee de cada herramienta es la descripción inglesa de `tool_descriptions.en.v1.json`; si no hay, la española, y si tampoco, la del catálogo (mind.py:269-270). Ninguna de las herramientas de entrada (`input.*`) tiene descripción por argumento.
- Mapa de riesgo (ProductCatalog.cs:2202-2214 y RiskPolicy.cs:78-90). `read_only`, `low_reversible`, `recoverable_delete` y `privacy_sensitive` pasan sin preguntar. `external_communication` pregunta sólo para `message.send`, `message.send.test`, `email.send` y `email.latest.reply`. `work_loss`, `session_disruption`, `monetary` e `installation` preguntan.

### Hallazgos

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| 1 | Baxy.Kernel/Policy/RiskPolicy.cs:62-67; ProductCatalog.cs:1597-1603; Providers WindowsPowerTransitionAdapter.cs:37-40 | R5, R2 | `if (string.Equals(operation, "system.power", …)) return PolicyDecision.Allow;`. Así, cerrar sesión (`ExitWindowsLogoff \| ExitWindowsForceIfHung`), reiniciar y apagar cierran todas las apps del dueño sin preguntarle. Las descripciones dicen lo contrario: la del catálogo, «Solicita una transición **confirmada**», y la inglesa, «… restart the PC, **with confirmation**». | violación | Quitar el atajo de 64-67 para que `work_loss` pregunte. Como mucho, dejar directo sólo `lock` y `sleep`, que no cierran nada, leyendo el argumento `action`. |
| 2 | RiskPolicy.cs:170-175; ProductCatalog.cs:873-882, 891; tool_descriptions.en.v1.json (`input.key.press`: no menciona `target` ni `onto` y no tiene `arguments`) | R5 | `return KeyOf(arguments) is "enter" or "space" && (TargetOf(arguments) is "message_composer" \|\| LabelReachesAPerson(OntoOf(arguments)));`. Que se pida confirmación depende de que **el modelo** declare `target`/`onto`, y nadie le explica esos argumentos. Los comentarios dicen que los llenaba «la mente desde el control enfocado» (171-172) o «la misión» (873-876), y ninguna de las dos existe ya. Basta `message.draft` y luego `input.key.press{key:"enter"}` para que el mensaje llegue a otra persona sin el sí del dueño (era K8, **sigue presente**). | violación | Fallar cerrado: Enter o Espacio preguntan salvo que el proveedor lea en el control enfocado que no es un campo de mensaje. El riesgo se decide por lo observado, no por el rótulo del modelo. |
| 3 | Baxy.Core/Operations/WindowControlHandlers.cs:74-84; MissionEngine.cs:272-293 | R5 | `provider.HoldsNoDocument(windowId) ? OperationRisk.Reversible : null`. Si la ventana es de una app «sin documento» (documentless_applications.v1.json) o de una app «cuyo contenido vive en la cuenta», `app.close` deja de preguntar. Así se cierra sin confirmar una app que el dueño abrió (Configuración, Calculadora, un cliente de cuenta). | violación | Bajar el riesgo sólo para una ventana que BAXY lanzó y en la que no escribió (`LaunchProvenance`). Toda otra ventana del dueño sigue con `work_loss`. |
| 4 | ProductCatalog.cs:617-620 (+2205), 1155-1158, 1218-1221, 1974-1977, más las mismas frases en tool_descriptions.en.v1.json | R2 | Descripciones que prometen una confirmación que la política no pide: `filesystem.known.trash.named` «después de confirmar» / «after confirmation» (es `recoverable_delete`, que se trata como `Reversible` y no pregunta); `memory.enable` «con confirmación explícita»; `memory.sensitive.save` «después de confirmación»; `wifi.radio.set` «con confirmación de la persona». Las tres últimas son `privacy_sensitive`, que pasa directo (RiskPolicy.cs:84), y ningún handler pregunta por su cuenta. | violación | Quitar «después de confirmar» de esas descripciones. Mandar a la Papelera sin preguntar cumple R5. Si el dueño quiere confirmación para alguna, cambiarle el riesgo. |
| 5 | ProductCatalog.cs:217-231, 244-250 vs Providers WebBrowserAdapter.cs:171-177, 207-215, 236-240 | R2 | `browser.control` dice «Controla la pagina CDP actual», `browser.navigate` «sesión CDP autenticada» y `browser.page.read` «la pagina CDP activa». El proveedor actúa primero en el **navegador propio de la persona**: `if (_userBrowser?.Resolve() is { } userBrowser) return await _userBrowser.ControlAsync(…)`, y cierra o recorre sus pestañas reales. | violación | Que la descripción diga qué navegador se toca (el predeterminado de la persona; el CDP sólo si no hay ninguno). |
| 6 | ProductCatalog.cs:1276-1287 (`message.send`), 707-713 (`filesystem.trash.restore`); Providers DesktopMessagingAdapter.cs:162-170, 186-190 | R4, R2 | Son públicas, pero el id que piden sólo lo emite una operación interna que nadie llama: `recipientId` sale del diccionario en memoria de `message.recipient.resolve`, y `restoreId` sale de `filesystem.trash.commit`. Nunca pueden tener éxito. La descripción inglesa igual le ofrece al modelo «Send a message to an already identified contact». | muerto | Borrarlas (con su rama de proveedor), o hacer pública la resolución. Hoy el envío real de mensajes no existe en el producto, y la descripción no debe sugerir que sí. |
| 7 | ProductCatalog.cs:589-595, 688-706, 756-762, 776-782, 809-827, 1263-1275, 1763-1774; Core FilesystemHandlers.cs:19, 24-25, 66-67, 82-87; ExternalCapabilityHandlers.cs:51, 53, 57-58, 76; TaskHandlers.cs:17, 227-250; Providers SteamLocalAdapter / DesktopMessagingAdapter / WindowsExternalCapabilityProvider | R4 | Las 9 operaciones `ToolExposure.Internal` (`filesystem.hash`, `filesystem.trash.prepare/commit`, `game.install.prepare/commit`, `game.purchase.prepare/commit`, `message.recipient.resolve`, `task.resolve.exact`) no las invoca nadie: ni la App, ni la mente, ni otro handler. Sólo existen su handler y su proveedor. Además repiten mecanismos que ya existen: `filesystem.known.trash.named` y `game.install.named`. | muerto | Borrar las 9 operaciones, sus handlers y sus ramas de proveedor. `ValidateAgainst` (ProductCatalog.cs:2182-2200) ya obliga a quitarlas juntas. |
| 8 | RiskPolicy.cs:38-44, 85-87; ProductCatalog.cs:268-280; Providers MicrosoftAccountAdapter.cs:132, 146-148 | R5 | `calendar.event.create` es `external_communication`, pero no está en `ExternalRequiringConfirmation`, así que pasa sin preguntar. Crea el evento en el Outlook del dueño, que lo sincroniza con su cuenta: es un envío a un servicio externo sin confirmación. `email.send`, que sigue el mismo camino, sí pregunta. | zona gris | Añadir `calendar.event.create` a `ExternalRequiringConfirmation`, o que el dueño lo declare permitido por escrito. |
| 9 | ProductCatalog.cs:860-864, 869, 891; tool_descriptions.en.v1.json `input.key.press` («safe shortcut … Ctrl+S/Z/F/T/W») | R5, R4 | El comentario afirma que ninguno de esos atajos «cierra una ventana ni un proceso: cerrar una pestaña deja el navegador abierto». No es cierto para `ctrl_w`: en el Explorador, en muchas apps y en la última pestaña de Chromium cierra la ventana del dueño. RiskPolicy no lo mira y `window` es opcional, así que va a la ventana del frente. | zona gris | Pedir confirmación para `ctrl_w` en RiskPolicy, o quitarlo del enum y corregir el comentario. |
| 10 | Kernel/Operations/OperationVisibleFacts.cs:386-394 | R2 | `element.EnumerateArray().Take(ocrObservation ? int.MaxValue : processInventory ? 50 : 20)` recorta en silencio cualquier lista a 20, sin marcar `truncated` (la proyección por tamaño, 248-276, sí lo marca). El modelo puede pedir `limit` 50 o 100 (`file.find` 473, `filesystem.list` 625, `note.list` 1356, `game.catalog.list` 718, `network.port.list` 1328, `window.resolve` 2080), y lo observado le llega cortado sin aviso. | zona gris | Al recortar, poner `truncated:true` y `<lista>Count`, como hace `Project`, o no recortar por debajo del `limit` que se pidió. |
| 11 | RiskPolicy.cs:165-178; Providers WindowsDesktopInteractionAdapter.cs:418-420 | R5 | RiskPolicy no evalúa `input.text.type`, y el proveedor sólo rechaza caracteres de control cuando hay `window`: `(typing && window != 0 && text.Any(char.IsControl))`. Sin `window`, un texto con `\r` o `\n` se teclea en el campo con foco, y en un chat eso puede enviar el mensaje sin confirmación. | zona gris | Rechazar los caracteres de control también sin `window`. Un salto de línea que envía es una tecla, y debe pasar por `input.key.press`. |
| 12 | ProductCatalog.cs:847-850, 873-882, 962-965, 999-1000, 1040-1061; RiskPolicy.cs:171-172, 196-198; Providers WindowsDesktopInteractionAdapter.cs:398-408 | R4 | Quedan argumentos y comentarios de la misión retirada (K9 sólo se arregló a medias: salieron `collapse` y `dismiss`). En `input.text.type`, `field` «la misión lo resuelve a su índice» ya no lo resuelve nadie: el proveedor sólo hace `if (fieldNamed && index is null) → input_field_not_found`. `consequence`, `onto` y `target` («lo marca la misión») no se le describen al modelo. A `wanted`, `windows` y `tail` de `input.visible.controls` les pasa lo mismo. | zona gris | Quitar `field` y corregir los comentarios. Los argumentos que decide RiskPolicy deben salir de lo observado (ver #2) o describírsele al modelo. |
| 13 | baxy_mind/mind.py:269-270; ProductCatalog `Description`; decider_catalog.es.v1.json | R4 | Siguen tres fuentes de descripción apiladas (K11): inglesa, luego española y luego la del catálogo. La española no tiene `input.scroll`. Por eso las descripciones del catálogo (#1, #4, #5) pueden desfasarse sin que nadie lo vea. | zona gris | Una sola fuente de descripción. |
| 14 | ProductCatalog.cs:325-338, 946-952 vs 868-869; Core Program.cs:141-144; ProductCatalog.cs:1880-1891 vs 1913-1916 | R4 | Mecanismos dobles para lo mismo. `clipboard.copy`, `clipboard.paste` e `input.select.all` hacen lo mismo que `input.key.press` con `ctrl_c`, `ctrl_v` y `ctrl_a`. El volumen general va por dos proveedores: `AudioVolumeHandler` (con su invocation store) y `ExternalCapabilityHandler("audio.volume.adjust")` (WindowsAudioAdjustmentAdapter). Hay noticias en `web.news.headlines` y en `web.search{source:"news"}`. | zona gris | Dejar un solo camino en cada caso. |
| 15 | ProductCatalog.cs:1288-1300; RiskPolicy.cs:41 | R4 | Sigue `message.send.test` (K12), una operación de banco de pruebas dentro del catálogo público. Envía de verdad a los destinos de prueba del dueño. Confirma. | permitido-dudoso | Moverla al banco de pruebas, o que el dueño la ratifique. |
| 16 | Contracts/ProtocolContracts.cs:57-65, 82-83; BaxyJsonContext.cs:20; Kernel/Journal/JournalJsonContext.cs:15; (App OperationResponseProjection.cs:16-20) | R4 | Queda `HonestyCorrectionTrace` en el contrato aunque la capa HonestyCorrection del kernel se borró (K5). Ningún código de producto lo construye (`new HonestyCorrectionTrace` sólo aparece en tests/Baxy.Contracts.Tests/ProtocolContractTests.cs:455), así que la rama de la App que lo lee nunca corre. | muerto | Quitar el campo, su tipo, sus dos registros de serialización y la rama de la App. |
| 17 | Security.Windows/ProtectedJsonEnvelopeCodec.cs:8-15 vs Kernel/Mission/PrivateOperationBoundary.cs:37, 61, 112; Security.Windows/BoundProtectedJsonCodec.cs:17-18; Providers Memory/LocalMemoryStore.cs:33-35 | R4 | Las constantes `ProtectedPayloadPurposes` sólo las usa un test. El producto repite los mismos literales (`"memory.arguments.v1"`, `"memory.result.v1"`, `"memory.store.v1"`…) en cuatro sitios. | muerto | Usar `ProtectedPayloadPurposes` en esos cuatro sitios, o borrarla. |
| 18 | Security.Windows/IProtectedPayload.cs:11, 13; WindowsProtectedPayload.cs:119-160 | R4 | `SealUtf8` y `OpenUtf8` no los llama ningún código de producto, sólo los tests (ProtectedPayloadWindowsTests, LocalMemoryStoreTests). | muerto | Quitarlos de la interfaz y de la implementación. |
| 19 | Kernel/Journal/FileInvocationJournal.cs:153-196, 75, 91, 1458, 3086-3101; Mission/InMemoryConfirmationAuthority.cs:148; Mission/MissionEngineOptions.cs:19-23; Operations/ProductCatalog.cs:2129-2130 | R4 | Costuras que sólo usan los tests y que viven en el ensamblado de producto: `OpenWithCapacityForTestingAsync`, `OpenWithRotationForTestingAsync`, el `crashHook` con `JournalCommitStage`, `ActiveChallengeCount`, `MissionEngineOptions.ConfirmationAuthority` (su comentario lo admite: «Sólo la usan las pruebas») y `ProductCatalog.Descriptors` («only the catalog's tests»). Es lo que queda de D-K10 y D-K11. | muerto | Moverlas a los tests (subclase o fábrica de test), o aceptarlas por escrito como costuras de prueba. |
| 20 | Contracts/ApplicationCatalogContract.cs:14-46 vs GameCatalogContract.cs:14-46 | R4 | Dos `NormalizeName` idénticos línea por línea (comprobado con `diff`). | muerto (duplicado) | Uno solo, compartido. |
| 21 | baxy_mind/data/app_places.v1.json (en cada lugar: `names`, `said`, `shows`, `within`, `search`; `source` del encabezado); world_acts.v1.json:3 (`source`) y 69 (`examples`); Kernel/Operations/OperationVisibleFacts.cs:100-102 | R4 | Datos que el producto no lee: ApplicationPlaces.cs sólo lee `address`, `schemes`, `gameCatalog`, `acts` y `titles` (166-242). `names` son listas de frases con que la persona nombra un lugar, que leía la mente semántica. `examples` sólo lo leen los tests. Además hay textos obsoletos: los `source` dicen que también los lee «la mente (semantic/account_acts…, semantic/app_places…)», y en OperationVisibleFacts queda «the planner's projection». | muerto | Borrar los campos que nadie lee y corregir los `source` y el comentario. |
| 22 | Core/LegacyJournalMigration.cs:1-164; Core/Program.cs:338-348 | R4 | Sigue la migración del diario v1 previo al HMAC (D-K12). En un perfil con anchor o clave sale en la línea 30-33, y nadie lee `ArchivePath` ni `Sha256`. | zona gris | Borrarla si el dueño confirma que no queda ningún perfil v1. |
| 23 | RiskPolicy.cs:100-148 (`ShellMayChange`, `ReadingCommands`) | R5 | `shell.command.run` corre directo sólo si cada etapa del pipeline empieza con una orden de lectura de la lista y no hay `> < & ; \` { } $ ( ) [ ] @` ni saltos de línea. Todo lo demás pregunta con el comando exacto. Es fallar cerrado sobre el argumento exacto. | permitido | — |
| 24 | RiskPolicy.cs:186-219, 287-366; WorldActs.cs | R1, R5 | Regex de compra o borrado y palabras de «sale al mundo» sobre el rótulo exacto del clic. Es política de riesgo del kernel sobre argumentos. `input.key.press{key:"delete"}` pregunta salvo `target:"text_field"`, que el modelo puede declarar sin que nadie se lo explique (mismo patrón que #2, pero aquí falla cerrado). | permitido-dudoso | Igual que #2: que el «campo de texto» salga del control enfocado observado. |

### Estado de lo reportado antes en esta área

| Ítem anterior | Estado |
|---|---|
| K1 (enmascarado de `noteId`, `deviceId`, `sha256`) | **Arreglado**: OperationVisibleFacts.cs:345-376 sólo oculta `hwnd`, `handle`, `pid`, `processId`, `fingerprint`, `invocationId`, `requestId`, `missionId` y `token`. |
| K2 (operaciones «Paso interno») | **A medias**: la exposición ya va por `ToolExposure` y se añadió `package.install`. Quedan 9 operaciones Internal que nadie invoca y 2 públicas inalcanzables (#6, #7). |
| K3 (`mission.computer.use`) | **Arreglado** (no está en el catálogo ni en Core). |
| K4 (MissionPlanValidator) | **Arreglado** (ya no existe Baxy.Kernel/Planning). |
| K5 (HonestyCorrection) | **Arreglado en el kernel**; queda el campo en Contracts (#16). |
| K6 (`_consentedCaptures`) | **Arreglado**. |
| K7 (FirstSignal con lista de palabras) | **Arreglado** (no existe). |
| K8 (Enter según el rótulo que declara el modelo) | **Sigue presente** (#2). |
| K9 (argumentos de la misión) | **A medias** (#12). |
| K10 (`placeOpened`) | **Arreglado**: `PlaceRequested` (AppOpenHandler.cs:104-124). |
| K11 (tres fuentes de descripción) | **Sigue presente** (#13). `app.status` ya no existe. |
| K12 (`message.send.test`) | **Sigue presente** (#15). |
| D-K1 (overload de `Evaluate`, `WorldActOf`, `Joins`, `FamilyOf`) | **Arreglado**. |
| D-K2 (comentarios que citan la mente semántica) | **A medias**: los comentarios C# se corrigieron; los `source` de los JSON y los `examples`, no (#21). |
| D-K3 (`HasConversation`) | **Arreglado**. |
| D-K4 (rama `chatLines`) | **Arreglado**: `ChatLines` es ahora sólo la constante que usa el proveedor. |
| D-K5 (`Shortened` público) | **Arreglado** (privado). |
| D-K6 (dos narradores) | **Arreglado**. |
| D-K7 (`PublicFailureMessage`, `PublicSuccessMessage`) | **Arreglado**. |
| D-K8 (`PointingOperationsTypedArguments`, `provenance`) | **Arreglado**. |
| D-K9 (`app.status`) | **Arreglado**. |
| D-K10 (`Descriptors`, `AdditionalProperties`, `ActiveChallengeCount`) | **A medias**: `AdditionalProperties` se fue; quedan `Descriptors` y `ActiveChallengeCount`, sólo para tests (#19). |
| D-K11 (InMemoryInvocationJournal y costuras de test) | **A medias**: InMemoryInvocationJournal se fue; quedan las costuras (#19). |
| D-K12 (LegacyJournalMigration) | **Sigue presente** (#22). |
| D-K13 (`_ = StartedAt`, overload de `WriteMessageAsync`) | **Arreglado**: queda una sola `WriteMessageAsync` (Program.cs:461), y `_ = StartedAt` es intencional y está documentado (Program.cs:34-36). |
| D-K14 (196 Public / 1 Internal, decidido por un prefijo) | **Arreglado**: 175/9, y ahora se aplica de verdad. |
| P2 (visión remota) | **Arreglado**: CaptureVisionAdapter.cs:390 usa `LocalVisionEndpoint.TryResolve`. |
| W19 (ip-api por http) | **Arreglado**: PublicPlaceLocator.cs:30-34 va sólo por https. |

### Resumen

El kernel cumple R1: en Kernel, Core, Contracts y Security.Windows no hay código que interprete las palabras de la persona ni reescriba argumentos del modelo. Lo que queda es política de riesgo sobre argumentos exactos (`ShellMayChange`, las regex sobre el rótulo del clic, WorldActs). Casi todos los arreglos de la auditoría anterior están hechos: el enmascarado de ids, la exposición por `ToolExposure`, la misión de pantalla, el planificador, HonestyCorrection en el kernel, las capturas consentidas, FirstSignal y `placeRequested`. Los problemas serios que siguen están en la **confirmación de R5**:
- `system.power` se salta la política: cierra sesión, reinicia o apaga sin preguntar, y su descripción dice que confirma.
- Que un Enter en un chat pida confirmación depende de un argumento `target` que nadie le explica al modelo, así que un mensaje puede llegar a otra persona sin el sí del dueño.
- `app.close` deja de preguntar para apps del dueño «sin documento».
- `calendar.event.create` sale a la cuenta del dueño sin confirmar.
- `ctrl_w` se anuncia como un atajo seguro.

En R2, cuatro descripciones prometen una confirmación que no ocurre, y las de `browser.*` dicen «CDP» cuando el proveedor actúa en el navegador de la persona. Además, `Sanitize` recorta las listas a 20 sin avisar. En R4 quedan 9 operaciones internas que nadie invoca, 2 públicas inalcanzables (`message.send` y `filesystem.trash.restore`), el campo `HonestyCorrectionTrace`, API de Security.Windows que sólo usan los tests (`ProtectedPayloadPurposes`, `SealUtf8`/`OpenUtf8`), costuras de test en el journal y en el motor, normalizadores duplicados, datos JSON que nadie lee y tres fuentes de descripción apiladas.

## Computer use, apps y ventanas


Copia congelada `BAXY-Renew-audit` en `bde62d76c` (hub/baxy-renew). Todas las rutas son relativas a `src/Baxy.Providers.Windows/`, salvo que la ruta diga otra cosa. Cada fila se comprobó leyendo el código en esas líneas. Para el contexto de lo que ve el modelo se consultaron `ProductCatalog.cs` y `tool_descriptions.en.v1.json`, pero no se auditaron.

### Hallazgos

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| CU1 | External/WindowsDesktopInteractionAdapter.cs:130-137, 174-246; External/DesktopKeyPress.ps1:198, 208-219, 224-227, 228-232; External/DesktopSelectAll.ps1:149 | R3 | `clipboard.copy`, `clipboard.paste`, `input.select.all`, `input.pointer.control` e `input.keyboard.layout` no tienen argumento de ventana. El script actúa sobre `$before=[BaxyKeyInput]::GetForegroundWindow()`: Ctrl+C y Ctrl+V con `PressChord`, y `MouseAction(click)` «en su posición actual». `SetSpanishLayout($before…)` hace `PostMessage(WM_INPUTLANGCHANGEREQUEST)` a la ventana del frente. Ctrl+A va a `AutomationElement::FocusedElement`. El clic de puntero y el cambio de idioma ni siquiera esperan la pausa de la persona: el lease sólo se usa para copy, paste y select.all (227-229). Todas tienen riesgo LowReversible o PrivacySensitive, así que no piden confirmación. | violación | Exigir `window` (un hwnd que BAXY abrió o trajo como app objetivo) en las cinco. Sin él, `FailureBeforeEffect`. Borrar `input.pointer.control` «clic donde esté el cursor». |
| CU2 | External/WindowsDesktopInteractionAdapter.cs:370-375, 419-421, 512-519, 531-560 | R3 | En `input.key.press` e `input.text.type`, `window` es opcional. Con `window == 0` no se adquiere ningún burst ni se espera pausa: se ejecuta `accepted = _keyboard.PressChord(chord)` o `_keyboard.TypeText(text, KeepGoing)` sobre lo que esté delante. La única guarda es `_keyboard.Foreground().ProcessId == before.ProcessId`, es decir, seguir en la ventana de la persona. | violación | Rechazar `window` nulo antes de cualquier efecto (`input_window_required`). |
| CU3 | External/WindowsVisibleControlAdapter.cs:2428-2433, 1083-1085; External/WindowsScrollAdapter.cs:143-145 | R3 | Si `input.visible.click` no recibe `window` ni hay una vista viva, termina en `hwnd = await VisibleControlSurface.ResolveForegroundAsync(...)` («the window in front, as the descriptor says»). Ahí pulsa por UIA, y luego OCR, tooltip y visión sobre la misma ventana (`boundWindow` puede valer 0). `input.scroll` sin `window` hace `window = missionWindow != 0 ? missionWindow : await _foreground(...)` y gira la rueda en la ventana de la persona. | violación | La misma compuerta que en CU1 y CU2: sin `window`, nada. |
| CU4 | External/VisibleControlSurface.cs:510-541 (`ProtectedProcesses`, `ProtectedFrom`); External/WindowsVisibleControlAdapter.cs:2027-2031, 2445-2449; External/WindowsDesktopInteractionAdapter.cs:370-375 | R3 (y R4 por el comentario) | La guarda que protegía el editor, las terminales y BAXY mismo ya no actúa. En la vista sólo escribe `writer.WriteBoolean("protected", true)`, con el comentario «The mission acts on no such window», pero la misión que leía esa marca se retiró y nadie la lee hoy (grep en `src/`). Antes de pulsar, `InvokeUiaAsync` sólo comprueba `_elevated(hwnd)`, y `SendKeysAsync` acepta cualquier hwnd > 0. Con VS Code o la terminal al frente, o con su hwnd como `window`, BAXY escribe y pulsa ahí. `ProtectedFrom` sólo filtra la resolución por título (VisibleControlSurface.cs:260) y los candidatos de destino. | violación | Llamar a `ProtectedFrom(proceso, null)` en cada camino que actúa (clic, tecla, texto, rueda, portapapeles) y fallar con `protected_window`. Mejor aún, exigir que la raíz de `window` sea una ventana que BAXY lanzó (`LaunchProvenance`). Hoy sólo la consulta `app.close`. |
| CU5 | External/WindowsVisibleControlAdapter.cs:555-560, 1713-1715 | R1, R3 | `NamesTheCategory` es una lista de frases sobre el texto libre `application` del modelo: `words[0] is "el" or "mi" or "tu" or "su" or "the" or "my" or "your"` … `is "navegador" or "navegador web" or "browser" or "web browser"`. Cuando coincide, la vista toma `_browserWindow.FrontWindow()`, la ventana del navegador de la persona. | violación | Un argumento tipado (p. ej. `target: "user_browser"`) o el `window` de una vista anterior. Borrar la lista. |
| CU6 | External/VisibleControlSurface.cs:158-190, 262, 304, 316, 527-531, 547-559, 565-575, 611-672; WindowsVisibleControlAdapter.cs:1728-1732 | R1 | `ResolveTitledWindowAsync(application)` resuelve el nombre de app que dio el modelo a una ventana por palabras: `GenericApplicationWords` («navegador», «google», «microsoft», «app»…), `FunctionWords` («del», «para», «the»…), `PlatformWords={"windows"}` y `ProperNameWords`, que mira las mayúsculas. Basta que una palabra «propia» de 3 letras o más aparezca en el último segmento del título (`NamesAsWords(segment, word)`). Ese hwnd sale en la vista como el «window N» sobre el que luego se actúa. | violación | Que la vista reciba el `windowId` que dio `app.open` o `window.list`, o el nombre exacto del catálogo comparado con el proceso o AUMID (ver CU7). Sin eso, que devuelva candidatos. |
| CU7 | Applications/WindowsInstalledApplicationOpenProvider.cs:1971-2003, 2117-2132, 2222-2252, 1723-1728, 142-143 (D3/D4) | R1, R2, R3 | Con identidad débil (`Inventory`, `strongIdentityOnly: false`), una ventana «es» de la app si `normalizedProcessName.StartsWith(identity)` con cualquier palabra de 3 letras o más del nombre (`token is not ("microsoft" or "google" or "app")`), o si el título empieza por el nombre. «Windows PowerShell» aporta el token `windows`, y `windowsterminal` empieza por él, así que se reutiliza la Terminal de la persona. Una pestaña «Spotify - Web Player…» pasa por Spotify. `app.open` informa `reused` y devuelve ese `windowId`, y los actos siguientes escriben ahí. | violación | Identidad por la ruta del ejecutable (escritorio) o por AUMID (empaquetadas), como ya hace `strongIdentityOnly: true` (1704-1745). Borrar `BuildProcessIdentities` y el respaldo por título. |
| CU8 | Windows/WindowsWindowControlProvider.cs:1350-1355 | R1 | Con `byTitle`, `window.resolve` compara el texto del modelo con el título usando `WindowTitleIdentifiesApplication`: prefijo seguido de `' ' '-' ':' '|' '('`. «Spotify» encaja en «Spotify - Web Player». | zona gris | Sólo `string.Equals(title.Trim(), processName, OrdinalIgnoreCase)` (la primera mitad de la condición, que ya existe). |
| CU9 | External/UserBrowserScripts.cs:138-151, 270-280 (`PagePlay.Rank`) | R1 | El título que pidió el modelo se compara con las tarjetas de Disney+, HBO o Netflix por rango: 1 o 2 si `StartsWith`, 3 si `$folded.Contains($want)`. Se pulsa la mejor aunque su rango sea 3: «Coco» pulsa «Cocoon». Las palabras de reproducción (`$playWords`) son rótulos de la interfaz del servicio y eso está permitido. El recibo final sí depende de la sesión SMTC observada (UserBrowserSurface.cs:216-237). | violación | Pulsar sólo con rango 0 (igualdad plegada o run aislado). Si no, `streaming_title_not_found` con los nombres vistos. |
| CU10 | External/UserBrowserSurface.cs:202-205; External/UserBrowserTabs.cs:3-9, 36-59; Baxy.Kernel/Operations/ProductCatalog.cs:218-224 | R3, R5, R4 | `PagePlay` escribe en el buscador y pulsa dentro del navegador de la persona. `browser.control` (atrás, recargar, cerrar o `close_all` de hasta 50 pestañas) actúa sobre «the front window of their default browser». Es una decisión documentada del dueño (2026-10-06). Pero el catálogo dice «Controla la pagina CDP actual», el contrato es `browser.control.cdp.postread.v1` y el riesgo de `close_all` es LowReversible. | zona gris | Corregir la descripción y el contrato: es el navegador de la persona, no CDP. Que `close_all` pida confirmación (WorkLoss). |
| CU11 | External/WindowsVisibleOcrLocator.cs:109-114, 141, 212-229 | R2 | Tras un clic por OCR, `writer.WriteBoolean("selected", surfaceObserved)`, donde `surfaceObserved` sólo dice que la etiqueta sigue en pantalla (`LabelPresent`: `Fold(recognized.Text).Contains(needle)`). Nada se comprobó seleccionado. Los localizadores de tooltip y de visión escriben `selected: false`. | violación (menor) | Quitar `selected` de este recibo: ya está `labelStillOnScreen`. |
| CU12 | External/WindowsDesktopInteractionAdapter.cs:644-646, 669-686; External/DesktopKeyPress.ps1:224-227, 262-271; ProductCatalog.cs:917 | R2 | En teclas, texto y clic de puntero, `verified = accepted == expected` y `effectObserved = accepted > 0`: SendInput aceptó los eventos, pero no se leyó el control. El contrato del puntero se llama `…win32.postread.v1`, aunque la autoridad que informa es `'win32_sendinput_return_count'`. | zona gris | Llamar a esto «entregado», no «efecto observado» (`effectObserved:false` más `delivered:true`), o releer el control (valor, foco, superficie) como ya hacen los caminos con `window`. |
| CU13 | External/ScreenStateLines.cs:15-38; External/WindowsVisibleControlAdapter.cs:1911; src/baxy_mind/data/screen_state_lines.v1.json (`purpose`) (P6) | R1, R2, R4 | Reescribe lo observado: una línea de OCR que es un estado de una lista ES/EN se une con la de encima (`Text = $"{owner.Text}: {line.Text}"`). Su `purpose` cita `semantic.mission_answer.screen_states`, que ya no existe, y el JSON vive en la carpeta de la mente sin que la mente lo lea. | zona gris | Entregar las líneas con su caja (ya existen `LayoutLine` y `textLines`) y borrar `ScreenStateLines` y el JSON. |
| CU14 | External/DesktopUiaWorker.ps1:2457-2462, 2447-2450 | R1, R4 | `Test-WantedName` usa `$folded.Contains($needle)` con las palabras `wanted` del modelo para dar cupo reservado en la vista a los controles que las contienen. Es sólo presentación (no pulsa), pero es subcadena sobre texto del modelo. El comentario dice «las que la mente usa para ordenar la vista» y cita `ComputerUseSuccessCheck.ComparedControls`, que no existe en `src/`. | zona gris | Igualdad de palabra plegada, o quitar `wanted`. Corregir el comentario. |
| CU15 | External/DesktopMessagingAdapter.cs:1288-1289, 914-915, 1276-1283, 1295-1300 (C1) | R1 | `NamesRecipient`: ahora la frase va entera y en orden (`ContainsPhrase`). «ron» ya no encaja en «Ronaldo», pero «Ana» todavía encaja en «Ana María» o en «Ana y Pedro». El recibo da el `displayName` observado, así que es honesto. | zona gris | Igualdad del nombre plegado con el título o la cabecera ya separados de su estructura (« - Discord», «@»). Si no hay igualdad, devolver candidatos. |
| CU16 | Applications/ApplicationPlaceOpener.cs:50-60, 11 (D8) | R3, R4 | Devuelve el frente a `before` en cuanto `now != before`, sin comprobar que `now` sea la ventana de la app: puede deshacer un cambio que hizo la persona. El comentario de la línea 11 dice «Whether the window arrived is read on the window by the mission's check», y esa comprobación ya no existe. | zona gris | Devolverlo sólo si `now` pertenece al proceso o AUMID de la app. Corregir el comentario. |
| CU17 | Windows/WindowsWindowControlProvider.cs:442-450, 466-467; External/VisibleControlSurface.cs:510-524; Applications/WindowsInstalledApplicationOpenProvider.cs:1971-2003 frente a External/VisibleControlSurface.cs:547-672 | R4 | Hay mecanismos apilados para lo mismo. Tres listas de «ventanas de la persona o de BAXY» (`OwnProcessNames`, `KeptProcessNames`, `ProtectedProcesses`) con contenidos distintos: Kept no tiene `devenv`, `powershell` ni `cmd`. Y hay dos identificadores de «la ventana de la app X» que no coinciden: `WindowProcessIdentifiesApplication` y `WindowTitleIdentifiesApplication` frente a `ProcessIsApplication`, `TitleNamesApplication` y `DescriptionNamesApplication`. | muerto/apilado | Una sola lista de procesos protegidos y una sola identidad de app (ruta del ejecutable o AUMID). |
| CU18 | External/MissionFrontSignal.cs:12-19, 49-51; External/ForegroundLease.cs:46-55, 300-304, 386-391; External/WindowsExternalCapabilityProvider.cs:206-209 | R4 | `IMissionFrontSignal.MissionBegins` y `MissionEnds` no tienen ningún llamador en `src/` (ni App ni Core). El bloque compartido siempre vale 0, `Read()` devuelve `(0, true)`, y por eso `input_mission_ended` y la devolución del frente «once the mission ended» son inalcanzables. `TakeForMissionAsync` sí se usa, porque lo llama el proveedor cuando hay `window`. | muerto | Borrar `IMissionFrontSignal`, `WindowsMissionFrontSignal.Write`, la generación y la rama `!running`. Corregir los comentarios que hablan del fin de la misión. |
| CU19 | Applications/WindowsApplicationOpenProvider.cs (75 líneas), WindowsApplicationLauncher.cs (711), WindowsApplicationOpenVerifier.cs (135), ApplicationInvocationStore.cs (493), NotepadIdentityPolicy.cs:6-36 y 51-175, WindowsApplicationPlatform.cs:9-487; ApplicationOpenContracts.cs:5, 8-13, 118-131 (D-P1) | R4 | Toda la ruta de apertura de Notepad sigue entera y sólo se usa entre sí y en los tests: Baxy.Core/Program.cs:103-111 conecta `WindowsCalculatorOpenProvider` y `WindowsInstalledApplicationOpenProvider`. `ApplicationIds.Notepad`, `ApplicationIds.DisplayName`, `IApplicationLauncher` e `IApplicationOpenVerifier` sólo los usa esa ruta. Hay que conservar `ApplicationInventoryException` (NotepadIdentityPolicy.cs:38-49) y `NativeMethods` (WindowsApplicationPlatform.cs:489-615), que usan el proveedor instalado y MicrophoneInUse. | muerto | Borrar esos archivos o tramos y sus tests. |
| CU20 | Applications/WindowsInstalledApplicationOpenProvider.cs:507-513; Applications/FileActivation.cs:52; Applications/InvokerLaunch.cs:144-148 y WindowsApplicationLauncher.cs:10 | R4 | `ResolveWindowIdentitiesAsync` no tiene ninguna referencia, ni siquiera en los tests. `FileActivation.HandOffFor` sólo lo usan los tests. `CreateBreakawayFromJob` está duplicado, y el comentario de InvokerLaunch remite a `WindowsApplicationLauncher`, que está muerto. | muerto | Borrar. |
| CU21 | External/WindowsDesktopInteractionAdapter.cs:35-38, 64-89; External/DesktopUiaWorker.ps1:1365-1369; External/UiaWorkerHost.cs:57, 77; External/ForegroundLease.cs:268-271 (`watchMission`) (D-P2) | R4 | Miembros que sólo usan los tests: el constructor sin parámetros (sólo lo usa ComputerUseSpeedLiveCheck.cs:79) y los dos constructores de 3 y 4 scripts; `Test-AsksMore` (sólo lo llama ComputerUsePressedNameTests); `ScriptExists`; el `init` de `RenderClasses` («unless a test sets others»); y el parámetro `watchMission`. | muerto (sólo tests) | Moverlos a los tests o quitarlos, y que los tests usen el constructor completo. |
| CU22 | External/WindowsVisibleControlAdapter.cs:2201-2202 y WindowsVisibleOcrLocator.cs:257 (`semantic.chat_lines`); Applications/WindowsInstalledApplicationOpenProvider.cs:2074 (`MindArgumentNormalization`); External/DesktopUiaWorker.ps1:294 («the planner's fact»), 2447 y 2450; External/WindowsVisibleControlAdapter.cs:2028-2030 («The mission acts on no such window») (D-P3) | R4 | Comentarios obsoletos: citan módulos de la mente semántica, el planificador o la misión, que ya no existen (`src/baxy_mind` sólo tiene `mind.py`, `protocol.py`, `llm_server.py` y `voice*`), o describen una protección que hoy no se aplica (CU4). | muerto (comentario) | Reescribirlos según lo que el código hace hoy, o borrarlos. |

#### Permitido o permitido-dudoso (se queda)

- **LocalVisionEndpoint.cs:12-29 (P2):** `CaptureVisionAdapter` y `WindowsVisibleVisionLocator` sólo aceptan un endpoint loopback (`IsLoopback`). La captura ya no sale del equipo. Permitido.
- **WindowsInstalledApplicationOpenProvider.cs:1295-1336 (D1):** se abre sólo con la coincidencia exacta plegada. Levenshtein sólo ordena los `Candidates` que se devuelven y nunca elige. Permitido-dudoso.
- **SearchBurst.cs:444-462 (B1/B2), `SameLabel` (WindowsVisibleControlAdapter.cs:3331-3335) y `Test-NameMatch` del worker (DesktopUiaWorker.ps1:1303-1312) (P3):** igualdad plegada. Permitido.
- **DesktopUiaWorker.ps1:3631-3662 (`Test-NamesLabel` y `Select-PointHolders`):** contiene como palabras enteras, pero sólo para comprobar que el control en el punto lleva la etiqueta exacta que leyó el OCR. Es verificación sobre datos del sistema. Permitido-dudoso.
- **DesktopMessagingAdapter.cs:1361-1430 (C4):** la tolerancia de OCR en la entrega aparece en el recibo (`deliveryRead`, `deliveryMatch: "tolerant"`). Permitido.
- **Mensajería:** escribe y pulsa dentro del cliente que la persona pidió (`FindWindow` por proceso `Discord` o `WhatsApp.Root`, DesktopMessagingAdapter.cs:1679-1705, dentro del lease). Es acto en la app objetivo. Permitido.

### Estado de lo que reportaron las auditorías anteriores (en esta área)

| Ítem | Estado |
|---|---|
| P1 (entrada en la ventana del frente) | **Sigue** (CU1, CU2, CU3). Ninguna operación de entrada exige `window` ni consulta `LaunchProvenance`. |
| P2 (visión remota) | **Arreglado.** Sólo acepta loopback. |
| P3 (alias, subcadena y erratas en rótulos) | **Arreglado** en el adaptador, los localizadores de tooltip y OCR y el worker. |
| P4 (`PagePlay` y `Act` en el navegador de la persona) | **Sigue.** El rango por subcadena es CU9; actuar en el navegador de la persona es CU10, una decisión del dueño que el catálogo describe mal. |
| P5 (palabras del título para resolver la app) | **Sigue** (CU6), y además está CU5 (`NamesTheCategory`). |
| P6 (`ScreenStateLines`) | **Sigue** (CU13). |
| P7 (`ProtectedProcesses`, que se consideraba permitido) | **Ya no protege al actuar** (CU4). |
| B1, B2 | **Arreglados.** |
| C1 | **Parcial** (CU15): queda la frase contenida en vez de igualdad. |
| C2, C3, C4, C5, C6, C7, C8, C9, C10, C11, C14 | **Arreglados** (verificados en el código: `HeaderLine` sin tolerancia, sin clic si no está `named`, `deliveryRead` y `deliveryMatch`, `ComposerHoldsTextAsync`, destinos en `test-destinations.v1.json`, `InNormalizedWindowAsync` que devuelve el tamaño, `Get-Root -Front` sólo en lecturas, `Find-EntryNamed` exacto, `NamedCandidates` devueltos como candidatos, sin `any`). |
| D1, D2, D5, D6 | **Arreglados.** Queda la constante `ApplicationIds.Notepad`, que está muerta (CU19). |
| D3, D4 | **Siguen** (CU7). |
| D7 | **Parcial.** El recibo ya dice `hidden` y `alreadyGone`, pero sigue `KeptProcessNames` fija en el código (CU17). |
| D8 | **Sigue** (CU16). |
| D9 | **Arreglado.** |
| D-P1 (ruta de Notepad) | **Sigue** (CU19). |
| D-P2 | **Parcial.** Las constantes muertas de la mensajería y los miembros por defecto ya no están. Siguen `Test-AsksMore`, `ScriptExists`, los constructores de test y otros (CU21). |
| D-P3 | **Parcial.** El script de Spotify y SearchBurst están limpios. Quedan los comentarios de CU22, CU14 y CU16, y el `purpose` del JSON de CU13. |
| `MissionFrontSignal` sin llamadores (auditoría 1, n.º 17) | **Sigue** (CU18), ahora acotado a `MissionBegins` y `MissionEnds`. |

### Resumen

Hoy se arregló casi todo lo de rótulos, mensajería, apertura exacta y visión remota: no queda alias, errata ni subcadena en la elección del control pulsado, ninguna captura sale del equipo y los recibos de mensajería dicen lo observado.

Lo grave que sigue es la regla 3. Ninguna operación de entrada exige la ventana objetivo:

- `clipboard.copy` y `clipboard.paste`, `input.select.all`, `input.pointer.control` e `input.keyboard.layout` no la admiten siquiera;
- `input.key.press`, `input.text.type`, `input.visible.click` e `input.scroll` caen a la ventana del frente sin `window`;
- cualquier hwnd vale como `window`;
- la protección del editor, las terminales y BAXY (`ProtectedFrom`) quedó reducida a una marca en la vista que nadie lee, porque la leía la misión retirada.

Una sola compuerta resolvería las cuatro filas (CU1-CU4): `window` obligatorio, ventana no protegida y, en lo posible, lanzada por BAXY. La regla 1 sigue viva en la resolución de «qué ventana es la app»:

- palabras del título, `NamesTheCategory` y el prefijo de proceso, que hace que «Windows PowerShell» reutilice la Terminal (CU5-CU8);
- el rango por subcadena de `PagePlay` (CU9).

En regla 4 quedan la ruta de Notepad entera (unas 1 600 líneas), la señal de fin de misión sin emisor, listas e identificadores duplicados, miembros que sólo usan los tests y comentarios que citan la mente semántica o la misión.

## Otros proveedores


Copia congelada `BAXY-Renew-audit` (hub/baxy-renew `bde62d76c`). Auditoría de sólo lectura: no se editó, compiló ni ejecutó nada.

Rutas relativas a `src/Baxy.Providers.Windows/` salvo que se indique otra cosa. Abreviaturas: `PC` es `src/Baxy.Kernel/Operations/ProductCatalog.cs`, `EN` es `src/baxy_mind/data/tool_descriptions.en.v1.json`, `RP` es `src/Baxy.Kernel/Policy/RiskPolicy.cs`.

**Alcance.** Web, archivos, multimedia, winget, Steam y juegos, shell, avisos programados, Memory/Notes/Tasks, Audio, SystemStatus, Network, control de dispositivos, Outlook, diagnóstico de cierres, energía, terminación de procesos y Papelera. También los datos de `src/baxy_mind/data` que sólo lee C#.

Quedan fuera los componentes de computer use excluidos en el encargo: `WindowsDesktopInteractionAdapter`, `UserBrowser*`, `Applications/*`, `Windows/*` y el resto de la lista. Cuando un hallazgo depende de uno de ellos se indica.

### Estado de lo reportado antes en esta área

| Ítem anterior | Estado | Evidencia actual |
|---|---|---|
| W1 enrutador de `web.search` por palabras | **Arreglado** | `External/WebBrowserAdapter.cs:665-698`: `switch` sobre el enum tipado `source`. |
| W2 `NotNewsWords`, W3 `SearchQueryYear`, W5 `SearchPertinence`, W6 reconsulta, W7 `FigureWords`, W8 `answerWords`, W9 `listing`, W13/W14 Wikimedia, W15 `WeatherSynonyms`, W20 `NamesOnlyOr` | **Arreglados** | Los símbolos y los archivos ya no existen en `src/`. |
| W4 Wikipedia `IsEncyclopedic` y marcas de idioma | **Arreglado** | `External/WikipediaSearchSource.cs` sólo arma la URL; `language` es un enum. |
| W10 divisas por nombre y pesos regionales | **Arreglado** | `WebBrowserAdapter.cs:735-741`: códigos ISO 4217 tipados. |
| W11 analizador de ESPN y alias | **Arreglado** | `External/EspnScheduleSource.cs:66-100`. |
| W12 diccionario OSM y regex `PlacePhrase` | **Arreglado** | `kind` y `place` tipados (`External/OpenStreetMapPlaceSource.cs:27`). |
| W16 filtro por palabras vacías | **Arreglado** | `WebBrowserAdapter.cs:1009-1020`: sólo filtros estructurales. |
| W17 `YouTubeSearch.Fits` | **Arreglado** | `External/YouTubeSearch.cs:34-42`: toma el primer `videoRenderer`. |
| W18 `dialectCountry` y `Namesakes` | **Sigue** | Ver fila 3 y fila 26. |
| W19 `nearby` (ipwho.is + `http://ip-api.com`) | **Parcial** | Se quitó ip-api por HTTP (`External/PublicPlaceLocator.cs:30-35`). Siguen ipwho.is y la ciudad añadida a la consulta (fila 25). |
| W21 extracto pegado al snippet | **Arreglado** | `WebAsync` (751-781). |
| O1 `web.download` raspando Bing | **Arreglado** | Esquema `folder`/`name`/`url` (PC:1853-1859); `External/WindowsFileToolsAdapter.cs:612-617`. |
| O2 colores por nombre | **Arreglado** | `WindowsFileToolsAdapter.cs:575-585`: sólo `#RRGGBB`. |
| O3 dos adaptadores de calendario | **Arreglado** | No queda nada de Graph. Sigue su descripción (fila 20). |
| S1 ranking de Spotify por palabras, S2 `matchesQuery`, S3 descripción, S5 título pedido, S6 `Contains("spotify")` | **Arreglados** | `External/SpotifyDesktopAutomation.ps1:290-319` y `:613`; `External/SpotifyDesktopAdapter.cs:210-218` y `:325`. |
| S4 «ya sonaba» con `effectObserved:true` | **Arreglado en el recibo** | `ps1:466-471`. La comparación que decide «ya sonaba» es nueva y está mal (fila 10). |
| S7 verificación por prefijo de palabra | **Sigue (zona gris, declarado en `playbackEvidence`)** | `ps1:192-210`, usado en `:224`. |
| S8 prefijo «Estás escuchando:» sólo en español | **Sigue** | Fila 27. |
| D-P3 comentario que citaba un test de Python en el script de Spotify | **Arreglado** | Commit bd8ab336c. |
| winget cuenta «instalando» como éxito | **Arreglado** | `External/WingetPackageAdapter.cs:150-153` falla con `winget_install_still_running`. Queda un comentario obsoleto (fila 37). |
| El toggle de Spotify siempre dice `paused` | **Arreglado** | `External/SpotifyMediaControl.ps1:153-157` y `:192`. |
| Juego por subcadena («Portal» → «Portal 2») | **Arreglado** | `External/WindowsGameInstallationAdapter.cs:216` y `External/SteamLocalAdapter.cs:541-546`, `:611-619`: igualdad tras plegar. |
| Red Wi-Fi por subcadena | **Arreglado** | `External/WindowsDeviceControlAdapter.cs:1566-1603`. Queda un plegado de más (fila 30). |
| Zona horaria por subcadena o población | **Parcial** | Ya no hay subcadena, pero gana el lugar más poblado (fila 29). |
| Volumen por app por subcadena | **Parcial** | Ya no hay subcadena, pero basta una palabra suelta (fila 28). |
| `WindowsInventoryAdapter` (fallos enlatados, duplicado) | **Parcial** | Los fallos enlatados desaparecieron, pero el adaptador sigue registrado como segunda lista Bluetooth (fila 33). |
| O4 `keypad_keys` y la interfaz de la Calculadora | **Sigue permitido** | Hay restos muertos (fila 39). |
| `routine.*` nunca se ejecuta | **Arreglado** | No queda `routine` ni `on_phrase` en `src/`. |
| `memory_subjects.v1.json`: `selectors` y `withoutNamingMemory` sin lector, `_doc` obsoleto | **Sigue** | Fila 41. |
| `filesystem.trash.restore` inalcanzable y `filesystem.hash` «Paso interno» | **Sigue como código muerto** | Fila 34. El prefijo «Paso interno» ya no existe; ahora son `Internal`. |
| Comentario obsoleto en `SearchAddresses.cs:11` | **Sigue** | Fila 40. |
| P1 `clipboard.copy`/`clipboard.paste` en la ventana de delante | **Sigue**, pero el mecanismo es de computer use | `WindowsDesktopInteractionAdapter.cs:176-229` y `DesktopKeyPress.ps1:208-219` quedan fuera de esta área. No se cuenta aquí. |

### Hallazgos

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| 1 | External/WindowsDeviceControlAdapter.cs:1158-1178 (`client.channel.locate`, PC:311-321) | R3, R1 | `foreach($c in …'Chrome_WidgetWin_1'){if($c.Current.Name -match 'Discord')…}` y después `SetForegroundWindow`, Esc, `Ctrl+K` y `Text($label)` en esa ventana. Chrome, Edge y VS Code comparten esa clase, así que una pestaña de la persona titulada «…Discord…» recibe las teclas. Además filtra los ítems con `$n.ToLowerInvariant().Contains($nd)` (1163). | violación | Hallar la ventana por el proceso `Discord.exe`, no por el título. Devolver los ítems del buscador tal como los da Discord, sin `Contains`. |
| 2 | External/WindowsProcessTerminationAdapter.cs:45, 48-51, 133-134 | R5, R2 | `process.Kill(entireProcessTree: true)`: la confirmación nombra un ejecutable, pero mueren también sus hijos («termina explorer» cierra casi todo lo de la persona). `catch (ArgumentException) { return true; }` cuenta como terminado un proceso que ya no existía. Si no había ninguno, devuelve `Success(…, effectObserved: false)` y el kernel lo convierte en `external_verification_failed`, sin decir la causa. | violación | `entireProcessTree: false`, o listar los hijos en la confirmación. Devolver `FailureBeforeEffect("process_not_running")`. No contar los procesos que ya habían salido. |
| 3 | External/OpenMeteoWeatherAdapter.cs:418-427 (`RegionKind`, usado en 281, 309, 331), 355-366, 276-280 | R1 | Hay tres ayudas sobre `location`, que es texto libre del modelo. Una regex de palabras (`comunidad autonoma\|estado\|provincia\|state\|province…`) borra la clase de región. Si no hay igualdad, `Fold(name).Split(' ').Intersect(askedWords).Any()` toma el primer lugar que comparte una palabra. Y `location.Split(',', 2)` interpreta «Lugar, Región» sin que ninguna descripción se lo diga al modelo. | violación | Quitar `RegionKind` y el bucle `Intersect`, y fallar con `weather_place_not_found`. Si hace falta la región, que sea un argumento tipado `region` o `countryCode`, con su descripción. |
| 4 | External/WindowsSandboxNamedFileAdapter.cs:86-87, 110-129, 134-136 | R1, R4 | `diff.named` resuelve el archivo con `Path.GetFileName(path).Contains(query…)`, y el derecho con una heurística: misma extensión y `…WithoutExtension(path).Contains(leftStem…)`. Es además un segundo proveedor sobre la misma raíz `filesystem-sandbox` que `LocalFilesystemProvider` (`move.named` duplica a `filesystem.move`). Su `Enumerate()` no excluye `.trash` ni `.backups`. | violación | Igualdad exacta del nombre (como ya hace `Move` con `exact:true`) y borrar `ResolveRelatedUnique`. Llevar diff y move por nombre a `LocalFilesystemProvider` y borrar el adaptador. |
| 5 | External/WindowsKnownFileAdapter.cs:741-747, 753-766 | R1, R2 | Una ruta completa se reduce a ruta relativa: `name = Path.GetRelativePath(holding[0].Root, …)`. Si el archivo estaba en la raíz, `name` queda de una sola parte y cae en `Enumerate(roots)` recursivo por nombre. Así, `…\Desktop\notas.txt` inexistente lee o edita `Desktop\viejo\notas.txt`. Los recibos de read, edit y trash no dicen la ruta (590-591, 706-707, 431). | violación | Una ruta dada completa se resuelve exacta con `Path.Combine(root, name)`, sin búsqueda. Escribir `relativePath` o `fullPath` en los recibos de read, edit y trash. |
| 6 | Memory/LocalMemoryStore.cs:1129-1140 (`MatchesQuery`), usado en 299, 336 y 1151; src/Baxy.Core/Operations/MemoryHandlers.cs:585-590 | R1 | `record.Selector.Contains(query…)`, `normalizedLabel.Contains(query…)`, `tag.Contains(query…)`. `memory.recall` con scope `"exact"` («una cosa concreta», EN:99) devuelve todo lo que contiene el texto. `memory.forget` por tema borra todo registro que lo contenga. | violación | Recall exact: igualdad del selector plegado. Forget por tema: igualdad exacta de tag, o quitar el scope. |
| 7 | src/Baxy.Core/Operations/MemoryHandlers.cs:784-785 (`ForgottenStateMatches`) | R2 | Para los scopes kind, topic y all exige `return status.TotalRecords == 0;`. Si queda cualquier otra memoria, un olvido correcto se informa como fallo con efecto ambiguo. El almacén ya verificó la ausencia en `LocalMemoryStore.cs:915-938`. | violación | Releer con el mismo criterio del olvido (tipo o tema), o usar la verificación del almacén. |
| 8 | External/MicrosoftAccountAdapter.cs:237, 292-303 | R1, R2 | La relectura del correo enviado usa `([string]$candidate.To).ToLowerInvariant().Contains($to…)`: `an@x.com` encaja en `juan@x.com`. El recibo escribe `to` y `subject` **pedidos**, y descarta los observados (`sentTo` y `subject`, 242). | violación | Comparar con `-ieq` cada `Recipients[i].Address`. Escribir en el recibo `sentTo` y `subject` observados. |
| 9 | External/WebBrowserAdapter.cs:2008-2011, 2053-2057 (Netflix) y 2153, 2158 (Disney+) | R1, R2 | `named.find(x=>x.t===wanted)\|\|…startsWith(wanted)\|\|…includes(wanted)\|\|named[0]`: subcadena del `title` del modelo y, si nada encaja, la primera ficha. `matched=(document.title+' '+body).includes(wanted)` cuenta como «se abrió lo pedido» (`opened`, 2057). El recibo sí lleva `chosenName`. | violación | Igualdad plegada. Si no hay, el primer resultado del buscador del servicio, declarado en el recibo. Quitar `matched` como prueba. |
| 10 | External/SpotifyDesktopAutomation.ps1:465 frente a :571 | R1, R2 | `$beforeNowPlaying.StartsWith($foldTitle+' ') -and …Contains(' de '+$candidateIdentity)`: con «hello», «hello from the other side de adele» cuenta como lo pedido y el recibo dice `alreadyPlaying:true` sin pulsar. La verificación posterior (571) usa otra regla: `-eq $foldTitle -or StartsWith($foldTitle+' de ')`. | violación | Usar en 465 la misma lectura estructural que en 571. |
| 11 | External/SpotifyDesktopAdapter.cs:304-418 + External/SpotifyMediaControl.ps1 entero, frente a External/WindowsMediaSessionAdapter.cs:655-778 | R4, R2 | Dos mecanismos para `media.control` de Spotify: clics por UIA y SMTC. El que actúa depende de cómo escriba el modelo `sourceApp`. `'stop' {@('detener','stop')}` (ps1:80) busca un botón que Spotify no tiene, así que siempre falla. | violación | Quitar `ControlAsync` de Spotify y `SpotifyMediaControl.ps1`, porque Spotify publica su sesión SMTC. Quitar «or spotify» de la descripción de `sourceApp`. |
| 12 | External/WindowsMediaSessionAdapter.cs:17-28, 268-275, 382-568 | R4 | Camino de la API web de Spotify que sólo se activa con `BAXY_SPOTIFY_ACCESS_TOKEN`. Nada del producto define esa variable: sólo la usan los tests. Además ordena por `popularity` (418-419), en contra de «primer resultado». | muerto | Borrar ese camino. |
| 13 | External/WindowsMediaSessionAdapter.cs:691-701 y 765-768; External/YouTubeMpvAdapter.cs:433-445 | R2 | Se calcula `alreadySatisfiedBeforeDispatch`, pero se devuelve `ExternalJson.Success(…)`, que por defecto lleva `effectObserved = true`. En mpv, con `current == wanted`, también `effectObserved: true`. | violación | `ExternalJson.Switched(op, result, effectObserved: !alreadySatisfied)` en SMTC, y `current != wanted` en mpv. |
| 14 | External/YouTubeMpvAdapter.cs:288, 464 | R2 | `json.WriteString("title", title ?? query)` y `_activeTitle ?? _activeQuery`: lo pedido aparece en el campo del título. `titleObserved:false` lo atenúa. | zona gris | Omitir `title` cuando no se observó. |
| 15 | External/WingetPackageAdapter.cs:229-232, 424-442 | R2 | Desinstalar con un nombre que no coincide devuelve `winget_package_not_installed` aunque `winget list` trajo filas, así que la causa es falsa. `LaunchDetached` descarta el código de salida, y `*_not_verified` nunca dice el error de winget. | violación | Con `installed.Count > 0`, devolver `Candidates(…"winget_package_not_resolved"…)` como ya hace la instalación. Adjuntar `ExitCode` y la última línea de la salida. |
| 16 | External/SteamLocalAdapter.cs:912-983 y 419-460, frente a External/WindowsGameInstallationAdapter.cs:98-173 | R4 | Dos lectores de los manifiestos de Steam (`appmanifest_*.acf`, `StateFlags`) y de Epic, con raíces y criterios distintos. `game.entitlement.named` y `game.installed.named` pueden contestar distinto sobre «instalado». | violación | Que `game.installed.named` use `SteamLocalAdapter.GetCatalogSnapshot()`, y un solo lector de Epic. |
| 17 | External/SteamLocalAdapter.cs:115-118, 134-135, 231-286, 28, 905-910, 991; PC:756-762, 776-782, 809-827; Core ExternalCapabilityHandlers.cs:51-58 | R4 | La pareja preparar/confirmar de instalación y compra de Steam es `ToolExposure.Internal` y no tiene ningún llamador en `src/`; sólo la usan los tests. `game.install.named` ya cubre la instalación. | muerto | Borrar las operaciones, los handlers y su rama. |
| 18 | External/WindowsExternalCapabilityProvider.cs:363-443, 495-500, 7-11 | R4 | El `switch` de errores de respaldo sólo se alcanza si ningún adaptador hace `CanHandle`. Todas las operaciones que lista tienen un adaptador que las reclama, así que sólo lo alcanzan los tests por el constructor interno. `ProcessExists` sólo lo usan esas ramas. El resumen («delegates no effect until an authenticated official adapter is injected») ya no describe el código. | muerto | Dejar sólo `external_operation_not_supported`, borrar `ProcessExists` y reescribir el resumen. |
| 19 | External/NativeScheduledNotificationBackend.cs:26-56, 278-297; External/WindowsScheduledNotification.ps1; External/WindowsScheduledNotificationAdapter.cs:37-44, 80-81 | R4 | Dos backends completos para los avisos: COM nativo y script, con caída al script ante cualquier fallo del host. `notification-scheduler-fallback.jsonl` se escribe y sólo lo lee un test. Hay un constructor «The script alone, as before M119» que sólo usan los tests, y el `.ps1` es obligatorio incluso en el camino nativo. | violación (apilado) | Quedarse con el backend nativo; borrar el script, el diagnóstico de caída y ese constructor. |
| 20 | PC:269-280 (`calendar.event.create`), External/MicrosoftAccountAdapter.cs:44-46, 470-478 | R2, R4 | La descripción «verifica su identidad remota» viene de la época de Graph; hoy es un `GetItemFromID` sobre el MAPI local. `RequireUtc` exige UTC al modelo, el mismo problema que `schedule.alarms` resolvió con hora local (E004). | zona gris | Descripción: «calendario de Outlook de este PC, verificado releyendo el elemento». Aceptar hora local como `schedule.alarms`. |
| 21 | External/MicrosoftAccountAdapter.cs:102-104, 208, 49-52, 345-346 | R2 | El `catch` cambia `outlook_inbox_empty`, `outlook_sent_postread_missing` y `outlook_latest_identity_mismatch` por `'outlook_mail_failed'`, y C# lo reduce a `outlook_mail_operation_failed`. En el calendario pasa lo mismo. | zona gris | Emitir el código conocido (`error=$_.Exception.Message`) y propagarlo hasta el recibo. |
| 22 | External/NativeScheduledNotificationBackend.cs:410-411 (sin `WakeToRun`); WindowsScheduledNotification.ps1 (valores por defecto de `New-ScheduledTaskSettingsSet`) | R2 | `DisallowStartIfOnBatteries` y `StopIfGoingOnBatteries` valen `true`: una alarma verificada como programada no suena con el portátil a batería, y «despiértame» no despierta un PC suspendido. EN:127 promete «ring on this PC». | zona gris | Poner ambos en `false` y `WakeToRun=true`, o decir el límite en la descripción y en el recibo. |
| 23 | External/WindowsScheduledNotificationAdapter.cs:668 frente a NativeScheduledNotificationBackend.cs:312-323 | R4, R2 | Cada aviso escribe en su `.fired` `{rangUtc, notificationShown, sound}`, pero el diagnóstico «por qué no sonó» sólo cuenta los archivos y nunca lee ese recibo. | zona gris | Que el diagnóstico lea cada `.fired` e informe si se mostró. |
| 24 | External/WebBrowserAdapter.cs:175-179 (`browser.control`, `ListTabsAsync` 308-310) frente a 235-241; PC:217-224 | R3, R5, R2 | `ControlAsync` va siempre al navegador de la persona (`_userBrowser.ControlAsync`), aunque haya una sesión CDP activa. `ReadPageAsync` sí la respeta (caso E016). `close_all` cierra las pestañas de la persona con riesgo `LowReversible`, sin confirmar. La descripción española sigue diciendo «la página CDP actual». El mecanismo (`UserBrowserTabs`) es de computer use. | zona gris (decisión del dueño, 2026-10-06) | Misma guarda `_sessionContext?.Active is null` que en `ReadPageAsync`. Riesgo que confirme `close_all`. Alinear la descripción española. |
| 25 | External/PublicPlaceLocator.cs:21-35, 44, 18, 81-83; WebBrowserAdapter.cs:685-688, 711-719 | R3, R4 | Con `nearby`, o con `weather.current` sin `location`, se pregunta la ubicación del PC a ipwho.is y se añaden la ciudad y el país a la consulta que va a DuckDuckGo, Google News, Wikipedia o Nominatim. El resumen todavía habla de «dos servicios… el segundo contesta cuando el primero no», con un único servicio en el arreglo. `CountryCode` se escribe y nadie lo lee. | zona gris (R3) / muerto (comentario y campo) | Que el dueño decida si «clima aquí» cuenta como pedido explícito, y decirlo en la descripción. Corregir el resumen y quitar `CountryCode`. |
| 26 | PC:1832-1836 (`weather.current.dialectCountry`); EN `weather.current` | R1, R4 | Al modelo le llega `dialectCountry` sólo con el enum `AR/CL/CO/ES/MX/VE`. Su significado («el país que marca el habla de la persona») está en un comentario de C# que el modelo no ve. Es un residuo de la mente semántica (W18). | zona gris | Quitar `dialectCountry` y `Namesakes`, o cambiarlo por un `country` ISO descrito. |
| 27 | External/SpotifyDesktopAutomation.ps1:443, 570 | R2 | `$prefix=Fold('Estás escuchando:')`. Con el cliente en inglés, `observedNowPlaying` queda vacío y toda reproducción falla después de pulsar, sin decir la causa. | zona gris | Leer también `'Now playing:'`, como ya se hace con `'spotify search'` (477). |
| 28 | Audio/WindowsCoreAudioPlatform.cs:810-830 | R1 | `applicationName.Split([' ','-','_','.',…])` y luego `if (token == process) return true;`: basta una palabra suelta del texto del modelo («Windows Media Player» encaja con un proceso `media`). | zona gris | Igualdad plegada de todo el argumento `app` con el proceso o con el nombre visible de la sesión, y describirlo así. |
| 29 | SystemStatus/PlaceTimeZoneResolver.cs:53-55, 71 | R1 | `candidates.MaxBy(place => place.Population)` elige al homónimo más poblado. El clima usa otra regla sobre el mismo geocodificador. | zona gris | El primer resultado del geocodificador, o «ambiguo» con los candidatos cuando caen en zonas distintas. |
| 30 | External/WindowsDeviceControlAdapter.cs:2231-2234 (`FoldProfile`) | R1 | `.Where(c => char.IsLetterOrDigit(c) \|\| char.IsWhiteSpace(c) \|\| c is '-' or '.')`: «Net_1» = «Net1». Es más que plegar mayúsculas y tildes. | zona gris | Quitar sólo mayúsculas y marcas diacríticas. |
| 31 | PC:1977 y EN:164 (`wifi.radio.set`); PC:1603 y EN:136 (`system.power`); PC:620, EN:60 y decider_catalog.es:61 (`filesystem.known.trash.named`); PC:1157, 1221 y EN:95, 101 (`memory.enable`, `memory.sensitive.save`) | R2 | Las descripciones dicen «con confirmación» o «tras confirmar», pero el riesgo resuelve `Allow`: PrivacySensitive y RecoverableDelete en RP:81-84, y `system.power` en RP:62-67. | zona gris | Quitar la promesa de los textos, o hacer que pregunten. |
| 32 | External/WindowsDeviceControlAdapter.cs:416-417 y 1943; External/WindowsAudioAdjustmentAdapter.cs:195-196, 297-298; con Core ExternalCapabilityHandlers.cs:328-339 | R2 | «Ya estaba en el estado pedido» (Bluetooth ya emparejado, no molestar, volumen por app ya en el valor) devuelve `Success(…, effectObserved:false)` sin `StateAlreadyReached`, y el handler lo convierte en `external_verification_failed`. La causa real se pierde. | zona gris | `ExternalJson.Switched(…, effectObserved:false)` o un `FailureBeforeEffect("…_already_…")`. |
| 33 | External/WindowsInventoryAdapter.cs:1-107; WindowsExternalCapabilityProvider.cs:85, 336-357 | R4, R2 | Segunda ruta de lista Bluetooth (PnP) que se ejecuta tras cualquier fallo de WinRT. Sus `deviceId` no se guardan en `_bluetooth`, así que emparejar uno falla con `bluetooth_identity_expired` (WindowsDeviceControlAdapter.cs:413-414). | muerto (apilado) | Borrar el archivo y su registro; el timeout de WinRT es la respuesta. |
| 34 | PC:589-595, 688-713; Core FilesystemHandlers.cs:19, 24-26, 66-67, 82-89; Filesystem/LocalFilesystemProvider.cs:22-48, 267-311, 485-486; Filesystem/FilesystemContracts.cs:33-42, 60-68, 85-87 | R4, R2 | `filesystem.trash.prepare` y `filesystem.trash.commit` son Internal y sólo las usan los tests. El `restoreId` sólo sale de `commit`, así que `filesystem.trash.restore`, que es Public y que EN:67 ofrece («devuelve viejo.txt»), siempre falla. `filesystem.hash` (Internal) no tiene llamador. `CreateDirectory(relativePath)` de un argumento y su cuerpo por defecto no los llama nadie. | muerto | Retirar las cuatro operaciones y la `.trash` privada (borrar en el sandbox con `WindowsRecycleBin`), y dejar una sola firma de `CreateDirectory`. |
| 35 | External/WindowsRecycleBinAdapter.cs:10-12 frente a Filesystem/WindowsRecycleBin.cs:101-105; resolución de carpetas conocidas en WindowsFileToolsAdapter.cs:754-762, WindowsKnownFileAdapter.cs:1037-1044, LocalFilesystemProvider.cs:226-234, WindowsKnownBackupAdapter.cs:349-363, KnownFolderOpen.ps1:22-28, KnownFileOpen.ps1:15-21 | R4 | Dos implementaciones de la Papelera: `Shell.Application Namespace(10)` con `Clear-RecycleBin`, y `SHQueryRecycleBin` con `SHFileOperation`. Cinco resoluciones de carpetas conocidas: los `.ps1` usan `shell:Downloads` (la carpeta real) y C# usa `%USERPROFILE%\Downloads`, que no coinciden si Descargas está reubicada. | zona gris (apilado) | Un solo `WindowsRecycleBin` (`SHEmptyRecycleBin`) y un solo helper con `SHGetKnownFolderPath`, que pase la ruta ya resuelta a los `.ps1`. |
| 36 | External/WindowsFileToolsAdapter.cs:360-367, 386-451 | R1 | Si el archivo no está en la carpeta nombrada, `file.open` lo busca por nombre exacto en desktop, documents, downloads y pictures, y abre el de otra carpeta. El recibo dice `askedFolder`, pero ni el catálogo (PC:500) ni la descripción lo cuentan. | zona gris | Fallar con `file_not_found` (el modelo tiene `file.find`), o describirlo. |
| 37 | External/ShellCommandAdapter.cs:160; External/WingetPackageAdapter.cs:20-22 | R2, R4 | `ExternalJson.Success(operation, result, effectObserved: true)` también con `exitCode != 0` y también para un `ls`. El comentario de winget («el recibo dice que empezó y con qué proceso») no coincide con 152-153, que falla sin `processId`. | zona gris / muerto (comentario) | `Failure` con stderr cuando `ExitCode != 0`, y `effectObserved: RiskPolicy.ShellMayChange(...)`. Corregir el comentario. |
| 38 | External/WindowsDeviceControlAdapter.cs:1946-1951; PC:1659, 1667; EN:141 | R4, R2 | `night_light` está en el enum y en los ejemplos («prende la luz nocturna»), pero el código siempre devuelve `night_light_public_api_unavailable`. | muerto | Sacarlo del enum y de las dos descripciones. |
| 39 | src/baxy_mind/data/keypad_keys.v1.json:20-21; WindowsDeviceControlAdapter.cs:799, 816, 857, 871-876, 232-236, 744-751; PC:267 | R4, R1 | Los paréntesis no se pueden pulsar nunca, porque la regex de 857 no los admite y EN dice «no parentheses». Se aceptan `× ÷ x X` y se reescriben como operadores, aunque EN dice «+ - * / only». Los comentarios de 232-236 y 744-751, y PC:267 («en primer plano»), describen el camino viejo de SendInput. | muerto / zona gris | Quitar los paréntesis del JSON y del script, aceptar sólo `+ - * /` y reescribir los comentarios. |
| 40 | External/SearchAddresses.cs:11; src/baxy_mind/data/search_addresses.v1.json:3 y campo `site` | R4 | «the same table baxy_mind.semantic.search_address reads» y «Lo lee baxy_mind.semantic.search_address»: ese módulo no existe. `Parse` (27-44) no lee el campo `site`. | muerto | Borrar las dos citas y el campo `site`. |
| 41 | src/baxy_mind/data/memory_subjects.v1.json:2-4, 20-26 | R4 | Su único lector, `Baxy.App/MemoryPanel.cs:195-214`, sólo lee `labels` y `factLabel`. Nadie lee `selectors` (frases «color favorito», «favorite color»…) ni `withoutNamingMemory`. `_doc` cita `NaturalMemoryRequestParser`, su test y `semantic.memory.memory_request`, que no existen. | muerto | Dejar sólo `labels` y `factLabel`, y reescribir `_doc`. |
| 42 | src/baxy_mind/data/screen_state_lines.v1.json:3 | R4 | `purpose` dice que «the mind reads the same states… (semantic.mission_answer.screen_states)», y eso no existe. El fondo del dato (P6, reinterpretar líneas de OCR) es de computer use. | muerto (comentario) | Quitar la frase H3. |
| 43 | External/WebBrowserAdapter.cs:1040-1056 con FetchAsync 280-295 | R2 | `if (buffer.Length + read > maximumBytes) break;` trunca a 1,5 MB en silencio, y `web.fetch` informa `totalCharacters` del texto truncado y `hasMore:false`. | zona gris | Devolver `truncated` desde `ReadBoundedBytesAsync` e informar `bodyTruncated:true`. |
| 44 | External/SearchPageReader.cs:51-78; WebBrowserAdapter.cs:153-158, 277-279 | R2 | Estado no exitoso, tipo no HTML, redirección a una dirección no pública y demasiadas redirecciones salen todos como `web_fetch_page_unreadable`. | zona gris | Un código por causa (`web_fetch_status_<n>`, `web_fetch_not_html`…). |
| 45 | External/NamedBrowserAdapter.cs:175-189, 53, 140-141; WebBrowserAdapter.cs:57-60, 2602-2630 | R4 | La rama de Bing (177-189) no puede devolver nada que no haya devuelto ya 170-174, y su comentario («must retain the exact public query») es falso. `requestedBrowser` siempre vale lo mismo que `browser`. El constructor `WebBrowserAdapter(string dataRoot)` no tiene llamadores. `SendAsync` tiene un único llamador, una rama `else` inalcanzable y duplica a `CommandAsync`. | muerto | Borrar 175-189, `requestedBrowser`, el constructor y `SendAsync` (usar `CommandAsync`). |
| 46 | Audio/WindowsAudioControlProvider.cs frente a External/WindowsAudioAdjustmentAdapter.cs:8-109; WindowsAudioControlProvider.cs:22-25, 744-749 | R4 | Dos mecanismos para el volumen maestro: `audio.volume` (intento durable, mutex y reconciliación) y `audio.volume.adjust` (escritura directa con otro recibo). Además, un constructor sin argumentos y `GetDefaultStateDirectory` sin llamadores. | zona gris (apilado) / muerto | Llevar `adjust` por `WindowsAudioControlProvider` y borrar el adaptador y el código sin llamadores. |
| 47 | Tasks/LocalTaskStore.cs:45-58; PC:1764-1774; Core TaskHandlers.cs:17, 227-250 | R4 | `task.resolve.exact` es Internal y ningún código de `src/` la llama; sólo los tests. | muerto | Borrar. |
| 48 | src/Baxy.Kernel/Policy/RiskPolicy.cs:62-67 | R5 | `if (… "system.power" …) return PolicyDecision.Allow;`: reiniciar, apagar y cerrar sesión (`ExitWindowsForceIfHung`, `External/WindowsPowerTransitionAdapter.cs:39`) cierran todas las apps del dueño sin preguntar. | permitido-dudoso (decisión del dueño: «apagar / cerrar sesión van directos») | Si se mantiene, borrar «with confirmation» de las descripciones (fila 31). |
| 49 | WindowsKnownFileAdapter.cs:385-388; LocalFilesystemProvider.cs:84; Notes/LocalNoteStore.cs:345-349; Tasks/LocalTaskStore.cs:79-83; SteamLocalAdapter.cs:166-169 | R1 | `Contains(query…)` en `file.find`, `filesystem.search`, `note.search`, `task.search` y `game.catalog.list`. Son herramientas de búsqueda declaradas, y el patrón lo elige el modelo. | permitido-dudoso | Si se quiere quitar toda interpretación: comodines explícitos (`MatchesSimpleExpression`), o en `game.catalog.list` devolver la lista entera. |

**Revisado y permitido (se mantiene):**
- `SearchPageReader.IsPublicPageAddress`: protege la red local.
- `SearchAddresses`: verificación posterior por la estructura de la URL.
- El parseo de DuckDuckGo lite y del RSS de Google News.
- Los códigos de liga de ESPN.
- Las etiquetas de la propia interfaz de Spotify, Netflix y la Calculadora.
- El diagnóstico de cierres por el esquema de cada evento (e0d22fd43).
- `network.status` por el nivel de conectividad de Windows (c842a4e7a).
- El ping a un host que da el modelo.
- `media.control` por id SMTC comparado entero (489135edc).
- `package.install`, `package.uninstall`, `game.*.uninstall/cancel` y `system.recyclebin.empty`: su riesgo es Installation o WorkLoss, así que confirman.
- `ShellMayChange` para `shell.command.run`. El comando corre en un `powershell.exe` oculto, nunca en la terminal de la persona.
- Relecturas por hash en `file.write`, `file.edit`, `move`, `copy` y `web.download`.
- Borrar en carpetas conocidas va a la Papelera de Windows con verificación (f690c0c75).
- `fullPath` en los recibos de escritura (cf3acc126).

No se encontró ninguna salida de datos del dueño a servicios remotos, salvo la ubicación por IP (fila 25) y el correo o evento pedido en Outlook.

### Resumen

**Lo arreglado.** La ruta `web.search` quedó limpia: enrutador, reescrituras, pertinencia, divisas, deportes, lugares y extractos se sustituyeron por argumentos tipados y la fuente tal cual. También el ranking de Spotify, `routine.*`, el raspado de Bing, los colores por nombre, el calendario por Graph y las subcadenas de juego y Wi-Fi.

**Lo que queda, por regla:**
- **R1.** Igualdades «casi exactas» sobre los argumentos del modelo:
  - el geocodificador del clima (regex de clases de región y cualquier palabra compartida);
  - el sandbox y `file.read`/`file.edit` con ruta completa;
  - `memory.recall exact` y el olvido por tema por subcadena;
  - el destinatario del correo;
  - Netflix y Disney+;
  - el «ya sonaba» de Spotify;
  - el volumen por app.
- **R2.**
  - Recibos que dicen efecto cuando el estado ya era el pedido (SMTC y mpv), o que pierden la causa («ya estaba», «no instalado», fallos de Outlook y de `web.fetch`).
  - Un olvido de memoria correcto que se informa como fallo.
  - Descripciones que prometen confirmaciones inexistentes.
- **R3.** `client.channel.locate` puede escribir en el navegador de la persona porque busca Discord por el título de la ventana.
- **R5.** `system.process.terminate.named` mata el árbol entero de procesos.
- **R4.** El grueso del muerto y lo apilado:
  - dos backends de avisos;
  - dos controles de Spotify y un tercer camino por la API web;
  - dos lectores de manifiestos de juegos;
  - dos papeleras y cinco resoluciones de carpetas conocidas;
  - dos rutas de volumen maestro;
  - la papelera privada del sandbox con `trash.restore` imposible;
  - la pareja de Steam preparar/confirmar y `task.resolve.exact`;
  - el `switch` de respaldo del dispatcher;
  - `WindowsInventoryAdapter`;
  - `night_light`;
  - datos y comentarios que citan la mente semántica (`search_addresses`, `memory_subjects`, `screen_state_lines`).

**Recuento:** 15 violaciones, 20 zonas grises, 12 muertos y 2 permitido-dudoso. Las filas mixtas se cuentan por su severidad principal.

## App, FieldUi y Setup


Copia congelada `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew-audit` (detached en `bde62d76c`, hub/baxy-renew). Fue
de solo lectura: no se compiló, no se ejecutó nada y no se tocó ningún archivo. Se leyeron enteros `NativeTurnLoop`,
`MainWindowViewModel`, `FieldProductChannel`, `FieldBridgeContract`, `Heartbeat`, `MemoryPanel`, `ScreenViewProjection`,
`SensitiveText`, `TurnVisibleFacts`, `PendingOperationConfirmation` y `field-native-bridge.js`. De `MindRuntimeDiscovery`,
`MemoryOperationProtection`, `MindSidecarClient`, `HeartbeatMoment`, `OperationResponseProjection`, `PreparedOperation`
y `ProductConductorHost`, más los paneles de FieldUi (`SettingsPanel`, `FieldCenter`, `MemoryPanel`, `ToolsPanel`,
`App.tsx`, `useEventStream`) y el contrato de paquete de Setup, se leyeron las partes pertinentes. Para contrastar se
consultaron `src/baxy_mind/mind.py`, `voice.py`, `voice_output.py` y `__main__.py`, además de `ProductCatalog.cs` y
`RiskPolicy.cs`.

### 1. Hallazgos que siguen en el código

#### Bucle nativo, confirmación y latido

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| H1 | Baxy.App/NativeTurnLoop.cs:251-253 (comentario 31-33); ProductCatalog.cs:311-331 | R3 | `WritesInThePersonsWindow` nombra 8 operaciones a mano y deja fuera `clipboard.copy` (verificador `clipboard.copy.win32.foreground.sendinput…`: manda Ctrl+C a la ventana al frente) y `client.channel.locate` («buscador rápido del cliente de escritorio (Discord: Ctrl+K)»). Las dos son `privacy_sensitive`/`low_reversible`, así que **en un latido se ejecutan sin que nadie lo pida y teclean en la ventana de la persona**. El comentario 31-33 («one that would type or click in the person's windows is held») es falso para ellas. | violación | En el latido, retener toda operación que no sea `read_only` (o marcar en el catálogo, con un atributo tipado, «actúa con entrada en una ventana») en vez de la lista de nombres. |
| H2 | NativeTurnLoop.cs:66-70 y 231 (G1 anterior) | R5 / R1 | `ProposedRisks = {"work_loss","recoverable_delete","external_communication","installation","monetary"}` es una copia a mano del mapeo del kernel. Todo lo demás corre solo en un latido: `shell.command.run` (`low_reversible`, ProductCatalog.cs:1516-1526; en modo Bypass el kernel permite cualquier comando, también un `Remove-Item` sin papelera), `file.write` (sobrescribe), `browser.control close`, `wifi.disconnect`, `system.settings.set`. | zona gris | Derivar la retención de `ProductCatalog.ToPolicyRisk` más el modo: en un latido se retiene todo lo que en modo Normal pediría confirmación o no es `ReadOnly`. |
| H3 | NativeTurnLoop.cs:231; ProductCatalog.cs:1896 (`web.search` `ReadOnly`); Heartbeat.cs:115-118; HeartbeatMoment.cs:56-71; MainWindowViewModel.cs:313-380 | R3 | El momento del latido lleva los títulos de las ventanas, las últimas 6 líneas de la conversación y los valores de la memoria (`moment["memory"]`). En el latido, `web.search`, `web.fetch`, `web.news.headlines` y `weather.current` no se retienen: el modelo puede mandar a DuckDuckGo o Wikipedia una consulta armada con datos del dueño **sin que el dueño haya pedido nada**. | zona gris | En el latido, retener como propuesta toda operación que salga del equipo (con un atributo tipado del catálogo, «sale a la red»). |
| H4 | Heartbeat.cs:94 frente a 115-121; MainWindowViewModel.cs:338-352; NativeTurnLoop.cs:200-201 | R2 / R5 | El latido comprueba `CanBeat` (sin confirmación pendiente) y después espera `memory.list` y `schedule.alarms` en el core (hasta 10 s cada una) antes de `RunBeatAsync`. Esa llamada sólo mira `_turnGate.Wait(0)`. Si mientras tanto un turno de la persona dejó una confirmación pendiente, la primera llamada del latido hace `DropPending()` («Anything else the person asked for replaces a confirmation», aunque en un latido nadie pidió nada). Cuando la persona dice «sí», recibe `nothing_pending`. | zona gris | Dentro de `RunBeatAsync`, ya con el turno tomado, volver a comprobar `!_loop.HasPendingConfirmation`. En `ExecuteAsync`, no descartar nada cuando `_beat`. |
| H5 | NativeTurnLoop.cs:222-228; MemoryOperationProtection.cs:236-244 y 296-304; SensitiveText.cs:86-89 (G4 anterior) | R2 | Un `memory.save` cuyo valor contiene «contraseña», «password», «rut» o «ssn» lanza `"La memoria requiere el canal sensible."`. El bucle lo atrapa y sólo le devuelve al modelo `"arguments_invalid"` con `argumentsGiven`: la causa se pierde y el modelo no sabe que debía usar `memory.sensitive.save`. En la transcripción, la línea entera se ve como `••••••` por una palabra de tema (MainWindowViewModel.cs:317). | violación (fallo sin causa) | Que la excepción lleve un código cerrado (`value_sensitive`) y ponerlo en `error`. Disparar el enmascarado sólo con forma de credencial (`LooksLikeCredentialToken` y prefijos), no con palabras de tema. |
| H6 | NativeTurnLoop.cs:227-228 y 473; ProductConductorHost.cs:99-110 (G3 anterior) | enmascarado / R3 local | `["argumentsGiven"] = arguments.DeepClone()` también en operaciones de memoria. `Record` vacía `Arguments`, pero la observación con el valor viaja en `NativeTurnStep.Observation`, y el conductor la escribe en `events.jsonl`. | zona gris | Omitir `argumentsGiven` cuando `IsMemoryOperation(operation)`. |
| H7 | MemoryOperationProtection.cs:70-72 y 199-209 (V3 anterior) | R1 / R4 | `ResolveWireOperationName` cambia la herramienta que eligió el modelo: `"memory.save" when sensitivity is "sensitive" or "secret" => "memory.sensitive.save"` y `"memory.forget" when scope == "session" => "memory.session.clear"`. El enum que ve el modelo excluye esos valores (ProductCatalog.cs:1177 y 1210), así que la rama sólo se alcanza cuando el modelo se sale de su enum, y entonces la App reescribe su decisión. | violación (muerta o reescritura) | Borrarla: el nombre que viaja es el que eligió el modelo, y el kernel rechaza el argumento con su causa. |
| H8 | NativeTurnLoop.cs:330-337 | confirmación | En `AnswerProposalAsync`, si el kernel desafía la propuesta del latido, la App contesta el reto en el acto con el «sí» que la persona dio a la redacción del modelo. La persona nunca ve el reto del kernel. | permitido-dudoso | Aceptable si la propuesta que vio la persona incluía los argumentos exactos (la observación los da, línea 243). Si no, devolver el reto como `needs_confirmation`. |
| H9 | NativeTurnLoop.cs:187, 201, 242, 267 y 378 | protocolo (llamadas pendientes repetidas) | Dentro de un turno, `final = … \|\| HasPendingConfirmation` ya corta la repetición (74725b320), y la mente marca `NOT_RUN` a las llamadas en cola. Entre turnos: si la persona dice «sí» y el modelo, en vez de `confirm_pending`, vuelve a llamar la misma operación, la línea 201 descarta la pendiente y el kernel vuelve a preguntar, sin fin. `"next"` no nombra `confirm_pending`. No hay autoaprobación. | permitido-dudoso | Presentación: `"next": "ask the person …; when they answer, call confirm_pending"`. |

**V1 (el modelo aprueba su propia llamada riesgosa): arreglado.** `AnswerPendingAsync` (NativeTurnLoop.cs:258-269)
rechaza `confirm_pending` con `only_the_person_answers` si es un latido (`_beat`), si no es la primera llamada del turno
(`_moves != 1`) o si llega en el mismo turno que levantó la pregunta (`_askedInTurn >= _turn`). Los botones Sí/No
(`mind.confirm`, mind.py:436-450) entran como turno nuevo de la persona. `CanBeat` excluye una confirmación pendiente
(MainWindowViewModel.cs:335), salvo la carrera de H4.

#### Lo que vuelve al modelo y lo que ve la persona (R2)

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| H10 | OperationResponseProjection.cs:57-64 y 32-55 frente a mind.py:423 | R4 / R2 | La App deja pasar 48 000 caracteres en `shell.command.run` y `system.process.list` y 16 384 en lo demás, y explica que «cutting JSON makes every observation vanish». Para `ocr.read` declara `observation_size_limit` por encima de 48 000. La mente corta de nuevo, en silencio, en `observation[:6000]`. Hay dos cortadores, y el de la App y su comentario no valen: el modelo recibe JSON roto sin marca. | violación (apilado) | Un solo cortador: que la App corte al límite real de la mente con su marca y que la mente no corte, o al revés. |
| H11 | FieldProductChannel.cs:844-863 (`CurrentSettings`); SettingsPanel.tsx:458-541 (pestaña Transcript, visible) | R2 | Valores fijos presentados como estado: `"sttModel" = "parakeet-tdt-0.6b-v3-int8"` (el lanzador carga `parakeet-ultra-sherpa-int8-oli`, scripts/run_renew.cmd:18), `"ttsProvider" = "sherpa-onnx piper (local)"` (la mente usa `piper.exe`, voice_output.py:141-151), `"ttsVoice"`, `"wakeWord" = "Baxy"` y `"voiceEnabled" = IsMicAvailable`. La pestaña dice «the rest will fetch on first use» (518), pero nada descarga, y «LiveKit baxy is the active local wake model» (538). `VoiceInventory` (815-841) ya mira los archivos: **V7 está arreglado a medias**. | violación | Quitar esos campos de `/settings` o tomarlos de las rutas `BAXY_RENEW_*` que lee la mente. Borrar las dos frases. |
| H12 | SettingsPanel.tsx:77 y 315 (pestaña Connection, visible); mind.py:456 | R2 | «max tokens per reply» muestra `maxTokens: 1280` de los DEFAULTS de la vista porque la App no lo envía. La mente usa `"max_tokens": 512`. El aviso «the agent talks to a llama-server you start separately» (319) es falso y sólo lo tapa el parche JS (H24). **V6:** el contexto quedó arreglado (`ContextSize` lee `BAXY_RENEW_CTX` con 49152, FieldProductChannel.cs:930-937, igual que `__main__.py:24`), y también se quitó «/ 4k». | violación | Quitar el campo `maxTokens` y ese aviso del código fuente. |
| H13 | FieldProductChannel.cs:376-379 y 399-403; MainWindowViewModel.cs:213; SettingsPanel.tsx:996-1009 (G14 anterior) | R2 | `PUT /settings` → `{"ok":true}` sin aplicar nada. `/agent/restart` devuelve `ok = IsReady` sin reiniciar (`if (_isInitializing \|\| IsReady) return;`), y la vista avisa `'agent restart triggered'`. Hoy queda latente porque el puente esconde esos botones. | zona gris | `405 settings_read_only`; `409 already_running`; borrar el aviso. |
| H14 | FieldProductChannel.cs:302-313, 339-361 y 391-397 (G15 anterior) | R2 / R4 | Textos fijos y falsos: `/profile` `"vram4"`, `/agent/modes` `"Planner local con selección segura de herramientas"` (no hay planificador), `/agent/personas` `"BAXY local"`. La pestaña Prompt (visible) muestra `"La mente local de BAXY administra su prompt…"` en lugar del prompt. | zona gris | Borrar las tres rutas. En Prompt, mostrar el prompt real o quitar la pestaña. |
| H15 | MainWindowViewModel.cs:417; FieldBridgeContract.cs:162-165; FieldProductChannel.cs:740-754 (G13 anterior) | R2 | El código del fallo (`mind_unavailable`, `decision_unavailable`, `turn_failed`) ahora termina en `StatusDescription`, pero `ResolveProgress` devuelve `null` cuando está lista y sin trabajo, y el estado queda en `idle`. La persona escribe y no ve ni respuesta ni causa. | zona gris | Publicar `LastTurnFailure` en el evento `agent` y que la vista use su `convState 'error'`. |
| H16 | FieldCenter.tsx:95 (G16 anterior) | R2 | `'llama-server offline · waiting for connection…'` aparece cuando `!agent.healthy` (`IsReady && !HasStartupError`), que es un estado del core y no de llama-server. | zona gris | Mostrar el código observado. |
| H17 | MemoryPanel.tsx:80-83 (G7 anterior) | R2 (texto fijo) | `` toastError(`no pude ${verb} …`) `` y «no pude confirmar si se pudo … · muestro lo guardado» hablan en primera persona de BAXY. | zona gris | Estado neutro (`${verb} · falló · ${code}`). |
| H18 | useEventStream.ts:311-317 (V9 anterior) | R2 / R4 | `msg: 'No te entendí — probá de nuevo'` es una frase fija de BAXY para `voice_no_speech`, un evento que nadie emite (la mente emite `error`, `wake_detected`, `partial` y `state`; voice.py:189-273). | muerto | Borrar el caso. |
| H19 | App.tsx:364-374 | R2 | Cualquier respuesta no OK de `/sessions/new`, incluido el `409 turn_in_progress` (FieldProductChannel.cs:216-219), se publica como `'new session · backend unreachable; UI-only reset'`: la causa es falsa y no se reinicia nada. El comentario «the backend pushes its own SYSTEM activity entry» también es falso: la App sólo publica `log_clear` y `session`. | zona gris | Mostrar el código del error y borrar el comentario. |
| H20 | MainWindowViewModel.cs:680-686 y 697-731 | R2 (voz) | Un transcript que llega mientras hay un turno en curso se descarta en silencio (`if (_isDisposed \|\| !IsInputEnabled) return;`). El evento `voice.event` `"error"` de la mente (voice.py:189) no tiene caso en `OnMindVoiceEvent`, así que un fallo del micrófono no deja estado. | zona gris | Publicar un estado (`voice_dropped_busy`, `voice_error`) en lugar de callar. |
| H21 | ScreenViewProjection.cs:76 (G11 anterior) | R1 (paso dictado) | `"(ninguno: la ventana no expone sus controles; actúa por el texto en pantalla)"` le dice al modelo qué hacer. | zona gris | `(ninguno)`. |
| H22 | ScreenViewProjection.cs:52 y 120-125 (G12 anterior) | R2 | Sin el dato `foreground` dice `", al frente"`. La proyección pierde `status`, `error` y `effectUncertain` del recibo. | zona gris | Escribir el frente sólo si se observó y copiar esos tres campos. |

#### Entorno (R4)

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| H23 | MindRuntimeDiscovery.cs:173-182, 285-293, 299-353, 355-359, 597 y 630 (V8 anterior, a medias) | R4 | Arreglado: las 6 variables `BAXY_MIND_STT_DIR`, `BAXY_VOICE_WAKE_*`, etc. ya no se publican. Siguen: (a) `SetIfMissing("HF_HUB_OFFLINE", "1")`, que no lee nadie (la mente sólo importa `sherpa_onnx`, `sounddevice` y `numpy`), y que además entra en la huella del entorno. (b) El registro **exige y verifica por hash** `stt_dir`, `wake_manifest` (con esquema `baxy-wakeword-v1`, aunque la mente lee una carpeta con `config.json`), `tts_model` y los adaptadores `cpu_prose_adapter`/`decider_adapter`, y no publica ninguno: son archivos que nadie carga, y si falta el STT registrado la mente entera no arranca (`stt is null → return null`). (c) La App no publica `BAXY_RENEW_STT_DIR`, `_WAKE_DIR`, `_TTS_MODEL` ni `_PIPER_DIR`, y la voz sólo existe si se arranca con `run_renew.cmd`. (d) El comentario 342, «SAPI remains the documented fallback», es falso: voice_output.py sólo tiene Piper. | violación | Publicar las cuatro `BAXY_RENEW_*` desde el registro (con una carpeta para wake) y dejar de exigir lo que no se usa (adaptadores, manifiesto). Borrar `HF_HUB_OFFLINE` y el comentario de SAPI. |
| H24 | MainWindowViewModel.cs:128-132 (y cada `StatusText = …`) | R4 | `StatusText` («Iniciando», «Lista», «Trabajando»…) se escribe y no lo lee nada: ni bindings, ni el canal, ni el conductor. | muerto | Borrar la propiedad. |
| H25 | MindSidecarClient.cs:63-74; voice.py:65-70 | R4 | En `MindVoiceStatus`, `VadAvailable`, `TtsAvailable`, `AecAvailable`, `DuckingAvailable`, `Mode`, `Listening` y `Speaking` no se leen nunca. La mente manda `"vad": False, "aec": False, "ducking": False` fijos. | muerto | Quitar esos campos de los dos lados. |

#### Código muerto o apilado (R4)

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| H26 | Baxy.Setup/PackageContract.cs:35-47, 56-57, 95-96 y 135-136; scripts/build_setup.ps1:29-30 y 66-67; ProductPackageVerifier.cs:177, 287 y 358-378 | R4 | El contrato de paquete fija `FieldUi/assets/index-CjozYCnU.css` e `index-D3QuhrLm.js`, pero el dist actual es `index-CQzIIbEB.js` / `index-_KMQUKwF.css`, y el verificador exige la lista exacta. Además el paquete no lleva `baxy_mind` ni el registro de la mente. Último cambio en Setup: 2026-10-06. **El instalador no puede empaquetar ni instalar el producto Renew actual.** | muerto (mecanismo de un producto anterior) | Generar la lista desde el build e incluir la mente, o sacar Baxy.Setup de la solución hasta que Renew se empaquete. |
| H27 | DurableRetryStore.cs (582 líneas); PreparedOperation.cs:164-178 y 248-254; MainWindowViewModel.cs:243-249 | R4 (y privacidad local) | Cada arranque retira todo (`registry.RetireWhere(static _ => true)`). La recuperación del core dentro de la sesión usa el registro en memoria (`_retryableOperations ??=`). La cola en disco no restaura nada nunca, pero en cada llamada escribe los argumentos (texto tecleado, cuerpos de correo, comandos) en `shell/retry-outbox.v1.json`. El comentario de `RetireWhere`, «retires what a computer-use mission … left; every other entry keeps its identity across the restart», ya no describe lo que hace. | muerto (apilado) | Registro sólo en memoria. Borrar `DurableRetryStore` y la carga del constructor. |
| H28 | MemoryOperationProtection.cs:455-507; MemoryPanel.cs:277 | R4 | `PendingMemoryConfirmation` es una copia de `PendingOperationConfirmation` (mismos campos y el mismo `ConfirmationChallengeParser.TryParse`), con un `IsMemoryOperation` de más. El bucle ya usa la segunda para memoria. | muerto (duplicado) | Usar `PendingOperationConfirmation` en `MemoryPanel` y borrar la copia. |
| H29 | MemoryPanel.cs:277-282 (G5 anterior) | confirmación | El panel contesta solo, con el token, el reto del kernel para cualquier operación de memoria (`memory.correct` incluida), no sólo para el olvido de dos pasos. Es un gesto de la persona en la vista propia de BAXY. | permitido-dudoso | Contestar sólo en `memory.forget`. |
| H30 | FieldBridgeContract.cs:40-45, 58-100, 177-187 y 215-234; FieldProductChannel.cs:445-451 y 748 (V12 anterior) | R4 | Siguen mapeadas descripciones que nadie escribe («Ejecutando paso », «Mirando la pantalla», «Preparando los pasos», «Esperando confirmación de memoria», `awaiting_mission_resume`, «Conexión interrumpida», «La voz se degradó…»…). `progressLabel` siempre llega `null`. `StatusDescription == "Te escucho"` nunca se cumple, porque el VM escribe «Te escucho…» (MainWindowViewModel.cs:718). | muerto | Usar códigos cerrados y mapear sólo los que se escriben. |
| H31 | SettingsPanel.tsx:1, 17-30, 33-104 (`followUpClosePhrases: 'gracias\nlisto\nya está\ncancelar'` en 89, `gameProcesses: 'steam.exe…'` en 92, `GEMMA4_*`) (V10 anterior) | R4 / R1 (listas inertes) | El formulario Gemma 4 completo sigue ahí; 8 pestañas se esconden en tiempo de ejecución. | muerto (apilado) | Borrar las pestañas ocultas y sus campos. |
| H32 | Assets/field-native-bridge.js:184-284 (V11 anterior); además 131-136 | R4 | El `MutationObserver` reescribe el DOM con regex (`/gemma\s*4/i`, `/llama-server you start separately/i`…), desactiva todos los controles y esconde botones. Los adjuntos tienen tres mecanismos para el mismo «no»: el botón y la subida de FieldCenter.tsx:139-160 y 226-233, el `FormData → 501` del puente y `/upload → 501` del canal (FieldProductChannel.cs:410-413). | muerto (apilado) | Corregir la fuente React y borrar el overlay, el botón de adjuntar y la ruta. |
| H33 | ToolsPanel.tsx:57-80 frente a FieldProductChannel.cs:297-300; App.tsx:133-156 y 145; useEventStream.ts:272-310; FieldProductChannel.cs:405-408 y 495-499; ActivityPanel.tsx:141; index.html:11-16 (V16 anterior, a medias) | R4 (funciones retiradas) | Arreglado: TriggersPanel ya no existe, `/tools` lista el catálogo y no hay rutas de rutinas. Sigue muerto: el formulario «run» de ToolsPanel llama a `/tools/execute`, que siempre responde 403; el banner `vision_threshold` y `/agent/recycle_server` (siempre 409); las ramas `prewarm_*`; `NormalizeActivitySource`, que acepta `GEMMA`, `TRIGGER`, `THOUGHT`, `BOOT`, `CONTEXT`, `MEMORY` y `TOOL` cuando la vista sólo postea `SYSTEM` (App.tsx:373 y 378), y que es un resto de los disparadores; los enlaces a Google Fonts, bloqueados por MainWindow.xaml.cs:404-420. | muerto | Borrar todo eso. |
| H34 | src/baxy_mind/data/memory_subjects.v1.json:2-4 y 20+; Baxy.App.csproj:28; MemoryPanel.cs:192-194 (V5 anterior) | R1 / R4 | `"selectors": {"favorite_color": ["color favorito",…]}` y `"withoutNamingMemory"` son listas de frases que no lee nadie. `_doc` cita `NaturalMemoryRequestParser`, que no existe. El comentario «one file with the mind» es falso: la mente no lee el archivo. | violación (datos sin lector) | Quitar `selectors`, `withoutNamingMemory` y los `_doc` obsoletos, y corregir los comentarios. |
| H35 | MemoryPanel.cs:203-214 (G6 anterior) | R1 (vocabulario fijo) | `labels` traduce 11 selectores a palabras fijas y llama «dato» a todo `historical_fact_*`. | zona gris | Mostrar el selector (`Replace('_',' ')`) y borrar el recurso. |
| H36 | OperationResponseProjection.cs:16-20 (V14 anterior) | R4 | La rama `HonestyCorrection`: ninguna respuesta viva la trae; sólo existe en el contrato y para deserializar el diario. | muerto | Borrar la rama de la App. |
| H37 | TurnVisibleFacts.cs:23 y 32-36 (resto de V15) | R4 | `Event` sólo se llama con `failure` y `status`, así que las ramas `"error"`, `"confirmation"` y `"clarification"` están muertas. | muerto | Volver privado `Event` y quitar esas ramas. |

#### Latido: ítems anteriores que siguen igual

| # | Archivo:líneas | Regla | Qué hace | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| H38 | HeartbeatMoment.cs:27-45 (G8) | R1 | `Speaks(activity) => activity == Free`, con umbrales de la App (pantalla completa más GPU → «jugando», micrófono ajeno → «llamada»). | zona gris (decisión del dueño por confirmar) | Anotarlo como decisión del dueño o pasarle al modelo las señales crudas. |
| H39 | Heartbeat.cs:151-166 (G9) | R1 | `foreach (int threshold in new[] { 20, 10 })` y `idle_min >= 10`: umbrales de la App. | zona gris | Confirmarlos con el dueño. |
| H40 | Heartbeat.cs:53 y 171-183 (G10) | R2 | `Note($"download finished: {name} en Descargas")` se dispara con `Created`, cuando la descarga puede estar empezando. | zona gris | `file appeared in Downloads: {name}`. |

### 2. Estado de los ítems de `auditoria-reglas-app.md`

| Ítem | Estado en `bde62d76c` |
|---|---|
| V1 | **Arreglado** (NativeTurnLoop.cs:77-80 y 258-269). Queda la carrera H4. |
| V2 | **Arreglado**: `Prepare` usa `EnsureMemoryOperation` (MemoryOperationProtection.cs:66) y `EnsureParserMemoryOperation` y `memory.configure` ya no existen. |
| V3 | **Sigue** (H7). |
| V4 | **Arreglado**: `KeysAsync`, `Candidates`, `Words` y `Fold` ya no existen. |
| V5 | **Sigue** (H34). |
| V6 | **Arreglado a medias**: el contexto (49152) y «/ 4k» están bien; sigue `maxTokens` 1280 y el aviso falso (H12). |
| V7 | **Arreglado a medias**: el inventario mira los archivos; `CurrentSettings` sigue con valores fijos (H11). |
| V8 | **Arreglado a medias**: se fueron las 6 variables sin lector; quedan `HF_HUB_OFFLINE`, la verificación de archivos que nadie carga y la falta de `BAXY_RENEW_*` (H23). |
| V9 | **Sigue** (H18). |
| V10 | **Sigue** (H31). |
| V11 | **Sigue** (H32). |
| V12 | **Sigue** (H30). |
| V13 | **Arreglado por borrado**: `ConsultedSource`, `SourceUrl` y `/source/open` ya no existen. La atribución CC BY-SA de D35 queda sin implementar; eso lo decide el dueño. |
| V14 | **Sigue en la App** (H36). |
| V15 | **Arreglado en lo grueso**: `AgentFieldGraph`, los restos del planificador en `PreparedOperation`, las inyecciones y `AuthenticateForOutbox` ya no existen. Quedan las ramas de `TurnVisibleFacts` (H37). |
| V16 | **Arreglado a medias**: TriggersPanel ya no existe y `/tools` tiene datos; queda el resto de H33. |
| G1 | **Sigue**, con agujeros nuevos (H1, H2, H3). |
| G2 | Depende del kernel (P1). La App sigue transportando la entrada a la ventana al frente en turnos de la persona; no se reauditó aquí. |
| G3 | **Sigue** (H6). |
| G4 | **Sigue**, y ahora el fallo no dice su causa (H5). |
| G5 | **Sigue** (H29). |
| G6 | **Sigue** (H35). |
| G7 | **Sigue** (H17). |
| G8, G9, G10 | **Siguen** (H38, H39, H40). |
| G11, G12 | **Siguen** (H21, H22). |
| G13 | **Sigue** (H15): el código llega a `StatusDescription`, pero no a la vista. |
| G14 | **Sigue** (H13). |
| G15 | **Sigue** (H14). |
| G16 | **Sigue** (H16). |

**Regla 3, red:** la App no tiene salidas de red propias. No hay `HttpClient` ni sockets salientes; el `fetch` externo
de la vista devuelve 403 (field-native-bridge.js:137-142) y WebView2 bloquea todo recurso externo (MainWindow.xaml.cs:404-420).
Lo único de la App que puede sacar datos del dueño es la consulta web que lanza un latido (H3).

### Resumen

El arreglo central de hoy se mantiene: el modelo ya no puede contestarse su propia confirmación, ni en el turno que la
levantó ni dentro de un latido. El latido, en cambio, todavía actúa por su cuenta con lo que su lista hecha a mano deja
pasar. Puede teclear Ctrl+C o Ctrl+K en la ventana de la persona (H1), lanzar una búsqueda web armada con títulos de
ventana o memoria del dueño (H3), ejecutar comandos de consola en modo Bypass (H2) y, por una carrera, descartar la
confirmación que la persona tenía pendiente (H4). En honestidad, el chat publica sólo lo que escribió el modelo, pero
los ajustes visibles siguen mostrando datos que nadie observó (H11, H12), varios fallos no dicen su causa (H5, H15, H19)
y la App y la mente cortan las observaciones con dos límites distintos, el de la mente en silencio (H10). Del lado del
código muerto quedan el formulario Gemma y su parche de DOM, mapeos de estado que nadie escribe, la cola durable que no
restaura nada pero guarda en disco lo que se teclea (H27), un duplicado de la confirmación pendiente (H28), la
verificación de archivos de voz que nadie carga (H23) y un instalador cuyo contrato de paquete no corresponde al build
actual ni incluye la mente (H26).

**Recuento:** violación 8 (H1, H5, H7, H10, H11, H12, H23, H34); zona gris 17 (H2, H3, H4, H6, H13, H14, H15, H16,
H17, H19, H20, H21, H22, H35, H38, H39, H40); muerto 12 (H18, H24, H25, H26, H27, H28, H30, H31, H32, H33, H36, H37);
permitido-dudoso 3 (H8, H9, H29).

## Mente, datos y jueces


Copia congelada: `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew-audit` (hub/baxy-renew `bde62d76c`).
Alcance: `src/baxy_mind/*.py`, `src/baxy_mind/data/*.json`, `scripts/run_renew.cmd` y los jueces de `scripts/renew/*.py`
con `catalog_equivalence.json`. Cada línea citada se leyó en el código. Los lectores de cada JSON se buscaron con grep
en todo el repositorio, C# incluido, sin bin/ ni obj/. Para medir cuánto afloja el juez se miró además el banco de
práctica de `F:\BAXYeval\renew_v1` (`practica/decision2.json`, `e2e/practice.json`). Los bancos sellados no están en
este equipo.

### Hallazgos

| # | Archivo:líneas | Regla | Qué hace (cita breve del código) | Severidad | Arreglo mínimo |
|---|---|---|---|---|---|
| 1 | src/baxy_mind/mind.py:422-423 | R2, R4 | `"content": observation[:6000] + "\n[En este turno: …]"`. Corta en silencio, sin marca, cada resultado a 6000 caracteres. El kernel y la App ya acotan con su propio aviso: 16 384 caracteres, o 48 000 para `shell.command.run`, `ocr.read` y `system.process.list` (OperationVisibleFacts.cs:60-65; OperationResponseProjection.cs:57-64 y `"… [respuesta truncada]"` en 71-75). Su comentario dice que lo subieron justo porque *«the final could say nothing of what came out»*. La mente deshace ese arreglo: el modelo lee una lista o salida a medias como si fuera entera, y `observed` va al final del JSON. El resumen `[En este turno]` sí conserva el estado. | **violación** (resultado recortado sin decirlo; dos topes apilados) | Quitar el `[:6000]`, porque el tope ya lo ponen el kernel y la App. Si hace falta uno aquí, que diga `[recortado: N de M caracteres]`. |
| 2 | mind.py:471-485 | R1, R2, R4 | `except json.JSONDecodeError: arguments = {}`, y `if wire in {...} or wire in self.wire_to_op:`. Una llamada a una herramienta que no existe se descarta sin dejar rastro en la conversación, y el modelo nunca sabe que falló. Unos argumentos que no son JSON, o no son un objeto, se cambian por `{}`, y la transcripción (482-485) registra `{}` como si el modelo hubiera llamado así. La App ya tiene su rechazo honesto para los dos casos: `unknown_operation` y `arguments_invalid` con `argumentsGiven` (NativeTurnLoop.cs:208-228). Este filtro previo lo esquiva. | zona gris (filtra y reescribe las llamadas del modelo; mecanismo apilado) | Pasar toda llamada tal cual, con su nombre y el texto crudo de los argumentos, y que el rechazo sea la observación que la App ya escribe. |
| 3 | mind.py:346-365 | R2 | El latido pide la decisión con `"max_tokens": 200` y un esquema JSON de seis campos de texto libre. Después hace `except json.JSONDecodeError: decision = {}`, luego `intervene = ... else False` y devuelve `"kind": "silence"`. Una decisión cortada por el tope de tokens, o ilegible, se vuelve silencio sin ningún `failure`. El banco de escenas la cuenta como acierto en las escenas que esperan silencio (ver #15). | zona gris (un fallo se presenta como decisión) | Devolver `failure: "beat_decision_unreadable"`, o un tipo propio, para que la App y el banco lo cuenten como fallo, y subir el tope. |
| 4 | src/baxy_mind/__main__.py:22-24; llm_server.py:41, 47 | R4, R3 latente | `extra = os.environ.get("BAXY_RENEW_SERVER_ARGS", "").split()` se añade después de `"--host", "127.0.0.1"`. Nadie fija esa variable: ni la App, ni `run_renew.cmd`, ni los bancos, que pasan `extra_args` directamente (bench_decision.py:133). Es una perilla muerta del producto, y un `--host 0.0.0.0` puesto en ella ganaría a la dirección de loopback. | muerto (con riesgo R3 latente) | Borrar la variable del producto y dejar `extra_args` sólo para los bancos, o rechazar `--host` y `--port` en ella. |
| 5 | src/baxy_mind/protocol.py:54-111 (con 12, 15, 17, 20-21) | R4 | `class _BoundedFileDescriptorLineReader` (58 líneas). Nadie la usa, ni siquiera los tests. `read_message` lee con `sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)` (114-123). Sólo existen para ella `_READ_CHUNK_BYTES`, `_PIPE_RETRY_SECONDS` y los imports `os`, `time` y `Callable`. | muerto | Borrarla, con sus constantes e imports. |
| 6 | src/baxy_mind/llm_server.py:33, 83-84 | R4 | `self._lock = threading.Lock()` no se lee nunca. `chat(..., *, slot)` y su docstring dicen *«each slot keeps its own prefix»*, pero sólo hay un slot (`DECIDE = 0`, 16-19) y todas las llamadas pasan ese. | muerto (menor) | Quitar `_lock`, fijar `id_slot` 0 sin parámetro y corregir el docstring. |
| 7 | mind.py:20, 241-245, 263-264; data/decider_catalog.es.v1.json (174 entradas) | R4 | `spanish = _SPANISH.get(name) or str(cap.get("description"))` y luego `description = self.english.get(name) or spanish`. Hay tres fuentes de descripción para lo mismo. Comprobado con un script: las 175 operaciones `Public` de ProductCatalog tienen texto inglés. Así, la española y la de C# sólo llegan al modelo si `BAXY_RENEW_DESCRIPTIONS≠en`, y eso sólo lo hace bench_decision.py:124 (`--desc`). El `source` del JSON (línea 3) dice *«the contextual decider reads it»*, y ese decisor ya no existe. | muerto (apilado; M5/K11 **sigue**) | Una sola fuente, el JSON inglés. Borrar `decider_catalog.es.v1.json` y la variable. |
| 8 | mind.py:127-128 | R4 | `if context.get("screen_text"): lines.append("Texto en pantalla: " ...)`. La App nunca manda `screen_text`: HeartbeatMoment.cs:53-117 y Heartbeat.cs:116-118 envían `now`, `weekday`, `owner_activity`, `foreground`, `windows`, `pc`, `events`, `history`, `memory` y `reminders`. Si las escenas selladas lo traen, el banco mide un contexto que el producto no da. Esto no se pudo comprobar, porque las escenas no están en el equipo. | muerto | Borrar las dos líneas, o que la App lo envíe de verdad. |
| 9 | data/memory_subjects.v1.json:2-4, 20-26 | R4 (resto de R1) | `"selectors": {"favorite_color": ["color favorito","color preferido",…]}` y `"withoutNamingMemory"` son listas de frases de la persona y nadie las lee. El único lector, MemoryPanel.cs:194-212, lee sólo `labels.*.es` y `factLabel.es`, así que tampoco se usan las versiones `en`. El `_doc` cita `NaturalMemoryRequestParser` y `semantic.memory.memory_request`, que no existen. | muerto (V5 **sigue**) | Dejar sólo `labels` y `factLabel` (en `es`, o usar `en`) y reescribir el `_doc`. |
| 10 | data/app_places.v1.json:3, 6, 40, 47, 61 (`source` y `_about`); `names` en 9-36, 43, 54-56, 71-75; `shows` 54; `within` 57, 74; `search` y `said` 73, 75; `examples` 79-94 | R4 (resto de R1) | ApplicationPlaces.cs:166-242 lee sólo `schemes`, `places.*.address`, `gameCatalog`, `acts` (`address`, `confirm`) y `titles`. Nadie lee `names` (listas de cómo dice la persona el lugar: «fondo de pantalla», «pagina de {game}», «shop»), `shows`, `within`, `search:false` ni `said`. `examples` sólo lo lee ApplicationPlacesTests.cs:25. El `source` dice *«la mente (semantic/app_places: el lugar de un sub-objetivo)»* y describe misiones, computer use y `cu_address`, que ya no existen. El lugar `library` de Spotify (55) sólo tiene `names`. | muerto | Borrar esas claves y la entrada que sólo tiene nombres, y reescribir `source` y `_about` para que describan lo que hace ApplicationPlaces. |
| 11 | data/world_acts.v1.json:3 y 69-89; data/search_addresses.v1.json:3 (y SearchAddresses.cs:11); data/screen_state_lines.v1.json:3 | R4 | Comentarios obsoletos que citan una mente que ya no existe: *«la mente (semantic/account_acts.world_act…)»*, *«Lo lee baxy_mind.semantic.search_address»* (más `llm._search_of_address`) y *«the mind reads the same states (semantic.mission_answer.screen_states)»*. Los `examples` de world_acts sólo los lee RiskPolicyWorldActsTests.cs:22-25. | muerto (comentario obsoleto; D-K2 **sigue**) | Reescribir esos campos para que nombren sólo al lector C# real. |
| 12 | scripts/renew/bench_decision.py:69-70, 76-77; catalog_equivalence.json:22-28 (`routine.*: {"op": null}`) | Bancos | Para una operación retirada, `return kind == "conversation" and bool(reply.strip())` da por buena cualquier respuesta no vacía, también una falsa como «Listo, creé la rutina modo fiesta». Le pasa a P235 de práctica. En `call_any` basta `if op is None and kind == "conversation": return True`, que acepta incluso una respuesta vacía (`failure: empty_reply`). Le pasa a P044. | zona gris (el juez acepta lo que no debe) | En `op: null`, exigir respuesta no vacía y pasar esa línea por el juez de falsedades, o sacar esos casos del recuento en vez de darlos por buenos. |
| 13 | scripts/renew/catalog_equivalence.json:11, 12, 21 | Bancos | `"reminder.restore": {"op": "schedule.alarms", "fixed": {"action": "create"}, "args": {"reminderId": null…}}` hace que crear un recordatorio nuevo cuente como restaurar. `reminder.resolve.exact` pasa a ser `list`. `"package.install.commit": {"op": "package.install", "args": {"confirmationId": null}}` acepta cualquier `package.install` con cualquier paquete. La equivalencia convierte en acierto una respuesta distinta. Ningún caso de práctica usa estas tres entradas; el banco sellado no se pudo ver. | zona gris | Poner `op: null`, o sacarlos del recuento, cuando el producto ya no hace esa acción. Nunca asignarle otra acción. |
| 14 | scripts/renew/bench_decision.py:62 | Bancos | `return norm(want) in norm(got)`: un argumento esperado vale si aparece como subcadena («8» casa con «18», «steam» con «steamvr»). | permitido-dudoso (es la vara del juez, no el producto) | Igualdad tras plegar mayúsculas y tildes, o `re:` explícito en el caso. |
| 15 | scripts/renew/bench_escenas.py:73-78, 113, 124 | Bancos, R2 | Una respuesta vacía o un `kind` inesperado cuenta como `verdict = "silence"`, que acierta las escenas de silencio (y se suma a #3). `"risky_alone": False` por fila y `"risky_alone": 0` en el resumen están escritos a mano: el banco usa `Mind` sin la App y no mide nada de eso. | zona gris (métrica no observada; fallo contado como acierto) | Contar la respuesta vacía o ilegible como `failure`, y quitar `risky_alone` o medirlo con la App. |
| 16 | scripts/renew/bench_falsedades.py:243-247, 283, 313-315 | Bancos | Si el JSON del juez no se puede leer, queda `{"afirmaciones": [], "falsedad": False, "unparsed": …}`: un veredicto ilegible cuenta como línea honesta, y el resumen no cuenta los `unparsed`. | zona gris | Contar `unparsed` en el resumen como no juzgado, y no como honesto. |
| 17 | scripts/renew/summarize.py:37-40 | Bancos | `counted = [parts[name] for name in ("decision", "e2e", "latido") if parts[name]]`: si un banco no corrió o no dejó su archivo, sale del holdout final sin aviso y el ≥ 85 % se calcula con menos casos. | zona gris | Si falta una parte, `holdout_final` debe ser `null` con la parte que falta nombrada. |
| 18 | scripts/renew/bench_e2e.py:238-239 | Bancos | `ok = all(o["ok"] for o in oracles) and spoken_ok`: un caso sin oráculos pasa (`all([])`), y los `LEFTOVER` de la limpieza no lo hacen fallar. En el banco de práctica, 0 de 30 casos no tienen oráculo. | permitido-dudoso | Exigir al menos un oráculo. Si se quiere, marcar los restos como fallo. |
| 19 | mind.py:513-514 y 518-528; __main__.py:26 | R3 (local) | `_log(... text=turn["text"], arguments=call["arguments"], content=content)` escribe en claro en `%LOCALAPPDATA%\BAXY\renew\turns.jsonl` las palabras de la persona, los argumentos del modelo (también los valores de `memory.save`) y las respuestas, sin límite de tamaño. La App, en cambio, vacía los argumentos de memoria en su `Record` (NativeTurnLoop.cs:471-472), y voice_output.py:192 dice *«What BAXY says is the person's: nothing stays on disk»*. No sale del equipo. | permitido-dudoso (política de privacidad incoherente) | Vaciar los argumentos de las operaciones de memoria en la traza, como hace la App, y rotar el archivo. |

### Lo que se revisó y está permitido

- **R1 en la mente.** No hay regex, listas de palabras ni coincidencia aproximada sobre el texto de la persona:
  - `decide` pasa el texto tal cual (mind.py:322-336);
  - `confirm` pasa la etiqueta del botón (436-450);
  - las constantes del contrato (`const` o un `enum` de un único valor) se añaden de vuelta (194-220, 507);
  - el reloj va en un mensaje aparte (300-308).
  Lo único que la mente toca antes de mandar es esto:
  - voice.py:243-265 corta la llamada «Baxy» por las marcas de tiempo del reconocedor, no por palabras;
  - voice_output.py:311 y 434 parten la respuesta en frases sólo para sintetizarla.
- **Prompt y latido.** `SYSTEM`, `BEAT_RULES`, `BEAT_DECIDE` y `BEAT_ACT` (mind.py:23-90) son reglas en el prompt, que es presentación permitida. Lo mismo vale para el resumen `[En este turno: …]` (93-111, 417-423): sale de los campos `status`, `verified`, `succeeded`, `error`, `cause`, `polarity` y `effectUncertain` del propio recibo, y nunca dice «verificado» sin `verified`. Lo mismo para `NOT_RUN` en las llamadas que nunca corrieron (154, 386-394).
- **R3 en red.** `llama-server` escucha en `--host 127.0.0.1` (llm_server.py:41), y la salud y `chat` van a `127.0.0.1` (62, 90). El juez de falsedades también corre en `127.0.0.1` (bench_falsedades.py:238, 252). La voz es local (sherpa-onnx y piper.exe). Ni la mente ni los bancos abren conexiones fuera del equipo, y ningún banco modifica los casos: sólo los lee y escribe en `runs/`.
- **run_renew.cmd** sólo fija rutas por máquina y lanza `main.py`, sin tocar nada de los bancos.

### Quién lee cada JSON de src/baxy_mind/data

| Archivo | Lector real (grep en todo el repo) | Nota |
|---|---|---|
| tool_descriptions.en.v1.json | mind.py:21, 242-245 | La única descripción que ve el modelo. |
| decider_catalog.es.v1.json | mind.py:20, 263 | Respaldo al que nunca se llega en el producto (#7). |
| app_places.v1.json | Baxy.Kernel/ApplicationPlaces (incrustado, Baxy.Kernel.csproj:14); SteamLocalAdapter usa sus `titles` y `acts` a través del kernel | Claves muertas (#10). |
| world_acts.v1.json | Baxy.Kernel/Policy/WorldActs.cs → RiskPolicy (csproj:12) | `source` obsoleto; `examples` sólo para tests (#11). |
| memory_subjects.v1.json | Baxy.App/MemoryPanel.cs:194-212 (csproj:29), sólo `labels.*.es` y `factLabel.es` | #9. |
| search_addresses.v1.json | Providers/SearchAddresses.cs (csproj:44) → UserBrowserSurface | `source` obsoleto (#11). |
| screen_state_lines.v1.json | Providers/ScreenStateLines.cs (csproj:45) | `purpose` obsoleto (#11). Que reescriba la pantalla es asunto del informe de los providers. |
| keypad_keys.v1.json | Providers/WindowsDeviceControlAdapter.cs:847-851 (csproj:41) | Sólo C#. |
| documentless_applications.v1.json | Providers/DocumentlessApplications.cs (csproj:42) → WindowControlHandlers | Sólo C#. |
| render_surface_classes.v1.json | Providers/RenderSurfaceClasses.cs (csproj:43) → DesktopUiaWorker.ps1 | Sólo C#. |
| client_cold_start.v1.json | Providers/ClientColdStart.cs (csproj:46) | Sólo C#. |

Siete de los once archivos sólo los lee C#, aunque viven en la carpeta de la mente. Es el D-P4 anterior y **sigue**,
aunque es sólo una cuestión de ubicación.

### Estado de lo reportado antes en esta área

| Ítem anterior | Estado |
|---|---|
| M1: exposición por el prefijo «Paso interno» | **Arreglado.** mind.py:261-285 no filtra nada, y ProductCatalog.cs:2114 sólo expone `ToolExposure.Public`. |
| M2: `hello()` muerto en protocol.py | **Arreglado.** Ya no existe, y __main__.py:37-43 anuncia sólo las peticiones que atiende. Ahora el código muerto de protocol.py es otro (#5). |
| M3: `_decided` | **Arreglado.** No queda en mind.py, y bench_decision.py:153 lee `result["arguments"]`. |
| M4: parámetro `error` de `startup_failure` | **Arreglado** (llm_server.py:76). |
| M5 / K11: tercera fuente de descripciones | **Sigue** (#7). Ya no hace de marca de exposición, pero es un respaldo al que nunca se llega. |
| V5: `selectors` y `withoutNamingMemory` de memory_subjects | **Sigue** (#9). |
| D-K2: `source` que citan la mente semántica (world_acts, app_places, search_addresses, screen_state_lines) | **Sigue** (#10, #11). |
| D-P4: datos sólo de C# en la carpeta de la mente | **Sigue** (ubicación). |
| Fuera de mi área, visto de paso | V1 (`confirm_pending` desde el latido) está arreglado en la App (NativeTurnLoop.cs:258-268, `only_the_person_answers`). V6 (`BAXY_MIND_CTX`) está arreglado (FieldProductChannel.cs:933 lee `BAXY_RENEW_CTX`). |

### Resumen

La mente cumple R1 en lo esencial. No interpreta, reescribe ni veta lo que dice la persona: el texto llega tal cual,
el «sí» lo da el botón o el modelo, y las reglas viven en el prompt. R3 también se cumple: el modelo escucha sólo en
loopback y no hay salidas de red.

Lo que queda grave está en la frontera con los recibos. El recorte mudo a 6000 caracteres (#1) deshace el tope
honesto que el kernel y la App subieron a propósito, y deja al modelo leyendo resultados incompletos como si
estuvieran enteros. El filtro de llamadas (#2) borra las llamadas a herramientas inexistentes y cambia argumentos
malformados por `{}` antes de que la App los rechace honestamente. Del latido (#3), una decisión ilegible sale como
silencio.

En R4 quedan:
- una clase entera sin uso en protocol.py (#5);
- una perilla de argumentos de llama-server que nadie fija y que podría pisar `--host` (#4);
- el catálogo español, que sólo usa un banco (#7);
- `screen_text`, que la App nunca manda (#8);
- claves de datos sin lector en memory_subjects y app_places, que son restos de las listas de frases del analizador
  viejo (#9, #10);
- campos `source` que citan módulos borrados (#11).

Los bancos no editan los casos sellados, pero su vara afloja en varios puntos:
- una operación retirada se aprueba con cualquier texto, incluso falso o vacío (#12);
- tres equivalencias aceptan otra acción como acierto (#13);
- un veredicto ilegible del juez cuenta como línea honesta (#16);
- el holdout ignora en silencio el banco que falta (#17);
- `risky_alone` es una constante escrita a mano (#15).
