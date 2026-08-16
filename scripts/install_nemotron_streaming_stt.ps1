[CmdletBinding()]
param(
    [string]$Destination
)

# Instala el export ONNX int8 oficial utilizado solo para hipótesis parciales.
# Parakeet sigue siendo el bundle obligatorio y el verificador final/AEC.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'asset_resolver.ps1')

$modelName = 'sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11'
$uri = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11.tar.bz2'
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $resolution = Resolve-BaxyAsset -Name 'stt_nemotron_streaming'
    if ($resolution.Candidates.Count -eq 0) {
        throw 'No hay una ubicación declarada para instalar Nemotron Streaming.'
    }
    $Destination = Split-Path -Parent $resolution.Candidates[0]
}
$destinationFull = [IO.Path]::GetFullPath($Destination)
$target = Join-Path $destinationFull $modelName
$archive = Join-Path $destinationFull ($modelName + '.tar.bz2')
$receipt = Join-Path $destinationFull ($modelName + '.install.json')

function Test-CompleteBundle {
    param([Parameter(Mandatory = $true)][string]$Path)
    $files = @('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt')
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    foreach ($file in $files) {
        if (-not (Test-Path -LiteralPath (Join-Path $Path $file) -PathType Leaf)) {
            return $false
        }
    }
    return (Get-Item -LiteralPath (Join-Path $Path 'encoder.int8.onnx')).Length -gt 100MB
}

if (Test-Path -LiteralPath $target -PathType Container) {
    if (-not (Test-CompleteBundle -Path $target)) {
        throw "El directorio destino existe pero el bundle Nemotron está incompleto: $target"
    }
    [pscustomobject]@{
        installed = $true
        reused = $true
        model = $modelName
        directory = $target
        receipt = if (Test-Path -LiteralPath $receipt -PathType Leaf) { $receipt } else { $null }
    }
    return
}

$null = New-Item -ItemType Directory -Path $destinationFull -Force
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
    throw 'curl.exe no está disponible para descargar el export ONNX oficial.'
}

# --continue-at permite retomar una descarga interrumpida sin reemplazar datos.
& curl.exe --fail --location --retry 3 --retry-delay 2 --continue-at - --output $archive $uri
if ($LASTEXITCODE -ne 0) {
    throw "La descarga de Nemotron falló (curl exit code $LASTEXITCODE)."
}

$staging = Join-Path $destinationFull ('.nemotron-extract-' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $staging
& tar.exe -xjf $archive -C $staging
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo extraer el bundle Nemotron. Se preservó el staging para diagnóstico: $staging"
}

$extracted = Join-Path $staging $modelName
if (-not (Test-CompleteBundle -Path $extracted)) {
    throw "El archivo descargado no contiene un bundle Nemotron completo. Staging: $staging"
}

# El destino se comprobó inexistente arriba; Move-Item no sustituye un modelo
# instalado. Si hay una carrera, se aborta antes de tocar el bundle existente.
if (Test-Path -LiteralPath $target) {
    throw "El bundle apareció durante la instalación; no se reemplazó: $target"
}
Move-Item -LiteralPath $extracted -Destination $target
$archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
$metadata = [ordered]@{
    schema = 'baxy-nemotron-streaming-stt-install-v1'
    model = $modelName
    source = $uri
    archive_sha256 = $archiveHash
    installed_at_utc = [DateTime]::UtcNow.ToString('O')
    license = 'OpenMDW-1.1; verificar la tarjeta del modelo antes de redistribuir'
}
[IO.File]::WriteAllText(
    $receipt,
    ($metadata | ConvertTo-Json -Depth 3) + "`n",
    [Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    installed = $true
    reused = $false
    model = $modelName
    directory = $target
    receipt = $receipt
    archive_sha256 = $archiveHash
}
