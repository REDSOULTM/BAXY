# Cierre posterior a wake v17 — 2026-08-11

Este runbook no autoriza abrir R2 ni modificar el árbol wake antes del recibo
físico combinado. Su única finalidad es recuperar la secuencia exacta después de
una compactación de contexto.

## Condición de entrada

Debe existir
`artifacts/holdout/baxy_wake_v25a_physical_v17_combined_receipt_v2.json` y el
certificador externo debe probar simultáneamente 48/48 positivos, 0/96 falsas
activaciones, p50 <= 1,5 s, p95 <= 2,0 s, identidades exactas, cero efectos y
`promotionEligible=true`.

Hasta entonces permanecen congelados `experiments/voice_latency`, `scripts` y
`src/baxy_mind`. La especificación prerregistrada de los dos cambios posteriores
es `artifacts/development/post_wake_repairs_preregistered_20260811.json`.

## 1. Reparar el contrato del perfil CPU

- En `scripts/measure_mind_budget.py`, conservar `gpu.llm_http=19.0` y cambiar
  sólo `cpu_fallback.llm_http` a `120.0`, igual que el runtime productivo cuando
  `BAXY_MIND_NGL=0`.
- Los deadlines exteriores de `turn.decide`, `arguments` y `narrate` siguen en
  22/20/20 s. No se rebaja ningún presupuesto de producto.
- En `tests/test_mind_budget_gate.py`, comprobar explícitamente 19 s para GPU y
  120 s para CPU, además de los deadlines exteriores compartidos.

## 2. Reparar la equivalencia de cierres sociales de Mind

- Ampliar sólo `_TRAILING_SOCIAL_CLOSURE` en
  `src/baxy_mind/effect_intent.py` para las familias terminales equivalentes
  concluye/finaliza/termina/completa y conclude/complete/end/finish.
- Mantener obligatorios el separador coma o punto y coma, el anclaje al final y
  la protección del contenido literal sin separador.
- Añadir a `tests/test_catalog_operation_aliases.py` variantes metamórficas de
  desarrollo para cada alias autenticado. No puntuar ni usar R1 para promover y
  no generar todavía R2 durante la implementación.

## 3. Regresiones de desarrollo

```powershell
$python = (Get-Content -Raw "$env:LOCALAPPDATA\BAXYRuntime\mind-runtime-v1.json" | ConvertFrom-Json).python
& $python -X utf8 -m pytest `
  tests/test_mind_budget_gate.py `
  tests/test_catalog_operation_aliases.py `
  tests/test_effect_intent.py -q
& .\scripts\test_source_quality.ps1 -Mode Fast
```

Si falla algo, se corrige antes de abrir cualquier evidencia ciega.

## 4. Repetir el presupuesto completo Qwen3

```powershell
& $python -X utf8 scripts/measure_mind_budget.py `
  --output artifacts/product/mind_budget_gate_qwen_current_tree_post_wake_20260811.json
```

La corrida debe ejecutar ambos perfiles completos. GPU conserva el techo de
4 GiB VRAM; CPU conserva <= 8 GiB RAM y su techo publicado. Un caso correcto
aislado no sustituye esta repetición.

## 5. Certificar las reparaciones y ejecutar las misiones físicas

El certificador rechaza cualquier presupuesto que no cierre 45/45 solicitudes
en ambos perfiles, conserva `gpu.llm_http=19` y `cpu_fallback.llm_http=120`,
repite las regresiones focalizadas y Fast, y liga todo al recibo wake exacto:

```powershell
$qualityPython = "$env:LOCALAPPDATA\BAXYQuality\source-quality-v1\Scripts\python.exe"
& $python -X utf8 experiments/mission_validation/certify_post_wake_repairs_v1.py `
  --quality-python $qualityPython
```

Sólo si crea un recibo `passed`, ejecutar primero las misiones físicas para no
perder la ventana de audio. Cada misión usa su propio `BAXY_DATA_DIR` temporal;
la única mutación permitida es `note.create`, confirmada contra su invocación
exacta. Todos los pasos deben cerrar verificados y el namespace se elimina al
detener Core y Mind.

```powershell
& $python -X utf8 experiments/mission_validation/run_physical_dependent_missions_v1.py text

& $python -X utf8 experiments/mission_validation/run_physical_dependent_missions_v1.py voice `
  --physical-output `
  --cascade-manifest D:\BAXYRuntime\experiments\wakeword\baxy_wake_routed_cascade_v25a_endpoint_development\baxy-wake-cascade-v2.json `
  --raw-capture-helper D:\BAXYRuntime\experiments\wakeword\raw-wasapi-capture-helper-v2\bin\Release\net9.0\RawWasapiCapture.exe `
  --input-device 6 `
  --output-device 9 `
  --gain 0.65 `
  --maximum-capture-attempts 6

& $python -X utf8 experiments/mission_validation/run_physical_dependent_missions_v1.py combine
```

El cierre válido es texto 3/3, voz 3/3, 20/20 pasos verificados, orden y
dependencias exactas, cero efectos ambiguos o externos, cero procesos propios y
cero audio o texto de transcripción retenidos. La implementación y sus hashes
están ligados por
`artifacts/development/physical_dependent_missions_program_supplement_20260811.json`.

## 6. Generar y abrir current-tree R2 una sola vez

Antes de empezar, deben seguir ausentes sus seis salidas prerregistradas:

- `artifacts/holdout/catalog_surface_current_tree_r2.jsonl`
- `artifacts/holdout/catalog_surface_current_tree_r2.preregistration.json`
- `artifacts/holdout/catalog_surface_current_tree_r2_mind.json`
- `artifacts/holdout/catalog_surface_current_tree_r2_mind.raw.jsonl`
- `artifacts/holdout/catalog_surface_current_tree_r2_memory.trx`
- `artifacts/holdout/catalog_surface_current_tree_r2_product.json`

La secuencia es:

```powershell
& $python -X utf8 experiments/mind_router_spike/build_catalog_surface_current_tree_r2.py
& $python -X utf8 experiments/mind_router_spike/probe_catalog_surface_current_tree_r2.py

$dotnetRoot = Join-Path $env:USERPROFILE '.dotnet'
$dotnet = Join-Path $dotnetRoot 'dotnet.exe'
$env:DOTNET_ROOT = $dotnetRoot
$env:DOTNET_ROOT_X64 = $dotnetRoot
$env:PATH = "$dotnetRoot;$env:PATH"
& $dotnet test tests/Baxy.Integration.Tests/Baxy.Integration.Tests.csproj `
  -c Release --no-build `
  --filter 'FullyQualifiedName~RoutesBlindCurrentTreeR2MemoryRequests' `
  --results-directory artifacts/holdout `
  --logger 'trx;LogFileName=catalog_surface_current_tree_r2_memory.trx'

& $python -X utf8 experiments/mind_router_spike/analyze_catalog_surface_current_tree_r2.py
```

R2 debe cerrar 169/169 y publicar por separado recuperación, decisión y vetos.
Su resultado se conserva aunque falle; nunca se usa para ajustar la misma
reparación.

## 7. Generar y abrir el corte B current-tree una sola vez

Sólo después de cerrar R2, deben seguir ausentes las seis salidas declaradas
por `build_generalization_product_current_tree_r22.py`. La construcción en
memoria ya probó 700 superficies únicas, entidades nuevas, cero solapamiento
normalizado con R2–R21 y 100 órdenes de composición ausentes de esos cortes.
No se ha generado ni abierto el holdout.

```powershell
& $python -X utf8 experiments/mind_router_spike/build_generalization_product_current_tree_r22.py
& $python -X utf8 experiments/mind_router_spike/probe_generalization_product_current_tree_r22.py

& $dotnet test tests/Baxy.Integration.Tests/Baxy.Integration.Tests.csproj `
  -c Release --no-build `
  --filter 'FullyQualifiedName~RoutesBlindCurrentTreeR22GeneralizationMemoryStatusRequests' `
  --results-directory artifacts/holdout `
  --logger 'trx;LogFileName=generalization_product_current_tree_r22_memory.trx'

& $python -X utf8 experiments/mind_router_spike/analyze_generalization_product_current_tree_r22.py
```

El corte debe alcanzar como mínimo 99 %, cero autoridad o efectos inseguros y
publicar recuperación, decisión y vetos por separado. Su resultado se conserva
aunque falle y nunca se reutiliza para ajustar el mismo árbol.

## 8. Generar y abrir el corte C current-tree una sola vez

El programa R4 conserva únicamente notas dentro de un `BAXY_DATA_DIR` temporal
y lecturas de estado. Sus seis casos es/en/spanglish suman 31 pasos, tienen
dependencias exactas y sólo permiten confirmar `note.create`. Deben seguir
ausentes el prerregistro y el reporte oficial antes de ejecutar:

```powershell
& $python -X utf8 experiments/mind_router_spike/build_compound_execution_current_tree_r4.py
& $python -X utf8 experiments/mind_router_spike/run_compound_execution_current_tree_r4.py
```

El único cierre válido es 6/6 misiones, 31/31 pasos completados y verificados,
cero efectos ambiguos, cero archivos persistentes y limpieza del namespace
temporal. Después se ejecutan, como evidencia física separada, las tres
misiones prerregistradas por texto y por voz; esa evidencia no reemplaza este
oráculo ciego.

## 9. Prerregistrar y abrir el corte D oficial una sola vez

Este es el último corte ciego y su uso es irreversible en esta máquina. Sólo se
prerregistra después de que wake v17, las dos reparaciones, Fast, el presupuesto
Qwen GPU/CPU y los cortes A-C hayan cerrado el árbol final. El prerregistro
congela la identidad del runtime, evaluador, instrumentación en memoria, lector
one-shot, catálogo, mapa, sello, umbrales y todas las fuentes de política. No
abre miembros del ZIP oficial.

Antes de evaluar deben seguir ausentes tanto el prerregistro como el reporte, y
la infraestructura focal debe conservar 15/15 pruebas verdes:

```powershell
$archive = 'D:\BAXYRuntime\datasets\mtop-v1\source\mtop.zip'
& $python -X utf8 -m pytest `
  tests/test_mtop_current_tree_cut_d.py `
  tests/test_mtop_turn_evidence.py -q

& $python -X utf8 experiments/mind_router_spike/run_mtop_current_tree_cut_d.py `
  preregister --archive $archive

& $python -X utf8 experiments/mind_router_spike/run_mtop_current_tree_cut_d.py `
  evaluate --archive $archive
```

`evaluate` comprueba de nuevo la identidad del runtime antes de crear el claim.
Después el claim `CREATE_NEW` se crea antes de decodificar: un fallo o cierre
consume la única oportunidad y nunca autoriza reintento. El reporte persiste
sólo agregados, prohíbe texto e identidades test y separa recuperación,
retrieval, decisión, primer veto y presentación. Sólo aprueba con exactitud
>=99 %, abstención/clarificación útil y segura al 100 %, auditoría completa,
cero efectos no solicitados, cero éxitos no verificados, cero respuestas fijas y
cero recuperaciones.

## 10. Cierre de esta etapa

Actualizar `documentacion/00_META_VIGENTE.md`,
`documentacion/01_ARQUITECTURA/REGISTRO_DE_MANTENIBILIDAD.md` y
`artifacts/fixes/integral_review_ledger_20260811.json`; después repetir la
compuerta Full. Esto cierra wake, CPU y los cortes current-tree A-D si todos sus
recibos pasan. No completa por sí solo el goal: aún quedan STT humano fresco,
la prueba física final con el usuario despierto y el ciclo limpio en una cuenta
o VM desechable.

La preparación real de esos cortes está inventariada, sin abrir datos, en
`artifacts/development/current_tree_cuts_readiness_audit_20260811.json`: A-D
tienen programas completos sin abrir. En D siguen ausentes el prerregistro, el
reporte y el claim; esa preparación no se puede declarar aprobada por evidencia
histórica.

Las misiones físicas dependientes por texto y voz tienen además un contrato
previo en
`artifacts/development/physical_dependent_missions_preregistration_20260811.json`.
Fija tres misiones es/en/spanglish, 10 pasos por modalidad, datos aislados,
confirmación ligada y cero efectos externos. Sus **3/3** pruebas estructurales
pasaron. Esta evidencia no sustituye el corte C ciego.
