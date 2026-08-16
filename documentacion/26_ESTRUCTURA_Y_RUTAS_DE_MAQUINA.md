# Estructura y rutas de máquina

Estado posterior a la normalización de portabilidad iniciada el 2026-07-28.
Este documento describe la frontera vigente; las rutas concretas de un host no
son arquitectura.

## Fuente de verdad

`assets.manifest.json` es el único inventario versionado de ubicaciones
candidatas para activos externos. Declara:

- modelo conversacional GGUF y `llama-server`;
- Parakeet final y Nemotron Streaming opcional;
- manifest wake calibrado;
- voz neural y visión opcionales;
- `mpv`, Vulkan y `yt-dlp`.

Cada activo indica tipo, obligatoriedad, variable de entorno explícita, lista
ordenada de candidatos, archivos requeridos y reparación. Los literales ligados
a una unidad o convención histórica viven allí y no en consumidores.

Los tres consumidores del descriptor son:

- `scripts/asset_resolver.ps1`, usado por bootstrap, registro, instaladores y
  build;
- `src/baxy_mind/assets.py`, usado por voz, STT y wake sin alterar su
  degradación;
- `src/Baxy.App/AssetManifestDiscovery.cs`, usado por el host para diagnóstico.

El consumidor .NET no activa directamente un candidato. La activación requiere
además `mind-runtime-v1.json`, cuyas rutas y hashes valida
`MindRuntimeDiscovery` de forma fail-closed.

## Override local fuera de Git

La ruta predeterminada es:

```text
%LOCALAPPDATA%\BAXYRuntime\assets.local.json
```

Puede cambiarse con `BAXY_ASSETS_OVERRIDE`. El formato cerrado es:

```json
{
  "schema": "baxy-assets-local-v1",
  "assets": {
    "conversation_model": ["E:\\BAXY-assets\\model.gguf"],
    "llama_server": ["E:\\BAXY-assets\\llama\\llama-server.exe"],
    "stt_parakeet": ["E:\\BAXY-assets\\stt\\parakeet"]
  }
}
```

El override antepone candidatos, no cambia nombres lógicos ni contratos. No se
versiona y un nombre de activo desconocido invalida el archivo.

## Bootstrap reproducible

```powershell
.\scripts\bootstrap.ps1 -CheckOnly
.\scripts\bootstrap.ps1
```

El modo de comprobación no escribe: localiza .NET 10.0.100, enumera cada ruta
buscada y valida el registro existente. El modo completo:

1. crea CPython 3.12 bajo `%LOCALAPPDATA%\BAXYRuntime\python`;
2. fija pip e instala el lock runtime con hashes;
3. localiza activos sin descargarlos;
4. registra rutas y SHA-256;
5. vuelve a validar el manifest e importa la mente.

Si falta un modelo, termina con “no arranca”, las rutas exactas y la instrucción
de restauración. Las únicas descargas automáticas del bootstrap son
dependencias Python fijadas; los modelos nunca se descargan implícitamente.

## Registro y diagnóstico

`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` contiene rutas absolutas porque
es un registro por equipo, no un archivo portable ni versionado. Declara
SHA-256 para Python, GGUF, `llama-server`, bundle STT y wake cuando está activo.
Un campo ausente, una ruta inexistente o un hash distinto invalida todo el
registro.

`Baxy.App` valida ese archivo y todos sus SHA-256 antes de configurar o iniciar
la mente. `scripts/run_baxy.ps1` no repite esa lectura completa de los modelos:
anuncia que la comprobación está pendiente y deja a App como única autoridad
fail-closed. Si el registro no es válido, la mente no arranca y el cuerpo
determinista continúa disponible.

## Compuerta contra regresiones

`tests/test_asset_resolution.py` comprueba paridad entre Python y PowerShell,
override fuera del repositorio y ausencia de literales de máquina BAXY en
`src/`, `scripts/` y `main.py`. Los literales de fixtures, corpus históricos y
el propio descriptor no son configuración de runtime y quedan fuera de esa
compuerta. También fija que el launcher conserve sus overrides y delegue la
verificación SHA-256 en App sin anunciar activos todavía no comprobados.

## Divergencias deliberadas

- `legacy/` permanece ignorado, de solo lectura y disponible como candidato; no
  se copia ni se versiona.
- El venv histórico bajo `experiments/` no es un fallback. Bootstrap crea un
  runtime externo.
- Instaladores opcionales de Nemotron y wake conservan sus flujos explícitos;
  bootstrap no los invoca.
- Rutas de documentos históricos o fixtures de seguridad no son candidatos de
  activos y no se reescriben como parte de esta normalización.
