# Octavo corte productivo: estado local de GPU

Estado del corte: implementado y verificado en los commits `3037445`,
`e33267d`, `cf44b89` y `18061e0`. Amplía la operación read-only
`system.status` con identificación y uso puntual de GPU mediante APIs locales de
Windows. No crea otra operación, no ejecuta herramientas de fabricantes y no
añade GPU al resumen genérico legado.

Este corte reduce B-004 y aporta evidencia acotada a B-006, pero no cierra
ningún Must ni los bloqueantes B-004/B-005/B-006. El progreso permanece en 5/15
Must (33,3 %): siguen pendientes conversación/composición general, el resto del
ledger, el instalador, Windows limpio y los gates físicos restantes.

## Alcance exacto

El catálogo conserva 21 operaciones totales y el handshake de la GUI conserva
20 capacidades interactivas; `app.status` sigue reservado a salud interna. Los
nuevos scopes públicos de `system.status` son:

| Scope | Resultado | No recopila |
|---|---|---|
| `gpu_identity` | Adaptadores en orden de snapshot, nombre, IDs de vendor/device, VRAM, RAM dedicada del sistema y límite de RAM compartida | Uso, procesos, temperatura |
| `gpu_usage` | La misma identidad y, por adaptador medido, porcentaje de uso, memoria gráfica dedicada usada y RAM compartida usada | Procesos, temperatura, energía, ventilador, clocks, monitoreo continuo |

`gpu_identity` no abre contadores de uso. `gpu_usage` es una fotografía puntual,
no una tarea persistente. El scope `summary` continúa delegado al provider
legado y conserva exactamente su forma anterior: no sondea ni incluye GPU. El
quinto corte y su oráculo 113/113 permanecen intactos.

Las frases históricas que nombran `nvidia-smi` son un alias natural acotado del
resultado `gpu_usage`. BAXY no lanza ese ejecutable, no abre un subprocess y no
afirma haber usado esa herramienta. La implementación es neutral al fabricante.

## Oráculo histórico congelado

`tests/data/gpu_status_corpus_oracle.json` define
`baxy.system-status.gpu-local.v1` y se liga al corpus consolidado
`tests/data/historical_messages.jsonl`. El archivo del oráculo tiene SHA-256
`01b0254a952dbb50e194747a7ac96117d1263fb9da6f1f2e58bf680762167e5f`.

| Grupo | IDs | Contrato |
|---|---:|---|
| identidad GPU | 7 | enrutar a `system.status`/`gpu_identity` |
| uso GPU | 19 | enrutar a `system.status`/`gpu_usage` |
| composiciones | 17 | no degradar una misión compuesta a snapshot standalone |
| negativos duros | 34 | rechazar conocimiento, precios/web, condicionales, afirmaciones, modelos históricos, investigación, mutación y falsos amigos |
| universo seleccionado | **77** | 26 positivos + 51 fronteras fail-closed |

El inventario léxico contiene 148 candidatos de producto; el oráculo selecciona
74 y añade tres colisiones de temperatura para formar sus 77 casos. No afirma
exhaustividad global. Esas colisiones adicionales impiden que una mención
de GPU convierta una consulta de temperatura no soportada en éxito falso.

La cadena ejecutada es:

mensaje → parser conservador → `system.status` con scope exacto → provider GPU
local → validación de consistencia en el core → JSON tipado interno → respuesta
natural acotada.

## Provider Windows y frontera pública

La identidad se enumera con DXGI. El uso se toma con contadores locales PDH y se
correlaciona internamente con los adaptadores DXGI. No hay WMI remoto, red,
telemetría ni procesos auxiliares. La interoperabilidad es manual y compatible
con NativeAOT.

El provider conserva el orden y la multiplicidad del snapshot: dos adaptadores
con el mismo nombre no se deduplican. `AdapterIndex` es cero-based dentro del
JSON interno; la respuesta visible usa ordinales uno-based (`GPU 1`, `GPU 2`,
etc.) para desambiguar nombres repetidos. Los identificadores internos usados
para correlación, como LUID o PID de contadores, no se publican ni se registran.

El contrato permite éxito parcial solo de forma explícita:

- un adaptador medido publica juntos porcentaje, memoria dedicada usada y
  memoria compartida usada;
- un adaptador cuya pareja de contadores de memoria no está disponible publica
  los tres campos como `null` y un fallo `unsupported` ligado a su índice;
- si ningún adaptador puede medirse, se publica un único fallo global
  `unsupported`, nunca porcentajes cero inventados;
- `invalid_measurement` representa evidencia numérica o metadata inválida;
  `measurement_failed` representa fallos de colección/buffer/hotplug; y
  `unsupported` representa APIs o contadores ausentes.

Antes de responder, el core valida cantidad de adaptadores, Unicode/nombres,
capacidades, overflow, rangos, presencia conjunta de los tres campos de uso y
la matriz exacta entre adaptadores y fallos. Un resultado contradictorio falla
cerrado. La identidad puede publicarse aunque un adaptador no tenga medición de
uso; el mensaje lo declara en vez de ocultarlo o inventar datos.

La respuesta diferencia capacidades y consumo:

- `VRAM` es memoria de video dedicada;
- `RAM reservada` es memoria del sistema dedicada a gráficos;
- el límite compartido es capacidad potencial, no consumo;
- el uso dedicado se expresa frente a `VRAM + RAM reservada`, y el uso
  compartido frente a su límite.

## Verificación ejecutada

La corrida completa Release aprobó:

| Suite | Resultado |
|---|---:|
| Contracts | 37/37 |
| Kernel | 44/44 |
| Providers Windows | 232/232 |
| Integración | 896/896 |
| **Total .NET** | **1.209/1.209** |
| Python | **74/74** |

Son 1.283 pruebas principales. La colección incluye el contrato del oráculo,
routing histórico, negativos/composiciones, agregación PDH, límites de buffers,
errores parciales/globales, serialización NativeAOT y aislamiento del summary.
La auditoría cruzada del corte no dejó P0/P1/P2 abiertos.

Una ejecución física del core **managed** en este host anunció 21 operaciones y
completó identidad y uso con tres adaptadores: dos tuvieron medición y uno quedó
no disponible mediante un fallo `unsupported` indexado; el proceso terminó con
exit 0.
Esta observación acredita la ruta core→provider en ese equipo, no diversidad de
hardware ni exactitud externa absoluta.

También se publicó un `baxy-core.exe` NativeAOT de 7.376.384 bytes, SHA-256
`17b88aed29af5d4cc9dffb3931b73ce13791b304e4f1a7692d2f9eb588550fe9`.
La compuerta reproducible `scripts/test_gpu_status.ps1` ejecutó ese binario real
y publicó atómicamente `artifacts/product/gpu_status_gate.json`, schema
`baxy-gpu-status-gate-v1`, con estado `passed`. Corroboró:

- hello de 21 operaciones;
- identity `completed`/`verified` con tres adaptadores;
- usage `completed`/`verified` con tres adaptadores;
- dos adaptadores medidos y uno no disponible;
- un fallo indexado `unsupported` y cero fallos globales;
- correlaciones exactas de las dos peticiones;
- warmup de transporte `malformed_json`, stderr de 0 bytes y exit 0.

El artefacto solo contiene el resumen sanitizado, no nombres de adaptadores,
LUID, PID, rutas privadas ni las mediciones variables del host. La compuerta
acredita la ruta NativeAOT punto-a-punto en ese equipo y snapshot.

## Límites honestos

- No se mide temperatura, consumo eléctrico, ventilador, clocks ni procesos por
  GPU.
- No hay monitoreo continuo ni una composición que cree carga y luego observe.
- No se validó exhaustivamente hardware multi-vendor, hotplug o drivers sin los
  contadores esperados.
- El host observado no constituye una prueba del perfil físico mínimo de 4 GB
  ni una matriz de equipos.
- No hay gate GUI/WPF específico de GPU, instalador, firma, VM Windows limpia o
  evidencia de upgrade/rollback para este corte.
- Los valores PDH son snapshots del sistema operativo, no causalidad ni
  atribución de una carga a BAXY.

## Commits del corte

| Commit | Cambio |
|---|---|
| `3037445` | congela el oráculo GPU y sus contratos de procedencia |
| `e33267d` | enruta `gpu_identity`/`gpu_usage` sobre `system.status` |
| `cf44b89` | añade el provider DXGI+PDH y su hardening NativeAOT |
| `18061e0` | integra provider, validación, JSON separado y respuesta natural en core/app |
