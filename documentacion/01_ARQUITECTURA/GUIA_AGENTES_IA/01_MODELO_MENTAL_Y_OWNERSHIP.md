# Modelo mental, composición y ownership

## El producto en una frase

BAXY es una aplicación local de Windows con una interfaz WPF/WebView2, un
sidecar Python opcional para lenguaje y voz, y un core .NET NativeAOT que
mantiene la autoridad determinista sobre un catálogo cerrado de operaciones,
su política, ejecución, verificación y journal.

No es un monolito ni una colección de scripts. Son procesos y capas con
autoridades deliberadamente separadas.

## Topología en runtime

```text
usuario
  │ texto / voz / confirmación
  ▼
Baxy.App.exe                         host WPF, WebView2 y lifecycle
  ├── WebView2 local
  │     ├── Baxy.FieldUi/dist        presentación histórica
  │     └── field-native-bridge.js   adaptación fetch/WebSocket → mensajes
  ├── baxy-core.exe                  autoridad determinista
  │     └── providers Windows        lecturas, efectos y postlecturas
  └── python -m baxy_mind            conversación, propuesta, planner y voz
        ├── router/encoder
        ├── llama-server local
        ├── STT/KWS/VAD/AEC
        └── SAPI
```

`Baxy.App` crea y posee los procesos hijos. Core y mente se comunican por
JSONL UTF-8 acotado; no se descubre un servicio remoto. FieldUi se sirve desde
archivos locales dentro de WebView2 y su bridge no abre un servidor HTTP.

La mente es degradable. El core no carga modelos y puede operar sin el sidecar
Python mediante las rutas deterministas que conserva la App.

## Dirección de dependencias

```text
Baxy.App ───────────────┬──────────────► Baxy.Contracts
                       ├──────────────► Baxy.Kernel
                       ├──────────────► Baxy.Providers.Windows
                       └──────────────► Baxy.Security.Windows

Baxy.Core ──────────────┬──────────────► Baxy.Contracts
                       ├──────────────► Baxy.Kernel
                       ├──────────────► Baxy.Providers.Windows
                       └──────────────► Baxy.Security.Windows

Baxy.Providers.Windows ─┬──────────────► Baxy.Contracts
                       ├──────────────► Baxy.Kernel
                       └──────────────► Baxy.Security.Windows

Baxy.Kernel ───────────────────────────► Baxy.Contracts

Baxy.Contracts, Baxy.Security.Windows y Baxy.Setup no referencian
otros proyectos BAXY.
```

La referencia de `Baxy.App` a `Baxy.Core` solo ordena el build:
`ReferenceOutputAssembly=false` y `Private=false`. App no enlaza el core como
biblioteca; lo ejecuta como proceso.

No inviertas esta dirección para ahorrar una interfaz. En particular:

- Contracts no conoce Windows, UI, providers ni modelos;
- Kernel no conoce UI, voz ni adapters concretos;
- Providers no decide conversación, riesgo ni éxito visible;
- Core no contiene heurísticas de lenguaje;
- Mind no ejecuta providers ni define operaciones;
- FieldUi no habla directamente con el core ni con el sistema operativo.

## Proyectos .NET

### `src/Baxy.Contracts`

Ownership: frontera serializada `baxy.local.v1`.

Contiene:

- DTO de hello, request, response, capabilities, planes y catálogos;
- constantes de protocolo;
- validación cerrada de contratos;
- serialización JSON source-generated en `BaxyJsonContext`;
- helpers de `ProtocolJson`.

No debe contener lógica de producto ni tipos de infraestructura. Como el core
se publica NativeAOT, un contrato nuevo debe entrar en el contexto JSON
generado y conservar validación estricta; no se debe recurrir a reflexión.

Pruebas propietarias: `tests/Baxy.Contracts.Tests`.

### `src/Baxy.Kernel`

Ownership: semántica de ejecución y autoridad independiente de Windows.

Áreas:

- `Operations/`: definición, registry, catálogo, schema, riesgo, invocation y
  outcome;
- `Planning/`: contrato y validación del DAG;
- `Policy/`: decisión de riesgo y confirmación;
- `Mission/`: `MissionEngine`, fingerprints, frontera privada y autoridad de
  confirmación;
- `Journal/`: estados, replay, capacidad, integridad HMAC y persistencia.

`ProductCatalog` es el catálogo compilado. El corte vigente tiene 170
descriptores registrados: 169 operaciones públicas y `app.status` como salud
interna. `ProductCatalog.ValidateAgainst` exige igualdad exacta entre catálogo
y handlers; una operación faltante, sobrante o con metadata divergente debe
fallar al componer el core.

Pruebas propietarias: `tests/Baxy.Kernel.Tests`.

### `src/Baxy.Security.Windows`

Ownership: primitivas de protección local específicas de Windows.

Contiene:

- DPAPI `CurrentUser`;
- claves protegidas y almacenamiento privado con política de ruta;
- envelopes AES-256-GCM ligados a purpose/AAD;
- codecs JSON protegidos;
- key store para autenticación del journal;
- comprobaciones de rutas, handles y almacenamiento privado.

No toda persistencia usa esta capa. Journal y payloads privados de `memory.*`
sí tienen autenticación/protección específica; notas, tareas, rutinas y el
outbox tienen contratos diferentes descritos en
[03_CONTRATOS_FLUJOS_Y_DATOS.md](03_CONTRATOS_FLUJOS_Y_DATOS.md).

Sus pruebas Windows viven principalmente en
`tests/Baxy.Providers.Windows.Tests`, porque ejercitan las primitivas junto a
la plataforma real.

### `src/Baxy.Providers.Windows`

Ownership: integración con Windows, aplicaciones y stores locales.

Subdirectorios:

| Área | Responsabilidad |
|---|---|
| `Applications/` | catálogo instalado, apertura y verificación de aplicaciones |
| `Audio/` | volumen, mute, lock, receipt y postlectura Core Audio |
| `Capture/` | capturas verificadas |
| `Clipboard/` | lectura/escritura acotada del portapapeles |
| `External/` | adapters de capacidades de aplicaciones y Windows |
| `Filesystem/` | sandbox y cambios de archivos |
| `Infrastructure/` | capacidad de estado y políticas de ruta |
| `Memory/` | store privado, exportación y modelos de memoria |
| `Network/` | estado, diagnóstico, IP y puertos |
| `Notes/` | store y contratos de notas |
| `Routines/` | store de rutinas |
| `SystemStatus/` | identidad, procesos, tiempo, sistema y GPU |
| `Tasks/` | tareas y recordatorios |
| `Windows/` | control de ventanas |

Un provider:

1. recibe argumentos ya tipados;
2. valida precondiciones y target;
3. aplica como máximo el efecto autorizado;
4. realiza una postlectura o genera un receipt acotado;
5. devuelve evidencia suficiente para que el handler decida honestamente.

Los adapters no comparten un único mecanismo. Según la capacidad pueden usar
Win32, COM, CDP, PowerShell, UI Automation o una API de aplicación. La garantía
común no es “API oficial”, sino target acotado, efecto conservador,
postcondición explícita y ausencia de reintento ciego después de un efecto
ambiguo.

Pruebas propietarias: `tests/Baxy.Providers.Windows.Tests`.

### `src/Baxy.Core`

Ownership: composition root y proceso de ejecución.

`Program.Main` y `Program.RunAsync`:

1. validan el data root privado y toman un mutex por perfil;
2. crean stores y providers;
3. crean todos los handlers;
4. construyen `OperationRegistry`;
5. validan el registry contra `ProductCatalog`;
6. preservan un journal v1 sin firma como archivo no confiable y abren el
   journal v2 autenticado;
7. crean `MissionEngine`;
8. emiten un `hello` con capabilities y catálogo de aplicaciones;
9. atienden una solicitud JSONL por vez;
10. serializan un outcome tipado.

El reader del Core acota cada solicitud a 1 MiB y el hello también se comprueba
antes de escribirlo. App acota las respuestas que lee. El writer de
`operation.response` todavía no rechaza el payload completo antes de
escribirlo; esa asimetría está registrada como deuda y no debe documentarse
como garantía simétrica. Core rechaza JSON inválido y falla cerrado ante
integridad inválida del journal. No presenta la interfaz, no carga el LLM y no
interpreta frases.

`Operations/` contiene handlers y narración determinista de respaldo. El
handler adapta el contrato genérico del kernel a un provider concreto; no debe
reimplementar la plataforma.

Pruebas de integración: `tests/Baxy.Integration.Tests`.

### `src/Baxy.App`

Ownership: shell de escritorio, coordinación de procesos y experiencia de
usuario.

Recorrido de arranque:

```text
App.OnStartup
  → mutex único de la aplicación
  → MainWindow
  → MainWindowViewModel
  → MainWindowSurfacePresenter
  → WebView2 + FieldUiBridge
  → CoreProcessClient
  → MindSidecarClient cuando existe runtime válido
```

Responsabilidades principales:

- lifecycle seguro de core y mente;
- verificación de identidad/hello/catálogo esperado del core hijo;
- unificación de texto y voz en `MissionInput`;
- preparación y conservación de operaciones;
- confirmaciones ligadas a la invocación;
- ejecución de DAG, checkpoints y recovery;
- outbox/retry durable;
- proyección de respuestas sin JSON visible;
- bridge tipado hacia la UI;
- navegación de superficies;
- estado de escucha, habla y cancelación.

La confianza del hello no es una firma criptográfica del mensaje. App inicia el
ejecutable local esperado, liga el proceso/PID y compara exactamente los
descriptores compilados antes de aceptar el catálogo. Usa “catálogo validado
del core hijo” al describir esta propiedad; no prometas autenticidad remota o
del editor.

Hotspots deliberados:

- `MainWindowViewModel.cs`: orquesta el turno completo;
- `FieldUiBridge.cs`: frontera de presentación;
- `LocalJsonlSidecarProcess.cs`: proceso y transporte;
- `PlannerExecutionSupport.cs`: plan y recovery;
- `DurablePlanStore.cs` y `DurableRetryStore.cs`: estado durable del shell.

Antes de añadir lógica a esos archivos, busca si la regla pertenece realmente
a Kernel, Core, Provider o Mind.

Pruebas: `tests/Baxy.Integration.Tests`.

### `src/Baxy.Setup`

Ownership: entrega e instalación transaccional independiente.

Es un ejecutable NativeAOT sin referencias a otros proyectos BAXY. Contiene:

- verificación del paquete embebido;
- rutas canónicas por usuario;
- versiones inmutables;
- activación y `current.previous`;
- lease y journal de operaciones;
- recovery;
- integración con Inicio y registro de desinstalación;
- install/update, launch, rollback y uninstall.

`Program.cs` acepta:

- sin argumentos: install o update;
- `--launch`;
- `--rollback`;
- `--uninstall`;
- las variantes quiet de keep/purge definidas por `SetupCommand`;
- `--verify-embedded --evidence <ruta>`, donde la ruta debe ser absoluta,
  nueva, tener un padre existente y no cruzar reparse points.

El formato del paquete está duplicado deliberadamente entre C# y los scripts de
build para que productor y consumidor se verifiquen mutuamente. Un cambio de
schema debe actualizar ambos lados y sus pruebas.

Pruebas propietarias: `tests/Baxy.Setup.Tests`.

## Componentes activos no .NET

### `src/baxy_mind`

Ownership: lenguaje natural, propuesta de plan y subsistema de voz local.

| Módulo | Rol |
|---|---|
| `__main__.py` | control plane, lanes seriales, dispatch, lifecycle y protocolo |
| `protocol.py` | JSONL `baxy.mind.v1` y límite de línea |
| `llm.py` | runtime LLM, decisiones, extracción, narración y validación |
| `llm_transport.py` | transporte HTTP local acotado hacia llama-server |
| `planner.py` | shortlist, DAG, schema y grounding |
| `router.py` / `router_worker.py` | encoder E5 aislado por proceso |
| `effect_intent.py` | conservación estructurada de efectos explícitos |
| `turn_evidence*.py` / `turn_probe.py` | evidencia semántica consultiva |
| `skill_registry.py` / `skills/` | instrucciones versionadas sin autoridad |
| `voice.py` | captura, VAD, STT y coordinación de turnos, TTS y ducking |
| `wakeword.py` | KWS acústico |
| `voice_aec.py` | referencia de loopback, AEC y primitiva `AudioDucker` |
| `voice_output.py` | cola/worker SAPI de TTS y cancelación |
| `corrector.py` / `phonetic_es.py` | corrección acotada de STT |
| `process_lifecycle.py` | ownership y reap de procesos/recursos |
| `time_budget.py` | deadlines monotónicos y presupuestos hijos |
| `public_turn_corpus.py` / `historical_intents.py` | fuentes de evidencia |
| `tools/` | builders offline; no runtime de ejecución |

La descripción de mensajes y variables está en
[src/baxy_mind/README.md](../../../src/baxy_mind/README.md). Las dependencias
directas están en `requirements-runtime-win-x64.in`; el grafo exacto y sus
hashes están en `pylock.runtime-win-x64.toml`.

Pruebas: archivos `tests/test_*.py`, con especialización por módulo.

### `src/Baxy.FieldUi`

Ownership: presentación React/TypeScript congelada y sus fuentes de
procedencia.

El producto carga `dist/`; Vite no corre en producción. La App inyecta
`Assets/field-native-bridge.js` antes del documento y adapta las solicitudes
históricas a `baxy.field.v1`. El bridge bloquea navegación y red no permitidas.

`ORIGIN.md` y ADR-0008 definen el sello histórico. `src/` permite comprender y
verificar la interfaz, pero ejecutar `pnpm build` reemplazaría los blobs que el
producto distribuye. Eso solo es válido si una decisión explícita reabre el
sello y se actualizan pruebas, procedencia y `dist/`.

### `main.py`

Ownership: experiencia de desarrollo.

Calcula un fingerprint de:

- proyectos .NET activos salvo Setup;
- propiedades `Directory.*`;
- `global.json`;
- `Baxy.FieldUi/dist`;
- el bridge nativo.

Si cambió ese conjunto, build de App y publish de Core; si no, reutiliza
outputs. Python se importa directamente desde `src`, por lo que no entra al
fingerprint. Setup y el pipeline de entrega tampoco pertenecen a este launcher.

## Directorios de soporte

### `tests`

Contiene cinco proyectos NUnit y la suite pytest:

| Suite | Ownership principal |
|---|---|
| `Baxy.Contracts.Tests` | wire contracts y validación |
| `Baxy.Kernel.Tests` | catálogo, plan, misión, journal y política |
| `Baxy.Providers.Windows.Tests` | stores, seguridad Windows, providers y adapters |
| `Baxy.Integration.Tests` | App↔Core, handlers, narración, recovery y E2E local |
| `Baxy.Setup.Tests` | paquete, lifecycle, paths, recovery e integración Windows |
| `test_*.py` | mind, voz, router, planner, locks, scripts, corpus y gates |

Una prueba `Explicit` o skip ambiental no equivale a pass. Consulta el motivo y
solo ejecútala si el host y la autorización corresponden.

### `scripts`

Familias:

- desarrollo y calidad: `run_baxy.ps1`, `build_layout.*`,
  `test_source_quality.ps1`;
- locks/runtime: `python_runtime_common.ps1`,
  `lock_python_dependencies.ps1`, `register_mind_runtime.ps1`,
  `setup_mind_voice.ps1`;
- entrega: `build_product.ps1`, `package_product.ps1`, `build_setup.ps1`,
  `product_build_common.ps1`;
- gates de producto/hardware: `test_*.ps1`, `run_*_gate.*`;
- corpus/evidencia: `build_*`, `audit_*`, `measure_*`, `seal_*`, `train_*`;
- restauración: `restore_agent_assets.ps1`.

Un nombre de script no concede permiso para ejecutar un efecto físico. Revisa
parámetros, precondiciones y archivos de evidencia antes.

### `artifacts`

Evidencia por dominio (`product`, `setup`, `development`, `audit`, etc.).
Puede contener resultados versionados o salidas locales ignoradas. Un JSON bajo
esta ruta no es configuración del runtime salvo que el código lo nombre
explícitamente. No uses un artefacto como input productivo por similitud de
nombre.

### `experiments`

Laboratorios y torneos. Pueden contener entornos Python y modelos auxiliares
del notebook, pero solo las piezas copiadas/promovidas explícitamente a `src/`,
locks, manifests y ADR forman parte del producto. El runtime registrado no debe
resolver código desde un experimento.

### `contexto` y `documentacion`

`contexto/04_arquitectura/ADR/` contiene decisiones aceptadas.
`documentacion/01_ARQUITECTURA/` contiene el mapa vigente y esta guía.
El resto conserva investigación, cortes e historia; debe leerse con su fecha.
`documentacion/agentes/` es un índice/export histórico, no una cola de trabajo
ni una especificación actual.

### `bootstrap` y `AGENT_HANDOFF.md`

Restauran corpus o activos privados exactos por hash. Se usan únicamente cuando
una validación necesita esos datos. No fuerces su inclusión en Git y no
reconstruyas una aproximación si falta el original.

### `legacy`

Snapshot ignorado de generaciones anteriores. Solo sirve para genealogía o
comparación. Ningún archivo activo debe importar, ejecutar o copiar
silenciosamente implementación desde `legacy/`.
