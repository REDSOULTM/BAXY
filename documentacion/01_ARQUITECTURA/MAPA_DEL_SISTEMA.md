# Mapa del sistema activo

Estado: **mapa de implementación a 2026-07-28**.

La fuente de verdad ejecutable es `src/`; este mapa explica su estructura sin
convertir `legacy/`, torneos o evidencia en código activo.

## Topología

```text
BAXY Field (React/Vite congelado)
          │ mensajes nativos
          ▼
Baxy.App (WPF/WebView2 + superficies WPF, UX, sidecars, voz y coordinación)
      │ baxy.mind.v1                 │ baxy.local.v1
      ▼                              ▼
baxy_mind (Python)             Baxy.Core (NativeAOT)
 conversación/router/plan       composición y protocolo
      │ propone                      │
      └──────── catálogo validado ───┤
                                     ▼
                           Baxy.Kernel
                 catálogo · policy · confirmación
                      journal · replay · outcomes
                                     │
                                     ▼
                         Baxy.Providers.Windows
                         efecto · postlectura · receipt
                                     │
                                     ▼
                         Baxy.Security.Windows
                    DPAPI · rutas/handles protegidos
```

`Baxy.Setup` queda fuera de este runtime: instala y conmuta versiones del
paquete atestado.

## Proyectos .NET reales

`Baxy.slnx` contiene siete proyectos productivos y cinco proyectos de pruebas.

| Proyecto | Responsabilidad | Dependencias de proyecto permitidas |
|---|---|---|
| `Baxy.Contracts` | Contratos JSONL, constantes de protocolo y DTO compatibles con NativeAOT | ninguna |
| `Baxy.Kernel` | `ProductCatalog`, `OperationRegistry`, planner validado, `MissionEngine`, confirmación, journal y resultados tipados | `Baxy.Contracts` |
| `Baxy.Security.Windows` | DPAPI, payloads ligados y políticas de paths/handles Windows | ninguna |
| `Baxy.Providers.Windows` | Stores, providers nativos y adapters externos con postlectura | Contracts, Kernel y Security |
| `Baxy.Core` | Proceso NativeAOT, composition root, handlers, hello validado por App contra el hijo y narración determinista | Contracts, Kernel, Providers y Security |
| `Baxy.App` | Host WPF/WebView2, bridge, clientes core/mind, UX, ejecución del plan y voz | Contracts, Kernel, Providers y Security; construye Core sin referenciar su assembly |
| `Baxy.Setup` | Instalador NativeAOT independiente, paquete embebido, update/rollback/recovery | ninguna referencia al runtime |

Las pruebas .NET se separan en `Baxy.Contracts.Tests`, `Baxy.Kernel.Tests`,
`Baxy.Providers.Windows.Tests`, `Baxy.Integration.Tests` y
`Baxy.Setup.Tests`.

## Componentes activos no .NET

| Ruta | Estado | Función |
|---|---|---|
| `src/baxy_mind` | producto activo | Protocolo `baxy.mind.v1`, `turn.decide`, planner, grounding, narración, STT/TTS y voz |
| `src/Baxy.FieldUi` | producto activo congelado | Fuente React histórica y `dist/` servido localmente por WebView2 |
| `main.py` | entrada de desarrollo | Fingerprint del cierre App/Core, validación del layout real de MSBuild, build incremental y lanzamiento |
| `scripts/build_layout.py` y `.ps1` | tooling canónico de build | Leen el contrato literal de `Directory.Build.props`, validan segmentos y outputs evaluados y entregan TFM/RID/configuración a Python y PowerShell |
| `scripts/run_baxy.ps1` | launcher de desarrollo | Selección CPU/sin mente y arranque con runtime registrado |
| `scripts/baxy_runtime_config.py` | tooling canónico | Resolución fail-closed de manifest u overrides explícitos |
| `src/baxy_mind/tools` | tooling canónico de router | Fuentes y extracción versionadas del banco; cada builder debe fijar y registrar la revisión del modelo antes de reclamar reproducibilidad |

Los modelos, `llama.cpp` y activos STT/wake viven en el runtime externo. No se
copian dentro del repositorio.

## Catálogo y ejecución

`src/Baxy.Kernel/Operations/ProductCatalog.cs` contiene los descriptores
cerrados del catálogo. `src/Baxy.Core/Program.cs` construye los
`IOperationHandler`, crea el `OperationRegistry` y exige
`ProductCatalog.ValidateAgainst(registry)` antes de publicar el saludo. El
catálogo público vigente contiene **169 operaciones**.

El core envía el catálogo exacto al App; el App lo valida y lo entrega a la
mente mediante `catalog.configure`. El sidecar no lee un catálogo alternativo
en disco. Una operación propuesta que no exista, tenga argumentos inválidos o
contradiga el plan se rechaza antes del provider.

Las reglas explícitas de `effect_intent.py` conservan una única precedencia,
pero ya no forman un bloque indiferenciado: datos locales, sistema/red, audio,
catálogo instalado, aplicaciones/ventanas, entrada/captura, web/browser y
media/correo tienen reviewers de dominio. Estos reviewers sólo proponen
matches para una cláusula. `_resolve_explicit_effects_single` conserva su orden
y `_finalize_effect_matches` aplica la finalización por cláusula.
`resolve_explicit_effects` sigue siendo dueño del split, el contexto entre
cláusulas, la supresión cruzada de `app.open`, la composición, la cardinalidad
global y la evidencia final; extraer un reviewer no le da autoridad.

El oráculo exhaustivo de tooling aplica el mismo patrón mediante
`ORDERED_REVIEWERS`; no participa en runtime. Las fuentes del banco, sus
builders y escritura atómica viven en `src/baxy_mind/tools`, y una compuerta
verifica que los experimentos consuman ese banco canónico sin bifurcarlo.

## Flujo NL → efecto verificado

1. Texto o transcripción local forman un `MissionInput`.
2. El App valida el saludo del core y configura la mente con ese catálogo.
3. `turn.decide` devuelve conversación, aclaración, acción o plan. La evidencia
   E5 sólo puede reforzar conversación o abstenerse.
4. Una acción obtiene argumentos bajo su schema. Un plan se limita a 16 pasos,
   dependencias hacia atrás y observaciones estructuradas.
5. .NET vuelve a validar operación, DAG, argumentos y bindings derivados.
6. `MissionEngine` calcula fingerprint y policy. Si corresponde, emite un
   challenge ligado a misión, invocación, operación y argumentos.
7. El App valida y conserva la operación preparada. Una confirmación
   reconciliada no reconstruye la petición desde texto ni pierde el estado de
   efecto incierto.
8. El journal persiste `started` antes del efecto.
9. El handler llama al provider; el provider ejecuta y hace postlectura.
10. Sólo una evidencia válida produce `completed/verified`. Un fallo
    reintentable queda `pending`, que es no terminal. Un efecto ambiguo no
    reintentable queda `failed` con `effectMayHaveOccurred:true`.
11. El App detiene el plan en ambos casos. Si el efecto puede haber ocurrido,
    conserva la operación preparada y el checkpoint durable y prohíbe
    continuar, replanear o repetir hasta reconciliarlo.
12. El journal completa únicamente `completed`, `failed` o `rejected`; el
    narrador formula una respuesta natural y la voz puede pronunciarla mediante
    SAPI.

Replay sólo existe para una respuesta terminal ya completada en el journal:
con la misma identidad y fingerprint devuelve ese resultado sin repetir el
efecto. Un `pending` no se almacena como completado y puede reentrar con la
misma identidad. Una identidad reutilizada con otra petición se rechaza.

## Plano de control de la mente

El sidecar separa recepción/control del trabajo de modelos sin convertir el
planner o el LLM en ejecutores concurrentes:

```text
stdin JSONL
    │ lector incremental acotado (os.read)
    ▼
receptor único ── cola acotada ── coordinador de control
                                  ├─ voice.cancel / shutdown prioritarios
                                  └─ lane serial de requests pesadas
                                               │
                                               ▼
                              router · evidencia · LLM · planner
                                               │
                                               ▼
                                  escritor terminal único → stdout
```

La lane pesada conserva orden, IDs, scopes y ownership únicos. El coordinador
aplica backpressure en vez de crear workers sin límite y permite que
`voice.cancel` y `shutdown` no esperen detrás de una inferencia larga. El
receptor tiene vida de proceso porque Windows/Python no ofrecen cancelación
portable de una lectura bloqueada sobre stdin redirigido; usa un reader crudo,
stateful y limitado a `MAX_LINE_BYTES + 1`, no `BufferedReader`, para que una
caída del dispatcher no retenga su lock durante el cierre del intérprete.

Dentro del LLM, los builders de decisión, reanálisis y argumentos son fronteras
puras; `turn_evidence_contracts.py` posee las cuatro identidades/versiones de
schema compartidas y `llm_transport.py` sólo posee el HTTP loopback/retry
acotado. Proceso, endpoint, recovery y budget monotónico permanecen en
`LlmRuntime`. Los waits de router, procesos, LLM y voz calculan su remanente
mediante una sola aritmética monotónica, que capa el redondeo IEEE por el
presupuesto original y rechaza resultados HTTP terminados después del deadline.

`VoiceEngine` publica un único job activo de cleanup antes de tocar
dispositivos. Después de esa publicación, los waits concurrentes consumen sólo
su remanente; el daemon retenido señaliza las colas, drena admisiones TTS
anteriores, cancela, restaura ducking, detiene loopback y conserva las
referencias hasta retirar los workers. Los joins se sondean en slices para
aplicar un `shutdown` tardío y detener SAPI sin depender de un worker de
micrófono colgado. El estado se sella antes de invocar observadores
potencialmente bloqueables de finalización del cleanup; `start` y `speak` no
cruzan una limpieza pendiente o fallida. La primera llamada síncrona a
`Thread.start()` conserva el límite descrito en el registro.

## Persistencia y fronteras de privacidad

- El journal usa HMAC y una clave protegida por DPAPI; integridad ausente,
  truncada o revertida falla cerrado.
- El outbox del App persiste antes de enviar y conserva identidad durante
  reinicios. `retry-outbox.v1.json` es texto plano y detecta corrupción
  accidental, pero no ofrece confidencialidad ni evidencia autenticada de
  manipulación. Los payloads privados `memory.*` sí viajan cifrados y
  autenticados.
- Stores locales pertenecen a Providers. El core y la mente no escriben
  archivos privados por caminos improvisados.
- `memory.*` no se expone al planner general.
- Texto externo de web, OCR o documentos no se reinyecta como autoridad de
  ejecución.
- Los stores de invocación de aplicaciones y audio comparten
  `InvocationStateCapacityPolicy`: toda entrada JSON superior, incluso externa,
  participa en cuota; un reparse point falla cerrado y un reemplazo descuenta
  exactamente sus bytes anteriores. Comparten el algoritmo, no una bolsa de
  capacidad: cada store tiene su propio máximo de 16.384 entradas y 64 MiB;
  una entrada de aplicaciones admite 1 MiB y una de audio, 64 KiB.

La cuota durable es exacta para el snapshot enumerado bajo los locks de BAXY y
hoy es O(n): enumera el directorio en cada evaluación porque un resize in-place
de un hijo no actualiza un token agregado confiable y los eventos de filesystem
pueden perderse. No es transaccional frente a un escritor externo concurrente.
El límite vigente admite hasta 16.384 entradas y una secuencia
reserve+intent+receipt realiza tres evaluaciones. Volverla sublineal exige un
esquema persistente, transaccional y versionado con ownership exclusivo,
migración y recovery; ese cambio de formato no está autorizado.

## Presentación y bridge

`src/Baxy.App/MainWindow.xaml.cs` crea WebView2 sin servidor HTTP.
`src/Baxy.App/FieldUiBridge.cs` y
`src/Baxy.App/Assets/field-native-bridge.js` son la frontera revisada.
Navegación externa, ventanas nuevas y ejecución directa de JSON de tools
permanecen bloqueadas.

El árbol React está sellado por ADR-0008. `AppSurfaceCatalog`,
`AppSurfaceNavigator` y `MainWindowSurfacePresenter` forman una costura WPF
separada para vistas iniciadas por el host: factories perezosas, una sola
sesión activa, rollback, foco, disposal asíncrono y retorno correlacionado al
mismo WebView. La primera consumidora real es `FieldLoadingSurface`.

El procedimiento de ambos caminos se documenta en
[REGISTRO_DE_MANTENIBILIDAD.md](REGISTRO_DE_MANTENIBILIDAD.md). En el camino
React, alterar sólo `dist/` o sólo su source no es una extensión válida. La
costura WPF sí evoluciona como source nativo independiente; añadir una ruta
desde React requiere versionar el contrato del bridge. Ningún camino expone un
proxy genérico hacia App, core o providers.

## Desarrollo y runtime registrado

`py main.py` es la entrada única de desarrollo. `Directory.Build.props`
declara una vez el TFM base, TFM Windows, RID y configuración de desarrollo.
`scripts/build_layout.py` y `scripts/build_layout.ps1` aceptan sólo propiedades
literales y segmentos seguros; rechazan XML excesivo, DTD/entities, aliases de
dispositivo Windows y valores ambiguos. Antes de compilar, el helper Python
contrasta el contrato con `TargetDir`, `TargetName`, `TargetFramework`,
`UseAppHost`, `RuntimeIdentifier`, `PublishDir` y `PublishAot` evaluados por
MSBuild.

El fingerprint cubre los seis proyectos del runtime App/Core, `Directory.*`,
`global.json`, el bridge y `src/Baxy.FieldUi/dist`; excluye `node_modules`,
`src/Baxy.Setup`, `src/baxy_mind`, `bin` y `obj`. `main.py` sólo persiste el
nuevo fingerprint después de comprobar que App y Core produjeron exactamente
los ejecutables esperados. Python se carga directamente desde `src`.

Setup conserva sus TFM/RID literales atestados y validados por pruebas propias,
porque su layout forma parte del contrato sellado de paquete. Los gates físicos
que fijan explícitamente RID/configuración preservan el alcance de su claim; no
se interpretan como una segunda configuración de desarrollo.

`scripts/test_source_quality.ps1` es la compuerta única de fuente. Sus tests
ejercen etapas, propagación de fallos y restauración de estado; PowerShell tiene
validación propia, las guardas de planner se inspeccionan estructuralmente y
Ruff cubre también los experimentos activos. El modo Full comprueba además que
producto y pruebas corresponden a sus locks Python separados.

El launcher y la aplicación respetan
`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`. El manifest registrado y los
overrides explícitos son las únicas fuentes de rutas. Los gates que necesitan
modelo usan el mismo resolver canónico o los cuatro componentes explícitos;
el resolver no usa `legacy/` ni `experiments/` como fallback. Una ruta situada
allí sólo puede entrar si el host la registró deliberadamente en el manifest o
la proporcionó como override explícito.

## Lectura complementaria

- [Guía canónica para agentes de IA](GUIA_AGENTES_IA/README.md)
- [Decisión vigente](DECISION_VIGENTE.md)
- [Registro de mantenibilidad](REGISTRO_DE_MANTENIBILIDAD.md)
- [Contrato de producto](../01_CONTRATO_PRODUCTO.md)
- [Índice documental](../00_LEEME.md)
- [ADR canónicos](../../contexto/04_arquitectura/ADR/README.md)
