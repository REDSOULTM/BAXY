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
    'ngl'
)
# Entrega 1.1.0: the pieces beside the model on this machine, each a path and its SHA-256, or both null (that piece
# stays off): property, its hash, kind, label. The App applies each where no variable names one (MindRuntimeDiscovery).
$script:BaxyMindRuntimePieces = @(
    @('renew_tts_dir', 'renew_tts_sha256', 'Container', 'Voz de BAXY (Supertonic)'),
    @('renew_wake_dir', 'renew_wake_sha256', 'Container', 'Palabra de activacion (k4)'),
    @('renew_stt_dir', 'renew_stt_sha256', 'Container', 'Reconocedor (Parakeet Ultra)'),
    @('s1_gguf', 's1_gguf_sha256', 'Leaf', 'Modelo de decision de System One'),
    @('mmproj', 'mmproj_sha256', 'Leaf', 'Proyector de vision')
)

function Get-BaxySha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

# A folder's SHA-256, as the App checks it (MindRuntimeDiscovery.DirectorySha256): of the UTF-8 lines «name:sha256», one
# per file directly in it by ordinal name, each ending in a line feed. Subfolders are not part of it.
function Get-BaxyDirectorySha256 {
    param([Parameter(Mandatory = $true)][string]$Directory)

    [string[]]$names = @([IO.Directory]::GetFiles($Directory) | ForEach-Object { [IO.Path]::GetFileName($_) })
    if ($names.Count -eq 0) {
        throw "directory_empty: $Directory"
    }
    [Array]::Sort($names, [StringComparer]::Ordinal)
    $text = [Text.StringBuilder]::new()
    foreach ($name in $names) {
        $null = $text.Append("$name`:$((Get-BaxySha256 -Path (Join-Path $Directory $name)))`n")
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes($text.ToString())
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
    foreach ($piece in $script:BaxyMindRuntimePieces) {
        foreach ($name in @($piece[0], $piece[1])) {
            if ($actualProperties -ccontains $name) { $expectedProperties += $name }
        }
    }
    if ($actualProperties -ccontains 's1_threads') { $expectedProperties += 's1_threads' }
    # LoRAs bound by hash to the registered GGUF: property, schema, label.
    $adapterContracts = @(
        @('cpu_prose_adapter', 'baxy-cpu-prose-adapter-v1', 'Adaptador CPU'),
        @('decider_adapter', 'baxy-decider-adapter-v1', 'Adaptador del decisor')
    )
    foreach ($contract in $adapterContracts) {
        if ($actualProperties -ccontains $contract[0]) { $expectedProperties += $contract[0] }
    }
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
    if (-not (Test-BaxySha256Text $runtime.python_sha256) -or
        -not (Test-BaxySha256Text $runtime.gguf_sha256) -or
        -not (Test-BaxySha256Text $runtime.llama_server_sha256)) {
        $result.Code = 'runtime_manifest_hash_missing'
        $result.Detail = "El manifiesto no contiene hashes SHA-256 validos: $manifestFull"
        return [pscustomobject]$result
    }
    $hashChecks = @(
        @('Python', $python, [string]$runtime.python_sha256),
        @('GGUF conversacional', $gguf, [string]$runtime.gguf_sha256),
        @('llama-server', $server, [string]$runtime.llama_server_sha256)
    )
    foreach ($contract in $adapterContracts) {
        if ($actualProperties -cnotcontains $contract[0]) { continue }
        $code = if ($contract[0] -ceq 'cpu_prose_adapter') { 'runtime_cpu_adapter_invalid' } else { 'runtime_decider_adapter_invalid' }
        $adapter = $runtime.($contract[0])
        if ($null -eq $adapter -or $adapter -isnot [pscustomobject]) {
            $result.Code = $code
            $result.Detail = "$($contract[2]) debe ser un objeto de perfil."
            return [pscustomobject]$result
        }
        $fields = @('schema', 'gguf', 'gguf_sha256', 'base_gguf_sha256')
        $keys = @($adapter.PSObject.Properties.Name)
        if ($keys.Count -ne $fields.Count -or
            @($keys | Where-Object { $fields -cnotcontains $_ }).Count -ne 0 -or
            [string]$adapter.schema -cne $contract[1] -or
            -not (Test-BaxySha256Text $adapter.gguf_sha256) -or
            [string]$adapter.base_gguf_sha256 -cne [string]$runtime.gguf_sha256 -or
            $adapter.gguf -isnot [string] -or
            -not [IO.Path]::IsPathRooted([string]$adapter.gguf) -or
            [IO.Path]::GetExtension([string]$adapter.gguf) -ine '.gguf' -or
            -not (Test-Path -LiteralPath $adapter.gguf -PathType Leaf)) {
            $result.Code = $code
            $result.Detail = "$($contract[2]) no corresponde al modelo registrado."
            return [pscustomobject]$result
        }
        $hashChecks += ,@($contract[2], [string]$adapter.gguf, [string]$adapter.gguf_sha256)
    }
    foreach ($check in $hashChecks) {
        if ((Get-BaxySha256 -Path $check[1]) -cne $check[2]) {
            $result.Code = 'runtime_asset_hash_mismatch'
            $result.Detail = "$($check[0]) no coincide con el SHA-256 registrado: $($check[1])"
            return [pscustomobject]$result
        }
    }
    foreach ($piece in $script:BaxyMindRuntimePieces) {
        $path = $runtime.PSObject.Properties[$piece[0]]
        $sha = $runtime.PSObject.Properties[$piece[1]]
        $path = if ($null -eq $path) { $null } else { $path.Value }
        $sha = if ($null -eq $sha) { $null } else { $sha.Value }
        if ($null -eq $path -and $null -eq $sha) { continue }
        $actual = $null
        if ($path -is [string] -and [IO.Path]::IsPathRooted($path) -and (Test-BaxySha256Text $sha) -and
            (Test-Path -LiteralPath $path -PathType $piece[2])) {
            try {
                $actual = if ($piece[2] -ceq 'Leaf') {
                    Get-BaxySha256 -Path $path
                } else {
                    Get-BaxyDirectorySha256 -Directory $path
                }
            } catch {
                $actual = $null
            }
        }
        if ($null -eq $actual -or $actual -cne [string]$sha) {
            $result.Code = 'runtime_piece_invalid'
            $result.Detail = "$($piece[3]) falta o no coincide con su SHA-256: $path"
            return [pscustomobject]$result
        }
    }
    $threads = $runtime.PSObject.Properties['s1_threads']
    if ($null -ne $threads -and $null -ne $threads.Value -and
        ((($threads.Value -isnot [int]) -and ($threads.Value -isnot [long])) -or
            [long]$threads.Value -lt 1 -or [long]$threads.Value -gt 64)) {
        $result.Code = 'runtime_piece_invalid'
        $result.Detail = "Los hilos de System One del manifiesto son invalidos: $manifestFull"
        return [pscustomobject]$result
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
