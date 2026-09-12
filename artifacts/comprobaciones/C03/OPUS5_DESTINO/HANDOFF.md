# Handoff — C03 relevo en PC destino — 2026-09-12 — ed305c38

## Objetivo
Completar C03 «respuesta veraz de BAXY». Cierre: los 742 case_id de la encuesta adjudicados con
literal exacto ejecutado en el producto y dos variantes pertinentes por conducta; 11/11 filas C03.

## Estado
Hecho: destino actualizado a `ed305c38` por `merge --ff-only` (192 commits, worktree limpio, WIP
ajeno y `main` intactos); procesos de producto del arranque automático cerrados; runtime
inventariado y hasheado; Release compilado en destino; adjudicación 1025 cerrada en cobertura y
14/25 casos juzgados; propuesta 1024 revisada estáticamente.
En curso: nada en ejecución. Ningún proceso de producto activo, ninguna GPU en uso por BAXY.
Sin empezar: registro del runtime con el modelo decidido, medición de 1024, sellado de la siguiente
categoría. Los tres dependen del paquete privado.

## Decisiones tomadas
- **El crédito de 1025 es 3 y es definitivo.** Descripción de juegos tiene 2 de 3 variantes caídas y
  comparación ficcional 1 de 2: ninguna alcanza las 2 variantes en pie que exige un crédito, y
  KNOWLEDGE998 —única tanda anterior de la categoría con adjudicación versionada— sólo cubrió
  aritmética, conversiones, sustancia/mezcla y estilo humorístico. H0236/H0239/H0582 siguen open sea
  cual sea el veredicto de su literal. No reabrir sin una tanda nueva.
- **No registrar `D:/BAXYRuntime/assets/models/Qwen3-4B-Q4_K_M.gguf`.** Se llama igual que el
  candidato de `assets.manifest.json` pero su SHA es `7485fe6f…`, no el decidido `3605803b…`.
  Registrarlo sería el reemplazo silencioso prohibido.
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
- `scripts/register_mind_runtime.ps1` — para registrar el GGUF decidido en cuanto llegue.
- `artifacts/comprobaciones/C03/KNOWLEDGE1025/PLAN.md` — panel sellado; las 18 reservas de la
  categoría y sus condiciones están ahí, no reclasificar.

## Hipótesis
Confirmadas:
- Este PC nunca vio las tandas 1010–1027 → `%LOCALAPPDATA%/BAXY` tiene 1489 directorios, ninguno
  `C03-*-private`, evidencia más reciente 2026-09-06.
- La fuente de producto del destino es la de la entrega → `git log -1 -- src/baxy_mind/effect_intent.py`
  da `20dab7ed` y el SHA del fichero es la base declarada por 1024, `3bb83dc8…`.
- El backend de la decisión está aquí → `llama-server.exe` = `38a9d28e…`, coincide.

Descartadas:
- «El GGUF decidido estará en el PC porque el manifiesto lo lista» → los cuatro GGUF locales se
  hashearon y ninguno es `3605803b…`. El nombre coincidía, el contenido no.
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
- No ejecutado: ninguna tanda de producto — sin registro de la encuesta no habría dónde escribir el
  resultado, y sin el GGUF decidido el candidato no sería el de la decisión.

## Problemas pendientes
- **Paquete privado ausente**, con el dueño. `C03_OPUS5_RELEVO_PRIVADO.zip`, SHA `95bc3f23…fd8c704`.
  Bloquea `verification_status`, el sellado de paneles, las 11 causas de 1025 y el diff de 1024.
- **Pesos decididos ausentes**, con el dueño. Qwen3-4B-Instruct-2507 Q4_K_M, SHA `3605803b…`.
  Bloquea cualquier tanda con el candidato correcto.
- **`_time_only_reminder_request` en `effect_intent.py:13842`** es una abstención de la ruta de
  efecto que el diagnóstico 1024 no analiza. Deuda real de revisión antes de integrar.

## Siguiente acción recomendada
Al recibir el ZIP: verificarlo contra `TRANSFER_MANIFEST.json`, extraerlo en carpeta nueva y leer
`localappdata/BAXY/C03-knowledge1025-private/run/capture/events.jsonl` para cerrar los 11 veredictos
pendientes y fijar el texto verbatim de los 9 fallos ya juzgados en
`KNOWLEDGE1025/ADJUDICATION_STATUS.json`. El contador 126 no cambia por eso.
