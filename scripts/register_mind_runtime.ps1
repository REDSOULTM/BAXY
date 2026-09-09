[CmdletBinding()]
param(
    [string]$Python,
    [string]$PythonPath,
    [string]$Gguf,
    [string]$LlamaServer,
    [string]$SttDirectory,
    [string]$CpuProseAdapter,
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

function Test-BaxyForeignWorktreePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    return $full -match '(?i)[\\/]BAXY[\\/]'
}

$pythonFull = Resolve-BaxyRuntimePython `
    -Candidate $Python `
    -ManifestPath $manifestPath `
    -FailurePrefix 'mind_runtime_registration_failed'
$pythonPathFull = Resolve-RequiredDirectory -Path $PythonPath -Description 'baxy_mind source root'
$ggufFull = Resolve-RequiredFile -Path $Gguf -Description 'GGUF conversacional'
$serverFull = Resolve-RequiredFile -Path $LlamaServer -Description 'llama-server'
$sttFull = Resolve-RequiredDirectory -Path $SttDirectory -Description 'Parakeet STT bundle'
foreach ($candidate in @($pythonFull, $ggufFull, $serverFull, $sttFull)) {
    if (Test-BaxyForeignWorktreePath -Path $candidate) {
        throw ("mind_runtime_registration_failed: foreign_baxy_worktree: " +
            $candidate)
    }
}

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
$installedWake = Join-Path $registrationRoot 'assets\wake\baxy-wakeword-v1.json'
if (-not $wakeResolution.Found -and (Test-Path -LiteralPath $installedWake -PathType Leaf)) {
    $wakeResolution = [pscustomobject]@{ Found = $true; Path = $installedWake }
    $wakeCandidates += $installedWake
}
$wakeDeclared = $wakeResolution.Found
$wakeOnStart = -not $NoWake.IsPresent -and $wakeDeclared
if (-not $NoWake.IsPresent -and -not $wakeDeclared) {
    Write-Warning ("No hay un modelo wake acústico; BAXY se registra " +
        "con micrófono directo. Rutas comprobadas: " +
        ($wakeCandidates -join '; '))
}

$ttsModel = $null
$ttsSha = $null
$ttsResolution = Resolve-BaxyAsset -Name 'neural_tts_voice' -RepositoryRoot $repo
foreach ($candidate in @($ttsResolution.Path) + @($ttsResolution.Candidates)) {
    if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
    $onnx = $candidate
    if (Test-Path -LiteralPath $candidate -PathType Container) {
        $named = Join-Path $candidate 'es_MX-claude-high.onnx'
        if (Test-Path -LiteralPath $named -PathType Leaf) {
            $onnx = $named
        } else {
            $found = @(Get-ChildItem -LiteralPath $candidate -Filter '*.onnx' -ErrorAction SilentlyContinue)
            if ($found.Count -eq 1) { $onnx = $found[0].FullName } else { continue }
        }
    }
    if (Test-Path -LiteralPath $onnx -PathType Leaf) {
        $ttsModel = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $onnx).Path)
        $ttsSha = Get-BaxySha256 -Path $ttsModel
        break
    }
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
    wake_manifest = if ($wakeDeclared) { $wakeResolution.Path } else { $null }
    wake_manifest_sha256 = if ($wakeDeclared) {
        Get-BaxySha256 -Path $wakeResolution.Path
    } else {
        $null
    }
    tts_model = $ttsModel
    tts_sha256 = $ttsSha
    ngl = $GpuLayers
    wake_on_start = $wakeOnStart
}
if (-not [string]::IsNullOrWhiteSpace($CpuProseAdapter)) {
    $adapterFull = Resolve-RequiredFile -Path $CpuProseAdapter -Description 'Adaptador CPU'
    if ([IO.Path]::GetExtension($adapterFull) -ine '.gguf') {
        throw 'cpu_prose_adapter_must_be_gguf'
    }
    $manifest.cpu_prose_adapter = [ordered]@{
        schema = 'baxy-cpu-prose-adapter-v1'
        gguf = $adapterFull
        gguf_sha256 = Get-BaxySha256 -Path $adapterFull
        base_gguf_sha256 = $manifest.gguf_sha256
    }
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
