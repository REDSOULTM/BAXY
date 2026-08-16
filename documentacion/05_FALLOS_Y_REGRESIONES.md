# Fallos históricos convertidos en regresiones

## Contrato del ledger

Esta es la matriz canónica de lecciones→diseño→prueba. Un ID no significa que
la implementación nueva ya pase: **especificada** significa que el fallo tiene
un comportamiento esperado y un gate inequívoco; **pendiente** significa que
ese gate todavía no se ha ejecutado sobre BAXY 1.0.

Cada prueba automática debe observar contrato y estado, no un stub. Cada gate
físico requiere autorización cuando afecta cuentas, aplicaciones, hardware o
datos reales.

## Matriz canónica

| ID | Fallo y causa recuperada | Decisión de diseño | Regresión automática | Gate físico | Estado 1.0 |
|---|---|---|---|---|---|
| R-001 | Carter reportó 489/540 automáticos, pero sólo 417/540 eran reales: stubs y dispatch se contaban como efecto | Resultado `success` sólo tras observación independiente | `REG-001` rechaza provider simulado como acceptance real | `PHY-001` muestra estado anterior/posterior de una muestra por dominio | Especificada |
| R-002 | Gemma unificado obtuvo 0/11 con STT/visión vacíos; health no identificaba servidor/modelo | Attestation liga PID, parent, binario, commit, modelo, mmproj, puerto y request | `REG-002` inyecta listener/modelo equivocado y exige fail-closed | `PHY-002` verifica proceso y request del runtime instalado | Especificada |
| R-003 | La GUI mostró “core listo · 0 capacidades” | Readiness deriva del catálogo y providers atestados; degradación visible | `REG-003` impide estado listo con cero/no saludables | `PHY-003` arranque limpio, degradado y recuperado | Especificada |
| R-004 | Catálogos de cientos de tools aumentaron confusión y contexto | Operaciones pequeñas componibles; shortlist acotada; KPI por misiones | `REG-004` mide shortlist, colisiones y cobertura de las 42 familias | No aplica directamente | Especificada |
| R-005 | Router curado 99,64 % cayó a 85,7 % en logs reales | Corpus observado separado de train y replay obligatorio | `REG-005` ejecuta holdout histórico por el camino runtime | `PHY-005` muestra real de voz/texto | Especificada |
| R-006 | Holdout en exemplars e índices desincronizados fabricaron evaluaciones | Artefactos derivados versionados como unidad y cero solape | `REG-006` prueba disjunción, digest y consistencia ID→label | No aplica | Especificada |
| R-007 | El primer split FunctionGemma rompió abstención 0/3 y subsets dominados por familia | Gate KVA/no-tool independiente; incertidumbre termina en conversación | `REG-007` combina no-tool, conocimiento, acción y OOD multilingüe | `PHY-007` frases espontáneas no curadas | Especificada |
| R-008 | Modelo, encoder y schemas evolucionaron por separado y causaron sibling confusion | Bundle atómico con digests compatibles | `REG-008` rechaza combinaciones cruzadas y argumentos fuera de schema | No aplica | Especificada |
| R-009 | Acciones compuestas continuaban tras un paso fallido o narraban el objetivo completo | Plan con dependencias; stop/compensación; estado por paso | `REG-009` falla pasos 1..N y prohíbe efectos dependientes | `PHY-009` composición autorizada Steam+Spotify/alternativa local | Especificada |
| R-010 | Retry/replay podía repetir un efecto | Invocation ID, ledger durable e idempotency key del provider | `REG-010` repite request tras timeout/crash y exige un solo efecto | `PHY-010` replay de una acción reversible | Especificada |
| R-011 | Confirmar toda mutación hacía el producto inutilizable; aprobar todo era inseguro | Riesgo por dinero, irreversibilidad, privacidad, privilegio y estado sin guardar | `REG-011` cubre matriz allow/conditional/required/forbidden | `PHY-011` UX de confirmación sin efecto previo | Especificada |
| R-012 | Cerrar Word podía perder trabajo | Consultar `Saved/Dirty`; confirmar sólo pérdida posible | `REG-012` distingue documento limpio/sucio/inobservable | `PHY-012` documento temporal limpio y modificado | Especificada |
| R-013 | Instalar se trataba siempre como peligro o se confundía con compra | Propiedad/costo/fuente/privilegio determinan confirmación | `REG-013` separa instalado, poseído, gratis, pago y origen desconocido | `PHY-013` instalador reversible autorizado | Especificada |
| R-014 | Timeout fijo de 8 s falló al inventariar Spotify frío | Presupuesto por fase y percentiles warm/cold, siempre acotado/cancelable | `REG-014` usa provider lento y valida deadline por fase | `PHY-014` arranque frío y caliente | Especificada |
| R-015 | Workers, Playwright y servidores huérfanos sobrevivían a timeout/salida | Árbol de procesos con ownership, job object y cleanup verificable | `REG-015` mata padre durante cada fase y busca descendientes | `PHY-015` cierre y desinstalación sin procesos/puertos | Especificada |
| R-016 | `os.replace` de heartbeat falló con WinError 5 bajo lector concurrente | Persistencia atómica con retry acotado, fsync y recovery | `REG-016` bloquea temporalmente el destino e inyecta crash | No aplica | Especificada |
| R-017 | NUL, mojibake y consolas cp1252 rompían parsers/transporte | UTF-8 en bordes, sanitización y transporte length-safe | `REG-017` fuzz de NUL, Unicode, emoji, RTL y paths | `PHY-017` Windows con locale no UTF-8 | Especificada |
| R-018 | Behavior logs crecían sin techo y memoria/proactividad podía ser opaca | Consentimiento, minimización, TTL, cifrado, inspección y olvido | `REG-018` prueba TTL, export, forget, redacción y default-off | `PHY-018` flujo humano de permiso/inspección/olvido | Especificada |
| R-019 | Wake falso por ambiente/TTS creaba turnos fantasma | Wake + verificador + evidencia de voz + inhibición durante boot/TTS | `REG-019` mezcla silencio, música, TTS y hard negatives | `PHY-019` corpus real con ruido y distancia | Especificada |
| R-020 | Parakeet logró baja latencia, pero 81 % de recall de entidades | Corrección fonética y rescate selectivo sin inventar entidades | `REG-020` corpus de nombres, apps, canciones y códigos ES/EN | `PHY-020` dictado de entidades del usuario | Especificada |
| R-021 | AEC simulado y wake no demostraban barge-in acústico | Referencia loopback, ducking y cancelación medidos E2E | `REG-021` simulación de eco con SNR/ERLE | `PHY-021` interrumpir TTS por micrófono real | Especificada |
| R-022 | Respuesta hablada y mostrada podían divergir | Un resultado semántico alimenta ambos canales; secretos no se vocalizan | `REG-022` compara significado y política de redacción | `PHY-022` escucha/lectura humana de muestra | Especificada |
| R-023 | Qwen-VL inventó juegos ambiguos; visual diff podía dar falso éxito | UIA/OCR/proceso/título corroboran visión; salida triestado | `REG-023` corpus ambiguo/negativo y cambios visuales irrelevantes | `PHY-023` apps/juegos reales con ground truth | Especificada |
| R-024 | WebView2 podía caer por GPU y dejar la aplicación inutilizable | Shell aislado y fallback explícito, no loop permanente | `REG-024` simula crash/restart y preserva sesión | `PHY-024` crash de renderer en instalación | Especificada |
| R-025 | Perfil “4 GB” se infería desde GPU de 16 GB | Presupuesto por proceso y global; perfil físico separado del proxy | `REG-025` mide RAM/VRAM/picos/carga lazy y falla sobre límite | `PHY-025` GPU real de 4 GB o declaración honesta de no validado | Especificada |
| R-026 | El árbol antiguo mezclaba app/datos y dependía del Python del desarrollador | Paquete autocontenido, datos por usuario, pins, SBOM, firma/checksum, rollback | `REG-026` build doble reproducible y smoke sin tooling dev | `PHY-026` VM Windows limpia: install/update/uninstall/rollback | Especificada |
| R-027 | Flags experimentales contaminaban el perfil estable | Perfiles incompatibles con attestation y digest distintos | `REG-027` prueba defaults y todas las combinaciones prohibidas | `PHY-027` arranque estable/experimental claramente rotulado | Especificada |
| R-028 | Un visor JSON privado reemplazó la respuesta normal | Conversación natural por defecto; detalle técnico opt-in y redactado | `REG-028` prohíbe JSON/tool calls/secrets en respuesta normal | `PHY-028` evaluación humana de claridad | Especificada |
| R-029 | Soaks largos dominaron antes de cerrar funcionalidad; un run falló por el harness | Gates funcionales primero; harness se auto-verifica; soak final | `REG-029` preflight del harness y orden de gates | `PHY-029` 24 h sólo tras cero P0/P1 y acceptance | Especificada |
| R-030 | Conteos 5.532/5.535 divergieron entre resúmenes | Resultado ligado a comando, commit y artifact inmutable | `REG-030` genera manifiesto de suite y verifica digest | No aplica | Especificada |
| R-031 | Spotify Win32 tenía AUMID `None`; una regla Store lo rechazaba siempre | Identidad por variante: firma, executable, árbol y package cuando exista | `REG-031` fixtures Win32/Store falsos y válidos | `PHY-031` cliente instalado autorizado + SMTC | Especificada |
| R-032 | Steam podía no estar disponible y handles de preview no estar resueltos | Preview sin efectos; dependencias externas producen fallback/negativa honesta | `REG-032` prueba ausencia, offline, no poseído y handle tardío | `PHY-032` cliente/cuenta autorizados | Especificada |
| R-033 | Endpoints remotos y logs planos podían filtrar contenido | Local-first; egress opt-in visible; secretos en vault; canales público/privado | `REG-033` bloquea red por defecto y escanea artefactos/logs | `PHY-033` inspección de tráfico del paquete | Especificada |
| R-034 | Preguntas, negaciones y pedidos de lectura disparaban escrituras | Forma pragmática precede selección de operación; lectura≠escritura | `REG-034` multilingüe para interrogativa, negación y read/write | `PHY-034` frases espontáneas por voz | Especificada |
| R-035 | Capacidades ausentes como instalar podían terminar en claim inventado | Sin provider verificable: abstener, explicar y ofrecer alternativa | `REG-035` elimina provider y prohíbe claim de efecto | `PHY-035` dependencia ausente en Windows limpio | Especificada |
| R-036 | UIA/OCR/visión podían actuar sobre ventana/app equivocada | Target ligado a identidad, foco, sesión y precondición observable | `REG-036` cambia foco/ventana durante ejecución y exige abort/re-resolve | `PHY-036` carrera de foco en escritorio real | Especificada |

## Fuentes de autoridad

- Carter: historial Git y
  `../Carter OS AI/legacy/Carter_v4/CARTER_540_REAL_PROGRESS_REPORT.md`.
- Probando Gemma 4: `documentacion/01_arquitectura/ARCHITECTURE.md`,
  `documentacion/02_router/05_HISTORIAL_SPRINTS.md`,
  `documentacion/03_voz_stt/README.md`,
  `documentacion/04_computer_use/README.md`,
  `documentacion/08_memoria_jarvis/README.md` y
  `documentacion/09_finetune/DECISION_MAESTRA_4GB.md` del repositorio fuente.
- FunctionGemma: `INTEGRATION_HANDOFF.md` y `router/README_ROUTER.md`.
- BAXY archivado: `legacy/README.md`, historial hasta `ee06786` y suites
  preservadas en `legacy/`.
- Agentes: `09_LEDGER_EVIDENCIA_AGENTES.md`; una auditoría no aumenta de nivel
  por repetirse.
- Corpus actual: `tests/data/historical_messages.jsonl`,
  `historical_missions.jsonl` y `historical_message_mapping.jsonl`.

## Definición de cierre por regresión

Una regresión pasa a **cerrada** sólo cuando conserva:

1. fuente y causa o hipótesis explícita;
2. decisión de diseño implementada;
3. prueba automática que observa el contrato;
4. gate físico cuando afecta el mundo real;
5. artifact, entorno, comando y commit;
6. respuesta natural esperada y comportamiento de fallback.

Al cierre documental actual hay 36/36 modos de fallo estructurales
especificados y 0/36 cerrados sobre el producto nuevo. Las 117 ocurrencias de
feedback/fallo del corpus permanecen enlazadas individualmente a su misión;
esta matriz las generaliza sin borrarlas.
