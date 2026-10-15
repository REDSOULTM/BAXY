# Re-auditoría de la 2.ª ronda (notebook, sólo lectura)

Diff auditado: `bde62d76c..ac2971398` de `baxy-renew`, en una copia aparte. Dos agentes, uno por área, con las reglas
de la auditoría final y las decisiones que el líder mantiene a propósito (D1, `system.power` directo, el navegador de la
persona como objetivo), que no se cuentan como violación.

| Área | Nuevos | Siguen | Arreglados |
|---|---|---|---|
| Kernel, Core, Contracts, Security, Memory, Filesystem | 6 (1 R2, 5 R4 menores) | 10 | 12 |
| App, FieldUi, Setup, run_baxy* | 9 | 15 | 26 |

Lo más urgente:
- **Kernel, N1 (R2).** `window.close.all` sigue diciendo que respeta VS Code y la terminal, pero desde `660659ef8` sólo
  respeta las ventanas de BAXY.
- **App, H26.** El instalador sigue roto: `product_build_common.ps1` lista los archivos viejos de Field UI, así que las
  dos compilaciones fallan, y el paquete no lleva la mente.
- **App, H1, H2 y H3.** En un latido, `input.keyboard.layout`, la consola, `file.write` y los ajustes corren sin que
  nadie lo pida, y las herramientas web reciben datos del dueño.

## Kernel, Core, Contracts, Security, Memory y Filesystem


Copia `BAXY-Renew-r2` en `ac2971398` frente a `bde62d76c`. Sólo lectura: diff, `git grep`, `git show` y lectura de archivos. No se compiló nada.
Rutas relativas a `src/`, salvo `tests/` y `scripts/`. Para ver qué deja colgado lo borrado se leyeron también
DesktopMessagingAdapter, WindowsWindowControlProvider, WindowsDesktopInteractionAdapter (sólo la condición de `input.text.type`),
SteamLocalAdapter, `tool_descriptions.en.v1.json`, `catalog_equivalence.json` y las pruebas.

Lo que no se volvió a reportar, por decisión del líder: D1 (sin compuerta por procedencia del lanzamiento y sin `window` obligatorio),
`system.power` sin confirmación (RiskPolicy.cs:62-65 sigue igual, sin empeorar) y el navegador propio de la persona como destino.

### Hallazgos

| # | Archivo:líneas | Regla | Qué (cita breve) | Estado | Arreglo mínimo |
|---|---|---|---|---|---|
| N1 | Baxy.Kernel/Operations/ProductCatalog.cs:1739; baxy_mind/data/tool_descriptions.en.v1.json:167 vs Providers.Windows/Windows/WindowsWindowControlProvider.cs:434-461 | R2 | `window.close.all` sigue diciendo «salvo Visual Studio Code, la terminal y la propia» / «except VS Code, the terminal and BAXY». Desde 660659ef8 (en este rango) el proveedor sólo respeta `OwnProcessNames` (Baxy, Baxy.App, baxy-core): `targets = desktop.Where(!OwnProcessNames.Contains(...))`. El modelo, y con él la persona en la confirmación, oye que VS Code y la terminal quedan abiertos, y se cierran. | **nuevo** | Que las dos descripciones digan «todas las ventanas visibles salvo las de BAXY». |
| N2 | Providers.Windows/External/DesktopMessagingAdapter.cs:436-437 (se construye en 156-157 y 235-236) | R4 | `ResolvedRecipient(string RecipientId, …)`. Al retirar `message.send` y `message.recipient.resolve` se fue el único lector (`_recipients[recipientId]`, `RequiredString(arguments,"recipientId")` en bde62d76c). Ahora se escribe `"draft_"+Guid` / `"sendtest_"+Guid` y no lo lee nadie (`git grep RecipientId` da sólo la declaración). | **nuevo** | Quitar el campo y los dos `Guid` que lo llenan. |
| N3 | Baxy.Kernel/Operations/ProductCatalog.cs:1591-1593 | R4 | Comentario huérfano de `web.news.headlines` (retirada): «la encuesta pide las noticias… Titulares del día o de un tema nombrado desde un canal RSS público». Ahora queda encima del descriptor de `web.download`. | **nuevo** | Borrar esas tres líneas. |
| N4 | Providers.Windows/Filesystem/LocalFilesystemProvider.cs:442-444 (antes reservaba `IsUnderTrash`), 56, 79 | R4 (gris) | En bde62d76c el constructor hacía `Directory.CreateDirectory(_trash)` en cada arranque, así que todos los perfiles tienen `<sandbox>/.trash` (vacía, porque `commit` nunca se invocó). Ya nada la reserva ni la borra, y aparece como una entrada más en `filesystem.list` y `filesystem.search`. El commit 841346e0e dice «que ya nada escribe», pero la carpeta sigue ahí. | **nuevo** | Al construir, borrar `.trash` si está vacía. O aceptarla por escrito como resto inofensivo. |
| N5 | Baxy.Core/Operations/MemoryHandlers.cs:757-760; Providers.Windows/Memory/LocalMemoryStore.cs:482-492 vs 472 y 927-940 | R4 (apilado) | `ForgottenStateMatches` → `!_store.Holds(request)` vuelve a leer el estado y aplica `MatchesForget`. Pero `Forget` ya terminó con `VerifyForgetAbsentUnsafe(normalized)`, que comprueba ese mismo criterio sobre `current.bin` y `recovery.bin` y lanza una excepción si queda algo. Son dos verificaciones iguales, y para la segunda se añadió un miembro nuevo a `IMemoryStore`. El fallo anterior (un olvido por tipo o tema que se informaba como fallo) sí está arreglado. | **nuevo** (gris) | Quitar `Holds` y que el handler confíe en el recibo de `Forget`, que ya verificó. O quitar la verificación interna y dejar sólo `Holds`. |
| N6 | Providers.Windows/Filesystem/FilesystemContracts.cs:51-52 vs LocalFilesystemProvider.cs:224 | R4 (menor) | El doc nuevo de `CreateDirectory` enumera «("desktop", "documents", "downloads")», pero `RootFor` también acepta `"home"`, y el catálogo lo anuncia («la carpeta del usuario»). | **nuevo** | Añadir `"home"` al comentario. |
| 2 | Baxy.Kernel/Policy/RiskPolicy.cs:169-174 | R5 | `KeyOf(arguments) is "enter" or "space" && (TargetOf(arguments) is "message_composer" \|\| LabelReachesAPerson(OntoOf(arguments)))`. Ahora se le explica al modelo (tool_descriptions.en.v1.json:204-205, f111b79e1), pero la confirmación sigue dependiendo de lo que el modelo declare. Basta `message.draft` y luego `input.key.press{key:"enter"}` para enviar sin el sí. | sigue (mitigado) | Fallar cerrado: Enter o Espacio preguntan salvo que lo observado diga que el control enfocado no es un compositor. |
| 3 | Baxy.Core/Operations/WindowControlHandlers.cs:74-84 | R5 | `provider.HoldsNoDocument(windowId) ? OperationRisk.Reversible : null`, sin cambios. `app.close` no pregunta para apps del dueño «sin documento» o «de cuenta». | sigue | Bajar el riesgo sólo para una ventana que BAXY lanzó y en la que no escribió. |
| 12 | Baxy.Kernel/Operations/ProductCatalog.cs:445-446 | R4 | Ya salió `field`, y `target`/`onto`/`consequence`/`wanted`/`windows`/`tail` se le describen al modelo. Queda un comentario de la misión retirada: «a mission's file.open goes without it and stays behind». | sigue (resto) | Corregir el comentario. |
| 13 | baxy_mind/mind.py:259; ProductCatalog `Description` | R4 | Se fue `decider_catalog.es.v1.json`, pero quedan dos fuentes: la inglesa y, si falta, la del catálogo. Las 172 operaciones tienen descripción inglesa (comprobado), así que la del catálogo nunca llega al modelo y puede desfasarse, como ya pasó en N1. | a medias | Una sola fuente. |
| 14 | ProductCatalog.cs:293, 299, 806 vs `input.key.press` ctrl_c/ctrl_v/ctrl_a; Core/Program.cs:143-144 | R4 | Ya no hay dos caminos para las noticias (`web.news.headlines` salió). Siguen `clipboard.copy`/`clipboard.paste`/`input.select.all` junto a los atajos, y `audio.volume.adjust` va por dos handlers. | a medias | Un camino por cosa. |
| 15 | ProductCatalog.cs:1098; RiskPolicy.cs:44 | R4 | `message.send.test` sigue en el catálogo público. | sigue (permitido-dudoso) | Ratificación del dueño o moverla al banco. |
| 16 | Contracts/ProtocolContracts.cs:62, 83; Contracts/BaxyJsonContext.cs:20; Kernel/Journal/JournalJsonContext.cs:15 | R4 | `HonestyCorrectionTrace`: sólo lo construye tests/Baxy.Contracts.Tests/ProtocolContractTests.cs:455. | sigue | Quitar el campo, el tipo y sus registros. |
| 19 | Kernel/Journal/FileInvocationJournal.cs:75, 146-181, 1446; Mission/InMemoryConfirmationAuthority.cs:148; Mission/MissionEngineOptions.cs:19-23; **Operations/OperationDefinition.cs:5-15; Mission/MissionEngine.cs:303-307; Operations/OperationRegistry.cs:34-46** | R4 | Siguen `Open…ForTestingAsync`, `crashHook`, `ActiveChallengeCount` y `ConfirmationAuthority` («Sólo la usan las pruebas»). El diff hace explícita otra costura: el constructor `OperationDefinition(name, risk, description)` pasa a `internal` con «Kernel.Tests' seam», y una rama de producto sólo existe para él (`descriptor is null` → «Only Kernel.Tests' definitions have no catalog entry»). El `Lazy` de `ToolDescriptors` está para que esas definiciones no fallen al construir. `ProductCatalog.Descriptors` sí salió. | sigue (con una costura más a la vista) | Mover las costuras a los tests: fábricas o subclases de prueba con descriptores reales. |
| 21 | baxy_mind/data/app_places.v1.json (`examples`), world_acts.v1.json (`examples`) | R4 | El comentario «the planner's projection» salió (OperationVisibleFacts.cs:100-102) y también los campos `names/said/shows/within`. Siguen los `examples`, que ningún código de producto lee. Ahora el `source` lo dice («los ejemplos atan los datos a sus pruebas»). | a medias | Aceptarlo por escrito o mover los ejemplos a los tests. |
| 22 | Core/LegacyJournalMigration.cs; Core/Program.cs | R4 | Sigue la migración v1. | sigue | Igual que antes. |
| 24 | RiskPolicy.cs:201-204 | R1/R5 | `KeyOf is "delete" && TargetOf is not "text_field"`. Falla cerrado y ahora `target` se le explica al modelo. | sigue (permitido-dudoso) | — |
| P1 | Core/Operations/AppInstalledHandler.cs:38-45; Providers.Windows/Applications/WindowsInstalledApplicationOpenProvider.cs:1335-1344 | R1 | `app.installed` devuelve ahora `candidates`: «the names that hold every word asked, then by edit distance» sobre el `name` del modelo. Sólo informa y no actúa; es el mismo resolutor que ya usaba `app.open`. | permitido-dudoso (nuevo alcance) | — |

### Estado de cada hallazgo anterior (auditoria-final-nb.md, Kernel)

- **#1** `system.power`: el atajo sigue (RiskPolicy.cs:62-65) por decisión del líder. La parte R2 está **arreglada**: ni el catálogo (ProductCatalog.cs:1381) ni la descripción inglesa (en:134) prometen ya una confirmación.
- **#2** Enter en un chat: **sigue**. Está mitigado porque ahora se le describe `target` al modelo (en:204), pero la decisión sigue siendo del modelo.
- **#3** `app.close` sin documento: **sigue**.
- **#4** Descripciones que prometían confirmación: **arreglado**. `filesystem.known.trash.named` (557), `memory.enable` (1001), `memory.sensitive.save` (1058) y `wifi.radio.set` (1703) ya no la prometen, tampoco en inglés (en:60, 94, 100, 161).
- **#5** `browser.*` «CDP»: **arreglado** (ProductCatalog.cs:201, 207, 224, 232; en:27-31). `BAXY_BROWSER` existe y se lee (UserBrowserSurface.cs:71).
- **#6** `message.send` y `filesystem.trash.restore`: **arreglado**. Ambas salieron del catálogo, del handler y del proveedor. Queda el campo huérfano N2.
- **#7** Las 9 operaciones internas: **arreglado**, junto con `ToolExposure`, `Descriptors` y `ToolDefinitions`. Detalle de las referencias más abajo.
- **#8** `calendar.event.create`: **arreglado**. Está en `ExternalRequiringConfirmation` (RiskPolicy.cs:41-47) y ahora la descripción lo dice (ProductCatalog.cs:251; en:33). Hay prueba: OperationRegistryTests.
- **#9** `ctrl_w`: **arreglado**. Lo hace `MayCloseAWindow` (RiskPolicy.cs:284-287), que se invoca en la 71. El comentario del enum y las descripciones están corregidos (ProductCatalog.cs:727-730, 755; en:76) y hay prueba que cubre los modos Normal y Bypass.
- **#10** `Sanitize` cortaba en silencio: **arreglado**. `cut` se propaga, y la raíz lleva `truncated:true` y `<lista>Shown`/`<lista>Count` (OperationVisibleFacts.cs:103-113, 395-406, 419). Todas las raíces de Core son objetos, así que el caso de una raíz que es lista no se da.
- **#11** `input.text.type` con caracteres de control sin `window`: **arreglado**. WindowsDesktopInteractionAdapter.cs:414 ahora dice `(typing && text.Any(char.IsControl))`, con o sin ventana, y lo anuncian el catálogo (829-832, 839) y la descripción inglesa (en:83).
- **#12** Argumentos de la misión: **casi arreglado**. Salió `field` (con su rama `input_field_not_found` por rótulo), se corrigieron los comentarios y se describen los argumentos (en:203-221). Queda el comentario de la línea 446.
- **#13** Tres fuentes de descripción: **a medias**; quedan dos.
- **#14** Mecanismos dobles: **a medias**; lo de las noticias está arreglado.
- **#15** `message.send.test`: **sigue**.
- **#16** `HonestyCorrectionTrace`: **sigue**.
- **#17** `ProtectedPayloadPurposes`: **arreglado**. BoundProtectedJsonCodec.cs:17-18 y LocalMemoryStore.cs:33-35 usan las constantes. El kernel repite dos literales, una sola vez y con la causa documentada (PrivateOperationBoundary.cs:30-33): Security.Windows no referencia Contracts.
- **#18** `SealUtf8`/`OpenUtf8`: **arreglado**. Salieron de la interfaz y de la implementación, y las pruebas usan su propia extensión (tests/…/ProtectedPayloadText.cs).
- **#19** Costuras de test: **sigue** (ver la tabla). Salió `ProductCatalog.Descriptors`.
- **#20** Dos `NormalizeName`: **arreglado** con `CatalogNames.Normalize` (Contracts/CatalogNames.cs; ContractValidator.cs:116, 203).
- **#21** Datos que nadie lee: **a medias** (quedan los `examples`).
- **#22** LegacyJournalMigration: **sigue**.
- **#23** `ShellMayChange`: permitido, sin cambios.
- **#24** Suprimir según `target`: permitido-dudoso, sin cambios (ahora se describe).
- Del estado anterior: **K2** queda arreglado (ya no hay operaciones internas). K8 = #2 y K12 = #15 siguen. D-K10/D-K11 = #19 están a medias. D-K12 = #22 sigue.

#### Las 11 operaciones retiradas (más `web.news.headlines`)

`git grep` sobre `src`, `scripts` y `tests` de `filesystem.hash`, `filesystem.trash.{prepare,commit,restore}`, `game.{install,purchase}.{prepare,commit}`,
`message.recipient.resolve`, `message.send` (exacto), `task.resolve.exact` y `web.news.headlines`:
- En catálogo, handlers, proveedores, datos de la mente (`baxy_mind`) y `tool_descriptions` no queda ninguna referencia.
- Tampoco quedan sus miembros: `ResolveExact`, `LocalTaskAmbiguousException`, `task_ambiguous`, `PrepareTrash`/`CommitTrash`/`Restore`, `TrashHandle`, `FilesystemTrash*`, `SteamInstallPreparation`, `operation_forbidden`, `OperationRisk.Forbidden`, `PolicyDecision.Deny`, `session_disruption`/`monetary`/`forbidden_destructive` (NativeTurnLoop.cs:70 ya no lista `monetary`) y `MemoryListRequest.Topic`.
- Sí quedan referencias, todas a propósito:
  - `tests/Baxy.Kernel.Tests/ProductCatalogTests.cs:84-129` (la lista `RenewRetired`, que prueba su ausencia).
  - `scripts/renew/catalog_equivalence.json:22, 30, 31`: el banco las traduce a la operación que las sustituye o a `null`.
  - Comentarios históricos en GoogleNewsFeed.cs:7, TzDc2WorkerDelCoreTests.cs:11-12, X1EnvioBusquedaTests.cs:10 y la documentación.
- Lo único que quedó colgado es N2 (`RecipientId`) y N3 (el comentario de las noticias).
- `IFilesystemProvider.Hash` sigue, y con razón: lo usa `VerifiedMutation` (FilesystemHandlers.cs:99).

#### Lo que dicen los commits y no hacen (pregunta 3)

- 841346e0e, «la .trash privada… que ya nada escribe»: es cierto que nada escribe en ella, pero la carpeta que el constructor creó en cada perfil queda visible (N4).
- d1f0e50d3, «un olvido se relee con su criterio»: lo hace, pero esa relectura ya la hacía `Forget` por dentro (N5).
- El commit 660659ef8, del área de proveedores, cambió `window.close.all` sin actualizar sus dos descripciones (N1).
- Los demás commits del área hacen lo que dicen: 65277db33, 11d712dcf, 1b282bdb9, b16d43cb8, 1c0709bda, a37027a05, f111b79e1, d125581fa y 472d556af.

### Resumen

La ronda 2 arregló casi todo lo serio del área:
- `calendar.event.create` y `Ctrl+W` piden confirmación.
- Las descripciones ya no prometen confirmaciones que no existen, y las de `browser.*` dicen qué navegador tocan.
- `Sanitize` marca sus cortes.
- `input.text.type` rechaza los caracteres de control también sin ventana.
- `memory.recall` compara el selector exacto (plegado) y el olvido por tema ya no se informa como fallo.
- Salieron las 11 operaciones retiradas y `web.news.headlines`, sin referencias vivas, junto con `ToolExposure`, `Forbidden`/`Deny`, la API UTF-8 de Security y el `NormalizeName` duplicado.

Hay una violación nueva de R2: el cambio de `window.close.all` en el proveedor dejó sus dos descripciones diciendo que respeta VS Code y la terminal, y ya no lo hace. Eso muestra el riesgo de la doble fuente de descripción (#13). Además quedan restos menores de R4 que dejaron las borraduras: `ResolvedRecipient.RecipientId` sin lector, el comentario de las noticias, la carpeta `.trash` visible, la doble verificación del olvido y un doc sin `home`.

Siguen las dos zonas de R5 que el líder no cerró: Enter en un chat depende de que el modelo declare `target` (ahora se le explica), y `app.close` no pregunta en ventanas «sin documento» del dueño. También siguen las costuras de test en el ensamblado de producto, ahora más visibles con el constructor interno de `OperationDefinition` y su rama en `MissionEngine`.

## App, FieldUi, Setup y lanzadores


Worktree `C:\Users\usuario\Desktop\ETC\Programacion\BAXY-Renew-r2`, detached en `ac2971398`. Diff contra `bde62d76c` en
`src/Baxy.App`, `src/Baxy.FieldUi/src`, `src/Baxy.Setup` y `scripts/run_baxy*.ps1` (51 archivos: +522, −5363). Para
contrastar se leyeron además `ProductCatalog.cs`, `DesktopKeyPress.ps1`, `WindowsDesktopInteractionAdapter.cs`,
`WindowsNetworkStatusProvider.cs`, `src/baxy_mind/{mind,voice,voice_output,__main__}.py`,
`scripts/{product_build_common,build_setup,build_product}.ps1`, `scripts/run_renew.cmd`, `FieldUiProbe.cs`,
`ProductConductorHost.cs` y el `dist` de FieldUi (que coincide con `src`: contiene «memoria vacía», «diagnóstico
local» y los atajos nuevos, y ya no contiene «llama-server offline», «No te entendí» ni Google Fonts). No se compiló
ni se ejecutó nada. Las rutas de abajo son relativas al worktree.

Lo que se retiró se buscó con `git grep` en `src`, `tests`, `scripts` y `main.py` en `ac2971398`: `DurableRetryStore`,
`RetireWhere`, `retry-outbox`, `RetryableOperationRegistry.CreateDefault`, `AuthenticateLoadedMemoryOperation`,
`PendingMemoryConfirmation`, `StaleMemorySessionException`, `InspectForRecovery`, `MemoryOperationInspection`,
`ShouldCancelAfterSessionChange`, `ResolveWireOperationName`, `WritesInThePersonsWindow`, `HF_HUB_OFFLINE`,
`AssetManifestDiscovery`, `OwnedProcessReader`, `PresenceIdleSampler`, `PresenceStatusStore`, `FieldHardwareSnapshot`,
`FieldProgressNotice`, `ResolveProgress`, `NormalizeActivitySource`, `StatusText` (del VM), `mindClientFactory`,
`ITrayIconShell`, `BAXY_ASSET_DESCRIPTOR`, `BAXY_CONDUCTOR_COMMIT` y `BAXY_MIND_STT_DIR`. **No queda ninguna
referencia.** `AtomicFileReplacement` sigue, pero es la clase de `Baxy.Providers.Windows`, no la que se borró de la
App. Tampoco hay proyecto de tests de la App, así que ningún test quedó apuntando a algo borrado. Los tests de Setup
usan `PackageContract.PayloadPaths`, que ahora se genera desde `dist`.

### Tabla

| # | Archivo:líneas | Regla | Qué (cita breve) | Estado | Arreglo mínimo |
|---|---|---|---|---|---|
| 1 (H1) | Baxy.App/NativeTurnLoop.cs:265-271; Baxy.Providers.Windows/External/DesktopKeyPress.ps1:144-152; Baxy.Kernel/Operations/ProductCatalog.cs:757-761 | R3 | La lista sumó `clipboard.copy`, `client.channel.locate`, `browser.control` y `calculator.expression.evaluate`, pero deja fuera `input.keyboard.layout` (`low_reversible`): `PostMessage(window, WM_INPUTLANGCHANGEREQUEST…)` a la ventana enfocada. El comentario 265-267 dice «Every operation whose provider sends keys, clicks or window commands (… posted commands)», y no es cierto. En un latido corre sola en la ventana de la persona. | sigue (a medias) | Agregar `input.keyboard.layout` a la lista o, mejor, un atributo tipado del catálogo («actúa en una ventana») en vez de nombres. |
| 2 (H2) | NativeTurnLoop.cs:67-71 y 246 | R5 / R1 | `ProposedRisks` sigue siendo una copia a mano (se quitó `monetary` también del kernel, así que coinciden). En un latido siguen corriendo solos `shell.command.run` (`low_reversible`), `file.write`, `wifi.disconnect`, `system.settings.set` y `memory.save`. | sigue | Derivar la retención de `ProductCatalog.ToPolicyRisk` y el modo (todo lo que no es `ReadOnly`). |
| 3 (H3) | Heartbeat.cs:117-119; HeartbeatMoment.cs:73 y 77; NativeTurnLoop.cs:246; catálogo: `web.search`, `web.fetch`, `weather.current` = `ReadOnly`, `web.download` = `PrivacySensitive` | R3 | El momento sigue llevando `moment["memory"]` (los valores de la memoria), los títulos de las ventanas y las últimas 6 líneas. Ninguna operación que sale a la red se retiene en el latido: una consulta, URL o lugar armado con datos del dueño sale sin que nadie lo pida. | sigue | Retener en el latido toda operación que salga del equipo (atributo tipado «sale a la red»). |
| 4 (H5) | SensitiveText.cs:86-89; MainWindowViewModel.cs:334; MemoryOperationProtection.cs:209-214 | R1 | Arreglada la causa: `MemoryValueNeedsSensitiveChannelException` → `"memory_value_needs_sensitive_channel"` (NativeTurnLoop.cs:231-236). Pero el disparador sigue siendo una lista de palabras de tema (`password\|contrase(?:ñ\|n)a?\|\brut\b\|\bssn\b\|social security\|api key…`): vela toda la línea del transcript y rechaza el `memory.save` por una palabra. | sigue (a medias) | Disparar sólo con forma de credencial (`LooksLikeCredentialToken` y los prefijos `sk-`, `ghp_`…). |
| 5 | NativeTurnLoop.cs:237-244 (con MemoryOperationProtection.cs:180-244) | R2 | En memoria, todo argumento que no encaja vuelve como `"arguments_invalid"` a secas: `WithArguments` omite `argumentsGiven` (bien, por privacidad), pero la causa que lanza el protector («La operacion no coincide con su riesgo.», «La eliminacion requiere confirmacion.», «La limpieza de sesion excede su alcance.») se pierde. El modelo no sabe qué cambiar. | nuevo (efecto del arreglo de H6) | Códigos cerrados en esas excepciones (`memory_risk_mismatch`, `memory_forget_needs_confirmation`, `memory_session_scope`) y ponerlos en `error`. |
| 6 (H15) | MainWindowViewModel.cs:129 y 437-440; FieldProductChannel.cs:347-353 | R2 | `Failure => _startupFailure ?? _lastTurnFailure` llega a la vista (evento `agent`, `convState 'error'`, FieldCenter). Pero un fallo de arranque de la mente (`_mindStartupState = Failed`, líneas 917 y 938) sólo va a `StatusDescription` (`IdleStatus`), que la vista no muestra. La persona lo ve recién cuando un turno falla con `mind_unavailable`. El commit 746667a23 dice «cada fallo con su código». | sigue (a medias) | Incluir `mind_unavailable` en `Failure` cuando `_mindStartupState == Failed`. |
| 7 (H23) | MindRuntimeDiscovery.cs:29-35, 41-59, 205 y 266; scripts/run_renew.cmd:5-21; voice.py:114 y 123; voice_output.py:141-142 | R4 | Arreglado: `HF_HUB_OFFLINE`, el comentario de SAPI y la verificación por hash de la voz (una voz que falta ya no tumba la mente). Sigue: el registro **exige** `stt_dir`, `stt_sha256`, `wake_manifest`, `wake_manifest_sha256`, `tts_model`, `tts_sha256` y `wake_on_start` (`HasExactProperties`), acepta los adaptadores, y la App no lee ninguno. El comentario 33-34 («belong to the launcher (scripts/run_renew.cmd) and are accepted by shape only») es falso: `run_renew.cmd` no lee el registro, fija rutas por máquina. La App no publica `BAXY_RENEW_STT_DIR`, `_WAKE_DIR`, `_TTS_MODEL` ni `_PIPER_DIR`: la voz sólo existe si se arranca con `run_renew.cmd`. | sigue (a medias) | Publicar las cuatro `BAXY_RENEW_*` desde el registro, o sacar esas claves del esquema (aquí, en `register_mind_runtime.ps1` y en `mind_runtime_manifest.ps1`) y corregir el comentario. |
| 8 (H25) | src/baxy_mind/voice.py:66-70 frente a MindSidecarClient.cs:63-67 y 472-477 | R4 | La App ya sólo lee `available`, `input`, `stt` y `pending`. La mente sigue mandando `"tts"`, `"mode"`, `"listening"` y `"speaking"` en `status()`, que nadie lee. | sigue (a medias: lado App arreglado) | Quitar esos cuatro campos de `voice.py`. |
| 9 (H26) | scripts/product_build_common.ps1:17-52 (23-24) y 583-597; scripts/build_product.ps1:231; scripts/build_setup.ps1:259; Baxy.Setup/PackageContract.cs:52-87 | R4 / se rompe | El contrato de Setup y la lista de `build_setup.ps1` ya salen de `dist/assets` (bien). Pero `$script:BaxyProductPayloadPaths` sigue fijando `'FieldUi/assets/index-CjozYCnU.css'` e `'index-D3QuhrLm.js'`, y `Assert-BaxyExactProductPayloadFileSet` la exige por igualdad exacta en `build_product.ps1:231` y en `build_setup.ps1:259`. El dist actual es `index-D2Aa7RIK.css` / `index-uqiQcaoq.js`, así que el build de producto y el de setup lanzan «Product payload has an unexpected path». Además el paquete sigue sin `baxy_mind` ni el registro de la mente. | sigue (a medias) | Derivar `BaxyProductPayloadPaths` de `dist/assets` igual que `build_setup.ps1:61-75` (una sola lista compartida) e incluir la mente, o sacar Setup de la solución. |
| 10 (H35, resto de H34) | MemoryPanel.cs:203-214; src/baxy_mind/data/memory_subjects.v1.json:3-38; Baxy.App/Baxy.App.csproj:28 | R1 / R4 | H34 arreglado en los datos: `selectors`, `withoutNamingMemory` y el `_doc` obsoleto ya no existen, y el comentario de MemoryPanel dice que sólo lo lee el panel. Sigue el vocabulario fijo (11 etiquetas y «dato» para todo `historical_fact_*`), y el csproj:28 todavía dice «(one file with the mind)». | sigue | Mostrar el selector (`Replace('_',' ')`) y corregir el comentario del csproj. |
| 11 (H38, H39) | HeartbeatMoment.cs:27 y 43; Heartbeat.cs:158-162 y 168 | R1 | `Speaks => activity == Free`, umbrales de batería `{ 20, 10 }` e `idle_min >= 10`. | sigue (decisión del dueño por confirmar) | Anotarlo como decisión del dueño. |
| 12 (H8) | NativeTurnLoop.cs:363-370 | confirmación | El «sí» a la propuesta del latido contesta también el reto del kernel. La observación lleva los argumentos (252-258). | sigue (permitido-dudoso) | — |
| 13 | MainWindowViewModel.cs:60, 194 y 744-748 | R4 | `_firstWakeUtc` / `FirstWakeUtc` se escriben (con `OnPropertyChanged`) y ya no los lee nadie: su único lector era `PresenceHost.Publish`/`PresenceStatusStore`, borrados en 4af04c415. | nuevo (huérfano del borrado) | Borrar el campo, la propiedad y el bloque 744-748. |
| 14 | FieldUiProbe.cs:80-81, 87, 93, 719, 724-727 y 746 | R4 | La sonda lee `document.querySelector('.turn-progress')`, pero FieldCenter.tsx ya no tiene ese elemento (se borró en 214b4930e). `ProgressLength` siempre vale 0, y «no hay etapa en curso» / «ninguna etapa a la vista» no describen nada. | nuevo (huérfano del borrado) | Quitar `progress` del script, `ProgressLength` y esa condición de `Idle`. |
| 15 | scripts/run_baxy_conductor.ps1:21-22 y 61-72; ProductConductorHost.cs:346-391 | R4 | El lanzador pasa `--commit=$commit` y `--after-welcome`. `ConductorArguments.Parse` no lee ninguno (sólo `--profile`, `--capture`, `--turns-file`, `--text`, `--command-dir` y `--timeout-ms`). El comentario 21 («el primer turno espera a que la bienvenida esté compuesta») es falso. El commit d711f4f3e («los lanzadores no publican variables que nadie lee») cambió la variable por un argumento que tampoco lee nadie. | nuevo (lo tocó el diff) | Borrar `$commit` del argumento (dejar el `Write-Host` si sirve), el switch `-AfterWelcome` y su comentario. |
| 16 | FieldTelemetrySampler.cs:66-95; FieldProductChannel.cs:744 | R2 | Sólo la GPU viaja como `null` cuando no se lee. CPU (`system.Cpu?.UsagePercent ?? 0`), memoria, disco (`= 0`) y uptime (`?? 0` → «00:00:00») sin lectura se muestran como 0 medido. El comentario 744 («A reading the PC did not give … travels as null») y el commit 214b4930e («sólo con lo medido») dicen más de lo que hace el código. | nuevo | `double?` también para cpu/mem/dsk y uptime `null`, con «—» en la vista. |
| 17 | MainWindowViewModel.cs:700-706 | R2 | `voice_dropped_busy` también se publica cuando `!IsReady`, el caso «before BAXY is ready» que admite el propio comentario: el código dice «ocupado» cuando la causa es «no está listo». | nuevo (menor) | `IsReady ? "voice_dropped_busy" : "voice_dropped_not_ready"`. |
| 18 | Heartbeat.cs:88; Baxy.Providers.Windows/Network/WindowsNetworkStatusProvider.cs:33-39 y 59-77 | robustez | `await NoteChangesAsync(...)` está fuera de todo `try` y ahora llama dos veces a `NetworkInterface.GetAllNetworkInterfaces()` y a WinRT `NetworkInformation.GetInternetConnectionProfile()` cada 15 s. Una excepción ahí (por ejemplo `NetworkInformationException` o `COMException`) termina `RunAsync`, y el latido se apaga en silencio por el resto de la sesión. No se observó que falle: es la forma del código. | nuevo (riesgo) | Envolver la lectura de red y tratar el fallo como «sin lectura» (`connectivity` sin cambio). |
| 19 | Baxy.FieldUi/src/styles/prototype.css:750-810, 1270-1292, 167, 1651, 1374, 2015-2023; ActivityPanel.tsx:138-140 | R4 / R2 menor | El diff borró `Slider.tsx`, `Toggle.tsx`, `Select.tsx`, los adjuntos y las fuentes GEMMA/TOOL…, y sólo limpió parte del CSS. Quedan sin uso `.slider*`, `.toggle*`/`.knob`, `.st-select`, `.ibtn .badge` (del botón de adjuntar) y `.src.tool/.gemma/.memory/.trigger/.boot/.thought/.context`. El comentario 1374 todavía nombra el «vision banner». Además `.src.system { color: var(--carmine) }` (2022) pisa a la 545 (`--tag-sys`), así que el comentario de ActivityPanel («the view's own lines in var(--tag-sys)») es falso. | nuevo (huérfano del borrado) | Borrar esas reglas y la 2022, o corregir el comentario. |
| 20 (resto de H31) | Baxy.FieldUi/src/App.tsx:210-211, 310-311 y 355; hooks/useToast.ts:27 | R4 | Comentarios y nombres del producto anterior: «mirror the legacy QShortcut bindings … PyQt6 GUI», «captured without saying 'gemma'», «Gemma's TTS plays…» y el evento `'gemma4:toast'`. | sigue (resto) | Corregir los tres comentarios y renombrar el evento. |
| 21 | Baxy.App/WindowsAutostartRegistration.cs:28-44; PresenceContracts.cs:12-19 | R4 (no reportado antes) | Un constructor con cuatro inyecciones opcionales y la interfaz `IWindowsRunKey` existen sólo para pruebas, y no hay proyecto de tests de la App: el único llamador es `CreateDefault()`. El diff borró costuras iguales (`ITrayIconShell`, `mindClientFactory`, el `utcNow` de `RuntimeFileHashCache`) y dejó ésta. | sigue (previo) | Constructor privado con los valores fijos. |
| 22 | Baxy.App/MissionInput.cs:54-55 | R4 (no reportado antes) | «This is the existing WPF composer MaxLength, not the memory parser's narrower UTF-8 limit»: ni hay compositor WPF (MainWindow.xaml no tiene `MaxLength`) ni existe ya el parser de memoria. | sigue (previo) | Reescribir el comentario (el límite es el del `maxLength={4096}` de FieldCenter.tsx). |

### Estado por id del informe anterior

- **H1** a medias: entraron `clipboard.copy`, `client.channel.locate`, `browser.control` y `calculator.expression.evaluate`; falta `input.keyboard.layout`, y sigue siendo una lista por nombre (fila 1).
- **H2** sigue (fila 2). `monetary` se fue de los dos lados y coinciden.
- **H3** sigue (fila 3).
- **H4** arreglado: `RunBeatAsync` vuelve a mirar `HasPendingConfirmation` ya con el turno tomado (`_turnGate.Wait(0)` en MainWindowViewModel.cs:356-359; NativeTurnLoop.cs:137-142). Una confirmación de la persona ya no se descarta.
- **H5** a medias: la causa del canal sensible se arregló; la lista de palabras sigue (fila 4). Nuevo efecto: la fila 5.
- **H6** arreglado: `WithArguments` deja fuera los valores de memoria en `arguments_invalid`, en la propuesta y en `needs_confirmation` (NativeTurnLoop.cs:277-286).
- **H7** arreglado: `ResolveWireOperationName` ya no existe y viaja la operación que eligió el modelo (MemoryOperationProtection.cs:67-70).
- **H8** sigue, permitido-dudoso (fila 12).
- **H9** arreglado: `"next" = "ask the person whether to do it; when they answer, call confirm_pending with their answer"` (NativeTurnLoop.cs:274-275). La herramienta de la mente se llama `confirm_pending` (mind.py:160).
- **H10** arreglado: la mente ya no corta (mind.py: `observation[:6000]` → `observation`) y queda un solo cortador, el de la App, con la marca «… [respuesta truncada]» (OperationResponseProjection.cs:57-59 y 70-89).
- **H11** arreglado: `CurrentSettings` sólo tiene `modelAlias`, `ggufPath`, `ctxSize`, `wakeWordEnabled` y `voiceEnabled` (FieldProductChannel.cs:654-668), y las frases se borraron.
- **H12** arreglado: ni `maxTokens` ni el aviso de llama-server existen ya en SettingsPanel.tsx.
- **H13** arreglado por borrado: no existen `PUT /settings` ni `/agent/restart`, ni su aviso.
- **H14** arreglado por borrado: no existen `/profile`, `/agent/modes`, `/agent/personas` ni `/agent/system_prompt`, ni la pestaña Prompt.
- **H15** a medias (fila 6).
- **H16** arreglado: el placeholder es `agent.built ? 'ask…' : agent.failure ?? 'starting agent · loading tools…'`.
- **H17** arreglado: `${verb} · falló · …`, «memoria vacía · se guarda desde el chat».
- **H18** arreglado: se borró `voice_no_speech`.
- **H19** arreglado: `startNewSession()` muestra el código del error (hooks/newSession.ts), y el comentario falso se fue.
- **H20** arreglado: `voice_dropped_busy` y `voice_error` llegan por `last_error` de `/voice/status` (FieldProductChannel.cs:624) y al tooltip del micrófono. Resto: la fila 17.
- **H21** arreglado: `"(ninguno)\n"` (ScreenViewProjection.cs:82).
- **H22** arreglado: el frente se escribe sólo si se observó (ScreenViewProjection.cs:52-58) y se copian todos los hechos del kernel menos `observed` (126-136).
- **H23** a medias (fila 7).
- **H24** arreglado: `StatusText` ya no existe en el VM.
- **H25** a medias: el lado App está arreglado; la mente sigue mandando los campos (fila 8).
- **H26** a medias: el lado Setup está arreglado; `product_build_common.ps1` sigue con la lista vieja y falta la mente (fila 9).
- **H27** arreglado: el registro vive sólo en memoria (PreparedOperation.cs:156-187) y no queda ninguna referencia a la cola durable. Nota: ningún código borra un `shell/retry-outbox.v1.json` que haya quedado en perfiles existentes (con texto tecleado de sesiones viejas).
- **H28** arreglado: `PendingMemoryConfirmation` se borró y MemoryPanel usa `PendingOperationConfirmation` (MemoryPanel.cs:277-284).
- **H29** arreglado: el panel contesta el reto sólo si `operation == "memory.forget"` (MemoryPanel.cs:277-279).
- **H30** arreglado: `FieldBridgeContract` quedó en dos admisiones y no se mapea nada que nadie escriba (`progressLabel` y el pulso de progreso se fueron).
- **H31** arreglado en el formulario (SettingsPanel.tsx: tres pestañas, sólo lo que reporta el host); quedan los comentarios de la fila 20.
- **H32** arreglado: el puente ya no tiene `MutationObserver`/regex ni `FormData → 501`, y se borraron el botón de adjuntar y `/upload`.
- **H33** arreglado: se borraron `/tools/execute` y el formulario «run», `vision_threshold`, `/agent/recycle_server`, `prewarm_*`, `NormalizeActivitySource` (`POST /activity` es siempre `SYSTEM`) y Google Fonts (index.html).
- **H34** arreglado en los datos y en MemoryPanel; resto en el csproj:28 (fila 10).
- **H35** sigue (fila 10).
- **H36** arreglado en la App: la rama `HonestyCorrection` ya no existe en OperationResponseProjection. El tipo sigue en Contracts/Kernel, que no es de esta área.
- **H37** arreglado: `Event` es privado, con dos llamadores y sin ramas muertas.
- **H38, H39** siguen (fila 11).
- **H40** arreglado: `file appeared in Descargas: {name}` (Heartbeat.cs:189).

**V\*:** V3=H7 arreglado; V5=H34 arreglado salvo el comentario del csproj; V6=H12 arreglado; V7=H11 arreglado; V8=H23 a
medias; V9=H18 arreglado; V10=H31 arreglado salvo los comentarios; V11=H32 arreglado; V12=H30 arreglado; V14=H36
arreglado en la App; V15=H37 arreglado; V16=H33 arreglado. V1, V2, V4 y V13 ya estaban arreglados y siguen así: V1 en
NativeTurnLoop.cs:288-302.

**G\*:** G1 sigue (H1 a medias, H2, H3); G2 es del kernel; G3=H6 arreglado; G4=H5 a medias; G5=H29 arreglado; G6=H35
sigue; G7=H17 arreglado; G8 y G9 (H38, H39) siguen; G10=H40 arreglado; G11 y G12 (H21, H22) arreglados; G13=H15 a
medias; G14=H13 arreglado; G15=H14 arreglado; G16=H16 arreglado.

**Lo que se mantuvo a propósito (D1, `system.power` sin confirmación, el navegador de la persona como destino):** el
diff no lo empeora. `browser.control` ahora incluso se retiene en el latido.

### Lo que dicen los commits y no hacen (pregunta 3)

- d6d4f482d «el latido retiene toda entrada a una ventana»: falta `input.keyboard.layout` (fila 1).
- 7f3253fd8 «la memoria dice por qué rechaza»: sólo el caso del canal sensible; los demás rechazos de memoria vuelven sin causa (fila 5).
- e4ad142a9 «el arranque de la mente sin datos que nadie lee»: el registro todavía exige siete campos que la App no lee (fila 7).
- 4af04c415 «presencia sin ficheros que nadie lee»: lo hace, pero deja huérfano `FirstWakeUtc` (fila 13).
- 214b4930e «la interfaz … sólo con lo medido»: CPU, memoria, disco y uptime sin lectura se muestran como 0 (fila 16); la sonda sigue leyendo `.turn-progress` (fila 14) y quedó CSS sin dueño (fila 19).
- 746667a23 «la interfaz muestra cada fallo con su código»: el fallo de arranque de la mente no se muestra hasta que falla un turno (fila 6).
- 0d4e1d31b «el contrato de paquete toma los assets de la interfaz del build que entrega»: Setup sí, pero `product_build_common.ps1` no, y el build de producto y el de setup siguen rotos (fila 9).
- d711f4f3e «los lanzadores no publican variables que nadie lee»: las variables sí; quedan `--commit` y `--after-welcome`, que no lee nadie (fila 15).

### Resumen

El diff cumple lo central de esta área. El latido ya no pisa la confirmación de la persona (H4). Los valores de memoria
no viajan en las observaciones (H6). La App ya no cambia la herramienta que eligió el modelo (H7). Hay un solo cortador
de observaciones y lleva marca (H10). Los ajustes, el puente y la interfaz perdieron todo lo fijo, falso o retirado
(H11-H19, H21, H22, H30-H33). La cola durable y `PendingMemoryConfirmation` se fueron sin dejar ninguna referencia
(H27, H28). Lo que más pesa sigue en el latido: puede mandar a la red una consulta armada con la memoria o las ventanas
del dueño sin que nadie lo pida (H3), corre solo lo que la copia a mano de riesgos deja pasar, como `shell.command.run`
(H2), y su lista de «entrada a una ventana» todavía deja pasar `input.keyboard.layout`, que postea un mensaje a la
ventana enfocada de la persona (H1). El arreglo del instalador quedó a medias: `product_build_common.ps1` conserva los
nombres viejos de los assets y la exigencia exacta, así que el build de producto y el de setup siguen fallando con el
dist actual, y el paquete sigue sin la mente (H26). Lo nuevo es menor: dos huérfanos de los borrados (`FirstWakeUtc` y
el `.turn-progress` de la sonda), argumentos del lanzador del conductor que nadie lee, métricas que muestran 0 cuando
no se midieron, CSS sin dueño y un rechazo de memoria que perdió su causa.

**Recuento:** 9 nuevos (filas 5, 13, 14, 15, 16, 17, 18 y 19, más la 21, que no se había reportado). Siguen o a
medias: 15 ids (H1, H2, H3, H5, H8, H15, H23, H25, H26, H35, H38, H39, y los restos de H31 y H34), más la fila 22, que
no se había reportado. Arreglados: 26 (H4, H6, H7, H9, H10, H11, H12, H13, H14, H16, H17, H18, H19, H20, H21, H22,
H24, H27, H28, H29, H30, H32, H33, H36, H37 y H40), más H31 y H34 salvo comentarios.
