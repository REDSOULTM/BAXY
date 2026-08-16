# Construcción, ejecución y entrega

Este documento separa cuatro actividades que no deben confundirse:

1. preparar un entorno de desarrollo;
2. ejecutar y validar código fuente;
3. publicar binarios NativeAOT de diagnóstico;
4. producir, empaquetar o instalar una entrega.

Una suite verde no instala el producto. Un publish local no es el paquete. Un
paquete no demuestra instalación. Una ejecución física acredita únicamente el
host, target, commit y precondiciones registrados.

## Toolchains declarados

| Área | Fuente de verdad | Contrato |
|---|---|---|
| .NET SDK | `global.json` | `10.0.100`, sin roll-forward |
| TFM común | `Directory.Build.props` | `net10.0` |
| TFM Windows | `Directory.Build.props` | `net10.0-windows10.0.19041.0` |
| Runtime | `Directory.Build.props` | `win-x64` |
| Configuración de desarrollo | `Directory.Build.props` | `Release` |
| Paquetes NuGet | `Directory.Packages.props` | versiones centrales |
| Python de producto | `pylock.runtime-win-x64.toml` | CPython 3.12, wheels y SHA-256 |
| Python de pruebas | `pylock.test-win-x64.toml` | grafo de tests con wheels y SHA-256 |
| Ruff | `requirements-quality-win-x64.lock.txt` | entorno separado del runtime |
| FieldUi | `src/Baxy.FieldUi/pnpm-lock.yaml` | dependencias JS congeladas |
| Modelos y ejecutables ML | manifest runtime + validación estructural; hashes/recibos donde cada componente los contrata | fuera del repositorio |

`Directory.Build.props` también activa nullable, analyzers, style, build
determinista y warnings como errores. Los proyectos NativeAOT usan
serialización JSON source-generated.

Limitaciones actuales que un agente debe reconocer:

- la versión de Node y la de pnpm todavía no están fijadas en `package.json`;
- NuGet usa versiones centrales, pero no `packages.lock.json`/locked mode;
- NativeAOT en Windows también depende del linker de MSVC y de un Windows SDK
  compatibles; el repositorio no fija hoy sus versiones nativas exactas;
- `scripts/bootstrap.ps1` prepara el runtime Python bloqueado y registra los
  assets ya presentes, pero no instala Node/pnpm ni descarga modelos;
- `test_source_quality.ps1` comprueba precondiciones, pero no instala nada.

Por esa dependencia nativa, un build administrado verde no reemplaza el
`dotnet publish` NativeAOT real. La exactitud A/B se reclama únicamente dentro
del entorno y toolchain declarados por la evidencia.

No ocultes esas carencias con una instalación ad hoc no documentada. Si una
tarea exige resolverlas, debe hacerlo como cambio de tooling versionado.

## Preflight del checkout

```powershell
$repo = git rev-parse --show-toplevel
Set-Location $repo
git rev-parse --show-toplevel
git status --short --branch
dotnet --version
```

La versión debe ser `10.0.100`. Los scripts buscan primero un SDK 10.0.100
por-usuario y luego `dotnet.exe` en `PATH`; no exigen que esté en una ruta
particular.

Antes de cualquier cambio:

- identifica modificaciones y archivos no rastreados;
- no ejecutes `git clean`, reset destructivo ni restore sobre trabajo ajeno;
- no uses otra copia del repositorio;
- no trates una salida ignorada como source of truth.

## Preparación local por herramienta

### Restore .NET

La compuerta canónica compila con `--no-restore`. Un checkout nuevo necesita:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" restore .\Baxy.slnx --nologo
```

Para publicar un proyecto NativeAOT debe existir además el grafo del RID:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" restore `
  .\src\Baxy.Core\Baxy.Core.csproj -r win-x64
```

No interpretes `NETSDK1047` durante `publish --no-restore` como un defecto de
código antes de comprobar ese restore RID.

### Dependencias de FieldUi

Desde un checkout sin `node_modules`:

```powershell
Push-Location .\src\Baxy.FieldUi
pnpm install --frozen-lockfile
Pop-Location
```

Esto prepara ESLint y TypeScript. No ejecuta `pnpm build` y no debe modificar
`dist/`. Revisa cualquier cambio de lock antes de continuar.

### Entorno de calidad Python

Ruff no se instala dentro del Python productivo:

```powershell
$qualityRoot = Join-Path $env:LOCALAPPDATA `
  'BAXYQuality\source-quality-v1'
py -3.12 -m venv $qualityRoot
& "$qualityRoot\Scripts\python.exe" -m pip install `
  -r .\requirements-quality-win-x64.lock.txt
$env:BAXY_QUALITY_PYTHON = "$qualityRoot\Scripts\python.exe"
```

La variable es de proceso. El gate también puede recibir
`-QualityPython <ruta>`.

### Runtime Python y modelos

En un checkout nuevo, diagnostica primero sin mutar el equipo:

```powershell
.\scripts\bootstrap.ps1 -CheckOnly
```

Cuando la tarea autoriza preparar el runtime local, ejecuta el mismo script sin
`-CheckOnly`. El bootstrap crea el entorno Python fuera del repositorio,
instala únicamente dependencias bloqueadas y registra los assets encontrados;
nunca descarga modelos.

El runtime registrado se descubre en:

```text
%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json
```

Contiene rutas explícitas al Python y a los componentes locales, junto con sus
SHA-256. Las ubicaciones candidatas de los assets pesados viven únicamente en
`assets.manifest.json`; un equipo puede anteponer candidatos con
`%LOCALAPPDATA%\BAXYRuntime\assets.local.json`.

El hecho de que el Python registrado en este notebook resida bajo un
experimento no convierte `experiments/` en fallback ni dependencia implícita.
Solo el manifest validado y los overrides explícitos habilitan esa ruta.

`scripts/bootstrap.ps1`, `scripts/setup_mind_voice.ps1` y
`scripts/register_mind_runtime.ps1` mutan el runtime local. Úsalos únicamente
cuando la tarea autoriza preparar o cambiar ese runtime. El registro valida
locks, estructura, nombres y existencia, calcula los hashes del intérprete,
GGUF, llama-server, bundle STT y wake declarado, y vuelve a leerlos antes de
promover el manifest.

Los modelos Gemma, llama.cpp, E5, Parakeet, Nemotron y wake no se copian al
repositorio ni al ZIP de producto. Sus licencias, identidades y manifests
siguen siendo parte de la precondición; router, wake y algunos recibos añaden
vínculos por hash propios.

### Activos privados

Cuando una prueba necesita corpus o muestras ignoradas, sigue
[AGENT_HANDOFF.md](../../../AGENT_HANDOFF.md). La restauración verifica hashes y
conteos:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\restore_agent_assets.ps1
```

No es necesaria para toda tarea. No imprimas filas privadas, no las añadas con
`git add -f` y no sustituyas un activo ausente por datos aproximados.

## Ejecución de desarrollo

```powershell
py main.py
```

Opciones:

```powershell
py main.py --recompilar
py main.py --cpu
py main.py --sin-mente
```

`main.py`:

1. enumera todos los procesos `Baxy` cuyo ejecutable está bajo este repositorio,
   solicita `CloseMainWindow()` a cada uno y espera hasta 15 segundos; no mata
   otros BAXY instalados ni fuerza el cierre si la ventana no coopera;
2. calcula el fingerprint del source .NET, build props, FieldUi `dist/` y
   bridge;
3. build de App y publish de Core si faltan outputs o cambió el fingerprint;
4. guarda el fingerprint bajo `%LOCALAPPDATA%\BAXY\development`;
5. llama a `scripts/run_baxy.ps1`;
6. carga `baxy_mind` directamente desde `src`.

Outputs esperados:

```text
src/Baxy.App/bin/Release/net10.0-windows10.0.19041.0/Baxy.exe
src/Baxy.Core/bin/Release/net10.0-windows10.0.19041.0/win-x64/publish/baxy-core.exe
```

No incluye Setup, empaquetado ni instalación.

## Compuerta de calidad canónica

Preflight sin stages:

```powershell
.\scripts\test_source_quality.ps1 -PreflightOnly
.\scripts\test_source_quality.ps1 -Mode Full -PreflightOnly
```

Validación rápida:

```powershell
.\scripts\test_source_quality.ps1
```

Ejecuta:

1. salud estática del source PowerShell;
2. Ruff sin caché;
3. `compileall` con cache temporal segura;
4. ESLint con cero warnings;
5. TypeScript App sin emisión;
6. TypeScript Node sin emisión;
7. `dotnet format --verify-no-changes`;
8. build Release con `--no-restore`.

Validación completa:

```powershell
.\scripts\test_source_quality.ps1 -Mode Full
```

Añade:

- todos los proyectos NUnit de `Baxy.slnx`;
- toda la suite pytest con el Python 3.12 del manifest;
- validación de locks runtime y test.

El gate preserva CWD, variables y temporales. No instala dependencias, no
regenera FieldUi y no ejecuta automáticamente gates físicos `Explicit`.
El baseline más reciente está en
[REGISTRO_DE_MANTENIBILIDAD.md](../REGISTRO_DE_MANTENIBILIDAD.md).

## Ejecución manual de suites

Útil para diagnóstico o una iteración focalizada:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" build `
  .\Baxy.slnx -c Release --nologo
& "$env:USERPROFILE\.dotnet\dotnet.exe" test `
  .\Baxy.slnx -c Release --no-build --nologo

$runtimeManifest = Join-Path $env:LOCALAPPDATA `
  'BAXYRuntime\mind-runtime-v1.json'
$runtime = Get-Content -Raw -LiteralPath $runtimeManifest |
  ConvertFrom-Json
$env:PYTHONPATH = (Resolve-Path .\src).Path
& ([string]$runtime.python) -X utf8 -m pytest `
  -p no:cacheprovider .\tests -q
```

Ejemplos focalizados:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" test `
  .\tests\Baxy.Kernel.Tests\Baxy.Kernel.Tests.csproj `
  -c Release --nologo

& ([string]$runtime.python) -X utf8 -m pytest `
  -p no:cacheprovider .\tests\test_planner.py -q
```

Una ejecución focalizada acelera el ciclo; no sustituye el gate proporcional
antes del handoff.

## Publish NativeAOT de diagnóstico

Core:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" restore `
  .\src\Baxy.Core\Baxy.Core.csproj -r win-x64
& "$env:USERPROFILE\.dotnet\dotnet.exe" publish `
  .\src\Baxy.Core\Baxy.Core.csproj `
  -c Release -r win-x64 --no-restore
```

Setup sin payload, solo para comprobar compilación AOT:

```powershell
& "$env:USERPROFILE\.dotnet\dotnet.exe" restore `
  .\src\Baxy.Setup\Baxy.Setup.csproj -r win-x64
& "$env:USERPROFILE\.dotnet\dotnet.exe" publish `
  .\src\Baxy.Setup\Baxy.Setup.csproj `
  -c Release -r win-x64 --no-restore `
  -p:BaxyDevelopmentPayloadlessPublish=true
```

El segundo comando no crea un Setup distribuible: omite deliberadamente el
paquete embebido. Ninguno instala BAXY.

## Pipeline de entrega

Solo corresponde cuando la tarea autoriza generar una entrega. Requiere HEAD
limpio, versión explícita y herramientas locales revisadas.

```powershell
$version = '<semver-autorizado>'
$shortCommit = (git rev-parse --short=12 HEAD).Trim()
$sourceRoot = (Get-Location).Path
$buildRoot = Join-Path $sourceRoot `
  "artifacts\product\build\release-$version-$shortCommit"
$packageRoot = Join-Path $sourceRoot `
  "artifacts\product\build\package-$version-$shortCommit"
$setupRoot = Join-Path $sourceRoot `
  "artifacts\setup\build\release-$version-$shortCommit"
$mpvPath = '<ruta-absoluta-a-mpv.exe>'
$vulkanPath = '<ruta-absoluta-a-vulkan-1.dll>'
$ytDlpPath = '<ruta-absoluta-a-yt-dlp.exe>'

.\scripts\build_product.ps1 `
  -Version $version `
  -OutputRoot $buildRoot `
  -MpvPath $mpvPath `
  -VulkanLoaderPath $vulkanPath `
  -YtDlpPath $ytDlpPath

.\scripts\package_product.ps1 `
  -BuildRoot $buildRoot `
  -OutputRoot $packageRoot

.\scripts\build_setup.ps1 `
  -PackageRoot $packageRoot `
  -OutputRoot $setupRoot
```

### Etapa 1: `build_product.ps1`

- exige clean worktree para release;
- crea un snapshot de Git HEAD;
- publica App self-contained single-file;
- publica Core self-contained NativeAOT;
- incorpora mpv, Vulkan loader y yt-dlp exactos;
- valida el conjunto cerrado de payload;
- escribe `build-manifest.json` canónico con hashes;
- promociona atómicamente el resultado.

La lista cerrada, el JSON canónico y las primitivas compartidas de snapshot,
hash y ZIP pertenecen a `scripts/product_build_common.ps1`.

`-AllowDirtyDevelopmentBuild` solo etiqueta un artefacto no release. No lo uses
para evadir la precondición de una entrega.

### Etapa 2: `package_product.ps1`

- revalida manifest y cada byte;
- exige Release desde snapshot HEAD salvo override de desarrollo;
- crea un ZIP determinista Stored;
- incluye `SHA256SUMS`;
- verifica orden, timestamps, entradas, CRC y digest;
- produce el ZIP y su sidecar `.sha256`.

### Etapa 3: `build_setup.ps1`

- no acepta una fuente dirty;
- vuelve a verificar paquete, manifest y sidecar;
- embebe paquete y atestación en `Baxy.Setup.exe`;
- publica Setup NativeAOT en un snapshot limpio;
- ejecuta `--verify-embedded`;
- deja `Baxy.Setup.exe`, `setup-manifest.json` y `SHA256SUMS`.

El consumidor C# no confía ciegamente en lo producido por PowerShell:
`src/Baxy.Setup/PackageContract.cs` declara el conjunto/límites exactos y
`src/Baxy.Setup/ProductPackageVerifier.cs` vuelve a comprobar ZIP, manifest,
checksums, content-id y árbol antes de instalar.

El output de Setup debe ser nuevo. Los scripts de build/producto pueden
reemplazar su destino dentro de las raíces permitidas. Nunca uses como destino
una carpeta con archivos personales.

## Instalación y lifecycle

La instalación activa vive en:

```text
%LOCALAPPDATA%\Programs\BAXY
```

Solo un `Baxy.Setup.exe` atestado debe mutarla. Su interfaz:

| Invocación | Efecto |
|---|---|
| sin argumentos | install o update |
| `--launch` | lanza la versión activa |
| `--rollback` | activa la versión anterior válida |
| `--uninstall` | desinstala conservando datos |
| `--uninstall --keep-data --quiet` | variante quiet conservadora |
| `--uninstall --purge-data --confirm-purge-data --quiet` | purge destructivo explícito |
| `--verify-embedded --evidence <ruta>` | solo verifica y escribe evidencia |

La ruta de evidencia debe ser un archivo absoluto nuevo, con directorio padre
ya existente y una cadena de directorios sin reparse points.

Códigos de salida:

| Código | Significado |
|---:|---|
| 0 | éxito |
| 30 | paquete inválido |
| 40 | seguridad/ruta/lifecycle rechazado |
| 50 | fallo de launch |
| 64 | argumentos no soportados |
| 70 | fallo inesperado |

Instalar, actualizar, hacer rollback, desinstalar o purgar son mutaciones
externas y requieren autorización. No se usan para “probar que compila”.

Los paquetes actuales están ligados por hashes y content-id, pero el producto
no promete Authenticode si la atestación declara `NotSigned` o
`authenticity=not_provided`.

## Locks y actualización de dependencias

### Python

Inputs revisados:

```text
requirements-runtime-win-x64.in
requirements-test-win-x64.in
src/baxy_mind/requirements-voice.txt
constraints-runtime-win-x64.txt
constraints-test-win-x64.txt
```

Outputs generados:

```text
pylock.runtime-win-x64.toml
pylock.test-win-x64.toml
```

Comprobar sin reescribir:

```powershell
.\scripts\lock_python_dependencies.ps1 -Profile Runtime -Check
.\scripts\lock_python_dependencies.ps1 -Profile Test -Check
```

El script pasa requirements y constraints al resolver y solo reemplaza el
`pylock.*` correspondiente. Regenerar cambia el contrato de suministro;
revisa versiones, wheels, índices y hashes. `requirements-voice.txt` no es
instalable por sí solo.

### .NET

Las versiones se editan centralmente en `Directory.Packages.props`. Después:

1. restore;
2. build/tests del consumidor;
3. Full gate;
4. publish NativeAOT si afecta App/Core/Setup;
5. documentación/ADR si cambia un componente arquitectónico.

### FieldUi

Una actualización del lock o del source visual no es rutinaria porque
ADR-0008 mantiene source y `dist` con procedencia histórica. Requiere reabrir
esa decisión, revisar el bridge, regenerar el payload de forma deliberada y
actualizar sellos/pruebas.

## Qué se edita y qué se regenera

| Ruta | Acción normal |
|---|---|
| `src/**/*.cs`, `src/baxy_mind/**/*.py` | editar como source |
| `src/Baxy.FieldUi/src` | solo con decisión visual explícita |
| `src/Baxy.FieldUi/dist` | no regenerar incidentalmente |
| `bin`, `obj`, `node_modules`, caches | regenerar, nunca editar |
| requirements y constraints Python | editar deliberadamente como inputs revisados |
| `pylock.*` | generar/comprobar con `lock_python_dependencies.ps1` |
| `pnpm-lock.yaml` | regenerar solo mediante workflow de dependencia FieldUi |
| `artifacts/product/build`, `artifacts/setup/build` | outputs reemplazables/acotados |
| evidencia JSON versionada | regenerar solo con el gate y precondiciones declarados |
| corpus/sellos | builders específicos; no edición manual |
| instalación y manifest runtime | scripts/Setup autorizados; no edición directa |

Antes de concluir, `git status --short` debe permitir explicar cada cambio.
