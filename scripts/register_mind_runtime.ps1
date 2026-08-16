[CmdletBinding()]
param(
    [string]$Python,
    [string]$PythonPath,
    [string]$Gguf,
    [string]$LlamaServer,
    [string]$SttDirectory,
    [ValidateRange(0, 999)]
    [int]$GpuLayers = 99,
    [switch]$NoWake
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
. (Join-Path $PSScriptRoot 'python_runtime_common.ps1')
. (Join-Path $PSScriptRoot 'asset_resolver.ps1')
. (Join-Path $PSScriptRoot 'mind_runtime_manifest.ps1')
$localData = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::LocalApplicationData)
if ([string]::IsNullOrWhiteSpace($localData)) {
    throw 'Windows did not expose LocalApplicationData.'
}
$registrationRoot = Join-Path $localData 'BAXYRuntime'
$manifestPath = Join-Path $registrationRoot 'mind-runtime-v1.json'

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    $PythonPath = Join-Path $repo 'src'
}
if ([string]::IsNullOrWhiteSpace($Gguf)) {
    $resolution = Resolve-BaxyAsset -Name 'conversation_model' -RepositoryRoot $repo
    if (-not $resolution.Found) {
        throw ("GGUF conversacional ausente. Rutas comprobadas:`n- " +
            ($resolution.Candidates -join "`n- ") + "`n" + $resolution.Repair)
    }
    $Gguf = $resolution.Path
}
if ([string]::IsNullOrWhiteSpace($LlamaServer)) {
    $resolution = Resolve-BaxyAsset -Name 'llama_server' -RepositoryRoot $repo
    if (-not $resolution.Found) {
        throw ("llama-server ausente. Rutas comprobadas:`n- " +
            ($resolution.Candidates -join "`n- ") + "`n" + $resolution.Repair)
    }
    $LlamaServer = $resolution.Path
}
if ([string]::IsNullOrWhiteSpace($SttDirectory)) {
    $resolution = Resolve-BaxyAsset -Name 'stt_parakeet' -RepositoryRoot $repo
    if (-not $resolution.Found) {
        throw ("Parakeet STT ausente. Rutas comprobadas:`n- " +
            ($resolution.Candidates -join "`n- ") + "`n" + $resolution.Repair)
    }
    $SttDirectory = $resolution.Path
}

function Resolve-RequiredFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description is missing: $Path"
    }
    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

function Resolve-RequiredDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Description is missing: $Path"
    }
    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

$pythonFull = Resolve-BaxyRuntimePython `
    -Candidate $Python `
    -ManifestPath $manifestPath `
    -FailurePrefix 'mind_runtime_registration_failed'
$pythonPathFull = Resolve-RequiredDirectory -Path $PythonPath -Description 'baxy_mind source root'
$ggufFull = Resolve-RequiredFile -Path $Gguf -Description 'GGUF conversacional'
$serverFull = Resolve-RequiredFile -Path $LlamaServer -Description 'llama-server'
$sttFull = Resolve-RequiredDirectory -Path $SttDirectory -Description 'Parakeet STT bundle'

if (-not [string]::Equals(
        [IO.Path]::GetFileName($pythonFull),
        'python.exe',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The Python runtime must point to python.exe.'
}
if (-not (Test-Path -LiteralPath (Join-Path $pythonPathFull 'baxy_mind\__main__.py') -PathType Leaf)) {
    throw 'The Python path does not contain baxy_mind\__main__.py.'
}
if (-not $ggufFull.EndsWith('.gguf', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The conversation model must be a GGUF file.'
}
if (-not [string]::Equals(
        [IO.Path]::GetFileName($serverFull),
        'llama-server.exe',
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The llama.cpp runtime must point to llama-server.exe.'
}
foreach ($name in @('encoder.int8.onnx', 'decoder.int8.onnx', 'joiner.int8.onnx', 'tokens.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $sttFull $name) -PathType Leaf)) {
        throw "The Parakeet STT bundle is incomplete; missing $name."
    }
}
$null = Assert-BaxyRuntimeLock `
    -Python $pythonFull `
    -Repository $repo `
    -Profile Runtime `
    -FailurePrefix 'mind_runtime_registration_failed'

$wakeResolution = Resolve-BaxyAsset -Name 'wake_cascade_manifest' -RepositoryRoot $repo
$wakeCandidates = @($wakeResolution.Candidates)
if (-not $wakeResolution.Found) {
    $wakeResolution = Resolve-BaxyAsset -Name 'wake_manifest' -RepositoryRoot $repo
    $wakeCandidates += @($wakeResolution.Candidates)
}
$wakeOnStart = -not $NoWake.IsPresent -and $wakeResolution.Found
if (-not $NoWake.IsPresent -and -not $wakeOnStart) {
    Write-Warning ("No hay un modelo wake acústico calibrado; BAXY se registra " +
        "con micrófono directo. Rutas comprobadas: " +
        ($wakeCandidates -join '; '))
}

$manifest = [ordered]@{
    schema = 'baxy-mind-runtime-v1'
    python = $pythonFull
    python_sha256 = Get-BaxySha256 -Path $pythonFull
    python_path = $pythonPathFull
    gguf = $ggufFull
    gguf_sha256 = Get-BaxySha256 -Path $ggufFull
    llama_server = $serverFull
    llama_server_sha256 = Get-BaxySha256 -Path $serverFull
    stt_dir = $sttFull
    stt_sha256 = Get-BaxySttSha256 -Directory $sttFull
    wake_manifest = if ($wakeOnStart) { $wakeResolution.Path } else { $null }
    wake_manifest_sha256 = if ($wakeOnStart) {
        Get-BaxySha256 -Path $wakeResolution.Path
    } else {
        $null
    }
    ngl = $GpuLayers
    wake_on_start = $wakeOnStart
}
$temporaryPath = Join-Path $registrationRoot ('.mind-runtime-' + [Guid]::NewGuid().ToString('N') + '.tmp')
$null = New-Item -ItemType Directory -Path $registrationRoot -Force
try {
    $json = $manifest | ConvertTo-Json -Depth 3
    [IO.File]::WriteAllText($temporaryPath, $json + "`n", [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporaryPath -Destination $manifestPath -Force
}
finally {
    if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

$status = Get-BaxyMindRuntimeStatus -ManifestPath $manifestPath
if (-not $status.Valid) {
    throw "mind_runtime_registration_failed: $($status.Code): $($status.Detail)"
}

[pscustomobject]@{
    registered = $true
    manifest = $manifestPath
    wake_on_start = $wakeOnStart
    gpu_layers = $GpuLayers
}
