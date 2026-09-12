# MUSIC1079 — horizonte de verificación SMTC agotado

Diagnóstico fechado2026-09-12, sobre MUSIC1077 caso6 music1037-dev-03, candidato6929b5ff388bc1410213380a14f3a965458053eb. La operación correcta ya fue emitida; el corte está en postlectura del provider existente. Propuesta externa acotada: horizonte de ControlAsync de350ms a2000ms, conservando dispatch único y postcondición. Es una hipótesis aceptada por raíz para medir, no una reparación demostrada ni crédito.

## Hechos ligados a la invocación

Journal antes vacío(length0,SHAe3b0...), después4231bytes, SHA93e63d3c0682d716489e3b4be3256d61d1d033b886a9f5477aebcf81eaea9c66. El delta contiene sólo memory.status inicial y media.control. Invocación632be546-778b-4699-8e58-bebf5ea30ff8 empezó17:57:07.1350545Z y finalizó17:57:07.5446494Z, duración409,595ms. Respuesta failed, verified=false, result=null,errorCode=smtc_postcondition_not_verified,effectMayHaveOccurred=true,causeCode=external_effect_ambiguous. No se reatribuyen invocaciones anteriores.

Prelectura de raíz terminó17:56:41.355819Z: Aurora de cobre, artista Original BAXY preparation composition, Microsoft.ZuneMusic...,paused. Postlectura empezó17:57:28.594185Z y terminó17:57:30.611595Z: misma identidad/título/artista,playing. Raíz observó UI0:20 antes y0:45 después. La lectura posterior ocurre unos21s después del término de la invocación: NO indica que la transición tardase21s. No hay observaciones intermedias que fijen cuándo cambió ni basta ese estado posterior para conceder verificación retrospectiva. El final visible indicó resultado no verificado; no se sustituye por éxito.

## Lectura del owner y herencia

WindowsMediaSessionAdapter.cs404–509: TryPlayAsync se invoca una sola vez. Si devuelve false termina smtc_control_dispatch_rejected; ése no fue el código observado, por lo que el dispatch fue aceptado. Después realiza lecturas del mismo objeto session: TryGetMediaPropertiesAsync y GetPlaybackInfo.PlaybackStatus. Para play exige Playing(451–470). El bucle474–502 usa intento0..7 y siete retrasos50ms; horizonte nominal350ms más coste de llamadas. El total observado409,595ms es coherente con agotarlo.

El código específico smtc_postcondition_not_verified distingue este resultado del catch de excepción: al terminar la última lectura no se verificó la postcondición y no quedó una excepción final que fuese relanzada. No se sabe si Windows anunció tarde el estado, el proxy no lo actualizó a tiempo o hubo otra transición externa. La traza no registra cada valor intermedio; no se inventan esos datos.

Herencia: REGISTRO_DE_MANTENIBILIDAD.md546–554 conserva explícitamente horizonte SMTC350ms, lectura inmediata cuando no confunde estado previo y lectura terminal para idempotencia. Allí se aclara que el ahorro es simulado y no ejecución física Spotify. MUSIC1063 corrigió otro defecto del mismo owner: providerSpotify hardcoded; permanece corregido y no explica este fallo. git log -S SmtcPostreadPollIntervals sólo ubica el horizonte en el punto de partida7662b80c, no aporta validación física de suficiencia para esta sesión de Media Player.

## Propuesta mínima y límites

Único ownerWindowsMediaSessionAdapter.cs: constanteSmtcControlPostreadPollIntervals=40 y las dos referencias del bucle/terminal de ControlAsync. Intervalo existente50ms,40esperas=2s. Los bucles PlayExact y Seek siguen7/350ms; WebAPI conserva su horizonte propio. No se cambian descripciones/catálogo/modelo ni se crea otro provider.

La llamada de efecto queda antes del bucle y no se repite. Las lecturas siguen el mismo objeto de sesión; éxito requiere exactamente el mismo predicado IsVerified. Una condición satisfactoria antes del dispatch conserva lectura terminal (ahora2s) para no confundirla con el estado previo. Se conserva cancellationToken en cada delay y la política de cancelación de los catches; no se cambia el timeout de negocio ni el transporte. Si el estado no se verifica, vuelve el mismo failure con incertidumbre de efecto, sin rellenar result ni convertir postlectura externa de raíz en recibo del producto.

El plazo2s es un presupuesto de observación acotado que raíz autorizó ensayar; este único fallo no demuestra que sea suficiente ni identifica el instante real de transición. No hay nueva ejecución en este diagnóstico. Raíz observará caso7 y controles independientes antes de adoptar; luego sólo una medición dirigida con nueva preparación, candidato y respuesta útil puede resolver esta hipótesis. No repetir ciegamente el mismo efecto ni reanudar después de una acción ambigua sin volver a observar estado.

Revisión estática: diff de tres líneas funcionales(una constante y dos referencias), dispatch y predicates intactos, loopsajenos intactos, sourceSHA coincide con PREPARATION1077. IDENTITY.json preserva fechas/pins. Sin pruebas, importsproducto, Core, GPU, build, fuente canónica, registro, adjudicación ni crédito.
