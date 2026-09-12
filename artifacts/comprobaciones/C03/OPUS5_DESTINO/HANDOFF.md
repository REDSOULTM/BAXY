# Handoff — C03 en la máquina original — 2026-09-12 — tras SYSTEM1028

## Objetivo
Completar C03 «respuesta veraz de BAXY». Cierre: los 742 case_id adjudicados con literal exacto
ejecutado en el producto y dos variantes pertinentes por conducta; 11/11 filas C03.

## Papeles de las máquinas
REDPC (`C:`) es el BAXY original. El portátil sólo replicó el repositorio y su raíz en `D:` era porque
su `C:` estaba lleno. El tramo del 6 al 12 de septiembre corrió en la réplica.

## Estado
**130/742 cubiertos, 612 abiertos, 0 no aplican. Registro `af5ccd83…`.**
Hecho: paquete privado verificado (95/95) y registro restaurado; modelo decidido restaurado, registrado
y con carga verificada; 1025 adjudicada por completo sin repetirla; SYSTEM1028 sellada, ejecutada y
adjudicada con +4; tres causas transversales demostradas con su primera transformación incorrecta.
En curso: nada en ejecución, ningún proceso de producto activo.
Sin empezar: reparación de las tres causas de 1028; ampliación del referente ausente; integración de
1024.

## Decisiones tomadas
- **Modelo:** el decidido vive en `D:/BAXYRuntime/experiments/models/qwen3-4b-instruct-2507-a06e946b/`.
  `assets/models/Qwen3-4B-Q4_K_M.gguf` **no** es él: es el modelo activo anterior, Instruct AWQ
  `7485fe6f…`. El override oficial `%LOCALAPPDATA%/BAXYRuntime/assets.local.json` declara modelo y wake;
  sin la entrada de wake, bootstrap registra con `-NoWake`. Copia previa en `mind-runtime-v1.json.pre-c03-relay.bak`.
- **La comprobación heredada «Core efectivo == Core publicado» es correcta.** El producto sustituye el
  core junto a `Baxy.exe` por el publicado AOT en su primer arranque. Mi debilitamiento fue un error y
  está revertido. Consecuencia práctica: arranca el producto una vez **antes** de fijar `binary_pins`,
  o la medición se detendrá con `sealed_input_or_source_changed`.
- **El crédito de 1025 es 3 y es definitivo.** No reabrir sin una tanda nueva.
- **memory_total en 1028 usó el par heredado de 1022** (dev-03/dev-04), declarado en el PLAN sellado
  antes de ejecutar. La regla lo permite.
- **No se propone infraestructura de vídeo:** resolución, Hz y número de monitores son 4 casos, por
  debajo del mínimo de 10.

## Archivos tocados
- `artifacts/comprobaciones/C03/KNOWLEDGE1025/{ROOT_ADJUDICATION,REGISTRY_UPDATE}.json`, `DIAGNOSIS_REFERENTE_AUSENTE.md`
- `artifacts/comprobaciones/C03/SYSTEM1028/{PLAN.md,SEAL.json,PREREG,PROCESS,RESOURCES,EXIT,ROOT_ADJUDICATION,REGISTRY_UPDATE}` y `DIAGNOSIS.md`
- `artifacts/comprobaciones/C03/{CHECKPOINT.md,SURVEY_COVERAGE_CURRENT.json,RELEVO_ACTIVO.json,ESTADO_PARA_DUENO_2026-09-12.md}`
- `artifacts/comprobaciones/C03/AGENDA1024/ROOT_REVIEW_DESTINO.md`
- Ningún fichero de `src/`, `tests/` ni `scripts/` modificado en toda la sesión.

## Material fuera de Git que la siguiente sesión necesita
- Registro: `%LOCALAPPDATA%/BAXY/C03-survey-requirements336-private/requirements.jsonl`, `af5ccd83…`,
  con respaldos `.before-1025-adjudication.bak` y `.before-1028.bak`.
- Panel y runner de 1028: `%LOCALAPPDATA%/BAXY/C03-system1028-proposal/` (SEAL `eedb2688…`,
  runner `37bcfadd…`). El runner es la plantilla adaptada a esta máquina: cambia identidad de tanda,
  IDs, contadores, `BASELINE_HEAD`, seals, y cuenta pins por manifiesto en vez de fijar 584/18.
- Candidato: `%LOCALAPPDATA%/BAXY/C03-system1028-private/CANDIDATE_AUTHORIZED.json`, `bb336680…`.
- Paquete extraído: `%LOCALAPPDATA%/BAXY/C03-opus5-relevo-destino/` (histórico, sólo lectura).

## Hipótesis
Confirmadas:
- El compositor de prosa es fiel al payload en los tres tipos de fallo de 1028 → situaciones y payloads
  reales en `compose-audit.jsonl`, citados en `SYSTEM1028/DIAGNOSIS.md`.
- La ruta `llm.clarify_missing_referent` nunca se alcanza → `decision_path` de los 25 turnos de 1025 sin
  un solo `deictic_referent_clarification`, y sonda pura sobre `_deictic_open_request`.
- El scope `summary` no incluye GPU pero sí batería → payload de dev-08.

Descartadas:
- «El veto `nothing_to_clarify` impide preguntar el referente» → `read_request` devuelve intents vacío.
- «El GGUF decidido no está y hay que pedirlo» → estaba su procedencia atestada versionada; se restauró.
- «La categoría de sistema se cierra en una tanda» → 5 de sus 19 abiertos no tienen operación.

## Comandos ejecutados y resultado
- `runner.py prepare` → PREPARATION `b9c16014…`, 621 pins, 11941 MiB libres.
- `runner.py run` → exit 0, 31 terminales, 31 controles, 0 violaciones, 154.797 s, GPU 3494.93 MiB,
  RAM 2587.37 MiB.
- `main.compile_if_needed(force=True)` + `dotnet build-server shutdown` → 0 y 0, fingerprint coincidente.
- `bootstrap.ps1` → válido; `llama-server` con las banderas de `llm.py` → `/health` ok, 3513 MiB de VRAM
  atribuibles.
- No ejecutado: suites dueñas, Fast y Full — omitidas por instrucción del dueño, no verdes.

## Problemas pendientes
- Tres causas de `SYSTEM1028/DIAGNOSIS.md`, sin reparar. Es el trabajo de mayor rendimiento.
- `effect_intent.py:13842`: segundo uso de `_time_only_reminder_request` como abstención de la ruta de
  efecto que el diagnóstico 1024 no analiza. Decidirlo antes de integrar 1024.
- `assets.local.json` es configuración de esta máquina, no del repositorio: si se reinstala el runtime
  sin él, el descriptor volverá a resolver el Instruct AWQ por nombre.

## Siguiente acción recomendada
Sellar la reparación dirigida de la causa A de `SYSTEM1028/DIAGNOSIS.md` —lectura del catálogo
clasificada `out_of_catalog` en la decisión— con su subconjunto exacto y con H0442, H0539, H0655,
H0422, H0037 y H0114 como controles de no regresión. Empieza leyendo `__main__.py:6638-6655` y de dónde
sale `catalog_unavailable_decision`.
