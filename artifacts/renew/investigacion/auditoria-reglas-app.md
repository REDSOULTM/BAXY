# Auditoría de reglas: Baxy.App y Baxy.FieldUi

Rama `renew-nb`, commit auditado **`b33a3e62d`** (2026-10-15 06:26). Se hizo `git fetch hub`: `hub/baxy-renew` está en
`06adea769`, que es ancestro de `b33a3e62d` (16 commits detrás), así que se auditó el árbol local. Dentro del alcance no
había cambios sin commit. Fue una auditoría de solo lectura: no se tocó código y no hizo falta un worktree.

**Reglas contra las que se audita**
1. Ningún ayudante del modelo en código: ni regex, ni reglas semánticas, ni guardas, vetos, listas de palabras o pasos
   dictados que interpreten o reescriban lo que dijo la persona o lo que decidió el modelo. Se permiten el catálogo
   tipado, el kernel (riesgo y confirmación), el diario, la verificación del proveedor, el enmascarado de datos
   sensibles y los botones Sí/No.
2. Honestidad: nada se informa como hecho si no se ejecutó y verificó, y cero respuestas visibles fijas.
3. Ningún dato del dueño sale del equipo. BAXY nunca hace clic ni escribe en una ventana de la persona.
4. Cero código muerto; nada apilado.

**Cómo se revisó.** Se leyeron enteros `NativeTurnLoop`, `MainWindowViewModel`, `MindSidecarClient` (peticiones de
turno), `Heartbeat`, `HeartbeatMoment`, `MemoryPanel`, `MemoryOperationProtection`,
`MemoryOperationResponseProjection`, `OperationResponseProjection`, `ScreenViewProjection`, `TurnVisibleFacts`,
`ConfirmationChallengeParser`, `PendingOperationConfirmation`, `SensitiveText`, `FieldBridgeContract`,
`FieldProductChannel` (rutas y estado) y `field-native-bridge.js`. El resto de la App se barrió buscando literales en
español, variables de entorno, salidas de red y lanzamiento de procesos. En FieldUi se revisaron `ActivityPanel`,
`FieldCenter`, `MemoryPanel`, `SettingsPanel`, `TriggersPanel`, `useEventStream` e `index.html`. Para la regla 4 se
reutiliza el inventario Roslyn de `app-codigo-muerto.md` (commit `18e8546a1`), comprobando que sigue vigente en
`b33a3e62d`. Lo que lee la mente se tomó de `src/baxy_mind/__main__.py`, `mind.py`, `voice.py`, `voice_output.py` y
`llm_server.py`.

## Resumen por severidad

| Severidad | Bucle y confirmación | Memoria | Latido | Lo que vuelve al modelo | Lo que ve la persona | Entorno | Muerto o apilado | Total |
|---|---|---|---|---|---|---|---|---|
| Violación | 1 | 4 | 0 | 0 | 3 | 1 | 7 | **16** |
| Zona gris | 3 | 4 | 3 | 2 | 4 | 0 | 0 | **16** |
| Permitido (revisado y se mantiene) | 5 | 3 | 2 | 0 | 4 | 0 | 1 | **15** |

**Lo más grave**
1. **V1. El modelo puede aprobar su propia llamada riesgosa.** `confirm_pending` se acepta en cualquier paso del bucle,
   también en el mismo bucle donde el kernel acaba de pedir confirmación, y también dentro de un latido. En un latido,
   eso ejecuta sin nadie delante la propuesta de alto riesgo que el latido debía retener.
2. **V2. Cuatro herramientas públicas de memoria siempre fallan.** `memory.enable`, `memory.disable`,
   `memory.sensitive.save` y `memory.session.clear` chocan con un filtro del «parser de memoria» viejo, y el modelo
   recibe `arguments_invalid` aunque sus argumentos estén bien. La memoria viene apagada por defecto y desde el chat no
   se puede encender.
3. **V5, V6 y V7. La interfaz muestra datos que nadie observó.** El contexto aparece como 12288 cuando es 49152, figuran
   como «descargados» modelos de voz porque hay micrófono, y el panel de ajustes tiene un formulario Gemma 4 completo
   (listas de frases y de juegos incluidas) que un parche JS esconde en tiempo real.
4. **V8. La App publica 7 variables de entorno que la mente no lee y ninguna de las `BAXY_RENEW_*` que sí lee.** La voz
   funciona sólo si se arranca con `scripts/run_renew.cmd`.
5. **Regla 3, heredada del kernel (P1 de `auditoria-reglas-kernel-providers.md`).** En un turno de la persona, la App
   pasa al kernel `input.text.type`, `input.key.press`, `input.pointer.control`, `clipboard.paste` y similares, que
   actúan sobre la ventana al frente. El propio comentario de `NativeTurnLoop` lo reconoce (G2).

## 1. Bucle nativo y confirmación

### Violaciones

| # | Archivo:líneas | Regla | Cita / qué hace | Severidad | Arreglo mínimo honesto |
|---|---|---|---|---|---|
| V1 | Baxy.App/NativeTurnLoop.cs:184-187, 242-277, 281-314 (la mente siempre ofrece la herramienta: mind.py:219, 428) | 2 y confirmación del kernel (consentimiento de la persona) | `if (operation == MindStep.ConfirmationAnswer) { return await AnswerPendingAsync(...)`. No se comprueba si la persona contestó. Turno normal: el modelo llama a `file.delete` → `needs_confirmation` → llama a `confirm_pending{approve:true}` en el paso siguiente → la App reenvía la invocación con el token del kernel. Latido: la propuesta retenida (`_proposal`) se ejecuta en `AnswerProposalAsync` y el reto del kernel se contesta solo (306-311). | violación | Aceptar `confirm_pending` sólo en un `DriveAsync` abierto por `RunAsync` (palabras de la persona) **después** del turno que levantó el reto, o por los botones (`AnswerConfirmationAsync`). Si no, devolver `{"status":"rejected","error":"awaiting_person"}`. En `RunBeatAsync`, siempre rechazarlo. No se lee ninguna palabra: sólo se exige que la persona haya tenido turno. |

### Zona gris

| # | Archivo:líneas | Regla | Cita / qué pasa | Arreglo |
|---|---|---|---|---|
| G1 | NativeTurnLoop.cs:66-70, 220-232, 238-240 | 1 | La retención del latido (decisión del dueño, 2026-10-15) es un veto de la App con dos listas escritas a mano: `ProposedRisks = {"work_loss","recoverable_delete",…}` duplica el mapeo del kernel y deja fuera `session_disruption` y `privacy_sensitive`; `WritesInThePersonsWindow` nombra 8 operaciones a mano. | Derivarlo del catálogo: `ProductCatalog.ToPolicyRisk(descriptor.Risk) is OperationRisk.Irreversible or Forbidden`, más un atributo tipado del catálogo («actúa con entrada») en vez de la lista de nombres. O moverlo al kernel como origen de la invocación (`heartbeat`). |
| G2 | NativeTurnLoop.cs:31-33 y 234 | 3 | «one that would type or click in the person's windows». En un turno de la persona, la App manda esas mismas operaciones al kernel sin más. La violación está en el catálogo y los proveedores (P1 del kernel); la App sólo las transporta. | Arreglar P1 (exigir `window` objetivo y quitar `input.pointer.control`). Con eso, `WritesInThePersonsWindow` sobra. |
| G3 | NativeTurnLoop.cs:216-217 | 3 / enmascarado | `["argumentsGiven"] = arguments.DeepClone()` también para operaciones de memoria. Un secreto que rechazó el enmascarado (G8) vuelve en la observación y en `StepCompleted`, aunque `Record` vacía los argumentos de memoria (445). Todo queda local. Aparte, la mente ya escribe los argumentos en `turns.jsonl` (mind.py:463-464, fuera de alcance). | Omitir `argumentsGiven` cuando `IsMemoryOperation(operation)`. |

### Permitido (revisado y se mantiene)
- NativeTurnLoop.cs:159-171: publica `step.Text` tal cual; la ruta sólo decide si aparecen los botones.
- NativeTurnLoop.cs:189-190 (`DropPending`): el token va atado a la invocación exacta. Que otra llamada lo descarte no
  interpreta nada.
- NativeTurnLoop.cs:38-39 y 176: tope de 15 llamadas y luego `final`. Es presupuesto del arnés y el modelo redacta.
- NativeTurnLoop.cs:304-311: el «sí» de la persona a esa misma `PreparedOperation` cubre el reto del kernel que llega
  después (siempre que el «sí» venga de la persona; ver V1).
- ConfirmationChallengeParser.cs y PendingOperationConfirmation.cs: validan el reto del kernel (token base64url de 32
  bytes, vida ≤ máximo, misma misión e invocación).

## 2. Memoria

### Violaciones

| # | Archivo:líneas | Regla | Cita / qué hace | Severidad | Arreglo mínimo honesto |
|---|---|---|---|---|---|
| V2 | Baxy.App/MemoryOperationProtection.cs:67 y 442-456; efecto en NativeTurnLoop.cs:205-217 | 2, 4 | `EnsureParserMemoryOperation`: `if (operationName is not ("memory.configure" or "memory.correct" … "memory.status")) throw new InvalidDataException("La operacion no pertenece al parser de memoria.")`. Las herramientas públicas `memory.enable`, `memory.disable`, `memory.sensitive.save` y `memory.session.clear` (ProductCatalog.cs:1172-1260) siempre terminan en `arguments_invalid`, una observación falsa. La memoria está apagada por defecto (MemoryPanel.cs:217-221), así que el chat no la puede encender ni guardar un dato sensible. | violación | En `Prepare`, usar `EnsureMemoryOperation` (`IsMemoryOperation`) y borrar `EnsureParserMemoryOperation`. |
| V3 | MemoryOperationProtection.cs:200-208 y 222-236 | 1, 4 | `ResolveWireOperationName` cambia la operación del modelo: `"memory.save" when sensitivity is "sensitive" or "secret" => "memory.sensitive.save"`, `"memory.forget" when scope == "session" => "memory.session.clear"`, `"memory.configure" => …`. Con los esquemas de hoy ninguna rama se alcanza: `memory.save` sólo admite `normal`/`personal`, `memory.forget` no tiene alcance `session` y `memory.configure` no existe en el catálogo. La sobrecarga pública no tiene llamadores. | violación (muerta, con forma de regla 1) | Borrar el método y sus dos sobrecargas. El nombre que viaja es el que eligió el modelo. |
| V4 | MemoryPanel.cs:134-199 (`KeysAsync`, `Candidates`, `Names`, `Words`, `Fold`) | 1, 4 | «the kept keys a datum named in the person's words stands for … every key that carries all the asked words». Empareja palabras de la persona con claves guardadas. Nada en `src/` ni en `tests/` lo llama. | violación (muerta) | Borrar las cinco piezas. |
| V5 | src/baxy_mind/data/memory_subjects.v1.json (incrustado por Baxy.App.csproj:29) | 1, 4 | `"selectors": {"favorite_color": ["color favorito","color preferido","favorite color",…]}` y `"withoutNamingMemory"` son listas de frases que ya no lee nadie. `_doc` cita `NaturalMemoryRequestParser`, que no existe. La App sólo lee `labels` y `factLabel` (MemoryPanel.cs:262-284), y la mente no lee el archivo. | violación | Quitar `selectors`, `withoutNamingMemory` y los `_doc` obsoletos. Ver G6 para `labels`. |

### Zona gris

| # | Archivo:líneas | Regla | Cita / qué pasa | Arreglo |
|---|---|---|---|---|
| G4 | SensitiveText.cs:86-89 (`password\|contrase(?:ñ\|n)a?\|\brut\b\|\bssn\b\|api[ ]*key…`), MainWindowViewModel.cs:352, MemoryOperationProtection.cs:264-270 y 324-330 | 1 / enmascarado | El enmascarado se permite, pero aquí se dispara con palabras de tema y no con un secreto. «¿Cómo cambio mi contraseña?» se ve como `••••••` en la transcripción, y un `memory.save` cuyo valor contiene esas palabras termina en `arguments_invalid` sin decir por qué. Junto con V2, un dato sensible no se puede guardar de ninguna forma. | Mantener la detección de credenciales (`LooksLikeCredentialToken` y prefijos `sk-`, `ghp_`…). Al rechazar `memory.save`, devolver `error: "value_sensitive"` para que el modelo use `memory.sensitive.save`. Ocultar sólo el token, no la línea entera. |
| G5 | MemoryPanel.cs:347-352 | confirmación | El panel contesta solo, con su token, el reto del kernel para cualquier operación de memoria que lance. El gesto de dos pasos sólo existe para olvidar (MemoryPanel.tsx:216); `memory.correct` no lo tiene. | Contestar el reto sólo en `memory.forget` después del doble clic. En las demás, devolver `confirmation_required` a la vista. |
| G6 | MemoryPanel.cs:259-284 y memory_subjects `labels` | 1 (vocabulario fijo) | La App traduce 11 selectores ingleses a palabras fijas («color favorito», «cumpleaños») y llama «dato» a todo `historical_fact_*`. El modelo escribe el selector que quiere, así que sólo esos 11 se traducen. | Mostrar el selector tal como se guardó (ya es la rama de respaldo: `Replace('_', ' ')`) y borrar el recurso incrustado. |
| G7 | MemoryPanel.tsx:80-83 | 2 (cero respuestas fijas) | `` toastError(`no pude ${verb} · …`) `` y «no pude confirmar si se pudo … · muestro lo guardado»: frases fijas en primera persona de BAXY. | Estado neutro: `` `${verb} · falló · ${code}` `` y `` `${verb} · sin confirmar` ``. |

### Permitido (revisado y se mantiene)
- MemoryOperationResponseProjection.cs:486-488: `[REDACTED]` para `sensitive`/`secret`, que es enmascarado.
- MemoryOperationResponseProjection.cs:315-322: `integrityVerified` es cierto porque lo verifica el proveedor
  (`LocalMemoryExportWriter.Verify`, Providers.Windows/Memory/LocalMemoryExportWriter.cs:100-135).
- MemoryOperationResponseProjection.cs:230-231 y 506-509: `memory_forget_empty` y `memory_none` son hechos que lee el
  modelo, no texto visible. `CompletedFacts` sólo se arma con `Completed`, y el kernel exige `Succeeded && Verified`.

## 3. Latido (Heartbeat, HeartbeatMoment)

### Zona gris

| # | Archivo:líneas | Regla | Cita / qué pasa | Arreglo |
|---|---|---|---|---|
| G8 | HeartbeatMoment.cs:27-28 y 30-45; MainWindowViewModel.cs:82-91 | 1 | El canal lo decide la App: `Speaks(activity) => activity == Free`, y fuera de eso es notificación. La actividad sale de umbrales: pantalla completa con GPU ≥ 40 % → «jugando», pantalla completa → «viendo», otro programa con el micrófono → «llamada», ≥ 10 min sin entrada → «ausente». En el diseño de escenas (latido-escenas.md:43-54), el canal es parte de lo que el modelo debe acertar. | Si el dueño decidió «voz sólo si está libre», anotarlo como decisión suya y dejarlo. Si no, que el modelo devuelva el canal y que la App le pase las señales crudas (`fullscreen`, `gpu_load`, `mic_in_use`, `idle_min`) en vez de la etiqueta. |
| G9 | Heartbeat.cs:139-158 | 1 | `foreach (int threshold in new[] { 20, 10 })` y `idle_min >= 10`: umbrales de la App que deciden cuándo despertar al modelo, aparte de las pausas del dueño. | Confirmarlos con el dueño o quitar esos eventos; `battery_pct` e `idle_min` ya van en cada `pc`. |
| G10 | Heartbeat.cs:161-173 | 2 | `Note($"download finished: {name} en Descargas")` cuando se dispara `Created`. Un navegador que crea el nombre final al empezar (con su `.part` al lado) se anuncia como «terminado» al arrancar la descarga. | Decir lo que se vio (`file appeared in Downloads: {name}`), o esperar a que no haya hermano `.part`/`.crdownload` y el tamaño no cambie. |

### Permitido (revisado y se mantiene)
- Heartbeat.cs:86-98: la mirada de cada 5 minutos se pausa mientras la persona juega o la GPU está ocupada. Es decisión
  del dueño (latido-escenas.md:33). Un cambio la sigue despertando.
- HeartbeatMoment.cs:47-89 (títulos de ventana, historial reciente, estado del PC): todo va al modelo local (regla 3).
  El comentario de `GpuBusy` («while BAXY is not deciding») lo cumple `CanBeat`.

## 4. Lo que vuelve al modelo

### Zona gris

| # | Archivo:líneas | Regla | Cita / qué pasa | Arreglo |
|---|---|---|---|---|
| G11 | ScreenViewProjection.cs:75 | 1 (paso dictado) | `"(ninguno: la ventana no expone sus controles; actúa por el texto en pantalla)"` le dicta al modelo qué hacer. | Dejar sólo `(ninguno)`. |
| G12 | ScreenViewProjection.cs:51 y 119-125 | 2 | Sin dato de `foreground` dice «al frente» (`== false ? ", no está al frente" : ", al frente"`). La proyección conserva sólo `kind`, `operation`, `verified` y `succeeded`, y pierde `status`, `error` y `effectUncertain` de los hechos del kernel. | Escribir «al frente» o «no está al frente» sólo si se observó, y copiar esos tres campos. |

Comprobado sin hallazgo: OperationResponseProjection.cs:22-73 pasa `response.Message` (los hechos del kernel) o
`OperationVisibleFacts.FromStatus`, y sólo recorta. `TurnVisibleFacts` ya no se publica: construye el JSON de hechos de
memoria que lee el modelo (su comentario lo dice: «esto no se publica»).

## 5. Lo que ve la persona: texto fijo e interfaz

### Violaciones

| # | Archivo:líneas | Regla | Cita / qué hace | Severidad | Arreglo mínimo honesto |
|---|---|---|---|---|---|
| V6 | FieldProductChannel.cs:1099-1107 (`ContextSize`), 1022, 545-551; FieldCenter.tsx:220; SettingsPanel.tsx:77 | 2 | `GetEnvironmentVariable("BAXY_MIND_CTX") … : 12288`. Nadie publica esa variable; la mente usa `BAXY_RENEW_CTX` con 49152 por defecto (`__main__.py:24`). `/model`, `/settings` y el evento `ctx` informan un contexto falso. El compositor muestra `{tokens} / 4k`, y la pestaña Connection (visible) muestra `maxTokens` 1280 de los DEFAULTS de la vista, porque la App no lo envía. El comentario cita `llm.MAX_CONTEXT_TOKENS`, «Fase 3.5b», que ya no existe. | violación | Leer `BAXY_RENEW_CTX` (por defecto 49152), o mejor, que la mente lo anuncie en su `hello`. Quitar «/ 4k» y `maxTokens`. |
| V7 | FieldProductChannel.cs:991-1010 (`VoiceInventory`) y 1013-1031 (`CurrentSettings`) | 2 | `["downloaded"] = _viewModel.IsMicAvailable` para STT, TTS y wake. Además `["ttsProvider"] = "sherpa-onnx piper (local)"`, cuando la mente usa `piper.exe` (voice_output.py:91-92), y `wakeWord`, `sttModel` y `ttsVoice` fijos. La pestaña Transcript (visible) los muestra como estado real. | violación | Tomarlos de `voice.status` de la mente (`stt`, `tts`, `wake` ya llegan en `MindVoiceStatus`) y de las rutas que cargó, o quitar los campos. |
| V9 | Baxy.FieldUi/src/hooks/useEventStream.ts:313-319 | 2 (cero respuestas visibles fijas), 4 | `pushToast({ … msg: 'No te entendí — probá de nuevo' })` es una frase fija en primera persona de BAXY. La App nunca emite `voice_no_speech`. | violación (latente) | Borrar el caso, igual que su comentario en types.ts:151. |

### Zona gris

| # | Archivo:líneas | Regla | Cita / qué pasa | Arreglo |
|---|---|---|---|---|
| G13 | MainWindowViewModel.cs:92-97 y 449-453; FieldBridgeContract.cs:201-204 | 2 (silencio que oculta un fallo) | `Fail` sólo guarda `LastTurnFailure` (`mind_unavailable`, `decision_unavailable`, `turn_failed`). Eso únicamente lo lee el conductor (ProductConductorHost.cs:233). Lista y sin trabajo, `ResolveProgress` devuelve `null`: la persona escribe y no ve ni respuesta ni estado. | Publicar el código en el evento `agent` (`turnFailure`) y que la vista muestre el estado neutro que ya tiene (`convState 'error'`, FieldCenter.tsx:205-207), sin prosa. |
| G14 | FieldProductChannel.cs:493-496 y 516-520; SettingsPanel.tsx:996-1009 | 2 | `PUT /settings` responde `{"ok":true}` y no aplica nada. `/agent/restart` vuelve con HTTP 200 sin hacer nada cuando ya está lista (`InitializeAsync` sale en `if (_isInitializing \|\| IsReady) return;`), y la vista avisa `'agent restart triggered'`. Hoy queda latente porque el puente esconde «apply» y «restart» (field-native-bridge.js:259-270). | `PUT /settings` → 405 `settings_read_only`. `restart` → `already_running` cuando está lista. Borrar ese aviso de éxito. |
| G15 | FieldProductChannel.cs:419-431, 456-466, 468-479, 508-514 | 2 | Textos fijos y falsos: `"Planner local con selección segura de herramientas"` (no hay planificador), persona `"BAXY local"`, perfil `"vram4"`, y la pestaña Prompt (visible) muestra `"La mente local de BAXY administra su prompt…"` en lugar del prompt. | Borrar `/agent/modes`, `/agent/personas` y `/profile`. Que Prompt muestre el prompt real de la mente, sólo lectura, o quitar la pestaña. |
| G16 | FieldCenter.tsx:96 | 2 | `'llama-server offline · waiting for connection…'` sale cuando `!agent.healthy`, que la App calcula como `IsReady && !HasStartupError`, un estado del core y no de llama-server. | Mostrar un estado que diga lo observado (`engine not ready` o el código de causa). |

### Permitido (revisado y se mantiene)
- ActivityPanel.tsx:155-183 y MainWindowViewModel.cs:357-367: los botones Sí/No mandan `{approve}`, y la etiqueta «Sí»
  o «No» entra como turno de la persona.
- MainWindowViewModel.cs:352: la máscara `••••••` en la transcripción (enmascarado; el texto real sí va al modelo).
- `StatusText` («Iniciando», «Lista», «Trabajando»…) y las superficies de carga o fallo (MainWindow.xaml.cs:80, 379,
  400): son estados de la interfaz, no respuestas de BAXY.
- App.tsx:243-256 y FieldProductChannel.cs:1036-1063 (`PUT /confirmation`, modo bypass): es un gesto de la persona en
  la vista propia de BAXY y escribe el modo que lee el kernel.

## 6. Variables de entorno

La mente lee `BAXY_MIND_LLM_GGUF`, `BAXY_MIND_LLAMA_SERVER`, `BAXY_MIND_NGL`, `BAXY_RENEW_SERVER_ARGS`,
`BAXY_RENEW_CTX`, `BAXY_RENEW_DESCRIPTIONS`, `BAXY_RENEW_DECIDE_TEMPERATURE`, `BAXY_RENEW_STT_DIR`, `BAXY_RENEW_WAKE_DIR`,
`BAXY_RENEW_MIC`, `BAXY_RENEW_TTS_MODEL`, `BAXY_RENEW_PIPER_DIR` y `LOCALAPPDATA`. `PYTHONPATH` le llega desde
`BAXY_MIND_PYTHONPATH`.

| # | Archivo:líneas | Regla | Qué pasa | Severidad | Arreglo |
|---|---|---|---|---|---|
| V8 | MindRuntimeDiscovery.cs:186-201, 205-208, 210-229, 232; huella 661-731 | 4 | `SetIfMissing("BAXY_MIND_CPU_PROSE_ADAPTER"…)`, `"BAXY_MIND_DECIDER_ADAPTER"`, `"BAXY_MIND_STT_DIR"`, `"BAXY_VOICE_WAKE_MANIFEST"`, `"BAXY_VOICE_WAKE_CASCADE_MANIFEST"`, `"BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED"` y `"HF_HUB_OFFLINE"`: la mente no lee ninguna. Tampoco publica ninguna `BAXY_RENEW_*`, aunque el registro verificado trae `stt_dir`, `tts_model` y `wake_manifest` (RegistrationProperties 48-66). La voz depende de que `scripts/run_renew.cmd:11-19` las ponga. | violación | Publicar `BAXY_RENEW_STT_DIR`, `BAXY_RENEW_TTS_MODEL`, `BAXY_RENEW_PIPER_DIR` y `BAXY_RENEW_WAKE_DIR` desde el registro verificado (ojo: la mente espera una carpeta con `config.json`, no un manifiesto), y borrar las 7 que nadie lee, con sus campos en la huella. |

Otras, comprobadas: `BAXY_MIND_CTX` (FieldProductChannel.cs:1101) la lee la App y nadie la pone (ver V6).
`BAXY_COMPOSITION_INJECTION` (FieldProductChannel.cs:83-107) está en código muerto. `GpuLayersEnvironmentVariable`
(MindSidecarClient.cs:124) no se usa. `BAXY_VOICE_WAKE_ON_START`, `BAXY_DATA_DIR`, `BAXY_MIND_PYTHON*`,
`BAXY_MIND_DISABLED`, `BAXY_RENEW_HEARTBEAT`, `BAXY_CONVERSATION_LOG` y `BAXY_APP_TRACE` las lee la propia App o el
core, así que son legítimas.

## 7. Código muerto o apilado (regla 4)

| # | Archivo:líneas | Qué es | Severidad | Arreglo |
|---|---|---|---|---|
| V10 | Baxy.FieldUi/src/components/SettingsPanel.tsx:17-30 (12 pestañas), 33-104 (`SettingsConfig` y `DEFAULTS`), 325-457, 547-860 | Formulario completo de Gemma 4 (`safetyFilter`, `allowCoT` «allow gemma to expose chain-of-thought», `GEMMA4_*`, rutas `~/gemma4/...`) con listas de palabras: `followUpClosePhrases: 'gracias\nlisto\nya está\ncancelar'` y `gameProcesses: 'steam.exe\nRobloxPlayer.exe\njavaw.exe'`. Ocho pestañas se esconden en tiempo real y los controles se desactivan desde el puente. | violación (apilado, listas inertes) | Borrar las pestañas ocultas y sus campos. Dejar Connection y Transcript con datos reales (V6, V7), y Prompt y About. |
| V11 | Baxy.App/Assets/field-native-bridge.js:7-12, 184-284 | Una capa sobre la vista: `MutationObserver` que reescribe el DOM con regex (`/gemma\s*4/i` → «BAXY · desktop», `.st-tip` por texto), desactiva todo `input, select, textarea, button` de ajustes y esconde los botones del pie. | violación (apilado) | Cambiar la fuente React (TitleBar, AboutTab, SettingsPanel) y borrar `applyNativeBranding` y `startNativePresentationOverlay`. |
| V12 | FieldBridgeContract.cs:62-67, 85-127; FieldProductChannel.cs:925; MainWindowViewModel.cs:458-461, 538, 582, 630, 639 | Mapeo de descripciones en español que ya nadie escribe («Ejecutando paso », «Mirando la pantalla», «Paso », «Preparando los pasos», «Esperando confirmación de memoria», `awaiting_mission_resume`…). `"awaiting_confirmation"`, que sí se escribe, no está mapeado. `StatusDescription == "Te escucho"` nunca se cumple porque el VM escribe «Te escucho…». | violación | `StatusDescription` como códigos cerrados (`wake_waiting`, `listening`, `transcribing`, `awaiting_confirmation`…), mapear sólo esos y borrar el resto. |
| V13 | ConsultedSource.cs (todo), ConversationMessage.cs:3-4 y 11, FieldProductChannel.cs:133-143, 321-331, 605-614, 1141-1155, ActivityPanel.tsx:145-153 y 184-196 | `ConsultedSource.From` no se llama nunca y `SourceUrl` siempre es nulo: `/source/open` responde siempre 404 y el enlace «fuente» no aparece. Se perdió la atribución CC BY-SA que pedía la decisión D35 del dueño. | violación | Cablearlo: en `NativeTurnLoop`, guardar `ConsultedSource.From` del `web.search` verificado del turno y pasarlo al `Publish` de la respuesta. O borrar la cadena entera si D35 se retira. |
| V14 | OperationResponseProjection.cs:16-20 | Rama `HonestyCorrection`: nada en el producto la construye (K5 de la auditoría del kernel). | violación | Borrarla junto con K5. |
| V15 | Inventario de `app-codigo-muerto.md`, sigue vigente en `b33a3e62d` | `AgentFieldGraph.cs` (192 líneas); en PreparedOperation.cs, `CreateFollowUp`, `Matches`, `Replace`×3, `SnapshotPendingOperations` y `RestorePlanOperation`; `FieldCompositionInjection`/`FieldPublicationInjection` (ramas Silence/Filter/SuppressFinal, FieldProductChannel.cs:47-107, 738-803, 876-880); muestreos de PresenceIdleSampler; etapas de ShellTrace; `MemoryOperationProtector.AuthenticateForOutbox`/`Authenticates`. Unas ~1077 líneas. Además, `TurnVisibleFacts.Event` deja muertas las ramas `error`/`confirmation`/`clarification` (TurnVisibleFacts.cs:32-37), y `FieldUiBridge.cs:371` captura `MissionPlanValidationException` (K4). | violación | Borrar según ese inventario. |
| V16 | FieldUi: TriggersPanel.tsx (322 líneas; las rutas devuelven 409 `routines_require_planner`, FieldProductChannel.cs:393-401; aviso «trigger fired», 166), ToolsPanel.tsx (lista vacía, 403-417), botón de adjuntar (FieldCenter.tsx:234-240, `/upload` 501), ramas `prewarm`/`vision_threshold_reached` (useEventStream.ts:274-310), `/agent/recycle_server`, enlaces a Google Fonts (index.html:11-16, bloqueados por MainWindow.xaml.cs:404-420) | Interfaz heredada que no hace nada o siempre falla. | violación | Borrar los paneles, el botón, las ramas, las rutas y los enlaces. |

### Permitido (revisado y se mantiene)
- FieldUiProbe.cs (`--ui-probe`, sólo desarrollo): escribe en el WebView propio de BAXY, no en una ventana de la persona.

## 8. Comprobaciones pedidas expresamente

- **`ConfirmationReplyParser` o algo parecido:** no queda. En la App y en FieldUi no hay listas de «sí/no». El «sí» lo
  leen el modelo o los botones. Lo único que no anda es que el modelo pueda contestarse a sí mismo (V1).
- **`MissionNarration`, `PrivateOperationNarration`, `OperationFloor`:** ya no existe ningún símbolo con esos nombres en
  `src/`. Tampoco quedan `operation_floor.v1.json` ni `assent_words.v1.json`.
- **`TurnVisibleFacts`:** sigue vivo, pero sólo arma el JSON de hechos de memoria para el modelo y no se publica.
  Restos muertos en V15.
- **Lectores de `memory_subjects.v1.json`:** sólo uno, `MemoryPanel.Subjects` (`labels`, `factLabel`). Las listas
  `selectors` y `withoutNamingMemory` ya no las lee nadie (V5).
- **Texto fijo en español que ve la persona:** en el chat no hay ninguno; el chat sólo publica lo que escribió el
  modelo. Aparece en avisos de la vista (V9, G7), en datos de ajustes (V6, V7, G15) y en estados de la interfaz
  (permitidos).
- **Latido:** las pausas del dueño (juego o GPU) se respetan. La App decide además el canal, los umbrales de evento y la
  retención (G1, G8, G9). V1 deshace la retención.
- **Regla 3, red:** la App no tiene `HttpClient` ni sockets salientes. WebView2 bloquea toda red externa
  (MainWindow.xaml.cs:404-420) y el único `Process.Start(url)` es el enlace «fuente», que está muerto. La regla 3 se
  incumple sólo por la entrada en la ventana al frente (G2 / P1 del kernel).

## Recuento

- **Violaciones: 16** (V1-V16)
- **Zona gris: 16** (G1-G16)
- **Permitido, revisado y se mantiene: 15**
