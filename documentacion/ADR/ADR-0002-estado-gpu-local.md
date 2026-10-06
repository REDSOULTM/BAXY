# ADR-0002 — Estado local de GPU mediante DXGI y PDH

- Estado: **aceptado**.
- Fecha: 2026-07-15.
- Ámbito: identificación y snapshot de uso GPU para la operación read-only
  `system.status` en Windows.
- Evidencia ejecutable: `tests/data/gpu_status_corpus_oracle.json`, suites de
  Providers/Integración, `scripts/test_gpu_status.ps1` y
  `artifacts/product/gpu_status_gate.json`.
- Corte de referencia: `../../../documentacion/18_OCTAVO_CORTE_GPU_LOCAL.md`.

## Contexto

El corpus congelado contiene peticiones standalone para identificar GPU/VRAM y
consultar su uso, además de frases que nombran `nvidia-smi`. El producto necesita
responder localmente sin convertir una preferencia histórica de herramienta en
una dependencia, sin iniciar procesos auxiliares y sin mezclar la nueva sonda
con el resumen genérico ya estabilizado por el quinto corte.

Windows ofrece identidad/capacidades por DXGI y contadores puntuales por PDH.
Los contadores pueden faltar para un adaptador o para todo el host, cambiar
durante la lectura o devolver metadata inválida. Por tanto, el contrato necesita
representar evidencia parcial de manera explícita y conservar la identidad aun
cuando el uso no esté disponible.

## Alternativas consideradas

| Alternativa | Decisión |
|---|---|
| Ejecutar `nvidia-smi` | Descartada: dependencia vendor-specific, subprocess y afirmación de herramienta que no generaliza a Intel/AMD |
| WMI/CIM para identidad y uso | Descartada como ruta principal: no ofrece un contrato uniforme y puntual de uso por adaptador para este corte |
| API de fabricante por GPU | Pospuesta: amplía toolchains, licencias, despliegue y matriz de hardware sin ser necesaria para el resultado congelado |
| DXGI para identidad + PDH para uso | **Aceptada**: APIs locales de Windows, neutral al fabricante y compatibles con el core NativeAOT |
| Incluir GPU en `summary` | Descartada: rompería forma/costo/semántica del summary legado y haría la nueva sonda implícita |

## Decisión

- Mantener una sola operación pública `system.status` y añadir los scopes
  `gpu_identity` y `gpu_usage`; el catálogo queda en 21 operaciones totales y
  20 interactivas.
- Enumerar identidad y capacidades con DXGI; medir uso puntual y memoria usada
  con PDH; no crear subprocess, red ni telemetría.
- Tratar `nvidia-smi` únicamente como alias de lenguaje natural para
  `gpu_usage`; nunca afirmar que se ejecutó.
- Mantener `summary` completamente aislado en el provider legado. Identity no
  abre contadores de uso y usage no se convierte en monitoreo continuo.
- Conservar orden y multiplicidad de adaptadores. El índice interno es
  cero-based y la proyección visible uno-based.
- Publicar los tres campos de uso juntos o ninguno. Representar un adaptador no
  medido mediante `unsupported` indexado cuando existen otras mediciones, y la
  ausencia global de evidencia mediante un único fallo global.
- Sanear la frontera pública: no publicar LUID, PID ni metadata de correlación;
  validar nombres, Unicode, rangos, capacidades, overflow y consistencia entre
  adapters/failures antes de responder.
- Usar un contexto JSON separado para el resultado GPU y mantener explícita la
  serialización compatible con NativeAOT.

## Consecuencias

- BAXY puede identificar adaptadores y presentar uso parcial de forma honesta en
  equipos multi-GPU sin depender de un fabricante.
- Dos adaptadores con el mismo nombre siguen siendo elementos distintos y se
  desambiguan por ordinal visible.
- Un fallo PDH no borra identidad válida ni se convierte en uso cero; el usuario
  recibe el alcance exacto de lo que no pudo medirse.
- El snapshot no atribuye actividad a BAXY ni a procesos y no demuestra
  causalidad.
- Las APIs nativas y buffers PDH aumentan la superficie de validación; sus
  límites, metadata y cambios de tamaño deben permanecer cubiertos por tests.

## Evidencia y límites

El oráculo congela 77 casos: 7 de identidad, 19 de uso, 17 composiciones y 34
negativos duros. Release aprobó 1.209/1.209 pruebas .NET y 74/74 Python. Una
ejecución física managed observó tres adaptadores, dos medidos y uno no medido
con fallo indexado, y terminó con exit 0.

Se publicó un core NativeAOT de 7.376.384 bytes y SHA-256
`17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`,
y `scripts/test_gpu_status.ps1` lo convirtió en una compuerta reproducible.
Corroboró hello 21, identity/usage verificados, tres adaptadores, dos medidos,
uno no disponible, un `unsupported` indexado, cero fallos globales,
correlaciones, warmup `malformed_json`, stderr vacío y exit 0. El resumen
sanitizado `artifacts/product/gpu_status_gate.json` usa schema
`baxy-gpu-status-gate-v1` y estado `passed`. La compuerta no acredita
temperatura, procesos, monitoreo continuo, hardware exhaustivo, un equipo de
4 GB, GUI, instalación limpia ni firma.

## Fallback y criterio de reapertura

Si PDH no ofrece evidencia válida, el fallback es conservar identidad DXGI y
declarar uso no disponible; no ejecutar silenciosamente una herramienta de
fabricante. Reabrir esta decisión si una versión objetivo de Windows elimina o
degrada los contadores, si la matriz física muestra errores materiales de
correlación, o si una API local neutral al fabricante ofrece mejor precisión y
menor superficie sin romper NativeAOT ni privacidad.
