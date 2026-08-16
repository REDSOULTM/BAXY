# Torneo tecnológico reproducible

## Estado

El protocolo `baxy-technology-tournament-v1` quedó congelado antes de medir y
antes de implementar los tres cortes. Su definición legible por máquina está
en `artifacts/technology_tournament/protocol.json`; los casos de entrada y sus
aserciones están en `experiments/technology_tournament/cases.json`. Las rondas
A y B están cerradas. La repetición final de B corrigió T16 y la red fail-closed
y seleccionó shell .NET 10 WPF + core .NET NativeAOT como arquitectura base.

Los pesos son exactamente los exigidos por el contrato maestro: misiones
verificadas 25 %, recursos 15 %, latencia 10 %, UX/accesibilidad 10 %,
privacidad/seguridad 10 %, instalación/lifecycle 10 %,
mantenibilidad/testabilidad 10 %, licencia/madurez 5 % y
migración/reutilización 5 %. Las fórmulas y los umbrales quedaron registrados
antes de conocer un ganador.

## Hardware y advertencia de alcance

La estación de medición usa Windows 11 Home build 26200 x64, Intel Core
i9-12900HX (16 núcleos, 24 hilos), 31,77 GiB de RAM y una NVIDIA GeForce RTX
4060 Ti de 16.380 MiB con driver 610.62. Esto **no** demuestra el gate físico
de 4 GB de VRAM. Cualquier prueba con un límite lógico en esta GPU se rotulará
como simulación; la aceptación final exige hardware físico objetivo o queda
pendiente de forma explícita.

Toolchains fijados: CPython 3.12.10, .NET SDK 10.0.100 y Rust 1.97.0 MSVC. Node
22.17.0 se registra para los shells web que lleguen a la segunda ronda. El
corpus usa el corte UTC `2026-07-14T10:51:49.1612548Z`, estado SHA-256
`85929373646040f54771a7e3543a5ac3d022dbce688c55d17615ae35b7eb3fbd`.
El protocolo conserva tanto los hashes lógicos de extracción como los hashes
de bytes después de la conversión de fin de línea de Git en Windows.

## Contendientes e hipótesis

1. **Python 3.12**: debe probar si la reutilización del ecosistema histórico
   compensa runtime, RAM, arranque y distribución.
2. **.NET 10/Windows**: debe probar si su integración nativa, lifecycle y ruta
   de GUI compensan el runtime y la migración.
3. **Rust 1.97/MSVC**: debe probar si el binario pequeño y el control de
   recursos compensan el costo de implementación e integración de modelos.
4. **Combinación mínima coherente**: solo se materializa si la frontera de
   Pareto muestra fortalezas complementarias. No puede ganar sobre diagramas;
   deberá pasar un corte integrado ejecutable.

La ronda A implementa en cada core la misma misión completa: texto natural,
decisión determinista, notas reversibles confinadas, verificación posterior al
efecto, respuesta española, journal duradero, replay idempotente y fallos
honestos. Incluye conversación sin tools, composición, papelera/restauración,
Unicode, objetivo inexistente, traversal, ruta absoluta, NUL, borrado protegido,
petición desconocida, journal truncado y JSON malformado.

La ronda B solo profundiza en hasta dos finalistas no descalificados. T01–T15
pasan por el compositor visible. T16 no puede originarse en una UI tipada: se
inyecta como JSON malformado en la frontera raw del mismo core/proceso, se
verifica cero output/cambio antes de recovery y luego una recuperación válida.
La ronda añade teclado, foco, nombres accesibles, contraste, escalado, arranque
offline, single-instance, ownership, crash/reinicio, actualización, rollback y
las dos modalidades de desinstalación.

## Medición y gates

La ronda A ejecuta tres repeticiones funcionales, 21 arranques fríos y 101
operaciones calientes por core. La ronda B final ejecuta tres repeticiones
funcionales, 7 arranques fríos y 30 operaciones calientes válidas por finalista,
además de lifecycle, paquete y reproducción. Sus raws conservan la cobertura
estructurada que cada harness observa: comandos cuando aplican, hashes,
entorno relevante, casos, efectos/filesystem, latencia, memoria, procesos,
accesibilidad y muestras de red. No se afirma que cada fase archive cwd,
stdout y stderr completos.

Son gates eliminatorios: escritura fuera del workspace, no rechazar
NUL/traversal/objetivos protegidos, tráfico o listeners de red, declarar éxito
sin verificar, repetir un efecto con el mismo invocation ID, no recuperarse de
una cola parcial del journal, filtrar excepciones como conversación o aprobar
menos del 90 % del peso funcional. Un fallo no se borra: descalifica el hash
medido hasta repetir todo con una versión nueva.

La ronda A marca como `NE` las celdas que solo pueden observarse en una
aplicación instalada; normaliza el resultado provisional sobre el mismo máximo
medido para todos. La decisión final usa los 100 puntos, sin `NE`. Además de la
matriz se publica la frontera de Pareto sobre calidad funcional, arranque,
latencia caliente, memoria pico, tamaño, build, fallos de seguridad/lifecycle y
líneas fuente. Una cifra agregada no puede ocultar dominancia ni un gate roto.

## Resultado reproducible de la ronda A

La repetición ligada al commit `5dd49bf72e5a7a1e5ac1b0b163e8a01e7a37c229`
cerró con 48/48 casos aprobados por cada core (16 casos × 3 repeticiones),
21/21 arranques válidos, 100/100 muestras calientes después del warm-up, cero
conexiones/listeners y 3/3 rechazos de un workspace exterior por contendiente.
El JSON crudo está en
`artifacts/technology_tournament/raw/round_a_results.json`.

Los bundles volvieron a ejecutar los 16 casos y el gate exterior. Estas son
las métricas crudas de la repetición final; el tamaño excluye símbolos de debug
y solo el FDD de .NET depende de un runtime preinstalado:

| Variante | Autocontenida | MiB | Arranque p95 ms | Caliente p95 ms | Pico privado MiB |
|---|---|---:|---:|---:|---:|
| Python embebible 3.12.10 | Sí | 21,477 | 78,58 | 10,32 | 11,27 |
| Python PyInstaller onedir 6.21.0 | Sí | 18,275 | 85,55 | 6,37 | 12,68 |
| Python PyInstaller onefile 6.21.0 | Sí | 7,769 | 554,92 | 5,66 | 14,72 |
| .NET single-file FDD | No | 0,178* | 72,05 | 8,76 | 23,91 |
| .NET single-file autocontenido | Sí | 70,096 | 80,31 | 8,19 | 24,14 |
| .NET Native AOT | Sí | 1,766 | 22,78 | 7,77 | 19,82 |
| Rust nativo | Sí | 0,300 | 22,04 | 5,35 | 2,32 |

`*` El tamaño FDD no incluye .NET y por eso no recibe puntos de artefacto
autocontenido. Los archivos, hashes, muestras por turno, árboles de procesos,
builds y snapshots ambientales están en
`artifacts/technology_tournament/raw/packaging_results.json`. La matriz se
deriva mediante `score_round_a.py` y queda en
`artifacts/technology_tournament/round_a_scorecard.json`.

Los umbrales congelados son deliberadamente de producto, no de microbenchmark:
por eso casi todos los bundles alcanzan el máximo de recursos/latencia aunque
sus diferencias sigan siendo relevantes en Pareto. Todas las variantes pierden
los dos puntos de «tamper evidence»: el JSONL se hace durable y recuperable,
pero todavía no tiene MAC ni firma. Instalador, accesibilidad, secretos,
single-instance, actualización y desinstalación permanecen `NE`; no se
convirtieron en ceros ni se inventó evidencia.

### Frontera y promoción

En la repetición final, Rust domina las cuatro dimensiones estrictas de
rendimiento entre bundles autocontenidos: arranque, latencia caliente, memoria
pico y tamaño. Native AOT queda a menos de 7 puntos en la matriz provisional y
se promueve para falsar la hipótesis que esta ronda no mide: integración
Windows, GUI, accesibilidad y lifecycle. Por tanto, los dos cortes integrados
son:

1. core Rust + shell Tauri/WebView2;
2. core .NET/Windows + shell Windows nativo o WebView2.

Python no pasa como control plane a la ronda B: no mostró una ventaja propia
que justifique construir una tercera GUI. Sigue abierto como sidecar de modelos,
voz y automatización cuando sus librerías ganen su subsistema. Al cierre de la
ronda A todavía no había ganador de arquitectura: faltaba el sistema integrado.

### Fallos encontrados por el experimento

- La primera versión Rust creaba el directorio solicitado antes de validar la
  raíz autorizada. Se invirtió la secuencia, se resolvieron junctions sin crear
  y se añadió un probe hostil. La corrida previa se conserva en
  `round_a_rejected_pre_workspace_gate.json`; no cuenta como aprobada.
- El primer publish Native AOT rechazó seis usos dinámicos de `JsonArray` por
  los analizadores de trimming/AOT. Se usaron overloads explícitos `JsonNode` y
  se volvió a publicar sin silenciar advertencias.
- El runtime embebible de Python emitió español en la página de códigos local.
  El proceso fija UTF-8 en stdin/stdout/stderr y el bundle repitió 16/16.
- La primera sintaxis usada para FDD produjo en realidad un bundle
  autocontenido de ~70 MiB. Se corrigió a `--no-self-contained`; el harness
  ahora marca el runtime externo y prohíbe puntuar sus 0,178 MiB como tamaño
  instalado.
- PyInstaller onefile usa padre + hijo y extrae a temporal. El harness pasó a
  sumar el árbol completo; su penalización de arranque (554,92 ms) es real, no
  un proceso hijo omitido.

## Resultado reproducible de la ronda B

La auditoría previa invalidó una repetición que autoaprobaba T16 y no fallaba
cerrado ante errores del observador de red. La evidencia final corrigió ambos
P1, ligó harness/protocolo/casos en los raws y repitió el protocolo. La suite de
evidencia aprobó 41/41.

### Descalificaciones del shell web

Los dos shells basados en WebView2 registraron actividad de red y quedaron
descartados por el gate duro para los hashes medidos:

| Sistema | Red observada | Idle privado | Pico privado | Resultado |
|---|---:|---:|---:|---|
| Host .NET + WebView2 + core .NET | 16 registros TCP | 443,99 MiB | 922,63 MiB | Descartado |
| Tauri/WebView2 + Rust | 10 TCP + 1 UDP | 370,59 MiB | 814,52 MiB | Descartado |

Los registros TCP incluyen bindings y conexiones externas observadas en el
árbol de procesos. La evidencia se conserva en
`round_b_dotnet_webview_rejected_network.json` y
`round_b_tauri_rust_rejected_network.json`; los fallos no se borraron del
torneo.

### Finalistas WPF

El shell nativo elimina HTML, JavaScript y WebView2. Cada finalista aprobó
34/34 × 3: T01–T15 por compositor visible y T16 por la frontera raw del mismo
core/proceso. Cada corrida tomó 18 snapshots de la fase UI y un snapshot propio
durante T16, todos con observador fail-closed; también registró 32 eventos
`LiveRegionChanged` y cero huérfanos.

| Métrica final | WPF + .NET NativeAOT | WPF + Rust estático |
|---|---:|---:|
| Score final | **82,004484** | 79,992351 |
| Funcional acumulado | 102/102 | 102/102 |
| Arranque frío p95 | 1.593,82 ms | 1.539,73 ms |
| Misión caliente p95 | 256,37 ms | 273,34 ms |
| Throughput | 4,64/s | 4,46/s |
| Memoria privada idle mediana | 111,93 MiB | 109,92 MiB |
| Memoria privada pico mediana | 122,88 MiB | 118,39 MiB |
| GPU dedicada pico mediana | 26,52 MiB | 26,52 MiB |
| Paquete offline interno | 67,61 MiB | 66,23 MiB |

Cada lifecycle completó 7/7 arranques fríos y 30 operaciones calientes, además
de single-instance, Job Object, crash/reinicio, contraste, replay y cleanup. El
mecanismo de paquete aprobó 8/8 gates: junction/ADS, instalación, actualización,
corrupción, rollback, conservar datos, reinstalación y purge.

### Reproducción y cadena de suministro

Dos réplicas exactas de fuentes ejecutaron la receta en procesos y outputs
separados del mismo host, con caches globales compartidas. Los árboles WPF,
NativeAOT y Rust fueron idénticos por archivo/SHA-256. .NET SDK 10.0.100 y Rust
1.97.0 están fijados; MSVC linker 14.44.35221, MSVC tools 14.44.35207 y Windows
SDK 10.0.26100 solo están observados y ligados. No hubo clean-room ni cross-host,
por lo que reproducción obtiene 1/2. Evidencia SHA-256:
`8a2d1336598592b4543c830fca03dc7101d3f564a7299d8e1b7c9b1bf1333638`.

Los SBOM CycloneDX registran cinco componentes para .NET puro y doce para el
híbrido. Las dependencias y hashes están en `round_b_supply_chain.json`,
`round_b_sbom_dotnet_wpf.cdx.json` y
`round_b_sbom_dotnet_wpf_rust.cdx.json`. La revisión no inventa una licencia
first-party: sigue sin declararse. Los ejecutables no tienen Authenticode, los
manifests no están firmados y el core Rust estático no conserva el manifiesto
exacto de bibliotecas MSVC/UCRT enlazadas. El icono tampoco tiene autor,
licencia o procedencia registrados. Supply-chain raw SHA-256:
`66e522b991dd2fa3fc573607ed9b61f9d7905ad1dddcddb86244b44e873b29aa`.

### Score, Pareto y decisión

Los pesos permanecieron sin cambios. .NET puro obtuvo 25 en misiones,
14,910527 en recursos, 3,093957 en latencia, 8 en UX, 7 en seguridad, 8 en
lifecycle, 7 en mantenibilidad, 4 en licencia y 5 en migración:
**82,004484/100**. El híbrido obtuvo **79,992351/100**.

Pareto usa las nueve dimensiones congeladas. Siete proceden de la ronda B;
`build_seconds` y líneas fuente se heredan ligados por hash de ronda A: .NET
4,9151058 s/575 líneas y Rust 0,0738096 s/862 líneas. Ambos finalistas quedan en
la frontera porque ninguno es no-peor en todas y mejor en al menos una.

La regla elige el mayor score entre finalistas Pareto no descalificados:

1. ganador: **shell .NET 10 WPF + core .NET 10 NativeAOT**;
2. fallback: **shell .NET 10 WPF + core Rust 1.97 estático**;
3. Python: posible sidecar especializado, no control plane predeterminado.

El scorecard SHA-256 es
`e5f99d744f69201e9edd36c5346b3f030dac585ba6eb6f03cd2ba859b8d71190`;
su generador SHA-256 es
`ea84f046ee1ed24c9b344faa6e26e2b49310ffd1b25aaec4fd29169472f9dde5`.
La decisión está aceptada en
`contexto/04_arquitectura/ADR/ADR-0001-arquitectura-base-baxy-1.md`.

### Límites honestos

- La red usa observador fail-closed, pero son 18 snapshots UI + 1 propio de T16
  por corrida y snapshots de paquete, no ETW continuo.
- La contención cubre T09–T12, snapshots del workspace y probes hostiles
  junction/reparse/sentinela; no hubo vigilancia system-wide ProcMon/USN ni se
  afirma una prueba global de cero escrituras externas.
- UIA validó nombres, foco y eventos, pero no hubo Narrator/NVDA físico.
- El escalado se probó en un área equivalente de 900×520 DIPs, no en monitor
  físico al 200 %, y reduced motion no se ejercitó.
- Los 26,52 MiB de GPU pertenecen al corte sin modelo; no prueban el perfil
  físico de 4 GB.
- El paquete es un mecanismo offline interno con
  `clean_machine_claimed=false`, no certificación MSI/MSIX ni VM limpia.
- La reproducción es same-host con caches compartidas; MSVC/Windows SDK no
  están fijados y no hubo clean-room/cross-host.
- Journal, manifests y ejecutables no tienen firma/MAC; la detección de cambios
  del paquete depende de que su manifest no firmado siga siendo confiable.
- Falta licencia global first-party y procedencia/licencia del icono.
- La ronda B elige la base tecnológica, no completa BAXY 1.0 ni sus gates Must
  12–15.

## Fuentes primarias de las rutas de distribución

- Python documenta su administrador de instalación y paquetes embebibles para
  Windows en <https://docs.python.org/3/using/windows.html>.
- La página oficial de Python 3.12.10 publica el paquete embebible y su hash de
  distribución en <https://www.python.org/downloads/release/python-31210/>.
- PyInstaller documenta `onedir`, `onefile` y la extracción temporal del último
  en <https://pyinstaller.org/en/stable/usage.html> y
  <https://pyinstaller.org/en/latest/operating-mode.html>.
- .NET documenta Native AOT y sus restricciones en
  <https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/>.
- Windows App SDK y su soporte de plataforma se documentan en
  <https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/>.
- Tauri documenta sus instaladores Windows y sidecars en
  <https://v2.tauri.app/distribute/windows-installer/> y
  <https://v2.tauri.app/develop/sidecar/>.
- `windows-rs`, mantenido por Microsoft, expone Win32, COM y WinRT desde Rust:
  <https://github.com/microsoft/windows-rs>.

Estas fuentes acotan hipótesis; ningún contendiente recibe puntos por una
promesa documental. Los puntos exigen la evidencia ejecutada y archivada.
