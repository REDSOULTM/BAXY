# Plan post-goal C03 — 2026-09-20 (Fable 5.1 planifica, Opus 5 ejecuta)

> **Goal corto para el chat nuevo (pegar tras `/goal`):**
>
> Ejecutá íntegro el plan `C:\Users\usuario\.claude\plans\wise-foraging-quill.md` (Fable planificó; vos, Opus 5,
> sólo ejecutás). Repositorio `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama
> `codex/kiro-goal-c03`. Antes de tocar nada leé `AGENTS.md`, el plan entero y `MEMORY.md` de tu memoria.
> Seguí las fases en orden sin saltarte ninguna compuerta: Fast/Full verde sin relajar nada, cien 100/100
> tras cada cambio de mente/App, una tanda sellada por capacidad, adjudicación honesta, nunca editar `src`
> con algo corriendo. No pares hasta: (1) Full verde y G04.06/G06.06 selladas; (2) las 35 filas reabiertas
> vueltas a 742/742 con un motor general de computer use, 35/35 categorías; (3) cien 100/100 sobre el HEAD final; (4) todo
> empujado y documentado. Las decisiones del dueño ya están en el plan: lo que el plan marca «PREGUNTAR» se
> pregunta; lo demás no se vuelve a preguntar.

---

## 1. Contexto

El goal C03 se cumplió hoy: 742/742 filas del registro, 35/35 categorías, corridas cien-76…86 100/100,
HEAD local `1a8498bb1` (**3 commits sin empujar**: veto `playback_denied`, cien-86 + import `Iterable`,
seis filas formales selladas). El dueño (Emmanuel) pasó a Fable la planificación y a Opus 5 la ejecución.

**Decisiones del dueño de hoy (2026-09-20), literales o casi:**

| # | Decisión | Consecuencia |
|---|---|---|
| D1 | «Todo lo que se detalla en las encuestas son cosas que BAXY debe hacer (cada fila dice si debe o no y cómo)». | El registro es la especificación. Las filas positivas acreditadas como «límite» o con una lectura en vez de la acción se **reabren** (§5). |
| D2 | Envíos reales de mensajes «a cualquiera, con o sin preguntar dependiendo del modo: normal o bypass» (Q1: «a cualquier persona»). | `message.send` al destinatario nombrado; modo normal → confirma; bypass → envía. |
| D3 | «Hay muchas acciones que piden confirmaciones innecesarias (poner una serie…)». Elige que dejen de pedirla: reproducir/navegar, portapapeles/captura, pulsar/escribir en apps, Wi-Fi/Bluetooth/ajustes. «Lo que debe pedir permiso son sólo cosas destructivas o irreparables». | Nueva tabla de `RiskPolicy` en modo normal (§4 Fase 2). Coincide con `documentacion/00_IDENTIDAD.md` §«Peligro y confirmación — dos modos». |
| D4 | Correo: «BAXY debe adaptarse a Gmail o Outlook, dependiendo qué use el usuario»; aprueba Outlook clásico de REDPC → casilla de pruebas. | `email.send` con detección de proveedor (§4 Fase 7). |
| D5 | «Cerrame todo»: todo menos VS Code y las ventanas propias, cierre educado, si pide guardar se detiene y avisa. | Ya es así (`window.close.all`). Nada que construir; sólo verificar en la Full. |
| D6 | Pestañas: sobre **su** Chrome real, por teclado/UIA, sin cerrar la ventana. | Nueva operación (§4 Fase 5). |
| D7 | Spotify: «BAXY abre Spotify y pone algo él mismo antes de ajustar». | Misión encadenada (§4 Fase 9). |
| D8 | Full rojo: «arreglar todo hasta verde, sin relajar nada»; informar cuántas y qué tocan antes de arreglar. | §4 Fase 1 (el informe ya está en este plan). |
| D9 | «Quiero que Claude Code tenga permisos totales para mandar mensajes por Discord o WhatsApp; son canales seguros de prueba». | §4 Fase 0 paso 4: reglas de permiso confirmadas por el dueño. |
| D10 | BAXY «debe estar en el tope del arte del computer use, encadenar tools y hacer misiones compuestas; todo se detalla en AGENTS.md e identidad». | Principio transversal (§3): toda capacidad nueva se construye como misión encadenable; cascada UIA→OCR→visión es el núcleo (`00_IDENTIDAD.md:137`). |
| D11 | Reabrir también: ejecutar comandos, fondo de pantalla y PowerPoint, leer chats privados y memes/imágenes de la web. **Contactos NO**: «dice explícitamente que BAXY no puede hacerlo porque en PC esto no tiene sentido». | §5. |
| D12 | «Una vez que todo esté listo y bien, hacer merge con main como sea recomendado». | PR por merge commit al final (§4 Fase 12), sin volver a preguntar. |
| D13 | Terceros en los literales: «sólo cambiar por los canales seguros y listo: si es por Discord "Ron92", si es por WhatsApp "Música"; "Dile a mamá por wsp que ya voy" → "Dile a Música que ya voy"». | En las tandas el literal se mide con el destinatario sustituido por el canal de prueba; correo → casilla de pruebas. Los créditos se conservan; el panel anota `literal_measured` con la sustitución (§4 Fases 6–7). |
| D14 | Destinos de prueba confirmados: «Música» (WhatsApp), «Ron92» (Discord), casilla `autor@example.com`; sí a medir «al nombrado» con esos nombres. | Nada que preguntar en Fases 6–7. |
| D15 | Discord: «que se haga como sea recomendado»: texto/MD entra directo; voz pregunta antes y se queda conectado con el micrófono como esté (no se silencia salvo pedido). | §4 Fase 4. |
| D16 | Pestañas: «dejar abierto el navegador, a menos que el usuario diga lo contrario»; varios navegadores y ninguno nombrado → preguntar cuál. | §4 Fase 5. |
| D17 | «VS Code se debe mantener a toda costa porque estamos en pleno desarrollo». | `window.close.all` conserva Code/terminal/producto; nunca se toca. |
| D18 | Spotify: «hacer lo recomendado, sólo me interesa que BAXY funcione» → medir las cuatro formas (nivel absoluto, en pausa, control SMTC, nada) y construir sólo lo que falle, más la cadena de D7. | §4 Fase 11. |
| D19 | Full roja: «como sea mejor y recomendado, pero cumplir con goal C03 (y tener en cuenta que sigue en los demás goals)». | Re-anclar contratos citando decisiones + escribir las pruebas faltantes; no romper sellos de otros goals. |
| D20 | RAM: «cambié de PC, este tiene 32 GB; no cierres nada a menos que sea necesario para el desarrollo y pruebas de BAXY». | La guarda de 4000 MiB queda; Opera GX no se cierra salvo que la guarda falle de verdad. |
| D22 | «Los mensajes de prueba de Discord cambiaron a Ron92; ese es el nuevo canal de pruebas de desarrollo» (mensaje directo con el usuario `.wolfsoultm.4191`, título de ventana «Ron92»). | Sustituye a «Valeria» en todo: `ForcedTestDestination` (`DesktopMessagingAdapter.cs:36-46`), `approve_message_send.py`, drivers, y la sustitución D13 (tercero por Discord → «Ron92»). El primer paso de la Fase 6 es cambiar la constante y medirla. |
| D21 | «Las misiones de computer use se deben resolver de manera general: no al 100 % para eso, sino generalizar para que BAXY pueda hacer casi cualquier cosa en el PC mediante sus tools + computer use». | Fases 4–5 reescritas: un motor general (ver → decidir → actuar → verificar) y las 35 filas como banco de aceptación; herramientas tipadas nuevas sólo donde Windows verifica mejor que la pantalla. |

## 2. Estado de partida verificado (manda sobre cualquier documento viejo)

- **Full (`scripts/test_source_quality.ps1 -Mode Full`) está rojo**: `dotnet-tests` con 54 fallos (Integration 34/3234,
  Kernel 16/162, Providers 4/605; Contracts 70/70 y Setup 477/477 verdes). La etapa `python-tests` **no corrió**
  (el gate corta en la primera roja). Log en `C:\Users\usuario\AppData\Local\Temp\claude\c--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo\b0264e2d-8694-4887-bba6-c132eb18a1d2\scratchpad\full.log`.
- **Ya existe y ya es real** (no construir de nuevo): `window.close.all` (`WindowsWindowControlProvider.CloseAllAsync:362`,
  conserva Code/Code-Insiders/WindowsTerminal/baxy-core/Baxy.App, WM_CLOSE → menú de sistema, nunca fuerza;
  CLOSEALL1733 acreditó H0467/H0484); `audio.app.volume.adjust` (sesiones `IAudioSessionManager2`, genérico por
  proceso; AUDIO1801 acreditó H0652); `message.send` + `message.recipient.resolve` (envío real a un destinatario
  resuelto, `DesktopMessagingAdapter.SendAsync:148`, OCR de la burbuja) y `message.send.test` con destino forzado
  (`ForcedTestDestination`: WhatsApp «Música», Discord «Ron92», correo `autor@example.com`);
  correo por Outlook clásico COM (`SendTestMailAsync:306`, `MailScript` en `MicrosoftAccountAdapter.cs:55`);
  `client.channel.locate` (Ctrl+K por UIA, localiza y **no entra**); `browser.control close_all` (sólo el navegador
  CDP propio); `game.install.named/prepare/commit/status/cancel*`, `game.launch`, `game.purchase.prepare/commit`
  (`SteamLocalAdapter`: `steam://` URIs + manifiestos); `input.key.press`, `input.visible.click` (cascada UIA→OCR→visión),
  `input.text.type`; modo `ConfirmationMode.Normal/Bypass` (`RiskPolicy.cs`, `ConfirmationModeStore.cs`, PUT desde la
  UI `FieldProductChannel.cs:1014`, env `BAXY_CONFIRMATION_MODE`).
- **Falta**: entrar al canal (Discord), pestañas del navegador del dueño, envío al destinatario nombrado como camino
  vivo (hoy la mente prefiere `message.send.test`), correo a dirección libre (Outlook/Gmail), desinstalar juego,
  descargar/instalar/lanzar medidos de verdad, modo avión, pulsar enter/enviar dentro de una app, comprimir/abrir zip,
  ejecutar comandos, fondo de pantalla, presentación, leer chats, imágenes/memes de la web, cadena «abrir Spotify → sonar → ajustar»,
  nivel absoluto por app.
- Registro canónico (privado): `C:\Users\usuario\AppData\Local\BAXY\C03-survey-requirements336-private\requirements.jsonl`
  (742 filas; campos `case_id, literal, expectation_kind {positive 721, unmarked_limit 18, negative_limit 3},
  verification_status, verification_reason, verification_evidence, reopen_history`). Sólo lo escribe la raíz.
  `root_publish` sólo sube créditos; **reabrir es un script aparte** (precedente `reopen_1685.py`).
- Git: `origin/codex/kiro-goal-c03 = da3f4a2d5`; `origin/main` tiene base común `92310260f` con HEAD y va 2 commits
  por delante (MIT, política de evidencia privada); la `main` **local** está vieja (sin ancestro). Un PR por merge
  commit sería limpio. `C03_ASTRA_AUTORIDAD.md:62-70,176`: no hace falta integrar en `main`.
- Permisos: `.claude/settings.local.json` sólo tiene reglas de lectura; el clasificador de «transacciones reales»
  denegó en sesiones anteriores operar WhatsApp/Discord reales. Esta sesión corre en bypass; puede que no deniegue.
- Evidencia vieja ya fuera del repo: `C:\Users\usuario\BAXY-evidencia\2026-09-20\` (`MANIFEST.json`); memoria
  `c03-evidence-folder.md`.

## 3. Reglas transversales (no se relajan)

1. **Método de tandas** (memoria `c03-disney-instrument.md`, `c03-chain-instrument.md`, `c03-campaign-pitfalls.md`):
   scratchpad de instrumentos `S=C:\Users\usuario\AppData\Local\Temp\claude\d--Perfil-Escritorio-ETC-Programacion-BAXY-DEFINITIVO\250e1a56-9daa-4ae6-a51f-44fe3a271a6d\scratchpad`;
   generador `make_<NNNN>.py` → `next_tanda.py spec_<NNNN>.json` (campos `prev,new,grandparent,template,sources,plan_title,plan_body,note,owner,build_kind,cause,change,sentence,build_sentence,derive_extra`)
   → `setup_<camp>.sh` (commit de `src`, build oficial `C03-repairs<NNNN>-build`, derive, prepare, casos) →
   `write_results<NNNN>.py` → `chain_<camp>.sh` (adjudica, publica, documenta, commit, push). Trampas: apóstrofes en
   el spec, «BUILDnnnn» ajeno en el texto del spec, delta set vs 1142 = ficheros realmente cambiados, seises sellados,
   literales ya cubiertos abortan (`literal not open/eligible`), `git add` vacío cuando `sources=[]`, `build.py` se copia
   del build anterior, nunca `src` sucio con una tanda o cien corriendo. Crédito = literal aprobado + **dos** variantes
   aprobadas. Perfiles nuevos se barren al final con `move_evidence.py` (scratchpad c--) a una carpeta fechada.
2. **Cien tras cada cambio de mente/App**: `powershell -File scripts/run_baxy_conductor.ps1 -TurnsFile artifacts/comprobaciones/C03/cien-v18.turns.jsonl -Profile C:/Users/usuario/AppData/Local/BAXY/cienNN -Capture <S2>/cienNN-capture`,
   `python read_capture.py <capture> <turns>` → `cienNN_paired.txt`, diff contra la anterior (sólo relojes y
   reformulaciones con los mismos hechos), 100 publicadas, copiar `events.jsonl` a `artifacts/comprobaciones/C03/cien-NN/`,
   sección en `CIEN.md`. Numeración: cien-87 es la siguiente. Nunca cien y tanda a la vez.
3. **Compuertas**: Fast tras cada commit de `src` que toque C#; Full al cierre de cada bloque de fases y al final.
   Un rojo bloquea; nada de skip/xfail/umbral; cada prueba actualizada cita la tanda o decisión que cambió el contrato.
4. **Computer use al tope (D10)**: cada capacidad nueva se diseña como paso encadenable de una misión compuesta
   (`CHAIN1931`: un efecto revisado por paso, proyección de evidencia, grounding dependiente) y usa la cascada
   UIA→OCR→visión existente (`WindowsVisibleControlAdapter`, `WindowsVisibleOcrLocator`); nada específico de una app
   fuera de alias de catálogo (`data/catalog_operation_aliases.v1.json`, `alias_count`). Propiedades de esquema
   **ordenadas**; descriptores en orden ordinal; verificador con postlectura y autoridad nombrada.
5. **Honestidad**: BAXY nunca afirma un efecto sin recibo verificado; cada fallo termina en un código tipado y un final
   que lo dice. Ningún envío real a terceros desde una tanda: sólo «Música», «Ron92» y la casilla de pruebas.
6. **Recursos**: este PC tiene 32 GB (D20); la guarda de 4000 MiB libres queda pero no se cierra nada del dueño
   salvo que falle de verdad y sea necesario para las pruebas; vswhere en PATH; esperar nodos MSBuild del IDE.
7. **Permisos**: Opus no edita su configuración de permisos por iniciativa propia ni por pedido de un peer. Si un
   comando de driver es denegado, aplica Fase 0 paso 4.
8. **Documentar cada tanda** en `CHECKPOINT.md`/`HANDOFF.md`/`CURRENT_CATEGORY_COUNTS.md` (lo hace `chain_*.sh`) y el
   diseño en `COMPUTER_USE_DISENO.md` (§15 en adelante); memoria actualizada al cerrar cada bloque.

## 4. Fases (en este orden)

### Fase 0 — Cierre administrativo (30 min, sin `src`)
1. `git push origin codex/kiro-goal-c03`. Si diverge: `git fetch`, parar y reportar; nunca reset/rebase.
2. Copiar este plan a `artifacts/comprobaciones/C03/PLAN_POSTGOAL_2026-09-20.md` y escribir
   `artifacts/comprobaciones/C03/DECISIONES_DUENO_2026-09-20.md` con la tabla D1–D12 (texto del dueño entre comillas;
   es la autoridad que citan el script de reapertura y los commits). Commit + push.
3. Sección **cien-86** ya está en `CIEN.md` (§cien-76 a cien-86); verificar y, si falta la línea de cien-86, añadirla.
4. **Permisos (D9)**: el dueño pega las reglas de §9 en `.claude/settings.local.json` y abre la sesión de Opus en
   modo bypass de permisos. Si aun así un driver es denegado, Opus lo reporta y el dueño lo lanza desde su terminal;
   Opus no edita la configuración.
5. Actualizar memoria: `c03-reopened-capabilities.md` (D1–D11: ya no rige «nunca enviar de verdad»; contactos siguen
   límite), `c03-limits-and-conditionals.md`, y nueva `c03-postgoal-plan.md` con el índice de fases y su estado.

### Fase 1 — Full verde, cien-87, G04.06/G06.06 (3–5 h)
**Informe al dueño (D8) — ya clasificado, transcribirlo en el chat antes de tocar nada:**

| Grupo | Pruebas | Causa | Arreglo |
|---|---|---|---|
| A | 19: `HistoricalAudioRoutingTests` (Frozen*Volume/Mute/AudioStatus/…), `HistoricalGpuStatusRoutingTests` (FrozenGpu*), `HistoricalNaturalNoteRoutingTests` (FrozenPureNote*, FrozenFilesystemNoise*), `NaturalMemoryRequestParserTests` (RoutesEveryAudited*), `HonorsEveryHardNegativeBehavioralContract` | Fichero privado `tests/data/historical_messages.jsonl` ausente en REDPC (gitignored `.gitignore:209`) | Copiar `C:\Users\usuario\Desktop\ETC\Programacion\BAXY\tests\data\historical_messages.jsonl` → `tests/data/` (no se versiona). Correr `dotnet test tests/Baxy.Integration.Tests -c Release --filter FullyQualifiedName~Historical`; si algún id esperado no está en el corpus viejo, decirlo como ambiental, no inventar filas. |
| B | 7: `ShellRequiresExactOrderedPublicToolCatalog…`, `CatalogHasStableUniqueCompleteToolDescriptors`, `PublicToolProjectionCarries…`, `RegistryAndCatalogAreOneToOne…`, `ProtocolBoundaryRejects…` (169→190), `EveryExternalHandlerCrossesItsProviderAndVerifierBoundary` (85→102), `EveryCatalogOperationHasAnObservationOrAnUnverifiableReason`/`EveryIsolatedObservedMutationHasALyingExecutorTest`/`LiveCoreExercisesRestorableOperationsTwice` (regla Goal 05 faltante para `audio.app.volume.adjust`) | El catálogo creció en C03 (170→191 descriptores, 169→190 tools, 85→102 handlers) sin re-sellar; falta la regla de observación de una op nueva | `tests/Baxy.Kernel.Tests/ProductCatalogTests.cs:44,67,85,417` → cifras reales **más la lista nominal** de las ops añadidas (sacarla con `git log --oneline 53e1ff920..HEAD -- src/Baxy.Kernel/Operations/ProductCatalog.cs` y el diff); en `tests/Baxy.Integration.Tests` añadir a la matriz Goal 05 la regla de `audio.app.volume.adjust` (postlectura de sesión, autoridad `windows_core_audio_session_postread`) y su «lying executor». |
| C | 13: `WindowInventoryRemainsAReadOnlyBoundedOperationWithAnExplicitSelector` (v2→v3; caso `offset:0.5` ahora válido) | Contrato de `window.resolve` subido a v3 en C03 | Re-pinar a v3 citando la tanda (grep `inventory.v3` en CHECKPOINT). El caso `{"process":"*","offset":0.5}` que ahora valida es **posible regresión** de `OperationArgumentValidator`: mirar antes; si el validador acepta fracciones donde el esquema pide entero, arreglar el validador, no la prueba. |
| D | 5: `StrictProjectionAcceptsOnlyKnownCompletedShapes` ×3, `ExportProjectionNeverEchoes…`, `ExportCreatesInspectable…` (`KeyNotFoundException`) | `src/Baxy.App/MemoryOperationResponseProjection.cs` espera una clave que las formas selladas no traen (cambio MEMORY12xx) | Arreglar la proyección para aceptar las formas selladas (`TryGetValue`), no la prueba. |
| E | 1: `NetworkIpListIsPrivacySensitive…` (`privacy_sensitive`→`read_only`) | Decisión 13-09 (la IP sin confirmación) | Actualizar la prueba citando la decisión. |
| F | 5: `DecisionRecoveryPreservesFailureInsteadOfInventingPersonalData` (espera `turn_runtime_failure`, recibe `ambiguous_request`), `RejectedUnsupportedReplyKeepsItsCatalogBoundary…` (espera `out_of_catalog`, recibe «No pude abrir la aplicación.»), `VerifiedSystemTime…/ProposesUnsolicitedCatalogAction("cierra aquello")`, `StatusFactsDoNotCarryPreviousRequests`, `ExplicitLocalTimeQueriesRouteDirectly("Mi puoi dire che ore sono?")` | Contratos cambiados por tandas (LANG1909: otro idioma → pedir repetir; DIALOGUE: «cierra aquello» pregunta; `priorRequests` se conserva para la charla) **o** regresiones (un fallo de runtime convertido en aclaración; un rechazo fuera de catálogo convertido en «no pude abrir») | Una por una: con tanda sellada que lo justifique → actualizar la prueba citándola; sin justificación → arreglar `src/baxy_mind` y medir (Fast + cien). Los dos primeros huelen a regresión real. |
| G | 4: `NamedBrowserNavigationKeepsItsSessionForTheImmediatePageRead` (targetId real vs «opera-page»), `VerifierBindsAConvergedMainWindowAfterPackagedHandleTransition` (DelayCalls 0), `VerifierRequiresBothVisibleWindowAndObservedForeground` (verifica sin foreground), `ActivationKeepsTheOriginalObservationTimeout…` (28→300) | SITE1933 (sesión nombrada) y UI1775 (esperas) cambiaron el proveedor de apertura | `VerifierRequiresBothVisibleWindowAndObservedForeground` es probable **regresión** del verificador (aceptar sin foreground = afirmar sin verificar): arreglar el proveedor. Los otros tres: re-pinar citando la tanda. |

Pasos: (1) grupo A; (2) B–E; (3) F–G con diagnóstico escrito por prueba en el commit; (4) Fast; (5)
`test_source_quality.ps1 -Mode Full` en segundo plano (ahora corre pytest: si trae rojos, mismo tratamiento: grupo,
causa, arreglo sin relajar); (6) verde entero → commit + push; (7) **cien-87** sobre ese HEAD; (8) sellar G04.06/G06.06
en `documentacion/sprints/Sprints comprobación/03_MATRIZ_DE_CRITERIOS.md:151,181`:
«Fuente publicada en <sha40>, remoto verificado y main intacto. Full <fecha>: Python N pases/M skips ambientales/K
subpruebas; .NET N pases/M omisiones (Contracts/Kernel/Providers/Setup/Integration); Fast exit 0; cien-87 100/100;
Encuesta 742/0/0.» Commit + push. Aceptación: `source_quality_gate_passed: mode=Full`, `git status` limpio,
`git rev-list --count origin/codex/kiro-goal-c03..HEAD` = 0.

### Fase 2 — Confirmaciones sólo para lo destructivo (D3) (1–2 h + cien-88)
- Único fichero de política: `src/Baxy.Kernel/Policy/RiskPolicy.cs`. Tabla nueva en `Normal`:
  `ReadOnly/Reversible/Sensitive` → Allow; `External` → Allow **salvo** `message.send`, `message.send.test`,
  `email.latest.reply`, `email.send`, `client.channel.open` con canal de voz (una persona te oye; ver Fase 4) →
  RequireConfirmation; `Irreversible` (WorkLoss/SessionDisruption/Monetary) → RequireConfirmation, con `system.power`
  exento (ya); `Installation` → Allow (instalar no destruye; cancelar/desinstalar son WorkLoss); `Forbidden` → Deny.
  `Bypass` → Allow todo (ya). **No cambiar las etiquetas de riesgo del catálogo** (sellos históricos las citan).
- Ops que dejan de preguntar en normal (46): `media.play.exact/query/youtube`, `streaming.navigate`,
  `streaming.play.named`, `browser.navigate(.named)`, `browser.page.read`, `browser.tabs.list`, `calendar.event.create`,
  `capture.screenshot`, `capture.active.window`, `clipboard.*`, `input.text.type`, `input.visible.click`, `ocr.read`,
  `vision.describe`, `bluetooth.device.pair`, `wifi.*`, `system.settings.set`, `memory.enable/export`,
  `peripheral.print/scan`, `email.latest.read`, `message.draft`, `game.install.*`/`package.install.commit`. Siguen
  preguntando: `message.send*`, `email.*reply/send`, `game.purchase.commit`, `game.install.cancel*`, `memory.forget`,
  `system.process.terminate.named`, `system.recyclebin.empty`, `window.close.all`, `app.close`, `game.uninstall.named` (nueva).
- Tests: `tests/Baxy.Kernel.Tests` (RiskPolicy/ConfirmationAuthorityTests) actualizados citando
  `DECISIONES_DUENO_2026-09-20.md` D3. `ProductConductorHost.cs:381-407` (lista blanca del instrumento) **no cambia**.
- Sondas manuales (`turn-probe.sh` del scratchpad c--) en modo normal: «pon Daredevil en Disney+» reproduce sin
  pregunta; «copiá esto» sin pregunta; «mandale hola a Música por whatsapp» pregunta; con
  `BAXY_CONFIRMATION_MODE=bypass` envía. Fast → commit → **cien-88** → push.

### Fase 3 — Reapertura registral (D1, D11) (1 h, sin `src`)
- Script nuevo en el scratchpad c--: `reopen_1957.py`, calcado de `reopen_1685.py` (scratchpad d--): por fila
  `verification_status covered→open`, `reopen_history += {utc, from, to, cause, credited_by, previous_reason,
  decision: 'artifacts/comprobaciones/C03/DECISIONES_DUENO_2026-09-20.md'}`, `generalization_status='required_before_closure'`,
  `verification_reason='Reabierto 2026-09-20 (<TANDA> lo acreditó como <lectura|límite|parada honesta>): la encuesta
  pide <acción>; pendiente de medirse con el mecanismo real'`. Publica `artifacts/comprobaciones/C03/REOPEN1957/REGISTRY_UPDATE.json`
  (`c03-registry-reopen-v1`, before/after sha, counters) y reescribe `CURRENT_CATEGORY_COUNTS.md` (tabla desde registro +
  `taxonomy.json`), `CHECKPOINT.md`, `ESTADO_PARA_DUENO_2026-09-13.md`, `HANDOFF.md`, `GoalC03.txt`, `RELEVO_ACTIVO.json`,
  `CONDICIONES_POR_CATEGORIA_2026-09-13.md` (apéndice «Reapertura 2026-09-20»). Copia del registro antes de escribir.
- **Filas que se reabren (35)** — ver §5. Resultado: **707/742**. Commit «C03: REOPEN1957 por decisión del dueño
  2026-09-20 (35 filas: la encuesta es la especificación)» + push.
- **Auditoría semántica pendiente** (informe, no reapertura): de las 134 filas restantes acreditadas con «cero
  operaciones y una pregunta», Opus lista las que la encuesta podría esperar como acción directa (p. ej. H0011
  «cancelá la alarma» cuando hay una sola) y las presenta al dueño en un bloque al final de la Fase 3. **PREGUNTAR**
  sólo eso, una vez.

### Fase 4 — Motor general de computer use (D10, D21) (3–4 días + cien)
**Reparto (decisión del dueño 2026-09-20, tarde): esta fase la construye una sesión Fable 5.1 high; Opus 5 NO la
toca.** Fable trabaja en un worktree propio sobre la rama `fable/computer-use-engine` (creada desde
`codex/kiro-goal-c03`), sin correr tandas ni cien mientras Opus tenga algo corriendo en el PC; la tanda de aceptación
CU1959 se corre en una ventana acordada con Opus (mensaje entre sesiones o aviso del dueño). Cuando Fable entregue
(rama empujada, Fast verde, CU1959 adjudicada), Opus la fusiona en `codex/kiro-goal-c03`, corre una cien y arranca
la Fase 5. Mientras tanto Opus hace las Fases 1–3, 6–8 y las herramientas tipadas de la Fase 5 que no necesitan el
motor (`shell.command.run`, `file.compress`/`file.open`, `system.settings.set airplane_mode`, `desktop.wallpaper.set`,
`document.presentation.create`, `web.download`, `game.uninstall.named`, Steam por `steam://` + manifiesto).
**Reparto en dos sesiones Fable (D24)**: rama base `fable/computer-use-engine`; **Fable-A «ojos y manos»** en
`fable/cu-perception` (vista compacta, color HSV, grounding por texto/plantilla/encoder, `input.scroll`, clic por
índice/rect, `wait_for`, postlecturas) y **Fable-B «cerebro»** en `fable/cu-loop` (contrato de vista/acción,
`mission.computer_use` en mente + Kernel, memoria de procedimientos, journal CHAIN1931, tanda CU1959). Primer paso
común: el **contrato JSON de vista y acción** (`documentacion/computer-use/CONTRATO_VISTA_ACCION.md`) lo escribe B
y lo aprueba A antes de codificar; B trabaja con fixtures de vista hasta que A entregue. Fusiones diarias a
`fable/computer-use-engine` (merge commit, Fast verde). Opus, mientras, hace la **semántica a full** (Fase 3
ampliada): auditar las 742 filas contra la encuesta, reabrir lo que corresponda por D-audit, arreglar las lecturas de
la mente (contexto determinista, nombre aproximado, elegir por la persona sólo donde es determinista) con tandas y
cien; después las herramientas tipadas y las Fases 6–8. **Un solo proceso del producto en el PC a la vez**: quien
vaya a correr algo avisa por SendMessage a las otras dos sesiones y espera «ok».
Entregables adicionales del motor (D23): visión sin LLM en tres escalones (texto → plantilla local con OpenCV y
color HSV por control → encoder pequeño MobileCLIP2/SigLIP 2 y Florence-2-base sólo si el banco lo exige) y
**memoria de procedimientos** (misión lograda → secuencia guardada por app+objetivo, reproducida determinista y
verificada; el modelo interviene sólo cuando la vista se desvía).
**Principio (identidad, `00_IDENTIDAD.md:118-137`)**: cubrir el PC, no las apps; cero código por aplicación fuera de
alias; lo que no cabe en una herramienta se encadena; la cascada UIA → OCR → visión es el núcleo. Las filas de la
encuesta no se resuelven con una operación cada una: se resuelven con **un motor** que ve, decide, actúa y verifica
en bucle sobre cualquier ventana, y con las pocas herramientas tipadas del PC que Windows ofrece con verificación
propia (ficheros, registro, manifiestos, sesiones de audio, COM).

- **Percepción (existe, se completa)**: `input.visible.controls` (UIA: nombre, tipo, rect, estado) + `ocr.read` de la
  ventana en foreground (`WindowsVisibleControlAdapter`, `WindowsVisibleOcrLocator`, `DesktopClickVisible.ps1`).
  Añadir la **vista compacta** para el modelo: ≤ 60 controles accionables con índice, tipo, etiqueta, estado
  (selected/expanded/value), zona de pantalla; texto OCR agrupado por zonas; título y proceso de la ventana. Sin
  capturas al modelo (es texto).
- **Acción (existe, se completa)**: `input.visible.click(label|index)`, `input.text.type`, `input.key.press`
  (combos), `window.focus/resolve`, `app.open`, `browser.*`. Añadir `input.scroll(direction, amount)` y el clic por
  índice/rect cuando la etiqueta se repite. Cada primitiva conserva su postlectura (superficie cambió, control
  desapareció, texto esperado presente).
- **Bucle de misión (nuevo, en mente + Kernel)**: `mission.computer_use(goal, success_check, budget)`. Cada
  iteración: vista → el modelo elige **un** paso del catálogo (JSON estricto, temperatura 0, sólo primitivas
  permitidas) → el Kernel lo ejecuta con verificación → nueva vista. Termina cuando `success_check` se cumple
  (texto/control esperado visible **o un recibo independiente**: manifiesto, fichero, sesión de audio) o se agota
  el presupuesto (p. ej. 12 pasos / 90 s), con hito narrado cada ≤ 3 s y todos los pasos en el journal como misión
  encadenada (patrón CHAIN1931: un efecto por paso, proyección de evidencia). Riesgo por paso = el de la primitiva
  (Fase 2: en normal sólo confirma lo destructivo o un envío a una persona). Reintento acotado por paso
  (`wait_for` de etiqueta hasta 24 s, lección UI1735/UI1775).
- **Herencia primero (D-2026-09-16)**: `D:/Perfil/Escritorio/ETC/Programacion/Probando Gemma 4/gemma4_agent`
  (tools `computer_use` goal-driven, `gui.wait_for`, `uia`, `vision`): reutilizar el diseño del bucle y el
  `wait_for`; no copiar hard-codes de apps.
- **Modelo**: Qwen3-4B texto sobre UIA + OCR, dentro de las guardas. Si el banco (abajo) muestra pantallas sin UIA ni
  OCR útil (canvas, juegos), **PREGUNTAR** al dueño con números medidos (VRAM, latencia, qué filas desbloquea) si
  añade un modelo de visión pequeño; nunca decidirlo solo.
- **Tanda CU1959 — aceptación general del motor**: 6 misiones en apps distintas, todas por el mismo motor sin código
  por app: «ve a Cotele en Discord» (H0290), «cerrá todas las pestañas de chrome» (H0444), «abre Steam y ve a la
  biblioteca» (regresión de UI1731), «en Discord apretá enter» (H0175), «abrí Configuración y activá el modo avión»
  (H0107), «en la calculadora calculá 12×7» (regresión). Dos variantes por literal, límites. Crédito de lo que cubra.
  Fast → cien-89.

### Fase 5 — Banco de la encuesta sobre el motor (las 35 filas) (5–6 días + cien)
Las filas reabiertas se agrupan en **misiones** que corre el motor; sólo se añade una herramienta tipada cuando el
PC ofrece una verificación mejor que la pantalla. Cada grupo = una tanda (plantillas `ui1731`/`chain1931`,
drivers con snapshot/restauración de lo que tocan), literales por id, dos variantes aprobadas, límites, cien detrás
de cada cambio de mente/App.

| Grupo | Filas | Cómo lo resuelve el motor | Herramienta tipada nueva (sólo si hace falta) |
|---|---|---|---|
| Discord: entrar al canal | H0290, H0636 | foco → Ctrl+K → escribir → clic en la fila → verificar cabecera/«Voz conectada» (texto directo; voz confirma y se queda, D15) | ninguna (`client.channel.locate` queda de reserva) |
| Pestañas del navegador del dueño | H0444 | foco → contar `TabItem` → Ctrl+W hasta una → Ctrl+T → verificar 1 pestaña y título (D16: queda abierto) | ninguna |
| Pulsar dentro de una app | H0175, H0566 | foco → `input.key.press`/`input.visible.click` («Enviar») → postlectura (compositor vacío / burbuja) | ninguna; Enter con texto en un chat = envío → confirma en normal |
| Steam/Epic: descargar, instalar, lanzar | H0049, H0118, H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680, H0295, H0345, H0387, H0396, H0643, H0721, H0083, H0608 | misión GUI (biblioteca → buscar → título → «Instalar»/«Jugar») **verificada por manifiesto** (`appmanifest_*.acf` StateFlags / proceso del juego), no por pantalla; títulos grandes: iniciar y cancelar por la raíz; no poseídos → honesto + oferta de compra (`game.purchase.prepare`), nunca comprar en tanda | `game.uninstall.named` (steam://uninstall + ausencia de manifiesto; WorkLoss → confirma) para H0039, H0612 |
| Comprimir y abrir | H0542 | misión de 4 pasos por el planificador | `file.compress`, `file.open` (Compress-Archive, shell open, verificación de fichero/ventana) |
| Modo avión | H0107 | misión en Configuración **o** API | `system.settings.set airplane_mode` (`Windows.Devices.Radios`, postlectura de cada radio); el driver restaura |
| Comandos | H0245, H0048 | — | `shell.command.run(command, cwd)`: salida capturada (60 s, 8 KB), clasificación estática (destructivo → confirma), final que cita líneas verbatim |
| Fondo y PowerPoint | H0459, H0188 | abrir el archivo creado = misión (`file.open`) | `desktop.wallpaper.set` (SPI + registro, restaurar); `document.presentation.create` (python-pptx en el runtime, 6 diapositivas del modelo local) |
| Leer chats | H0510, H0720 | foco → buscar chat → **OCR de la banda de mensajes** (misma lectura que `SendAsync`), final que cita sólo texto OCR | `message.read.named` como proyección del recibo; quitar el contrato de límite `effect_intent.py:3393-3407` |
| Imágenes / memes | H0069, H0077 | misión: buscar → descargar → abrir con el visor | `web.download(url|query, folder)` (og:image de wikipedia.org; búsqueda de imágenes del motor existente) |

Orden de tandas: DISCORD1961 (+2) → TABS1963 (+1) → PRESS1965 (+2) → STEAM1967/1969/1971/1973 (+20; **PREGUNTAR**
antes qué títulos posee la cuenta) → CHAIN1975 zip (+1) → NET1977 avión (+1) → SHELL1979 (+2) → DESKTOP1981 (+2) →
CHATREAD1983 (+2) → WEB1985 (+2). Registro: 707 → 742.

### Fase 6 — Mensajes al destinatario nombrado (D2, D13, D14, D22) (3–4 h + cien; revalidación)
- **Primero (D22)**: el destino de prueba de Discord es el mensaje directo «Ron92» (usuario `.wolfsoultm.4191`), no «Valeria»:
  cambiar `ForcedTestDestination` en `src/Baxy.Providers.Windows/External/DesktopMessagingAdapter.cs:36-46`, el revisor
  `approve_message_send.py`, `discord_case.sh`/`msgsend_case.sh` y cualquier alias «Julia»/«ron.91» en `TitleNamesMatch`;
  verificar por título de ventana «Ron92» y OCR de la cabecera. Sonda antes de la tanda: un «hola» a Ron92 leído de vuelta.
- Hoy `effect_intent.py:18187-18194` prefiere `message.send.test`. Cambio: preferir `message.recipient.resolve` →
  `message.send` (`MissionPlanProposal.cs:157,214`; `DesktopMessagingAdapter.SendAsync:148`, OCR de la burbuja) para
  cualquier destinatario; External → confirma en normal, envía en bypass. `message.send.test` queda en catálogo
  (sellos) pero la mente no lo elige. La navegación hasta el chat puede pasar por el motor de la Fase 4; la
  verificación OCR del envío se conserva.
- Compositor: `sent_wrong_destination` (`llm.py:7945`) exige nombrar `seen.recipient`; no encontrado →
  `recipient_identity_not_verified` y final honesto.
- Tanda MSGNAMED1987 (plantilla `msgsend1847`, driver `msgsend_case.sh`, revisor `approve_message_send.py` adaptado a
  `message.send` con destino observado ∈ {Música, Ron92}): literales con el destinatario **sustituido por el canal de
  prueba (D13)** — WhatsApp H0008, H0540, H0489, H0208, H0611, H0225, H0024; Discord H0318, H0340, H0394 — más H0005,
  H0369, H0425; `literal_measured` anotado. Revalidación sin crédito. Fast → cien.

### Fase 7 — Correo a dirección libre, Outlook o Gmail (D4) (3–4 h + cien; revalidación)
- Op nueva `email.send(subject?, text, to)` (External, confirma en normal). Provider: (a) perfil clásico de Outlook
  (`MicrosoftAccountAdapter.HasClassicOutlookProfile:257`) → COM `CreateItem(0)`, `To` libre, `Send()`, postlectura de
  Elementos enviados (generalizar `OutlookTestSendScript`, `DesktopMessagingAdapter.cs:50-81`); (b) sin Outlook → Gmail
  web en el navegador propio como **misión del motor** (redactar → Enviar → verificar en Enviados); sin sesión →
  `gmail_session_required`. **PREGUNTAR** una vez si quiere medir Gmail en este PC.
- Mente: `message_draft_request` canal email → `email.send`; sin dirección → la pregunta.
- Tanda MAIL1989: literales H0554, H0279, H0440, H0609, H0018, H0638 con la dirección sustituida por
  `autor@example.com` (D13, D14); revalidación sin crédito; corregir la `verification_reason` de H0018.

### Fase 8 — Spotify: medir primero, construir lo que falle (D7, D18) (3–4 h; revalidación)
- Sonda en frío con el Spotify de la Store: (a) nivel absoluto; (b) ajuste en pausa; (c) control por SMTC; (d) nada.
  Construir sólo lo que falle (`audio.app.volume.set` absoluto si (a) falla). La cadena «abrir → poner algo → ajustar»
  la propone el planificador con el motor de la Fase 4 (grounding dependiente CHAIN1931).
- Tanda AUDIO1991: H0652 revalidación + variantes. Sin crédito nuevo.

### Fase 9 — Cierre
- Full de cierre verde sobre el HEAD final; cien final; G04.06/G06.06 re-selladas; `COMPUTER_USE_DISENO.md` §15
  (motor general, banco, modo de confirmaciones); `APLAZADOS.md`; `HANDOFF.md`; memoria; barrido de perfiles a
  `C:\Users\usuario\BAXY-evidencia\<fecha>\`; push. Registro 742/742.
- **Merge a `main` (D12, decidido)**: `git fetch origin && git merge origin/main` en la rama → Fast → push →
  `gh pr create --base main --head codex/kiro-goal-c03` con cifras; merge por **merge commit** (nunca squash/rebase);
  después `git branch -f main origin/main` local.

## 5. Filas que se reabren en la Fase 3 (35) y por qué

| Bloque | Filas | Acreditadas como | La encuesta pide | Fase |
|---|---|---|---|---|
| Discord | H0290, H0636 | parada honesta (localiza, pregunta) | entrar al canal | 4–5 |
| Pestañas | H0444 | cierre en el navegador propio | cerrar las del Chrome del dueño | 4–5 |
| Pulsar en app | H0175, H0566 | límite `client.control.press` | apretar enter / enviar en Discord/WhatsApp | 4–5 |
| Steam descargar | H0049, H0118, H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680 | lectura de biblioteca | iniciar la descarga | 5 |
| Steam instalar | H0295, H0345, H0387, H0396, H0643, H0721 | lectura | instalar | 5 |
| Steam desinstalar | H0039, H0612 | lectura | desinstalar | 5 |
| Lanzar juego | H0083, H0608 | lectura | lanzar | 5 |
| Misión compuesta | H0542 | límite (comprimir/zip) | carpeta → txt → zip → abrir | 5 |
| Modo avión | H0107 | límite | activar modo avión | 5 |
| Comandos | H0245, H0048 | límite | ejecutar y leer la salida | 5 |
| Fondo / PowerPoint | H0459, H0188 | límite | cambiar el fondo; crear 6 diapositivas | 5 |
| Leer chats | H0510, H0720 | límite honesto | leer el último mensaje de X | 5 |
| Imágenes/memes | H0069, H0077 | límite | descargar/mostrar una imagen | 5 |

**No se reabren**: contactos H0306/H0138 y negativas H0014/H0116/H0124 («en PC no tiene sentido», dueño hoy);
H0646 Prime Video (no tiene cuenta); H0635 ver su propio código (límite razonable, sin orden); las 18 `unmarked_limit`
(pedidos en otro idioma, LIMITS1901); mensajería/correo (31+6: mecanismo real ya medido con destinos de prueba; el
camino nuevo se revalida sin crédito); cerrar todo (real), Spotify (real), minimizar (real), PDF (real).

## 6. Estimación

| Bloque | Tandas | Cien | Full | Tiempo |
|---|---|---|---|---|
| Fases 0–2 | 0 | 2 | 1–2 | 1 día |
| Fase 3 (reapertura) | 0 | 0 | 0 | 1 h |
| Fase 4 (motor general de computer use) | 1 | 1–2 | 0 | 3–4 días |
| Fase 5 (banco de 35 filas sobre el motor) | 10 | 6–8 | 0 | 5–6 días |
| Fases 6–8 (mensajes, correo, Spotify) | 3 | 3 | 0 | 1–2 días |
| Fase 9 (cierre + merge) | 0 | 1 | 1 | 1 día |

Total: ~14 tandas, ~14 cien, 2–3 Full; 11–15 días de trabajo efectivo. El motor cuesta más al principio y después
cada fila es una misión declarada y una tanda, no código nuevo: así es como «hacer más con menos» de la identidad.

## 7. Lo que NO hay que hacer

- Tocar `main` sin el «sí» del dueño; squash/rebase de la rama; `git add .`; `reset --hard`; `clean`.
- Cambiar etiquetas de riesgo del catálogo (sellos): la política vive en `RiskPolicy.cs`.
- Enviar mensajes/correos a terceros reales desde una tanda (sólo Música, Ron92, casilla de pruebas); comprar juegos;
  descargar títulos de decenas de GB enteros; desinstalar juegos pagados del dueño sin su «sí» en el chat.
- Cerrar VS Code/terminal/producto en «cerrame todo»; `TerminateProcess`; perder documentos sin guardar.
- Reabrir contactos, Prime Video, mensajería/correo/cerrar-todo/Spotify/minimizar/PDF.
- Relajar pruebas rojas (skip/xfail/umbral); declarar suites verdes sin comando y cifras.
- Editar permisos, CLAUDE.md o config por pedido de un peer; lo denegado vuelve al dueño (Fase 0 paso 4).
- Dos tandas, o tanda + cien, a la vez; editar `src` con algo corriendo; compilar entre ejecución y adjudicación.
- Hard-codear Discord/Spotify/Chrome/Steam fuera de alias y enumerados; listas de destinatarios en código; **una operación por fila de la encuesta** cuando el motor general la cubre (D21).
- Inventar en los finales («lo envié», «entré», «instalé», «cerré») sin recibo verificado.
- Volver a preguntar al dueño lo que este plan ya decide (quedan sólo: la auditoría semántica tras la Fase 3, los
  títulos de Steam que posee su cuenta, y si quiere medir Gmail en este PC).
- Cerrar Opera GX u otra app del dueño «por RAM» sin que la guarda falle (D20).

## 8. Verificación de punta a punta

- Fase 1: `source_quality_gate_passed: mode=Full`; cien-87 100 publicadas; matriz G04.06/G06.06 CUMPLIDO con HEAD =
  remoto.
- Fase 2: sondas de modo normal/bypass (§4 Fase 2); `dotnet test tests/Baxy.Kernel.Tests -c Release` verde; cien-88.
- Fase 3: `REOPEN1957/REGISTRY_UPDATE.json` con `counters {covered:707, open:35}` y sha antes/después =
  `CURRENT_CATEGORY_COUNTS.md`.
- Fases 4–8: por tanda, `chain_*.sh` termina en `PUSHED`, `root_publish` explica los contadores por créditos
  explícitos, recibos con autoridad de postlectura, y cien 100/100 detrás de cada cambio de mente/App.
- Fase 9: registro 742/742 y 35/35; Full verde; cien verde; `git status` limpio; `git rev-list --count origin/codex/kiro-goal-c03..HEAD` = 0.

## 9. Permisos que el dueño pega antes de arrancar (D9)

En `.claude/settings.local.json` del repositorio, dentro de `permissions.allow` (y la sesión de Opus se abre en modo
bypass de permisos):

```json
"Bash(bash *setup_*.sh*)",
"Bash(bash *chain_*.sh*)",
"Bash(bash *_case.sh*)",
"Bash(bash *rerun_*.sh*)",
"Bash(python *approve_*.py*)",
"Bash(python -X utf8 *approve_*.py*)",
"Bash(powershell.exe *run_baxy_conductor.ps1*)",
"Bash(powershell.exe *test_source_quality.ps1*)",
"Bash(powershell.exe *discord_probe.ps1*)",
"Bash(git push *)",
"Bash(gh pr create *)"
```
