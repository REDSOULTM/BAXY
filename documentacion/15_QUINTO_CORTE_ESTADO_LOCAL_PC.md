# Quinto corte productivo: estado local del PC

Estado del corte: implementado y verificado en `88cb456`. Añade una consulta
local y de solo lectura del estado del equipo, y el red-team final terminó con
cero P0/P1 después de cerrar los casos de batería totalmente desconocida y la
distinción Windows 11/Windows Server. No cierra ningún Must adicional ni los
bloqueantes B-004/B-005/B-006. Tampoco añade voz, conversación general,
composición multioperación, instalador o aceptación física completa.

## Alcance exacto

El catálogo productivo del core contiene ocho operaciones. Siete son capacidades
interactivas exigidas por el handshake de la GUI; `app.status` sigue siendo la
operación interna de salud. La nueva operación es:

- `system.status`, riesgo `read_only`.

Los scopes públicos aceptados son:

| Scope | Medición solicitada |
|---|---|
| `summary` | CPU, RAM, disco del sistema, batería, Windows y tiempo activo |
| `cpu_memory` | CPU y RAM |
| `os_memory` | Windows y RAM |
| `cpu` | CPU |
| `memory` | RAM |
| `disk` | disco del sistema |
| `battery` | batería/alimentación |
| `os` | versión, compilación y arquitectura de Windows |

`uptime` existe como sección interna del snapshot completo, pero no es un scope
público ni una orden natural independiente. Las dos combinaciones admitidas son
una sola operación read-only con scope finito; no constituyen un planner ni
composición multioperación.

## Oráculo histórico congelado

El corpus canónico contiene 306 filas globales con la operación histórica
`system.status`: 294 de producto y 12 de traza. De las de producto, 279 son
`user_mission`. Este corte no afirma cubrirlas todas.

El oráculo curado congela un subconjunto de 113 IDs de producto y misión real:

| Scope | IDs |
|---|---:|
| `cpu_memory` | 9 |
| `os_memory` | 1 |
| `battery` | 56 |
| `memory` | 25 |
| `cpu` | 12 |
| `disk` | 10 |
| **Total** | **113** |

Los 113/113 IDs enrutan a `system.status` con un único argumento `scope` exacto.
Representan 50 literales, una misión canónica y nueve rutas `source`:

- misión `mission_user_mission_system_status_d2881a17ec`;
- digest SHA-256 de IDs
  `9d55e3fafc60a588da7714ee1dd795378952cc3f986ed166a3dd545b3027f21e`.

Las frases de resumen genérico, el resumen spanglish y `os` standalone solo
tienen contratos sintéticos y pruebas de parser/E2E; no cuentan como cobertura
histórica del oráculo. Once negativos congelados mantienen fuera de esta slice
GPU, conocimiento o precios, inventario de procesos, fecha/hora con IP, RAM de
un proceso concreto y composiciones con otra operación.

## Parser natural y frontera de composición

La GUI reconoce gramáticas finitas en español e inglés y un contrato sintético
spanglish. Las expresiones deben coincidir con la frase completa. El parser
rechaza, entre otros:

- GPU/VRAM, procesos, IP y preguntas de conocimiento o precio;
- estado de una aplicación o proceso concreto;
- negaciones y condicionales;
- fecha/hora combinadas con RAM o red;
- `system.status` combinado con abrir Notepad;
- controles y UTF-16 malformado.

`cpu_memory` y `os_memory` minimizan la recolección al par solicitado. Ninguna de
estas rutas habilita composición general ni permite mezclar efectos.

## Provider Win32 de solo lectura

El provider recopila únicamente las secciones solicitadas:

- uso de CPU mediante dos muestras separadas por 150 ms, cantidad de procesadores
  lógicos y modelo opcional;
- RAM total y disponible;
- capacidad y espacio disponible del disco del sistema;
- presencia de batería, carga, estado de carga y alimentación de CA;
- versión interna, build y arquitectura de Windows;
- tiempo activo del sistema dentro de `summary`.

No existe campo ni probe para GPU/VRAM, procesos, IP, hostname o usuario. Una PC
de escritorio sin batería es una medición válida, no un error. Si Windows no
puede corroborar la presencia de batería, la respuesta no inventa que haya o no
haya una. El resumen puede conservar las secciones válidas y nombrar de forma
saneada las que fallaron; una consulta de scope único sin medición corroborada
termina como fallo honesto.

El handler valida rangos, consistencia, scopes solicitados y contradicciones
antes de publicar éxito. Los errores internos del probe no atraviesan la
respuesta. El journal conserva y reproduce también resultados read-only; sigue
siendo almacenamiento local en texto plano con cadena SHA-256, sin HMAC ni
autenticidad adversarial.

## Evidencia ejecutada

| Evidencia | Resultado |
|---|---:|
| Contratos .NET | 23/23 |
| Kernel .NET | 27/27 |
| Provider Windows .NET | 81/81 |
| Integración .NET | 329/329 |
| Total .NET Release | 460/460 |
| Python canónico | 59/59 + 148 subtests |
| Total conjunto principal | 519/519 |
| Oráculo histórico curado | 113/113 |
| Red-team final | 0 P0/P1 |

El E2E automatizado recorrió ViewModel→core→provider Win32→respuesta natural
para CPU+RAM, disco, batería y Windows; verificó que no aparezcan JSON ni el
nombre interno de la operación y que el outbox termine vacío.

Un publish NativeAOT temporal produjo `baxy-core.exe` de 4.857.856 bytes, SHA-256
`83e972f4273380b587192684a14cb01f42837f08e389082a87cd8d443cb4c488`.
Dos de dos requests reales aprobaron contra ese ejecutable: `cpu_memory` devolvió
solo CPU+RAM y `summary` devolvió sus seis secciones. El artefacto temporal fue
eliminado después del smoke. No es el distribuible, no tiene manifest de release
y no acredita instalador ni instalación limpia.

Los artefactos protegidos permanecieron intactos:

- `artifacts/corpus_cutoff/source_manifest.json`:
  `9da873e4b30dd81d1cc85d6e9bf4b19fb13aa96e8fcc5ce3b1f8265012ca59b0`;
- `scripts/freeze_historical_sources.py`:
  `27acb6ccc34b6820ab8614a19d41409645aabeb151803bfec4d34843e6c4ae5c`;
- `artifacts/technology_tournament/protocol.json`:
  `383a9e54cfc5a186de61f060aeb2a6cd013bab3ec21bdeb387063d935d99a892`.

## Límites y deuda explícita

- 113/113 acredita solo el subconjunto curado; no las 306 filas globales ni todo
  el ledger `system.status`.
- No hay GPU/VRAM, procesos, red/IP, hostname, usuario, otros discos ni estado de
  aplicaciones concretas.
- El resumen y spanglish históricos no están cubiertos por el oráculo; tampoco
  existe una fila histórica `os` standalone en ese conjunto.
- El smoke NativeAOT no es un gate de release ni una prueba en Windows limpio.
- El último distribuible continúa siendo el del segundo corte: 14 archivos de
  carga, 50.546.916 bytes más el manifiesto, directorio de desarrollo y no
  instalador.
- El progreso permanece en 5/15 Must (33,3 %). Este corte reduce B-004, pero
  B-004/B-005/B-006 continúan abiertos.

## Referencias técnicas

- Microsoft Learn, `OSVERSIONINFOEXW`:
  <https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-osversioninfoexw>.
- Microsoft Learn, información de versiones de Windows 11:
  <https://learn.microsoft.com/en-us/windows/release-health/windows11-release-information>.
