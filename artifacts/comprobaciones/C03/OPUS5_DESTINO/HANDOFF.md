# Handoff — C03 relevo en PC destino — 2026-09-12 — ed305c38

## Objetivo
Completar C03 «respuesta veraz de BAXY». Cierre: los 742 case_id de la encuesta adjudicados con
literal exacto ejecutado en el producto y dos variantes pertinentes por conducta; 11/11 filas C03.

## Papeles de las máquinas
REDPC (`C:`) es el BAXY **original**; el portátil sólo replicó el repositorio y su raíz en `D:` era
porque su `C:` estaba lleno. El tramo de C03 desde el 2026-09-06 se ejecutó en la réplica: allí
quedaron su evidencia privada y la descarga del modelo decidido.

## Estado
Hecho: rama actualizada a `ed305c38` por `merge --ff-only` (192 commits, worktree limpio, WIP ajeno y
`main` intactos); procesos de producto del arranque automático cerrados; Release compilado; **modelo
decidido restaurado, registrado y verificado en carga**; adjudicación 1025 cerrada en cobertura con
14/25 casos juzgados; diagnóstico de referente ausente demostrado; propuesta 1024 revisada.
En curso: nada en ejecución. Ningún proceso de producto activo, ninguna GPU en uso por BAXY.
Sin empezar: medición de 1024, tanda de referente ausente, sellado de la siguiente categoría. Los
tres dependen del registro privado de la encuesta, no del runtime.

## Decisiones tomadas
- **El crédito de 1025 es 3 y es definitivo.** Descripción de juegos tiene 2 de 3 variantes caídas y
  comparación ficcional 1 de 2: ninguna alcanza las 2 variantes en pie que exige un crédito, y
  KNOWLEDGE998 —única tanda anterior de la categoría con adjudicación versionada— sólo cubrió
  aritmética, conversiones, sustancia/mezcla y estilo humorístico. H0236/H0239/H0582 siguen open sea
  cual sea el veredicto de su literal. No reabrir sin una tanda nueva.
- **No registrar `D:/BAXYRuntime/assets/models/Qwen3-4B-Q4_K_M.gguf`.** Se llama igual que el primer
  candidato de `assets.manifest.json` pero es el modelo activo **anterior**, Instruct AWQ `7485fe6f…`,
  identificado así por `artifacts/research/qwen3_4b_instruct_2507_candidate_preregistration_20260811.json`.
  Registrarlo sería el reemplazo silencioso prohibido.
- **El modelo decidido se restaura, no se pide.** Su procedencia atestada está versionada en esa misma
  prerregistración: `unsloth/Qwen3-4B-Instruct-2507-GGUF` en la revisión `a06e946b…`, 2 497 281 120
  bytes, SHA `3605803b…`, Apache-2.0, con orden congelado `.partial` → bytes → SHA → renombrado. Ya
  está en `D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/` y registrado.
- **El modelo y el wake se declaran en `%LOCALAPPDATA%/BAXYRuntime/assets.local.json`**, el override
  oficial del manifiesto. Sin la entrada de `wake_manifest`, bootstrap registra con `-NoWake` y
  `wake_on_start` cae a `false`. Copia del manifiesto previo en `mind-runtime-v1.json.pre-c03-relay.bak`.
- **No sellar ningún panel nuevo todavía.** `SURVEY_TAXONOMY846.json` no contiene literales; sellar
  sin el literal exacto es fabricar material.
- **dotnet efectivo aquí es el global** `C:/Program Files/dotnet/dotnet.exe` 10.0.100.
  `%USERPROFILE%/.dotnet` no existe en este PC; la nota del origen no aplica.

## Archivos tocados
- `artifacts/comprobaciones/C03/RELEVO_ACTIVO.json` — esquema v3: identidad del relevo, rutas del
  destino, inventario de runtime, artefacto ausente. Conserva `sourceThreadId` y la pausa histórica.
- `artifacts/comprobaciones/C03/KNOWLEDGE1025/ADJUDICATION_STATUS.json` — nuevo. 25 casos por
  estado, causas de los 9 fallos, aritmética de cobertura.
- `artifacts/comprobaciones/C03/AGENDA1024/ROOT_REVIEW_DESTINO.md` — nuevo. Revisión del diseño.
- `artifacts/comprobaciones/C03/OPUS5_DESTINO/{DESTINO_INVENTARIO.json,SOLICITUD_TRASLADO.md,HANDOFF.md}` — nuevos.
- `artifacts/comprobaciones/C03/CHECKPOINT.md` — cabecera reescrita; el «No repetir» y la historia
  posterior siguen intactos.
- `artifacts/comprobaciones/C03/ESTADO_PARA_DUENO_2026-09-12.md` — nuevo.
- Ningún fichero de `src/`, `tests/` ni `scripts/` modificado.

## Archivos relevantes aún sin tocar
- `src/baxy_mind/effect_intent.py:2235,2259,3170-3182,13842` — donde entra 1024 cuando se mida.
- `src/baxy_mind/__main__.py:2818,5831,5843` — reconocedor de referente ausente y la ruta que ya
  existe; donde entra esa reparación cuando haya panel.
- `artifacts/comprobaciones/C03/KNOWLEDGE1025/PLAN.md` — panel sellado; las 18 reservas de la
  categoría y sus condiciones están ahí, no reclasificar.

## Hipótesis
Confirmadas:
- Este PC nunca vio las tandas 1010–1027 → `%LOCALAPPDATA%/BAXY` tiene 1489 directorios, ninguno
  `C03-*-private`, evidencia más reciente 2026-09-06.
- La fuente de producto del destino es la de la entrega → `git log -1 -- src/baxy_mind/effect_intent.py`
  da `20dab7ed` y el SHA del fichero es la base declarada por 1024, `3bb83dc8…`.
- El backend de la decisión está aquí → `llama-server.exe` = `38a9d28e…`, coincide.

- El modelo decidido carga en este hardware con el perfil de producto → `/health` ok, 3 slots,
  4096 por slot, VRAM atribuible 3513 MiB por delta (5528 con servidor / 2015 sin él), RAM 708 MiB.

Descartadas:
- «El GGUF decidido estará en la máquina porque el manifiesto lo lista» → 93 GGUF locales revisados y
  ninguno era `3605803b…`. El nombre coincidía, el contenido no. Vivía en
  `D:/BAXYRuntime/experiments/models/…`, carpeta ausente aquí, y se restauró desde la revisión fijada.
- «Bootstrap registrará el runtime sin más» → falló con `runtime_lock_invalid` → `installed_missing`:
  el venv de la mente estaba desfasado respecto al `pylock` de los 192 commits. Faltaban
  `pywebrtc-audio 0.2.0+baxy.1` y `sherpa-onnx 1.13.4+baxy.2`.
- «El veto `nothing_to_clarify` es lo que impide preguntar el referente» → `read_request` devuelve
  `intents` vacío para los dos literales, así que ese veto no interviene. La causa es el reconocedor.
- «El ZIP privado quizá llegó a otra carpeta» → búsqueda recursiva por nombre exacto en C:/Users,
  D:, E:, F:, G: y J: para el ZIP y para `TRANSFER_MANIFEST.json`, cero resultados.
- «Los literales de la encuesta podrían salir de lo versionado» → `SURVEY_TAXONOMY846.json` sólo
  lleva case_id, categoría, estado y fecha; `SURVEY_REQUIREMENTS336.json` son 841 bytes de punteros.

## Comandos ejecutados y resultado
- `git merge --ff-only origin/Goal-c03` → `2bf3d4c5` → `ed305c38`, worktree limpio, `main` intacta.
- `dotnet build Baxy.slnx -c Release --nologo -v:minimal` → Compilación correcta, 0 advertencias,
  0 errores, 21.46 s. `baxy-core.dll` y `baxy-core.exe` junto a `Baxy.exe` iguales a los de `Baxy.Core`.
- `Get-FileHash` de los 4 GGUF de `D:/BAXYRuntime/assets/models` y de `llama-server.exe` → tabla en
  `OPUS5_DESTINO/DESTINO_INVENTARIO.json`.
- No ejecutado: suites dueñas, `test_source_quality.ps1` Fast y Full — omitidas por instrucción
  explícita del dueño. Omitidas, no verdes, no aprobadas.
- `curl` de la revisión fijada + `Get-FileHash` → 2 497 281 120 bytes y SHA `3605803b…` exactos.
- `scripts/bootstrap.ps1` → exit0, «BAXY arranca: los activos obligatorios y el runtime registrado
  son validos»; `mind_import_ok`; `wake_on_start: true`.
- `llama-server` con las banderas de `llm.py` → `model loaded`, `/health` = `{"status":"ok"}`,
  detenido después.
- No ejecutado: ninguna tanda de producto — sin registro de la encuesta no habría dónde escribir el
  resultado ni literales exactos con los que sellar.

## Problemas pendientes
- **Paquete privado ausente**, con el dueño. `C03_OPUS5_RELEVO_PRIVADO.zip`, SHA `95bc3f23…fd8c704`,
  en la réplica en `%LOCALAPPDATA%/BAXY/C03-opus5-transfer-20260911/`. Único bloqueo externo que
  queda. Bloquea `verification_status`, el sellado de paneles, las 11 causas de 1025 y el diff de 1024.
- **`_time_only_reminder_request` en `effect_intent.py:13842`** es una abstención de la ruta de
  efecto que el diagnóstico 1024 no analiza. Deuda real de revisión antes de integrar.
- **`assets.local.json` es configuración de esta máquina, no del repositorio.** Si se reinstala el
  runtime sin él, el descriptor volverá a resolver el Instruct AWQ por nombre.

## Diagnóstico añadido sin GPU
`KNOWLEDGE1025/DIAGNOSIS_REFERENTE_AUSENTE.md`. Sonda pura con el intérprete del runtime de la
mente: `_deictic_open_request('¿Cuál es su identidad secreta?')` y `('¿Quién es de verdad?')` dan
`False` con `read_request(...).intents` vacío. La ruta `llm.clarify_missing_referent` existe y está
sana; no se alcanza porque el reconocedor de `__main__.py:2818` sólo cubre aperturas. Reparación
propuesta y **no escrita**: ampliarlo a preguntas de tercera persona sin antecedente reutilizando la
misma ruta. No se integra sin controles, porque «su» es también tratamiento formal y una regla amplia
rompería «¿Cuál es su nombre?» dirigido a BAXY, en una categoría con 7 casos ya cubiertos.

## Siguiente acción recomendada
Al recibir el ZIP: verificarlo contra `TRANSFER_MANIFEST.json`, extraerlo en carpeta nueva y leer
`localappdata/BAXY/C03-knowledge1025-private/run/capture/events.jsonl` para cerrar los 11 veredictos
pendientes y fijar el texto verbatim de los 9 fallos ya juzgados en
`KNOWLEDGE1025/ADJUDICATION_STATUS.json`. El contador 126 no cambia por eso.
