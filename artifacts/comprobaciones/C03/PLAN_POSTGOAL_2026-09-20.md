# Plan post-goal C03 — 2026-09-20 (Fable 5.1 planifica, Opus 5 ejecuta)

> **Goal corto para el chat nuevo (pegar tras `/goal`):**
>
> Ejecutá íntegro el plan `C:\Users\usuario\.claude\plans\wise-foraging-quill.md` (Fable planificó; vos, Opus 5,
> sólo ejecutás). Repositorio `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo`, rama
> `codex/kiro-goal-c03`. Antes de tocar nada leé `AGENTS.md`, el plan entero y `MEMORY.md` de tu memoria.
> Seguí las fases en orden sin saltarte ninguna compuerta: Fast/Full verde sin relajar nada, cien 100/100
> tras cada cambio de mente/App, una tanda sellada por capacidad, adjudicación honesta, nunca editar `src`
> con algo corriendo. No pares hasta: (1) Full verde y G04.06/G06.06 selladas; (2) las 35 filas reabiertas
> vueltas a 742/742 con mecanismos reales, 35/35 categorías; (3) cien 100/100 sobre el HEAD final; (4) todo
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
| D13 | Terceros en los literales: «sólo cambiar por los canales seguros y listo: si es por Discord "Valeria", si es por WhatsApp "Música"; "Dile a mamá por wsp que ya voy" → "Dile a Música que ya voy"». | En las tandas el literal se mide con el destinatario sustituido por el canal de prueba; correo → casilla de pruebas. Los créditos se conservan; el panel anota `literal_measured` con la sustitución (§4 Fases 6–7). |
| D14 | Destinos de prueba confirmados: «Música» (WhatsApp), «Valeria» (Discord), casilla `autor@example.com`; sí a medir «al nombrado» con esos nombres. | Nada que preguntar en Fases 6–7. |
| D15 | Discord: «que se haga como sea recomendado»: texto/MD entra directo; voz pregunta antes y se queda conectado con el micrófono como esté (no se silencia salvo pedido). | §4 Fase 4. |
| D16 | Pestañas: «dejar abierto el navegador, a menos que el usuario diga lo contrario»; varios navegadores y ninguno nombrado → preguntar cuál. | §4 Fase 5. |
| D17 | «VS Code se debe mantener a toda costa porque estamos en pleno desarrollo». | `window.close.all` conserva Code/terminal/producto; nunca se toca. |
| D18 | Spotify: «hacer lo recomendado, sólo me interesa que BAXY funcione» → medir las cuatro formas (nivel absoluto, en pausa, control SMTC, nada) y construir sólo lo que falle, más la cadena de D7. | §4 Fase 11. |
| D19 | Full roja: «como sea mejor y recomendado, pero cumplir con goal C03 (y tener en cuenta que sigue en los demás goals)». | Re-anclar contratos citando decisiones + escribir las pruebas faltantes; no romper sellos de otros goals. |
| D20 | RAM: «cambié de PC, este tiene 32 GB; no cierres nada a menos que sea necesario para el desarrollo y pruebas de BAXY». | La guarda de 4000 MiB queda; Opera GX no se cierra salvo que la guarda falle de verdad. |

## 2. Estado de partida verificado (manda sobre cualquier documento viejo)

- **Full (`scripts/test_source_quality.ps1 -Mode Full`) está rojo**: `dotnet-tests` con 54 fallos (Integration 34/3234,
  Kernel 16/162, Providers 4/605; Contracts 70/70 y Setup 477/477 verdes). La etapa `python-tests` **no corrió**
  (el gate corta en la primera roja). Log en `C:\Users\usuario\AppData\Local\Temp\claude\c--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo\b0264e2d-8694-4887-bba6-c132eb18a1d2\scratchpad\full.log`.
- **Ya existe y ya es real** (no construir de nuevo): `window.close.all` (`WindowsWindowControlProvider.CloseAllAsync:362`,
  conserva Code/Code-Insiders/WindowsTerminal/baxy-core/Baxy.App, WM_CLOSE → menú de sistema, nunca fuerza;
  CLOSEALL1733 acreditó H0467/H0484); `audio.app.volume.adjust` (sesiones `IAudioSessionManager2`, genérico por
  proceso; AUDIO1801 acreditó H0652); `message.send` + `message.recipient.resolve` (envío real a un destinatario
  resuelto, `DesktopMessagingAdapter.SendAsync:148`, OCR de la burbuja) y `message.send.test` con destino forzado
  (`ForcedTestDestination`: WhatsApp «Música», Discord «Valeria», correo `autor@example.com`);
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
   que lo dice. Ningún envío real a terceros desde una tanda: sólo «Música», «Valeria» y la casilla de pruebas.
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

### Fase 4 — Discord: entrar al canal (H0290, H0636) (3–4 h + cien)
- Op nueva `client.channel.open(client:["discord"], name)` junto a `client.channel.locate`
  (`ProductCatalog.cs:292-306`), `LowReversible`, verificador `client.channel.open.uia.postread.v1`,
  `requiresObservedEffect:true`. Core: `ExternalCapabilityHandlers.cs:27`; provider reason en
  `WindowsExternalCapabilityProvider.cs:220`; lista blanca `ProductConductorHost.cs`.
- Adaptador en `WindowsDeviceControlAdapter.cs` (junto a `ClientChannelLocateAsync:921`), extrayendo a un helper
  compartido el bloque ya probado de `DesktopMessagingAdapter.ResolveAsync` rama Discord (`:555-591`: Escape → Ctrl+K
  1400 ms → texto → **clic relativo 0.5/0.381** sobre la fila → 2700 ms → verificación por título) más el prototipo
  `discord_probe.ps1 -Join` (scratchpad d--). Voz: unirse con el micrófono como esté (D15; no se silencia salvo pedido),
  verificar por UIA «Voz conectada»/«Desconectar»; texto: cabecera nombra el canal. Recibo `channelName,
  channelKind, server, joined:true`. Un solo proceso PowerShell (lección `commit_discord_single_process.txt`).
  Modo normal: voz pide confirmación (Fase 2), texto entra directo. Se queda dentro (la persona pidió ir).
- Mente: `effect_intent.py:18183-18186` enruta `client_channel_request` (`:1404`) a `open` si está disponible;
  `__main__.py:5131` args; `llm.py:4619-4635` guion (decir que entró, canal/servidor);
  veto `joined_claimed` (`:7899`) sólo cuando `seen.joined` no es true, y nuevo `joined_not_stated` cuando lo es;
  máscara del nombre «Cotele!!!??» (`:8892-8907`) se conserva.
- Tanda DISCORD1959 (plantilla `discord1839`, 6 casos): literales H0290, H0636; variantes «entrá al canal Cotele en
  Discord», «go to Cotele on Discord»; límites «no entres a ningún canal», «ve a Zzqx en Discord» (no existe → honesto).
  Driver `discord_join_case.sh`: Discord del dueño abierto (o lanzado por la raíz), micrófono del sistema silenciado
  por el driver durante la tanda y restaurado (higiene de la medición, no del producto), **la raíz desconecta tras cada
  caso** (`discord_probe.ps1` tiene la salida). Crédito +2.
  Fast → cien-89.

### Fase 5 — Pestañas del Chrome del dueño (H0444) (2–3 h + cien)
- Op nueva `browser.tabs.close.all(browser:["brave","chrome","edge","firefox","opera","opera_gx"])` tras
  `browser.tabs.list`; `LowReversible` (Ctrl+Shift+T recupera). Provider en `WindowsDeviceControlAdapter.cs`: ventana
  top-level del proceso (inventario `DesktopWindows()` + identidad por proceso como `CloseAllAsync`), foreground
  verificado, contar `ControlType.TabItem` por UIA, Ctrl+T una vez (el navegador sobrevive), `InvokePattern` sobre el
  botón «Cerrar» de cada `TabItem` restante (fallback Ctrl+W con verificación de cuenta), postlectura: 1 `TabItem`, título
  «Nueva pestaña/New Tab»; pestañas fijadas o diálogos «¿Cerrar N pestañas?» → `remaining`, nunca fuerza. Si el
  navegador no expone `TabItem` (medir Opera GX en frío) → `browser_tabs_not_exposed` honesto.
- Mente: `browser_close_all_tabs_arguments` (`effect_intent.py:8361`) devuelve el navegador nombrado → op nueva; sin
  nombre y un solo navegador abierto → ese; varios → aclaración; sin ninguno abierto → el propio (`browser.control
  close_all`, como hoy). `llm.py:7912-7927` veto de pasado falso se conserva; el final nombra el navegador.
- Tanda TABS1961 (plantilla `chrometabs1843`): literal H0444; variantes «close all Chrome tabs», «cerrá las pestañas
  de chrome»; límites «cerrá esta pestaña» (límite llano LIMITS1677), «no cierres nada del navegador». Driver
  `ownertabs_case.sh`: `chrome.exe --new-window about:blank about:blank about:blank` en el perfil del dueño, cuenta
  `TabItem` antes/después, deja el navegador abierto con una pestaña (D16) y cierra esa ventana de utillaje al final.
  Crédito +1. Fast → cien-90.

### Fase 6 — Mensajes al destinatario nombrado (D2) (3–4 h + cien; revalidación)
- Hoy `effect_intent.py:18187-18194` prefiere `message.send.test`. Cambio: preferir `message.recipient.resolve` →
  `message.send` (`MissionPlanProposal.cs:157,214`; `PlannerExecutionSupport.cs:582`; `DesktopMessagingAdapter.SendAsync:148`)
  para cualquier destinatario; `message.send` es External → confirma en normal, envía en bypass (Fase 2).
  `message.send.test` queda en catálogo (sellos) pero la mente no lo elige; el canal `email` pasa a Fase 7.
- Compositor: `sent_wrong_destination` (`llm.py:7945`) exige nombrar `seen.recipient` resuelto; `send_not_stated` se
  mantiene; destinatario no encontrado → `recipient_identity_not_verified` y final honesto («no encontré a X»).
- Tanda MSGNAMED1963 (plantilla `msgsend1847`, driver `msgsend_case.sh`, revisor `approve_message_send.py` adaptado a
  `message.send` cuyo `recipientId` resuelva a «Música» o «Valeria»; matar `whatsapp.root.exe` respawn; cerrar cliente
  después):
  literales con el destinatario **sustituido por el canal de prueba (D13)**: WhatsApp H0008, H0540, H0489, H0208,
  H0611, H0225, H0024 («mandale a mamá…» → «mandale a Música…»), Discord H0318, H0340, H0394 (ShooterCock → Valeria),
  más H0005, H0369, H0425 tal cual; el panel anota `literal_measured` con la sustitución. **Revalidación sin crédito**
  (ya cubiertas). Variantes «mandale hola a Valeria por discord», «send hi to Música on whatsapp»; límites. Evidencia
  `revalidation` en las filas. Si el driver es denegado: Fase 0 paso 4. Fast → cien-91.

### Fase 7 — Correo a dirección libre, Outlook o Gmail (D4) (3–4 h + cien; revalidación)
- Op nueva `email.send(subject?, text, to)` (`ExternalCommunication`, confirma en normal). Provider en
  `MicrosoftAccountAdapter.cs`: (a) `HasClassicOutlookProfile:257` → COM `CreateItem(0)`, `To` libre, `Send()`, postlectura
  de Elementos enviados ±2 min (generalizar `OutlookTestSendScript`, `DesktopMessagingAdapter.cs:50-81`); (b) sin Outlook →
  Gmail web en el navegador propio (sesión `browser-session-v1`, CDP como Disney/Netflix, `WebBrowserAdapter`): navegar a
  `https://mail.google.com/mail/?view=cm&to=<to>&su=<subject>&body=<text>`, pulsar «Enviar» por DOM, verificar en «Enviados»
  (asunto + destinatario); sin sesión de Gmail → `gmail_session_required` honesto. En REDPC manda (a).
  **PREGUNTAR una vez** al dueño si quiere el camino Gmail medido en este PC (tendría que iniciar sesión de Gmail en el
  navegador de BAXY); si no, Gmail queda construido y anotado en APLAZADOS como «sin sesión para medir».
- Mente: `message_draft_request` (`effect_intent.py:1432-1469`) canal email → `email.send`; sin dirección → pregunta
  la dirección (nunca la inventa); `_latest_email_domain` intacto; `__main__.py:5136-5146` args.
- Tanda MAIL1965 (plantilla `mail1867`): literales H0554, H0279, H0440, H0609, H0018, H0638 con la dirección
  **sustituida por la casilla de pruebas** `autor@example.com` (D13, D14) y `literal_measured` anotado;
  variantes. Revalidación sin crédito. Corregir de paso la `verification_reason` de H0018 (copiada de una fila de
  WhatsApp). Fast → cien-92.

### Fase 8 — Pulsar dentro de una app (H0175, H0566) (2 h + cien)
- Sin op nueva: cadena `window.resolve/window.focus` (app nombrada) → `input.key.press` (`ProductCatalog.cs:700`,
  autoridad `win32.sendinput.accepted.v1`) o `input.visible.click` («enviar»). Quitar el contrato de límite
  `client.control.press` (`effect_intent.py:3277-3285`) y enrutar «en <app> apretá <tecla|botón>» a la cadena; en
  WhatsApp/Discord «enviar»/Enter con texto en el compositor = envío → en normal confirma (Fase 2 lo hereda de
  `message.send`? No: la op es `input.key.press`; añadir en `RiskPolicy` la regla «`input.key.press` Enter con app de
  mensajería en foreground → RequireConfirmation en normal»). Postlectura: compositor vacío/burbuja nueva (OCR de
  `DesktopMessagingAdapter`) o superficie cambiada.
- Tanda PRESS1967 (plantilla `ui1731`): literales H0175, H0566 con el chat de «Música»/«Valeria» abierto y un borrador
  escrito por la raíz; variantes («press enter in Discord», «apretá enviar en whatsapp»); límites. Crédito +2. cien-93.

### Fase 9 — Steam de verdad: descargar, instalar, desinstalar, lanzar (20 filas) (2–3 días + cien)
- Existente: `game.install.named/prepare/commit/status/cancel/cancel.active`, `game.launch`, `game.purchase.prepare/commit`
  (`SteamLocalAdapter.cs`: `DispatchInstallAsync:305`, `LaunchAsync:602`, manifiestos `appmanifest_*.acf`, `catcache`).
  Nueva `game.uninstall.named(store:["epic","steam"], title)` (`steam://uninstall/<appid>` + ausencia del manifiesto y
  del directorio; `WorkLoss` → confirma). Lanzar: `game.launch` + verificación de proceso/ventana del juego
  (`ContinueLaunchDialogAsync`), y para «lanzá Mortal Kombat» sin store, resolver por biblioteca. Descargar/instalar:
  `game.install.named` → estado `downloading` en el manifiesto (`StateFlags`) = efecto verificado; títulos grandes o
  pagados: si la cuenta los posee, iniciar y **cancelar por la raíz** tras verificar (`game.install.cancel`), nunca
  bajar 80 GB en una tanda; si no los posee → honesto «no está en tu biblioteca» + `game.purchase.prepare` como oferta,
  **nunca** `game.purchase.commit` en tanda. Epic: `EpicEntitlementNamed` existe; instalar/lanzar por `com.epicgames.launcher://`
  con la misma verificación por manifiestos.
- Mente: los lectores de `game.entitlement.named` (`__main__.py`, `effect_intent.py` `_STEAM_LIBRARY_REQUEST`) pasan a
  proponer la acción pedida (descargar/instalar → `game.install.named`; desinstalar → `game.uninstall.named`; lanzar →
  `game.launch`) con la lectura como grounding previo (cadena de dos pasos, CHAIN1931). Compositor: nombrar el estado
  observado (iniciada la descarga / instalado / desinstalado / lanzado), vetos `extra_claim` existentes.
- Tandas (plantilla `steam1825`/`epic1937`, driver con snapshot/restauración de la biblioteca: Worms Rumble y Fall Guys
  son gratis → instalar/desinstalar de verdad; Doom Eternal/Batman/Mortal Kombat según posesión): STEAM1969 (descargar:
  H0049, H0482, H0659, H0272, H0434, H0118, H0382, H0680, H0390, H0671), STEAM1971 (instalar: H0295, H0345, H0643,
  H0396, H0387, H0721 —«en Teams»: la encuesta lo lista como Steam mal oído; medir como Steam y decirlo—),
  STEAM1973 (desinstalar: H0039, H0612), STEAM1975 (lanzar: H0083, H0608). **PREGUNTAR** al dueño antes de STEAM1969
  qué títulos posee su cuenta. Crédito +20. Fast + cien tras cada tanda que toque mente/App.

### Fase 10 — Cadenas y sistema (10 filas)
- **H0542** «creá una carpeta en el escritorio, mete un txt dentro, comprímela y abrí el zip» (3 h): inventariar ops de
  ficheros (`grep -o '"[a-z]*\.\(create\|delete\|compress\|zip\|open\|write\)[a-z.]*"' ProductCatalog.cs`); añadir
  `file.compress(folder|file, destination)` (Compress-Archive, verifica el zip) y `file.open(path)` (shell open,
  verifica ventana) si faltan; la misión de 4 pasos va por el planificador (CHAIN1931). Tanda CHAIN1977 con fixture
  en el Escritorio redirigido, borrado después. +1.
- **H0107** modo avión (2 h): `system.settings.set` gana valor `airplane_mode` (enum ordenado): `Windows.Devices.Radios`
  → todos los radios `Off` con postlectura; restaurar en el driver (`bt_radio.ps1` preset/restore existe). Tanda
  NETWORK1979. +1.
- **H0245, H0048** ejecutar comandos (3 h): op nueva `shell.command.run(command, workingFolder?)` con salida capturada
  (pwsh, timeout 60 s, 8 KB), clasificación estática del comando (`rm|del|format|rd|Remove-Item|git reset` → WorkLoss →
  confirma; resto Allow), final que cita líneas de salida verbatim y su cuenta (vetos: nada que no esté en la salida).
  Tanda SHELL1981: `ls` sobre una carpeta fixture, `pytest` sobre un test fixture de 1 caso. +2.
- **H0459** fondo azul, **H0188** PowerPoint (4 h): `desktop.wallpaper.set(color|imagePath)` (SPI_SETDESKWALLPAPER /
  `SetSysColors`, postlectura de registro; driver guarda y restaura el fondo del dueño); `document.presentation.create(topic,
  slides)` con `python-pptx` en el runtime de la mente (instalación autorizada por D11), texto de 6 diapositivas por el
  modelo local, guardado en Documentos y abierto (PowerPoint o visor por defecto; sin PowerPoint → fichero creado +
  abierto con lo que haya, dicho tal cual). Tanda DESKTOP1983. +2.
- **H0510, H0720** leer chats (3 h): `message.read.named(channel, contact, count)` → `ResolveAsync` existente + OCR de
  la banda de mensajes (misma maquinaria de `SendAsync`), recibo con líneas OCR atribuidas; compositor cita sólo texto
  OCR (veto invented). Quitar el contrato `message.read.named` de `known_unsupported_effect_request`
  (`effect_intent.py:3393-3407`). Tanda CHATREAD1985: la raíz envía antes un texto conocido a «Música»/«Valeria»
  (mecanismo Fase 6) y lo lee de vuelta. +2. (Privado: `PrivacySensitive` → Allow en normal, D3.)
- **H0069, H0077** imágenes de la web (3 h): `web.image.download(query|url, folder, open)`: H0077 → página wikipedia.org,
  `og:image`/logo, descarga al Escritorio, verifica fichero; H0069 → búsqueda de imágenes (motor ya usado por
  `web.search`) → descarga → abre con el visor (`file.open`), «te muestro este»; fixtures borrados después. Tanda WEB1987. +2.
- Cien tras cada tanda con cambio de mente/App (cien-94…).

### Fase 11 — Spotify: medir primero, construir lo que falle (D7, D18) (3–4 h; revalidación)
- Primero una sonda en frío con el Spotify de la Store (driver `spotify_case.sh`/`appvol_case.sh` del scratchpad d--):
  (a) nivel absoluto «poné spotify al 50»; (b) ajuste con Spotify en pausa (`app_audio_session_not_found`); (c) control
  «pausá/siguiente en spotify» (`media.control sourceApp` por SMTC); (d) nada. Construir sólo lo que falle.
- Cuando `audio.app.volume.adjust` devuelve `app_audio_session_not_found` y la app está en el catálogo de inicio, el
  planificador propone la cadena `app.open(spotify)` → `media.play.query` (Spotify; `spotify_case.sh`/`approve_spotify.py`)
  → `audio.app.volume.adjust` (CHAIN1931, grounding dependiente). Añadir `audio.app.volume.set(app, level)` absoluto
  (`ISimpleAudioVolume.SetMasterVolume` en `WindowsCoreAudioPlatform.cs`). Mente: `app_volume_request` (`effect_intent.py:4990,19045`)
  admite nivel absoluto.
- Tanda AUDIO1989: H0652 revalidación + variantes («poné Spotify al 30», «bajá spotify 20 con spotify cerrado»);
  volumen maestro preajustado y restaurado. Sin crédito nuevo. cien.

### Fase 12 — Cierre
- Full de cierre verde sobre el HEAD final; cien final; G04.06/G06.06 re-selladas con ese HEAD;
  `COMPUTER_USE_DISENO.md` §15 (reaperturas, modo de confirmaciones, capacidades nuevas), `APLAZADOS.md` (lo que quede
  sin poder medir: Gmail sin sesión, títulos de Steam no poseídos…), `HANDOFF.md`, memoria (`c03-postgoal-plan.md` con
  estado por fase), barrido de perfiles a `C:\Users\usuario\BAXY-evidencia\<fecha>\`, push. Registro: 742/742 de nuevo.
- **PR a `main` (D12, decidido: sí, sin volver a preguntar)**: `git fetch origin && git merge origin/main` en la rama
  (2 commits de docs, sin conflictos esperados) → Fast → push → `gh pr create --base main --head codex/kiro-goal-c03`
  con cifras (742/742, 35/35, cien, Full por suite) y la nota de que el diff es evidencia; merge por **merge commit**
  (nunca squash/rebase: 1 600 commits citados por SHA); el dueño pulsa el merge en GitHub; después
  `git branch -f main origin/main` local.

## 5. Filas que se reabren en la Fase 3 (35) y por qué

| Bloque | Filas | Acreditadas como | La encuesta pide | Fase |
|---|---|---|---|---|
| Discord | H0290, H0636 | parada honesta (localiza, pregunta) | entrar al canal | 4 |
| Pestañas | H0444 | cierre en el navegador propio | cerrar las del Chrome del dueño | 5 |
| Pulsar en app | H0175, H0566 | límite `client.control.press` | apretar enter / enviar en Discord/WhatsApp | 8 |
| Steam descargar | H0049, H0118, H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680 | lectura de biblioteca | iniciar la descarga | 9 |
| Steam instalar | H0295, H0345, H0387, H0396, H0643, H0721 | lectura | instalar | 9 |
| Steam desinstalar | H0039, H0612 | lectura | desinstalar | 9 |
| Lanzar juego | H0083, H0608 | lectura | lanzar | 9 |
| Misión compuesta | H0542 | límite (comprimir/zip) | carpeta → txt → zip → abrir | 10 |
| Modo avión | H0107 | límite | activar modo avión | 10 |
| Comandos | H0245, H0048 | límite | ejecutar y leer la salida | 10 |
| Fondo / PowerPoint | H0459, H0188 | límite | cambiar el fondo; crear 6 diapositivas | 10 |
| Leer chats | H0510, H0720 | límite honesto | leer el último mensaje de X | 10 |
| Imágenes/memes | H0069, H0077 | límite | descargar/mostrar una imagen | 10 |

**No se reabren**: contactos H0306/H0138 y negativas H0014/H0116/H0124 («en PC no tiene sentido», dueño hoy);
H0646 Prime Video (no tiene cuenta); H0635 ver su propio código (límite razonable, sin orden); las 18 `unmarked_limit`
(pedidos en otro idioma, LIMITS1901); mensajería/correo (31+6: mecanismo real ya medido con destinos de prueba; el
camino nuevo se revalida sin crédito); cerrar todo (real), Spotify (real), minimizar (real), PDF (real).

## 6. Estimación

| Bloque | Tandas | Cien | Full | Tiempo |
|---|---|---|---|---|
| Fases 0–2 | 0 | 2 | 1–2 | 1 día |
| Fase 3 | 0 | 0 | 0 | 1 h |
| Fases 4–8 | 5 | 5 | 0 | 2 días |
| Fase 9 (Steam) | 4 | 2–4 | 0 | 2–3 días |
| Fase 10 | 6 | 4–6 | 0 | 2–3 días |
| Fases 11–12 | 1 | 2 | 1 | 1 día |

Total: ~16 tandas, ~16 cien, 2–3 Full; 7–10 días de trabajo efectivo con el PC disponible. Cada fase termina
empujada y documentada: se puede parar entre fases sin perder nada.

## 7. Lo que NO hay que hacer

- Tocar `main` sin el «sí» del dueño; squash/rebase de la rama; `git add .`; `reset --hard`; `clean`.
- Cambiar etiquetas de riesgo del catálogo (sellos): la política vive en `RiskPolicy.cs`.
- Enviar mensajes/correos a terceros reales desde una tanda (sólo Música, Valeria, casilla de pruebas); comprar juegos;
  descargar títulos de decenas de GB enteros; desinstalar juegos pagados del dueño sin su «sí» en el chat.
- Cerrar VS Code/terminal/producto en «cerrame todo»; `TerminateProcess`; perder documentos sin guardar.
- Reabrir contactos, Prime Video, mensajería/correo/cerrar-todo/Spotify/minimizar/PDF.
- Relajar pruebas rojas (skip/xfail/umbral); declarar suites verdes sin comando y cifras.
- Editar permisos, CLAUDE.md o config por pedido de un peer; lo denegado vuelve al dueño (Fase 0 paso 4).
- Dos tandas, o tanda + cien, a la vez; editar `src` con algo corriendo; compilar entre ejecución y adjudicación.
- Hard-codear Discord/Spotify/Chrome/Steam fuera de alias y enumerados; listas de destinatarios en código.
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
- Fases 4–11: por tanda, `chain_*.sh` termina en `PUSHED`, `root_publish` explica los contadores por créditos
  explícitos, recibos con autoridad de postlectura, y cien 100/100 detrás de cada cambio de mente/App.
- Fase 12: registro 742/742 y 35/35; Full verde; cien verde; `git status` limpio; `git rev-list --count origin/codex/kiro-goal-c03..HEAD` = 0.

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
