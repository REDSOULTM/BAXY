# ADR-0001 — Arquitectura base de BAXY 1.0

- Estado: **aceptado**.
- Fecha: 2026-07-14.
- Ámbito: shell Windows, core de control, frontera local entre procesos y
  patrón de lifecycle. No decide modelos, voz, visión, memoria, providers ni
  instalador productivo.
- Protocolo: `artifacts/technology_tournament/protocol.json`.
- Scorecard: `artifacts/technology_tournament/round_b_scorecard.json`, SHA-256
  `e5f99d744f69201e9edd36c5346b3f030dac585ba6eb6f03cd2ba859b8d71190`.
- Generador del scorecard: SHA-256
  `ea84f046ee1ed24c9b344faa6e26e2b49310ffd1b25aaec4fd29169472f9dde5`.

## Contexto

BAXY necesita una base Windows local, privada, accesible y de bajo consumo que
pueda ejecutar misiones tipadas, verificar efectos y sobrevivir a fallos. El
stack histórico no recibió ventaja por legado. El protocolo
`baxy-technology-tournament-v1` congeló pesos, casos y gates antes de medir.

La ronda A comparó cores Python, .NET y Rust. Rust lideró el corte aislado y
.NET avanzó por la regla de promoción congelada. La ronda B comparó sistemas
Windows completos y añadió GUI, accesibilidad automatizada, single-instance,
ownership, crash/reinicio, actualización, rollback y desinstalación.

Antes de aceptar este ADR se invalidó una repetición en la que T16 se
autoaprobaba y la observación de red no fallaba cerrado. La corrida final
ejecuta JSON malformado contra el core real, exige recuperación/redacción y
filesystem intacto, falla ante errores del observador y liga cada raw a los
hashes de harness, protocolo y casos. El fallo previo se conserva como lección
del medidor, no como resultado de un contendiente.

## Alternativas medidas

| Sistema | Resultado final |
|---|---|
| .NET 10 WPF nativo + core .NET NativeAOT | **82,004484/100**; no descalificado; Pareto; ganador |
| .NET 10 WPF nativo + core Rust estático | 79,992351/100; no descalificado; Pareto; fallback |
| Host .NET + WebView2 + core .NET | Descartado por gate de red observado en su hash medido |
| Tauri/WebView2 + Rust | Descartado por gate de red observado en su hash medido |
| Python como control plane | No promovido tras ronda A; elegible como sidecar si gana un subsistema |

Los dos finalistas WPF aprobaron 34/34 puntos en cada una de tres corridas:
T01–T15 por el compositor visible y T16 como JSON malformado en la frontera raw
del mismo core/proceso. Cada corrida tomó 18 muestras de red durante la fase UI
y una propia de T16 con observador fail-closed, registró 32 eventos
`LiveRegionChanged` y cerró sin huérfanos. Ambos completaron 7/7 arranques
fríos, 30 operaciones calientes, lifecycle y los ocho gates del paquete. La
suite de evidencia aprobó 41/41.

| Métrica final | WPF + .NET | WPF + Rust |
|---|---:|---:|
| Arranque frío p95 | 1.593,82 ms | 1.539,73 ms |
| Misión caliente p95 | 256,37 ms | 273,34 ms |
| Throughput caliente | 4,64/s | 4,46/s |
| Memoria privada idle mediana | 111,93 MiB | 109,92 MiB |
| Memoria privada pico mediana | 122,88 MiB | 118,39 MiB |
| GPU dedicada pico mediana | 26,52 MiB | 26,52 MiB |
| Paquete interno validado | 67,61 MiB | 66,23 MiB |
| Build de core heredado de ronda A | 4,915106 s | 0,073810 s |
| Líneas fuente de core heredadas | 575 | 862 |

La frontera de Pareto usa las nueve dimensiones congeladas. Siete provienen de
la ronda B integrada y `build_seconds`/líneas fuente se heredan, ligados por
hash, del core promovido en ronda A. Ambos finalistas permanecen en la frontera.

La reproducción comparó dos réplicas exactas de fuentes en procesos y outputs
separados del mismo host, con caches globales compartidas. Los árboles WPF,
NativeAOT y Rust fueron idénticos por archivo y SHA-256. .NET SDK 10.0.100 y
Rust 1.97.0 están fijados; MSVC linker 14.44.35221, MSVC tools 14.44.35207 y
Windows SDK 10.0.26100 solo están observados y ligados, no fijados. Por eso la
celda de reproducción recibe 1/2, no certifica clean-room ni otro host. Evidencia:
`artifacts/technology_tournament/raw/round_b_reproducibility.json`, SHA-256
`8a2d1336598592b4543c830fca03dc7101d3f564a7299d8e1b7c9b1bf1333638`.

La cadena de suministro está inventariada en los SBOM CycloneDX y en
`artifacts/technology_tournament/raw/round_b_supply_chain.json`, SHA-256
`66e522b991dd2fa3fc573607ed9b61f9d7905ad1dddcddb86244b44e873b29aa`.
El sistema .NET tiene una toolchain de implementación y cinco componentes SBOM;
el híbrido añade Rust, crates y CRT estático y registra doce componentes.

## Decisión

Adoptar como arquitectura base de BAXY 1.0:

- shell nativo **.NET 10 WPF**;
- core de control **.NET 10 NativeAOT** en proceso separado;
- JSONL UTF-8 por stdin/stdout redirigidos como frontera local inicial, sin
  transporte de red;
- instancia única y ownership del árbol mediante Windows Job Object;
- efectos confinados, verificación independiente, journal durable y replay
  idempotente como invariantes;
- directorios de versión inmutables y punteros `current`/`current.previous`
  atómicos como patrón a llevar al paquete productivo.

La regla congelada elige el mayor score entre finalistas Pareto no
descalificados. .NET puro conserva el comportamiento y GUI verificados sin
sumar una segunda toolchain, crates ni el inventario del CRT estático. Las
ventajas puntuales de recursos/build del híbrido no compensan su costo medido
de mantenibilidad y migración.

## Consecuencias

- La fase productiva puede compartir contratos, tipos y diagnóstico entre
  shell y core.
- WPF reemplaza el shell web, pero cada superficie nueva debe validar teclado,
  UIA y, después, lectores y hardware físicos.
- NativeAOT exige mantener límites compatibles con trimming/AOT y generación
  de JSON explícita.
- Python, Rust y runtimes de modelos pueden entrar como sidecars solo cuando
  ganen su subsistema con evidencia.
- El paquete del torneo demuestra invariantes de lifecycle; no es el instalador
  Windows final.

## Fallback

El fallback reproducible es **.NET 10 WPF + core Rust 1.97 estático**. Permanece
en Pareto por su menor RAM/tamaño, arranque y build de core. No es el default
por su segunda toolchain, mayor superficie de cadena de suministro y más líneas
de implementación. Comparte shell y contrato, por lo que puede revalidarse sin
rediseñar la GUI.

## Límites de la evidencia

- La red usa un observador fail-closed, pero sigue siendo discreta: 18 muestras
  por corrida, una muestra durante T16 y snapshots de lanzamientos de paquete;
  no es ETW continuo.
- La contención está demostrada por T09–T12, snapshots del workspace y probes
  hostiles junction/reparse/sentinela; no hubo observación system-wide con
  ProcMon/USN y no se afirma una prueba global de cero escrituras externas.
- UIA confirmó 48 nodos nombrados, foco y live regions, pero no hubo Narrator o
  NVDA físico.
- El escalado usó 900×520 DIPs equivalentes; no hubo DPI físico al 200 % ni
  reduced motion físico.
- Los 26,52 MiB GPU corresponden al corte sin modelo y no validan 4 GB físicos.
- El paquete no se instaló en VM limpia y no certifica MSI/MSIX ni privilegio
  mínimo.
- La reproducción es same-host con caches compartidas; MSVC y Windows SDK no
  están fijados y no hubo reproducción cross-host.
- Ejecutables y manifests no tienen firma/Authenticode; el journal no tiene MAC.
- No existe licencia global first-party y el icono carece de autor, licencia y
  procedencia registrados. El core Rust tampoco conserva un manifiesto exacto
  de bibliotecas MSVC/UCRT estáticas.

## Criterio de reapertura

Reabrir si el stack rompe un gate duro; falla hardware objetivo, Narrator/NVDA
o lifecycle productivo; o si otro sistema completo, bajo este protocolo o uno
sucesor congelado, domina materialmente sin degradar seguridad, accesibilidad,
mantenibilidad ni migración. Una diferencia aislada pequeña no basta.
