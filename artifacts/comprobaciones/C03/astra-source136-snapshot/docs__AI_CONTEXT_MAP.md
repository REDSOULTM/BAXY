# Mapa de contexto para agentes

Enrutador. No explica BAXY: te dice **dónde mirar** para no reconstruir el árbol en
cada sesión. Qué es BAXY lo dice `documentacion/00_IDENTIDAD.md`; qué hay que hacer lo
dice tu goal.

Ámbito por defecto de cualquier búsqueda: **`src tests scripts main.py`**.

---

## Si quiero tocar X, ¿dónde miro?

| Quiero… | Empieza por | Y arrastra |
|---|---|---|
| Añadir o cambiar una **operación** | `src/Baxy.Kernel/Operations/ProductCatalog.cs` | handler en `src/Baxy.Core/Operations/`, provider en `src/Baxy.Providers.Windows/<área>/`, alias en `src/baxy_mind/data/catalog_operation_aliases.v1.json`, pruebas en `tests/Baxy.Kernel.Tests` y `tests/Baxy.Integration.Tests` |
| Cambiar **cómo se entiende** una petición | `src/baxy_mind/router.py`, `family_classifier.py`, `semantic_family_arbiter.py` | corpus en `src/baxy_mind/data/`, `tools/router_bank_sources.py`, pruebas `tests/test_catalog_*`, `tests/test_*router*` |
| Cambiar el **plan** de una misión compuesta | `src/baxy_mind/planner.py`, `src/Baxy.Kernel/Planning/` | `src/Baxy.Kernel/Mission/MissionEngine.cs`, `tests/Baxy.Integration.Tests` |
| Cambiar **autorización, riesgo o confirmación** | `src/Baxy.Kernel/Policy/`, `src/Baxy.Kernel/Mission/` | journal en `src/Baxy.Kernel/Journal/`, `tests/Baxy.Kernel.Tests` |
| Cambiar el **protocolo** mente↔kernel | `src/Baxy.Contracts/ProtocolContracts.cs` | `src/baxy_mind/protocol.py` — **los dos extremos, siempre**; `tests/Baxy.Contracts.Tests` |
| Cambiar un **efecto real** sobre Windows | `src/Baxy.Providers.Windows/<Audio\|Applications\|Filesystem\|Capture\|Network\|Windows\|…>/` | `tests/Baxy.Providers.Windows.Tests` |
| Cambiar **lo que lee la persona** | Nunca con texto fijo en la App. Ver invariante 5: lo formula el modelo, en `src/baxy_mind/` | `src/Baxy.App/` sólo transporta |
| Cambiar la **GUI** | `src/Baxy.FieldUi/src/` | `src/Baxy.FieldUi/dist/` es un sello histórico (ADR-0008): **no se regenera de paso** |
| Cambiar **voz / wake / STT / TTS** | `src/baxy_mind/voice.py`; AEC en `speex_aec.py`, dispositivos en `voice_aec.py`, salida en `voice_output.py`/`piper_tts.py`; `scripts/setup_mind_voice.ps1` | `documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/07_LATENCIA_END_TO_END.md` |
| Cambiar **instalación o empaquetado** | `src/Baxy.Setup/` | `scripts/build_product.ps1`, `scripts/package_product.ps1`, `tests/Baxy.Setup.Tests` |
| Cambiar la **evidencia de un turno** | `src/baxy_mind/turn_evidence*.py` | `tests/data/turn_evidence_public_holdout.v1.jsonl` (3 MB — nunca entero) |

## Si falla Y, ¿qué es relevante?

| Síntoma | Mira |
|---|---|
| La petición va a la operación equivocada | `src/baxy_mind/router.py`, `semantic_family_arbiter.py`, alias del catálogo; corridas en `artifacts/development/goal03*` |
| «Dice que lo hizo» y no pasó | Handler en `src/Baxy.Core/Operations/` + postlectura del provider. Invariantes 2 y 3 |
| Confirmación aceptada para otra cosa | `src/Baxy.Kernel/Mission/InMemoryConfirmationAuthority.cs`. Invariante 4 |
| Frase fija en pantalla | `grep` de `"[A-ZÁÉÍÓÚ][^"]{15,}"` en `src/Baxy.App` y `src/Baxy.FieldUi/src`. Invariante 5 |
| Silencio > 1 s antes de la primera señal | `src/baxy_mind/time_budget.py`, `llm_transport.py`, y `07_LATENCIA_END_TO_END.md` |
| La compuerta se pone roja tras un clon limpio | `.gitattributes` (sellos byte a byte), `scripts/test_gate14_clean_environment.ps1` |
| Falla el arranque del proceso Core | `src/Baxy.App/CoreProcessClient.cs`, `src/baxy_mind/process_lifecycle.py` |

## Comandos por clase de validación

```powershell
py main.py                                          # ejecutar en desarrollo
py -m pytest tests/test_X.py -q                     # nivel 1, Python
dotnet test tests/Baxy.Kernel.Tests -c Release --nologo   # nivel 1, .NET
.\scripts\test_source_quality.ps1                   # nivel 2 (Fast)
.\scripts\test_source_quality.ps1 -Mode Full        # nivel 3 (entrega)
```

Fast = fuente PowerShell + ruff + compileall + eslint + tsc(app,node) + dotnet format
+ build Release. Full = Fast + suites .NET + pytest completo.
Nivel 4 (publish, hardware, ciclo instalado) **no** está dentro de Full.

## Qué directorios son ruido por defecto

| Ruta | Ficheros | Regla |
|---|---|---|
| `artifacts/` | 2.938 | Evidencia fechada de una corrida concreta. Se abre con ruta exacta, nunca se recorre |
| `artifacts/_trazas_locales/` | 47 | Trazas crudas de corridas que ningún documento cita. Ignorada por Git; no es evidencia citable |
| `biblioteca/` | 1.352 | Las cuatro escrituras anteriores. Entrada única: `biblioteca/00_INDICE.md`. Ver skill `evidencia-baxy` |
| `experiments/` | 879 | Investigación. No entra al runtime por existir |
| `documentacion/1x_*_CORTE_*.md`, `2x_*.md` | — | Cortes históricos: evidencia, no instrucción |
| `contexto/` | 41 | Snapshot del intento anterior. Los ADR (`04_arquitectura/ADR/`) siguen vigentes; el resto está fechado |
| `bin/`, `obj/`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/` | — | Generados. Nunca se editan ni se leen |

`src/Baxy.FieldUi/dist/` está versionado a propósito: artefacto visual sellado por
ADR-0008.

## Ficheros que no se leen enteros

60 ficheros versionados pasan de 1 MB; 706 pasan de 100 KB. Los peores:

```
tests/data/historical_messages.jsonl                    69 MB
artifacts/corpus_cutoff/source_manifest.json            16 MB
tests/data/historical_message_mapping.jsonl             16 MB
artifacts/development/r207_cross_encoder_pairs.jsonl    11 MB
artifacts/research/functiongemma_training_corpus.v3.jsonl  11 MB
tests/data/historical_missions.jsonl                     5 MB
tests/data/turn_evidence_public_holdout.v1.jsonl         3 MB
```

`read_file` por rango, `grep` por clave, y `Get-Content -TotalCount 3` para ver la
forma de un JSONL. Nunca el fichero entero.
Comprobar tamaño antes de abrir: `git ls-tree -r -l HEAD -- ruta`.

## Dónde vive el conocimiento profundo

Todo esto es **carga bajo demanda**: no lo leas salvo que la tarea lo pida.

| Pregunta | Documento |
|---|---|
| ¿Quién es dueño de una conducta? | `documentacion/01_ARQUITECTURA/GUIA_AGENTES_IA/01_MODELO_MENTAL_Y_OWNERSHIP.md` |
| ¿Cómo compilo, ejecuto o entrego? | `…/GUIA_AGENTES_IA/02_CONSTRUCCION_EJECUCION_Y_ENTREGA.md` |
| ¿Cómo viajan datos, voz y confirmaciones? | `…/GUIA_AGENTES_IA/03_CONTRATOS_FLUJOS_Y_DATOS.md` |
| ¿Qué archivos toco para añadir una capacidad? | `…/GUIA_AGENTES_IA/04_RECETAS_DE_CAMBIO.md` |
| Matriz de pruebas y checklist de seguridad | `…/GUIA_AGENTES_IA/05_VALIDACION_SEGURIDAD_Y_HANDOFF.md` |
| ¿Qué hace cada script y qué estado muta? | `…/GUIA_AGENTES_IA/06_INVENTARIO_DE_SCRIPTS_Y_GATES.md` |
| ¿Dónde se gasta la latencia de un turno? | `…/GUIA_AGENTES_IA/07_LATENCIA_END_TO_END.md` |
| Baseline vigente, deuda, hotspots | `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md` |
| Topología del producto activo | `documentacion/01_ARQUITECTURA/MAPA_DEL_SISTEMA.md` |
| Piezas sustituibles y qué medición decide | `documentacion/03_COSTURAS.md` |
| Fronteras aceptadas (ADR) | `contexto/04_arquitectura/ADR/` |
| Qué se midió y **se rechazó** | `documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md` + biblioteca |
| Lo que se ve y no se persigue | `documentacion/APLAZADOS.md` |

## Reglas de mantenimiento de este fichero

Rutas y responsabilidades, sí. Números que cambian cada semana (conteos de pruebas,
último commit validado, deuda), **no** — ésos viven en `REGISTRO_DE_MANTENIBILIDAD.md`.
Si mueves un ownership, actualiza aquí la fila en el mismo commit.
