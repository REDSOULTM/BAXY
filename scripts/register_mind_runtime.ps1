# Registers the mind runtime BAXY installed starts with (%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json; the App
# verifies every hash, src\Baxy.App\MindRuntimeDiscovery.cs). Entrega 1.1.0: besides the model, the pieces of this
# machine that scripts\run_renew.cmd gave the benches (each optional; one not given stays off): BAXY's voice
# (-VoiceDirectory, Supertonic), the ear (-WakeDirectory k4, -SttDirectory Parakeet Ultra), System One's decision model
# (-SystemOneGguf, -SystemOneThreads) and the vision projector (-VisionProjector).
[CmdletBinding()]
param(
    [string]$Python,
    [string]$PythonPath,
    [string]$Gguf,
    [string]$LlamaServer,
    [string]$CpuProseAdapter,
    [string]$DeciderAdapter,
    [ValidateRange(0, 999)]
    [int]$GpuLayers = 99,
    [string]$VoiceDirectory,
    [string]$WakeDirectory,
    [string]$SttDirectory,
    [string]$SystemOneGguf,
    [ValidateRange(1, 64)]
    [int]$SystemOneThreads = 4,
    [string]$VisionProjector
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
# The pieces: property, given path, kind, the file the mind looks for in a folder (or the extension of a file), label.
$pieces = @(
    @('renew_tts', $VoiceDirectory, 'Container', 'baxy-voice.json', 'Voz de BAXY (Supertonic)'),
    @('renew_wake', $WakeDirectory, 'Container', 'config.json', 'Palabra de activacion (k4)'),
    @('renew_stt', $SttDirectory, 'Container', 'tokens.txt', 'Reconocedor (Parakeet Ultra)'),
    @('s1_gguf', $SystemOneGguf, 'Leaf', '.gguf', 'Modelo de decision de System One'),
    @('mmproj', $VisionProjector, 'Leaf', '.gguf', 'Proyector de vision')
)
$pieceFull = @{}
foreach ($piece in $pieces) {
    if ([string]::IsNullOrWhiteSpace($piece[1])) {
        $pieceFull[$piece[0]] = $null
        continue
    }
    if ($piece[2] -ceq 'Leaf') {
        $full = Resolve-RequiredFile -Path $piece[1] -Description $piece[4]
        if ([IO.Path]::GetExtension($full) -ine $piece[3]) {
            throw "$($piece[4]) must be a GGUF file: $full"
        }
    } else {
        $full = Resolve-RequiredDirectory -Path $piece[1] -Description $piece[4]
        if (-not (Test-Path -LiteralPath (Join-Path $full $piece[3]) -PathType Leaf)) {
            throw "$($piece[4]) has no $($piece[3]): $full"
        }
    }
    $pieceFull[$piece[0]] = $full
}
foreach ($candidate in @($pythonFull, $ggufFull, $serverFull) + @($pieceFull.Values | Where-Object { $null -ne $_ })) {
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
$null = Assert-BaxyRuntimeLock `
    -Python $pythonFull `
    -Repository $repo `
    -Profile Runtime `
    -FailurePrefix 'mind_runtime_registration_failed'

$manifest = [ordered]@{
    schema = 'baxy-mind-runtime-v1'
    python = $pythonFull
    python_sha256 = Get-BaxySha256 -Path $pythonFull
    python_path = $pythonPathFull
    gguf = $ggufFull
    gguf_sha256 = Get-BaxySha256 -Path $ggufFull
    llama_server = $serverFull
    llama_server_sha256 = Get-BaxySha256 -Path $serverFull
    ngl = $GpuLayers
}
foreach ($piece in $pieces) {
    $full = $pieceFull[$piece[0]]
    $path = if ($piece[2] -ceq 'Leaf') { $piece[0] } else { "$($piece[0])_dir" }
    $manifest[$path] = $full
    $manifest["$($piece[0])_sha256"] = if ($null -eq $full) {
        $null
    } elseif ($piece[2] -ceq 'Leaf') {
        Get-BaxySha256 -Path $full
    } else {
        Get-BaxyDirectorySha256 -Directory $full
    }
}
$manifest['s1_threads'] = if ($null -eq $pieceFull['s1_gguf']) { $null } else { $SystemOneThreads }
# LoRAs bound by hash to the registered GGUF (the mind turns each on only for its own role).
foreach ($bound in @(
        @('cpu_prose_adapter', 'baxy-cpu-prose-adapter-v1', 'Adaptador CPU', $CpuProseAdapter),
        @('decider_adapter', 'baxy-decider-adapter-v1', 'Adaptador del decisor', $DeciderAdapter))) {
    if ([string]::IsNullOrWhiteSpace($bound[3])) { continue }
    $adapterFull = Resolve-RequiredFile -Path $bound[3] -Description $bound[2]
    if ([IO.Path]::GetExtension($adapterFull) -ine '.gguf') {
        throw "$($bound[0])_must_be_gguf"
    }
    $manifest[$bound[0]] = [ordered]@{
        schema = $bound[1]
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
    gpu_layers = $GpuLayers
    pieces = @($pieces | Where-Object { $null -ne $pieceFull[$_[0]] } | ForEach-Object { $_[0] }) -join ', '
}
