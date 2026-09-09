Set-StrictMode -Version Latest

$script:BaxyMindRuntimeSchema = 'baxy-mind-runtime-v1'
$script:BaxyMindRuntimeMaximumBytes = 16KB
$script:BaxyMindRuntimeProperties = @(
    'schema',
    'python',
    'python_sha256',
    'python_path',
    'gguf',
    'gguf_sha256',
    'llama_server',
    'llama_server_sha256',
    'stt_dir',
    'stt_sha256',
    'wake_manifest',
    'wake_manifest_sha256',
    'tts_model',
    'tts_sha256',
    'ngl',
    'wake_on_start'
)
$script:BaxySttRequiredFiles = @(
    'encoder.int8.onnx',
    'decoder.int8.onnx',
    'joiner.int8.onnx',
    'tokens.txt'
)

function Get-BaxySha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-BaxySttSha256 {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $lines = [Collections.Generic.List[string]]::new()
    foreach ($name in $script:BaxySttRequiredFiles) {
        $path = Join-Path $Directory $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "stt_bundle_incomplete: $path"
        }
        $lines.Add("$name`:$((Get-BaxySha256 -Path $path))")
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes(($lines -join "`n") + "`n")
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace(
            '-',
            '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Test-BaxySha256Text {
    param([AllowNull()][object]$Value)

    return $Value -is [string] -and [string]$Value -cmatch '^[0-9a-f]{64}$'
}

function Get-BaxyMindRuntimeStatus {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)

    $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    $result = [ordered]@{
        Valid = $false
        Manifest = $manifestFull
        Code = 'runtime_manifest_missing'
        Detail = "No existe el manifiesto de runtime: $manifestFull"
        Runtime = $null
    }
    if (-not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
        return [pscustomobject]$result
    }
    $info = Get-Item -LiteralPath $manifestFull -Force
    if ($info.Length -le 0 -or $info.Length -gt $script:BaxyMindRuntimeMaximumBytes) {
        $result.Code = 'runtime_manifest_size_invalid'
        $result.Detail = "El manifiesto de runtime tiene un tamano invalido: $manifestFull"
        return [pscustomobject]$result
    }
    try {
        $runtime = Get-Content -LiteralPath $manifestFull -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
    } catch {
        $result.Code = 'runtime_manifest_json_invalid'
        $result.Detail = "El manifiesto de runtime no es JSON valido: $manifestFull"
        return [pscustomobject]$result
    }
    $actualProperties = @($runtime.PSObject.Properties.Name)
    $expectedProperties = @($script:BaxyMindRuntimeProperties)
    $hasCpuAdapter = $actualProperties -ccontains 'cpu_prose_adapter'
    if ($hasCpuAdapter) { $expectedProperties += 'cpu_prose_adapter' }
    if ([string]$runtime.schema -cne $script:BaxyMindRuntimeSchema -or
        $actualProperties.Count -ne $expectedProperties.Count -or
        @($actualProperties | Where-Object {
            $expectedProperties -cnotcontains $_
        }).Count -ne 0) {
        $result.Code = 'runtime_manifest_schema_obsolete'
        $result.Detail = "El manifiesto de runtime es obsoleto o tiene campos inesperados: $manifestFull"
        return [pscustomobject]$result
    }

    try {
        $python = [IO.Path]::GetFullPath([string]$runtime.python)
        $pythonPath = [IO.Path]::GetFullPath([string]$runtime.python_path)
        $gguf = [IO.Path]::GetFullPath([string]$runtime.gguf)
        $server = [IO.Path]::GetFullPath([string]$runtime.llama_server)
        $stt = [IO.Path]::GetFullPath([string]$runtime.stt_dir)
    } catch {
        $result.Code = 'runtime_path_invalid'
        $result.Detail = "El manifiesto contiene una ruta invalida: $manifestFull"
        return [pscustomobject]$result
    }
    foreach ($entry in @(
        @('Python', $python),
        @('GGUF conversacional', $gguf),
        @('llama-server', $server)
    )) {
        if (-not (Test-Path -LiteralPath $entry[1] -PathType Leaf)) {
            $result.Code = 'runtime_asset_missing'
            $result.Detail = "$($entry[0]) no existe en la ruta registrada: $($entry[1])"
            return [pscustomobject]$result
        }
    }
    if (-not (Test-Path -LiteralPath $pythonPath -PathType Container) -or
        -not (Test-Path -LiteralPath (Join-Path $pythonPath 'baxy_mind\__main__.py') -PathType Leaf)) {
        $result.Code = 'runtime_python_path_missing'
        $result.Detail = "La mente Python no existe en la ruta registrada: $pythonPath"
        return [pscustomobject]$result
    }
    if (-not (Test-Path -LiteralPath $stt -PathType Container)) {
        $result.Code = 'runtime_asset_missing'
        $result.Detail = "Parakeet STT no existe en la ruta registrada: $stt"
        return [pscustomobject]$result
    }
    if (-not (Test-BaxySha256Text $runtime.python_sha256) -or
        -not (Test-BaxySha256Text $runtime.gguf_sha256) -or
        -not (Test-BaxySha256Text $runtime.llama_server_sha256) -or
        -not (Test-BaxySha256Text $runtime.stt_sha256)) {
        $result.Code = 'runtime_manifest_hash_missing'
        $result.Detail = "El manifiesto no contiene hashes SHA-256 validos: $manifestFull"
        return [pscustomobject]$result
    }
    $hashChecks = @(
        @('Python', $python, [string]$runtime.python_sha256),
        @('GGUF conversacional', $gguf, [string]$runtime.gguf_sha256),
        @('llama-server', $server, [string]$runtime.llama_server_sha256)
    )
    if ($hasCpuAdapter) {
        $adapter = $runtime.cpu_prose_adapter
        if ($null -eq $adapter -or $adapter -isnot [pscustomobject]) {
            $result.Code = 'runtime_cpu_adapter_invalid'
            $result.Detail = 'El adaptador CPU debe ser un objeto de perfil.'
            return [pscustomobject]$result
        }
        $fields = @('schema', 'gguf', 'gguf_sha256', 'base_gguf_sha256')
        $keys = @($adapter.PSObject.Properties.Name)
        if ($keys.Count -ne $fields.Count -or
            @($keys | Where-Object { $fields -cnotcontains $_ }).Count -ne 0 -or
            [string]$adapter.schema -cne 'baxy-cpu-prose-adapter-v1' -or
            -not (Test-BaxySha256Text $adapter.gguf_sha256) -or
            [string]$adapter.base_gguf_sha256 -cne [string]$runtime.gguf_sha256 -or
            $adapter.gguf -isnot [string] -or
            -not [IO.Path]::IsPathRooted([string]$adapter.gguf) -or
            [IO.Path]::GetExtension([string]$adapter.gguf) -ine '.gguf' -or
            -not (Test-Path -LiteralPath $adapter.gguf -PathType Leaf)) {
            $result.Code = 'runtime_cpu_adapter_invalid'
            $result.Detail = 'El adaptador CPU no corresponde al modelo registrado.'
            return [pscustomobject]$result
        }
        $hashChecks += ,@('Adaptador CPU', [string]$adapter.gguf, [string]$adapter.gguf_sha256)
    }
    foreach ($check in $hashChecks) {
        if ((Get-BaxySha256 -Path $check[1]) -cne $check[2]) {
            $result.Code = 'runtime_asset_hash_mismatch'
            $result.Detail = "$($check[0]) no coincide con el SHA-256 registrado: $($check[1])"
            return [pscustomobject]$result
        }
    }
    try {
        $sttHash = Get-BaxySttSha256 -Directory $stt
    } catch {
        $result.Code = 'runtime_asset_incomplete'
        $result.Detail = "Parakeet STT esta incompleto: $stt"
        return [pscustomobject]$result
    }
    if ($sttHash -cne [string]$runtime.stt_sha256) {
        $result.Code = 'runtime_asset_hash_mismatch'
        $result.Detail = "Parakeet STT no coincide con el SHA-256 registrado: $stt"
        return [pscustomobject]$result
    }

    $wakeOnStart = $runtime.wake_on_start -is [bool] -and [bool]$runtime.wake_on_start
    if ($runtime.wake_on_start -isnot [bool]) {
        $result.Code = 'runtime_manifest_wake_invalid'
        $result.Detail = "El estado wake del manifiesto es invalido: $manifestFull"
        return [pscustomobject]$result
    }
    if ($null -eq $runtime.wake_manifest -and $null -eq $runtime.wake_manifest_sha256) {
        if ($wakeOnStart) {
            $result.Code = 'runtime_wake_invalid'
            $result.Detail = "wake_on_start exige un manifiesto wake: $manifestFull"
            return [pscustomobject]$result
        }
    } else {
        try {
            $wake = [IO.Path]::GetFullPath([string]$runtime.wake_manifest)
        } catch {
            $result.Code = 'runtime_wake_invalid'
            $result.Detail = "La ruta wake del manifiesto es invalida: $manifestFull"
            return [pscustomobject]$result
        }
        if (-not (Test-Path -LiteralPath $wake -PathType Leaf) -or
            -not (Test-BaxySha256Text $runtime.wake_manifest_sha256) -or
            (Get-BaxySha256 -Path $wake) -cne [string]$runtime.wake_manifest_sha256) {
            $result.Code = 'runtime_wake_invalid'
            $result.Detail = "El manifiesto wake falta o no coincide con su SHA-256: $wake"
            return [pscustomobject]$result
        }
    }

    if ($null -eq $runtime.tts_model -and $null -eq $runtime.tts_sha256) {
        # Neural TTS is optional; SAPI remains the documented fallback.
    } elseif (
        $null -eq $runtime.tts_model -or
        $null -eq $runtime.tts_sha256 -or
        -not (Test-BaxySha256Text $runtime.tts_sha256)
    ) {
        $result.Code = 'runtime_tts_invalid'
        $result.Detail = "El manifiesto TTS es incompleto: $manifestFull"
        return [pscustomobject]$result
    } else {
        try {
            $tts = [IO.Path]::GetFullPath([string]$runtime.tts_model)
        } catch {
            $result.Code = 'runtime_tts_invalid'
            $result.Detail = "La ruta TTS del manifiesto es invalida: $manifestFull"
            return [pscustomobject]$result
        }
        if (-not (Test-Path -LiteralPath $tts -PathType Leaf) -or
            (Get-BaxySha256 -Path $tts) -cne [string]$runtime.tts_sha256) {
            $result.Code = 'runtime_tts_invalid'
            $result.Detail = "El modelo TTS falta o no coincide con su SHA-256: $tts"
            return [pscustomobject]$result
        }
    }
    # ConvertFrom-Json materializes ordinary JSON integers as Int64 on Windows
    # PowerShell.  Accept both integral runtime representations, while keeping
    # the manifest's narrow, explicit GPU-layer range.
    if ((($runtime.ngl -isnot [int]) -and ($runtime.ngl -isnot [long])) -or
        [long]$runtime.ngl -lt 0 -or [long]$runtime.ngl -gt 999) {
        $result.Code = 'runtime_manifest_gpu_invalid'
        $result.Detail = "El perfil GPU del manifiesto es invalido: $manifestFull"
        return [pscustomobject]$result
    }

    $result.Valid = $true
    $result.Code = 'ready'
    $result.Detail = "Runtime verificado: $manifestFull"
    $result.Runtime = $runtime
    return [pscustomobject]$result
}
