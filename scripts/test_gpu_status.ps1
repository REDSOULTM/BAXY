param(
    [string]$CorePath,
    [string]$ArtifactPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'path_safety.ps1')
. (Join-Path $PSScriptRoot 'build_layout.ps1')

$maximumJsonLineBytes = 64 * 1024
$messageTimeoutMilliseconds = 10000
$processExitTimeoutMilliseconds = 5000
$knownFailureCodes = @('invalid_measurement', 'measurement_failed', 'unsupported')

function Assert-GateCondition {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) { throw $Message }
}

function Get-RequiredJsonProperty {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if ($Value -is [Collections.IDictionary]) {
        $keys = @($Value.Keys | Where-Object {
            [string]::Equals([string]$_, $Name, [StringComparison]::Ordinal)
        })
        if ($keys.Count -ne 1) { throw "$Label is missing $Name." }
        $dictionaryValue = $Value[$keys[0]]
        if ($dictionaryValue -is [array]) {
            Write-Output -NoEnumerate $dictionaryValue
            return
        }
        return $dictionaryValue
    }

    $property = $Value.PSObject.Properties |
        Where-Object { [string]::Equals($_.Name, $Name, [StringComparison]::Ordinal) } |
        Select-Object -First 1
    if ($null -eq $property) { throw "$Label is missing $Name." }
    if ($property.Value -is [array]) {
        Write-Output -NoEnumerate $property.Value
        return
    }
    return $property.Value
}

function Assert-ExactJsonProperties {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string[]]$Expected,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $actual = @($Value.PSObject.Properties | ForEach-Object { $_.Name })
    Assert-GateCondition ($actual.Count -eq $Expected.Count) `
        "$Label has an unexpected property count."
    foreach ($actualName in $actual) {
        $matches = @($Expected | Where-Object {
            [string]::Equals($_, $actualName, [StringComparison]::Ordinal)
        })
        Assert-GateCondition ($matches.Count -eq 1) `
            "$Label contains an unexpected property."
    }
}

function Assert-JsonArray {
    param(
        $Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Assert-GateCondition ($null -ne $Value -and $Value -is [array]) `
        "$Label must be a JSON array."
}

function Assert-SafeText {
    param(
        $Value,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$MaximumLength = 4096
    )

    Assert-GateCondition ($Value -is [string]) "$Label must be text."
    Assert-GateCondition (-not [string]::IsNullOrWhiteSpace($Value)) "$Label is empty."
    Assert-GateCondition ($Value.Length -le $MaximumLength) "$Label is too long."
    for ($index = 0; $index -lt $Value.Length; $index++) {
        Assert-GateCondition (-not [char]::IsControl($Value, $index)) `
            "$Label contains a control character."
        $category = [Globalization.CharUnicodeInfo]::GetUnicodeCategory($Value, $index)
        Assert-GateCondition ($category -ne [Globalization.UnicodeCategory]::Format) `
            "$Label contains a Unicode format character."
    }
}

function Get-DecimalNumber {
    param(
        $Value,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $isNumber = $Value -is [byte] -or
        $Value -is [sbyte] -or
        $Value -is [int16] -or
        $Value -is [uint16] -or
        $Value -is [int32] -or
        $Value -is [uint32] -or
        $Value -is [int64] -or
        $Value -is [uint64] -or
        $Value -is [single] -or
        $Value -is [double] -or
        $Value -is [decimal]
    Assert-GateCondition $isNumber "$Label must be numeric."
    if ($Value -is [single] -or $Value -is [double]) {
        $asDouble = [double]$Value
        Assert-GateCondition (-not [double]::IsNaN($asDouble)) "$Label is NaN."
        Assert-GateCondition (-not [double]::IsInfinity($asDouble)) "$Label is infinite."
    }
    try {
        return [decimal]$Value
    } catch {
        throw "$Label is outside the supported numeric range."
    }
}

function Get-BoundedInteger {
    param(
        $Value,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][decimal]$Minimum,
        [Parameter(Mandatory = $true)][decimal]$Maximum
    )

    $number = Get-DecimalNumber -Value $Value -Label $Label
    Assert-GateCondition ([decimal]::Truncate($number) -eq $number) "$Label must be an integer."
    Assert-GateCondition ($number -ge $Minimum -and $number -le $Maximum) `
        "$Label is outside its allowed range."
    return $number
}

function Read-CoreJsonMessage {
    param(
        [Parameter(Mandatory = $true)][IO.StreamReader]$Reader,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $task = $Reader.ReadLineAsync()
    try {
        if (-not $task.Wait($messageTimeoutMilliseconds)) {
            throw "Timed out waiting for $Label."
        }
        $line = $task.GetAwaiter().GetResult()
    } catch {
        throw "Unable to read $Label from the core."
    }
    if ($null -eq $line) { throw "Core exited before emitting $Label." }
    Assert-GateCondition (
        [Text.Encoding]::UTF8.GetByteCount($line) -le $maximumJsonLineBytes) `
        "$Label exceeds the JSONL byte limit."
    try {
        return $line | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "Core emitted invalid JSON for $Label."
    }
}

function Write-CoreJsonMessage {
    param(
        [Parameter(Mandatory = $true)][IO.StreamWriter]$Writer,
        [Parameter(Mandatory = $true)]$Message
    )

    $json = $Message | ConvertTo-Json -Depth 6 -Compress
    Assert-GateCondition ($json.IndexOfAny(@([char]0x0A, [char]0x0D)) -lt 0) `
        'A generated request contains a line break.'
    Assert-GateCondition (
        [Text.Encoding]::UTF8.GetByteCount($json) -le $maximumJsonLineBytes) `
        'A generated request exceeds the JSONL byte limit.'
    $Writer.WriteLine($json)
    $Writer.Flush()
}

function Assert-ResponseEnvelope {
    param(
        [Parameter(Mandatory = $true)]$Response,
        [Parameter(Mandatory = $true)]$Request,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Assert-ExactJsonProperties -Value $Response -Label $Label -Expected @(
        'type', 'requestId', 'missionId', 'invocationId', 'status', 'message',
        'verified', 'replayed', 'result', 'errorCode')
    Assert-GateCondition ((Get-RequiredJsonProperty $Response 'type' $Label) -ceq 'operation.response') `
        "$Label has the wrong type."
    foreach ($name in @('requestId', 'missionId', 'invocationId')) {
        Assert-GateCondition (
            (Get-RequiredJsonProperty $Response $name $Label) -ceq
                (Get-RequiredJsonProperty $Request $name 'request')) `
            "$Label does not preserve $name."
    }
    Assert-GateCondition ((Get-RequiredJsonProperty $Response 'status' $Label) -ceq 'completed') `
        "$Label did not complete."
    Assert-GateCondition ((Get-RequiredJsonProperty $Response 'verified' $Label) -is [bool] -and
        (Get-RequiredJsonProperty $Response 'verified' $Label)) "$Label is not verified."
    Assert-GateCondition ((Get-RequiredJsonProperty $Response 'replayed' $Label) -is [bool] -and
        -not (Get-RequiredJsonProperty $Response 'replayed' $Label)) "$Label was unexpectedly replayed."
    Assert-GateCondition ($null -eq (Get-RequiredJsonProperty $Response 'errorCode' $Label)) `
        "$Label contains an unexpected error code."
    Assert-GateCondition ($null -ne (Get-RequiredJsonProperty $Response 'result' $Label)) `
        "$Label has no result."
    $message = Get-RequiredJsonProperty $Response 'message' $Label
    Assert-SafeText -Value $message -Label "$Label message"
    Assert-GateCondition (
        $message.IndexOf('nvidia-smi', [StringComparison]::OrdinalIgnoreCase) -lt 0) `
        "$Label claims use of nvidia-smi."
}

function Read-Adapter {
    param(
        [Parameter(Mandatory = $true)]$Adapter,
        [Parameter(Mandatory = $true)][int]$ExpectedIndex,
        [Parameter(Mandatory = $true)][bool]$ExpectIdentity,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Assert-ExactJsonProperties -Value $Adapter -Label $Label -Expected @(
        'adapterIndex', 'name', 'vendorId', 'deviceId', 'dedicatedVideoMemoryBytes',
        'dedicatedSystemMemoryBytes', 'sharedSystemMemoryLimitBytes', 'usagePercent',
        'dedicatedMemoryUsageBytes', 'sharedMemoryUsageBytes')

    $adapterIndex = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'adapterIndex' $Label) `
        "$Label adapterIndex" 0 ([int]::MaxValue)
    Assert-GateCondition ($adapterIndex -eq $ExpectedIndex) "$Label has a non-contiguous index."
    $name = Get-RequiredJsonProperty $Adapter 'name' $Label
    Assert-SafeText -Value $name -Label "$Label name" -MaximumLength 256
    $vendorId = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'vendorId' $Label) `
        "$Label vendorId" 0 ([uint32]::MaxValue)
    $deviceId = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'deviceId' $Label) `
        "$Label deviceId" 0 ([uint32]::MaxValue)
    $dedicatedVideo = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'dedicatedVideoMemoryBytes' $Label) `
        "$Label dedicatedVideoMemoryBytes" 0 ([decimal]::MaxValue)
    $dedicatedSystem = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'dedicatedSystemMemoryBytes' $Label) `
        "$Label dedicatedSystemMemoryBytes" 0 ([decimal]::MaxValue)
    $sharedLimit = Get-BoundedInteger `
        (Get-RequiredJsonProperty $Adapter 'sharedSystemMemoryLimitBytes' $Label) `
        "$Label sharedSystemMemoryLimitBytes" 0 ([decimal]::MaxValue)
    $usage = Get-RequiredJsonProperty $Adapter 'usagePercent' $Label
    $dedicatedUsage = Get-RequiredJsonProperty $Adapter 'dedicatedMemoryUsageBytes' $Label
    $sharedUsage = Get-RequiredJsonProperty $Adapter 'sharedMemoryUsageBytes' $Label

    if ($ExpectIdentity) {
        Assert-GateCondition ($null -eq $usage -and $null -eq $dedicatedUsage -and
            $null -eq $sharedUsage) "$Label leaks usage into the identity scope."
        $measured = $false
    } else {
        $presenceCount = @($usage, $dedicatedUsage, $sharedUsage |
            Where-Object { $null -ne $_ }).Count
        Assert-GateCondition ($presenceCount -eq 0 -or $presenceCount -eq 3) `
            "$Label has a partial measurement tuple."
        $measured = $presenceCount -eq 3
        if ($measured) {
            $usageNumber = Get-DecimalNumber -Value $usage -Label "$Label usagePercent"
            Assert-GateCondition ($usageNumber -ge 0 -and $usageNumber -le 100) `
                "$Label usagePercent is outside 0..100."
            $dedicatedUsageNumber = Get-BoundedInteger `
                $dedicatedUsage "$Label dedicatedMemoryUsageBytes" 0 ([decimal]::MaxValue)
            $sharedUsageNumber = Get-BoundedInteger `
                $sharedUsage "$Label sharedMemoryUsageBytes" 0 ([decimal]::MaxValue)
            Assert-GateCondition ($dedicatedVideo -le ([decimal]::MaxValue - $dedicatedSystem)) `
                "$Label dedicated capacity overflows."
            Assert-GateCondition ($dedicatedUsageNumber -le ($dedicatedVideo + $dedicatedSystem)) `
                "$Label dedicated usage exceeds capacity."
            Assert-GateCondition ($sharedUsageNumber -le $sharedLimit) `
                "$Label shared usage exceeds its limit."
        }
    }

    return [pscustomobject][ordered]@{
        Index = [int]$adapterIndex
        Name = $name
        VendorId = $vendorId
        DeviceId = $deviceId
        DedicatedVideo = $dedicatedVideo
        DedicatedSystem = $dedicatedSystem
        SharedLimit = $sharedLimit
        Measured = $measured
    }
}

function Read-Failure {
    param(
        [Parameter(Mandatory = $true)]$Failure,
        [Parameter(Mandatory = $true)][string]$ExpectedScope,
        [Parameter(Mandatory = $true)][string]$Label
    )

    Assert-ExactJsonProperties -Value $Failure -Label $Label -Expected @(
        'scope', 'adapterIndex', 'errorCode')
    Assert-GateCondition ((Get-RequiredJsonProperty $Failure 'scope' $Label) -ceq $ExpectedScope) `
        "$Label has the wrong scope."
    $errorCode = Get-RequiredJsonProperty $Failure 'errorCode' $Label
    Assert-GateCondition ($errorCode -is [string] -and $knownFailureCodes -ccontains $errorCode) `
        "$Label has an unknown error code."
    $adapterIndexValue = Get-RequiredJsonProperty $Failure 'adapterIndex' $Label
    $adapterIndex = $null
    if ($null -ne $adapterIndexValue) {
        $adapterIndex = [int](Get-BoundedInteger `
            $adapterIndexValue "$Label adapterIndex" 0 ([int]::MaxValue))
    }
    return [pscustomobject][ordered]@{
        AdapterIndex = $adapterIndex
        ErrorCode = $errorCode
    }
}

function Write-SanitizedJsonAtomically {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$AllowedRoot
    )

    Assert-StrictDescendantPath -Parent $AllowedRoot -Child $Path
    $temporaryPath = Join-Path $AllowedRoot (
        '.gpu_status_gate.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    Assert-StrictDescendantPath -Parent $AllowedRoot -Child $temporaryPath
    $encoding = New-Object Text.UTF8Encoding($false, $true)
    $json = ($Value | ConvertTo-Json -Depth 6 -Compress) + [Environment]::NewLine
    $bytes = $encoding.GetBytes($json)
    $stream = $null
    try {
        $stream = New-Object IO.FileStream(
            $temporaryPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None,
            4096,
            [IO.FileOptions]::WriteThrough)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
        $stream.Dispose()
        $stream = $null

        if (Test-Path -LiteralPath $Path) {
            Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $Path) `
                'The prior GPU gate artifact disappeared during validation.'
            $item = Get-Item -LiteralPath $Path -Force
            Assert-GateCondition (-not $item.PSIsContainer) `
                'The GPU gate artifact path is a directory.'
            [IO.File]::Replace($temporaryPath, $Path, $null, $true)
        } else {
            [IO.File]::Move($temporaryPath, $Path)
        }
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        if (Test-Path -LiteralPath $temporaryPath) {
            Assert-StrictDescendantPath -Parent $AllowedRoot -Child $temporaryPath
            if (Assert-ExistingPathChainHasNoReparsePoint -Path $temporaryPath) {
                Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction Stop
            }
        }
    }
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$buildLayout = Get-BaxyBuildLayout -RepositoryRoot $root
Assert-GateCondition (
    $buildLayout.WindowsTargetFramework -ceq
        'net10.0-windows10.0.19041.0') `
    'The GPU gate is certified only for net10.0-windows10.0.19041.0.'
Assert-GateCondition ($buildLayout.RuntimeIdentifier -ceq 'win-x64') `
    'The GPU gate is certified only for win-x64.'
Assert-GateCondition ($buildLayout.DevelopmentConfiguration -ceq 'Release') `
    'The GPU gate is certified only for Release builds.'
$defaultNativeAotCore = $buildLayout.CorePublishExecutable
$artifactRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product'))
if ([string]::IsNullOrWhiteSpace($ArtifactPath)) {
    $ArtifactPath = Join-Path $artifactRoot 'gpu_status_gate.json'
}
$ArtifactPath = [IO.Path]::GetFullPath($ArtifactPath)
Assert-StrictDescendantPath -Parent $artifactRoot -Child $ArtifactPath
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $artifactRoot
if (-not (Test-Path -LiteralPath $artifactRoot -PathType Container)) {
    throw 'The product artifact root does not exist.'
}
if (Test-Path -LiteralPath $ArtifactPath) {
    Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $ArtifactPath) `
        'The prior GPU gate artifact disappeared during validation.'
    $priorArtifact = Get-Item -LiteralPath $ArtifactPath -Force
    Assert-GateCondition (-not $priorArtifact.PSIsContainer) `
        'The GPU gate artifact path is a directory.'
    Remove-Item -LiteralPath $ArtifactPath -Force -ErrorAction Stop
}

if ([string]::IsNullOrWhiteSpace($CorePath)) {
    $CorePath = $defaultNativeAotCore
}
$CorePath = [IO.Path]::GetFullPath($CorePath)
Assert-StrictDescendantPath -Parent $root -Child $CorePath
Assert-GateCondition ([string]::Equals(
        [IO.Path]::GetFileName($CorePath),
        'baxy-core.exe',
        [StringComparison]::OrdinalIgnoreCase)) `
    'The GPU gate only accepts baxy-core.exe.'
Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $CorePath) `
    'The NativeAOT core does not exist.'
Assert-GateCondition (Test-Path -LiteralPath $CorePath -PathType Leaf) `
    'The NativeAOT core is not a file.'

$coreItem = Get-Item -LiteralPath $CorePath -Force
$coreBytesBefore = [long]$coreItem.Length
Assert-GateCondition ($coreBytesBefore -gt 0) 'The NativeAOT core is empty.'
$coreHashBefore = (Get-FileHash -LiteralPath $CorePath -Algorithm SHA256).Hash.ToLowerInvariant()

$coreDirectory = [IO.Path]::GetDirectoryName($CorePath)
foreach ($managedCompanion in @('baxy-core.dll', 'baxy-core.runtimeconfig.json')) {
    Assert-GateCondition (-not (Test-Path -LiteralPath (Join-Path $coreDirectory $managedCompanion))) `
        'The selected core has managed deployment companions and is not an authorized NativeAOT payload.'
}
$isCanonicalPublish = [string]::Equals(
    $CorePath,
    $defaultNativeAotCore,
    [StringComparison]::OrdinalIgnoreCase)
if (-not $isCanonicalPublish) {
    $allowedBuildRoot = [IO.Path]::GetFullPath((Join-Path $root 'artifacts\product\build'))
    $buildPrefix = $allowedBuildRoot.TrimEnd(
        [IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    Assert-GateCondition ($CorePath.StartsWith($buildPrefix, [StringComparison]::OrdinalIgnoreCase)) `
        'The selected core is outside an authorized NativeAOT publish or product build.'
    Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $CorePath

    $packagedBuildRoot = [IO.Directory]::GetParent(
        [IO.Directory]::GetParent(
            [IO.Directory]::GetParent($CorePath).FullName).FullName).FullName
    Assert-StrictDescendantPath -Parent $allowedBuildRoot -Child $packagedBuildRoot
    $expectedPackagedCore = [IO.Path]::GetFullPath((Join-Path $packagedBuildRoot `
        'app\core\baxy-core.exe'))
    Assert-GateCondition ([string]::Equals(
            $CorePath,
            $expectedPackagedCore,
            [StringComparison]::OrdinalIgnoreCase)) `
        'The selected product core is not at app/core/baxy-core.exe.'

    $buildManifestPath = [IO.Path]::GetFullPath((Join-Path $packagedBuildRoot `
        'build-manifest.json'))
    Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $buildManifestPath) `
        'The selected product core has no safe build manifest.'
    Assert-GateCondition (Test-Path -LiteralPath $buildManifestPath -PathType Leaf) `
        'The selected product core has no build manifest.'
    try {
        $buildManifest = Get-Content -Raw -LiteralPath $buildManifestPath |
            ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw 'The selected product core has an invalid build manifest.'
    }
    Assert-GateCondition ($buildManifest.deployment.core -ceq 'native_aot_self_contained') `
        'The build manifest does not attest a NativeAOT core.'
    Assert-GateCondition ($buildManifest.runtime -ceq 'win-x64') `
        'The build manifest does not attest win-x64.'
    $manifestedCore = @($buildManifest.files | Where-Object {
        $_.path -ceq 'core/baxy-core.exe'
    })
    Assert-GateCondition ($manifestedCore.Count -eq 1) `
        'The build manifest does not contain exactly one core payload.'
    Assert-GateCondition ([int64]$manifestedCore[0].bytes -eq $coreBytesBefore -and
        [string]$manifestedCore[0].sha256 -ceq $coreHashBefore) `
        'The selected product core does not match its NativeAOT build manifest.'
}

$localApplicationData = [Environment]::GetFolderPath(
    [Environment+SpecialFolder]::LocalApplicationData,
    [Environment+SpecialFolderOption]::DoNotVerify)
Assert-GateCondition (-not [string]::IsNullOrWhiteSpace($localApplicationData)) `
    'Windows did not expose LocalApplicationData.'
$localApplicationData = [IO.Path]::GetFullPath($localApplicationData)
$allowedDataRoot = [IO.Path]::GetFullPath((Join-Path $localApplicationData 'BAXY'))
Assert-StrictDescendantPath -Parent $localApplicationData -Child $allowedDataRoot
$null = Assert-ExistingPathChainHasNoReparsePoint -Path $allowedDataRoot
if (-not (Test-Path -LiteralPath $allowedDataRoot -PathType Container)) {
    New-Item -ItemType Directory -Path $allowedDataRoot -Force | Out-Null
}
Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $allowedDataRoot) `
    'The private BAXY data root is unsafe.'

$dataRoot = [IO.Path]::GetFullPath((Join-Path $allowedDataRoot (
    'gpu-status-gate-' + [Guid]::NewGuid().ToString('N'))))
Assert-StrictDescendantPath -Parent $allowedDataRoot -Child $dataRoot
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null
Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $dataRoot) `
    'The private GPU gate data root is unsafe.'
Assert-GateCondition (@(Get-ChildItem -LiteralPath $dataRoot -Force).Count -eq 0) `
    'The private GPU gate data root was not fresh before core startup.'

$process = $null
$stderrTask = $null
$summary = $null
try {
    $startInfo = New-Object Diagnostics.ProcessStartInfo
    $startInfo.FileName = $CorePath
    $startInfo.WorkingDirectory = [IO.Path]::GetDirectoryName($CorePath)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['BAXY_DATA_DIR'] = $dataRoot
    Assert-GateCondition (
        $startInfo.EnvironmentVariables['BAXY_DATA_DIR'] -ceq $dataRoot) `
        'The NativeAOT core was not bound to the isolated GPU gate data root.'

    $process = New-Object Diagnostics.Process
    $process.StartInfo = $startInfo
    Assert-GateCondition ($process.Start()) 'The NativeAOT core did not start.'
    $stderrTask = $process.StandardError.ReadToEndAsync()

    $hello = Read-CoreJsonMessage -Reader $process.StandardOutput -Label 'hello'
    Assert-ExactJsonProperties -Value $hello -Label 'hello' -Expected @(
        'type', 'protocol', 'coreVersion', 'pid', 'capabilities')
    Assert-GateCondition ((Get-RequiredJsonProperty $hello 'type' 'hello') -ceq 'hello') `
        'Core emitted the wrong greeting type.'
    Assert-GateCondition ((Get-RequiredJsonProperty $hello 'protocol' 'hello') -ceq 'baxy.local.v1') `
        'Core emitted the wrong protocol version.'
    Assert-SafeText (Get-RequiredJsonProperty $hello 'coreVersion' 'hello') 'hello coreVersion' 64
    $helloPid = Get-BoundedInteger `
        (Get-RequiredJsonProperty $hello 'pid' 'hello') 'hello pid' 1 ([int]::MaxValue)
    Assert-GateCondition ($helloPid -eq $process.Id) 'Core greeting PID does not match its process.'
    foreach ($privateStatePath in @(
        (Join-Path $dataRoot 'journal\missions.jsonl'),
        (Join-Path $dataRoot 'journal\missions.jsonl.anchor'),
        (Join-Path $dataRoot 'security\journal-hmac.v2.key')
    )) {
        $privateStatePath = [IO.Path]::GetFullPath($privateStatePath)
        Assert-StrictDescendantPath -Parent $dataRoot -Child $privateStatePath
        Assert-GateCondition (Assert-ExistingPathChainHasNoReparsePoint -Path $privateStatePath) `
            'Core startup did not create safe authenticated state in the isolated data root.'
        Assert-GateCondition (Test-Path -LiteralPath $privateStatePath -PathType Leaf) `
            'Core startup did not use the isolated GPU gate data root.'
    }
    $capabilitiesValue = Get-RequiredJsonProperty $hello 'capabilities' 'hello'
    Assert-JsonArray -Value $capabilitiesValue -Label 'hello capabilities'
    $capabilities = @($capabilitiesValue)
    Assert-GateCondition ($capabilities.Count -eq 22) 'Core does not expose exactly 22 operations.'
    $capabilityNames = New-Object 'System.Collections.Generic.HashSet[string]' `
        ([StringComparer]::Ordinal)
    $audioStatusCount = 0
    $systemStatusCount = 0
    foreach ($capability in $capabilities) {
        Assert-ExactJsonProperties -Value $capability -Label 'capability' -Expected @(
            'name', 'risk', 'description')
        $name = Get-RequiredJsonProperty $capability 'name' 'capability'
        $risk = Get-RequiredJsonProperty $capability 'risk' 'capability'
        Assert-SafeText $name 'capability name' 96
        Assert-SafeText $risk 'capability risk' 64
        Assert-SafeText (Get-RequiredJsonProperty $capability 'description' 'capability') `
            'capability description' 512
        Assert-GateCondition ($capabilityNames.Add($name)) 'Core exposes a duplicate capability.'
        if ($name -ceq 'audio.status') {
            $audioStatusCount++
            Assert-GateCondition ($risk -ceq 'read_only') 'audio.status has the wrong risk.'
        }
        if ($name -ceq 'system.status') {
            $systemStatusCount++
            Assert-GateCondition ($risk -ceq 'read_only') 'system.status has the wrong risk.'
        }
    }
    Assert-GateCondition ($audioStatusCount -eq 1) 'Core must expose audio.status exactly once.'
    Assert-GateCondition ($systemStatusCount -eq 1) 'Core must expose system.status exactly once.'

    # Windows PowerShell 5.1 writes a UTF-8 BOM through Process.StandardInput.
    # Send one deliberately malformed warmup line, require the bounded protocol
    # error, and then prove that the same native process recovers for real work.
    $process.StandardInput.WriteLine([string]::Empty)
    $process.StandardInput.Flush()
    $warmup = Read-CoreJsonMessage -Reader $process.StandardOutput -Label 'transport warmup'
    Assert-ExactJsonProperties -Value $warmup -Label 'transport warmup' -Expected @(
        'type', 'errorCode', 'message')
    Assert-GateCondition ((Get-RequiredJsonProperty $warmup 'type' 'transport warmup') -ceq
        'protocol.error') 'Transport warmup did not produce protocol.error.'
    Assert-GateCondition ((Get-RequiredJsonProperty $warmup 'errorCode' 'transport warmup') -ceq
        'malformed_json') 'Transport warmup produced the wrong error.'

    $missionId = [Guid]::NewGuid().ToString('D')
    $identityRequest = [ordered]@{
        type = 'operation.request'
        requestId = [Guid]::NewGuid().ToString('D')
        missionId = $missionId
        invocationId = [Guid]::NewGuid().ToString('D')
        operation = 'system.status'
        arguments = [ordered]@{ scope = 'gpu_identity' }
    }
    $usageRequest = [ordered]@{
        type = 'operation.request'
        requestId = [Guid]::NewGuid().ToString('D')
        missionId = $missionId
        invocationId = [Guid]::NewGuid().ToString('D')
        operation = 'system.status'
        arguments = [ordered]@{ scope = 'gpu_usage' }
    }

    Write-CoreJsonMessage -Writer $process.StandardInput -Message $identityRequest
    $identityResponse = Read-CoreJsonMessage -Reader $process.StandardOutput -Label 'GPU identity response'
    Assert-ResponseEnvelope $identityResponse $identityRequest 'GPU identity response'
    Write-CoreJsonMessage -Writer $process.StandardInput -Message $usageRequest
    $usageResponse = Read-CoreJsonMessage -Reader $process.StandardOutput -Label 'GPU usage response'
    Assert-ResponseEnvelope $usageResponse $usageRequest 'GPU usage response'

    $identityMessage = Get-RequiredJsonProperty $identityResponse 'message' 'GPU identity response'
    Assert-GateCondition ($identityMessage.IndexOf('VRAM', [StringComparison]::Ordinal) -ge 0) `
        'GPU identity message does not explain VRAM.'
    Assert-GateCondition (
        $identityMessage.IndexOf('RAM reservada', [StringComparison]::Ordinal) -ge 0) `
        'GPU identity message does not explain reserved RAM.'
    $usageMessage = Get-RequiredJsonProperty $usageResponse 'message' 'GPU usage response'
    Assert-GateCondition ($usageMessage.IndexOf('VRAM', [StringComparison]::Ordinal) -ge 0) `
        'GPU usage message does not explain VRAM.'
    Assert-GateCondition (
        $usageMessage.IndexOf('RAM reservada', [StringComparison]::Ordinal) -ge 0) `
        'GPU usage message does not explain reserved RAM.'

    $identityResult = Get-RequiredJsonProperty $identityResponse 'result' 'GPU identity response'
    $usageResult = Get-RequiredJsonProperty $usageResponse 'result' 'GPU usage response'
    foreach ($resultCase in @(
        [pscustomobject]@{ Value = $identityResult; Scope = 'gpu_identity'; Label = 'GPU identity result' },
        [pscustomobject]@{ Value = $usageResult; Scope = 'gpu_usage'; Label = 'GPU usage result' })) {
        Assert-ExactJsonProperties -Value $resultCase.Value -Label $resultCase.Label -Expected @(
            'scope', 'adapters', 'failures')
        Assert-GateCondition ((Get-RequiredJsonProperty $resultCase.Value 'scope' $resultCase.Label) `
            -ceq $resultCase.Scope) "$($resultCase.Label) has the wrong scope."
        Assert-JsonArray (Get-RequiredJsonProperty $resultCase.Value 'adapters' $resultCase.Label) `
            "$($resultCase.Label) adapters"
        Assert-JsonArray (Get-RequiredJsonProperty $resultCase.Value 'failures' $resultCase.Label) `
            "$($resultCase.Label) failures"
    }

    $identityAdapterValuesRaw = Get-RequiredJsonProperty `
        $identityResult 'adapters' 'GPU identity result'
    $usageAdapterValuesRaw = Get-RequiredJsonProperty `
        $usageResult 'adapters' 'GPU usage result'
    $identityAdapterValues = @($identityAdapterValuesRaw)
    $usageAdapterValues = @($usageAdapterValuesRaw)
    Assert-GateCondition ($identityAdapterValues.Count -ge 1 -and $identityAdapterValues.Count -le 64) `
        'GPU identity returned an unsupported adapter count.'
    Assert-GateCondition ($usageAdapterValues.Count -eq $identityAdapterValues.Count) `
        'GPU identity and usage adapter counts differ.'

    $identityAdapters = @()
    $usageAdapters = @()
    for ($index = 0; $index -lt $identityAdapterValues.Count; $index++) {
        $identityAdapter = Read-Adapter $identityAdapterValues[$index] $index $true `
            "GPU identity adapter $index"
        $usageAdapter = Read-Adapter $usageAdapterValues[$index] $index $false `
            "GPU usage adapter $index"
        foreach ($propertyName in @(
            'Index', 'Name', 'VendorId', 'DeviceId', 'DedicatedVideo',
            'DedicatedSystem', 'SharedLimit')) {
            Assert-GateCondition (
                $identityAdapter.$propertyName -ceq $usageAdapter.$propertyName) `
                "GPU adapter $index changed between identity and usage snapshots."
        }
        $identityAdapters += ,$identityAdapter
        $usageAdapters += ,$usageAdapter
    }

    $identityFailureValuesRaw = Get-RequiredJsonProperty `
        $identityResult 'failures' 'GPU identity result'
    $identityFailureValues = @($identityFailureValuesRaw)
    Assert-GateCondition ($identityFailureValues.Count -eq 0) `
        'GPU identity contains failures despite having adapters.'
    $usageFailureValuesRaw = Get-RequiredJsonProperty `
        $usageResult 'failures' 'GPU usage result'
    $usageFailureValues = @($usageFailureValuesRaw)
    $usageFailures = @()
    for ($index = 0; $index -lt $usageFailureValues.Count; $index++) {
        $usageFailures += ,(Read-Failure $usageFailureValues[$index] 'gpu_usage' `
            "GPU usage failure $index")
    }

    $measuredAdapters = @($usageAdapters | Where-Object { $_.Measured })
    $unmeasuredAdapters = @($usageAdapters | Where-Object { -not $_.Measured })
    $globalFailures = @($usageFailures | Where-Object { $null -eq $_.AdapterIndex })
    $indexedFailures = @($usageFailures | Where-Object { $null -ne $_.AdapterIndex })
    Assert-GateCondition ($measuredAdapters.Count -ge 1) `
        'This physical gate requires at least one measured GPU adapter.'
    Assert-GateCondition ($globalFailures.Count -eq 0) `
        'A partial GPU snapshot must not contain a global failure.'
    Assert-GateCondition ($indexedFailures.Count -eq $unmeasuredAdapters.Count) `
        'Unmeasured GPU adapters do not have a one-to-one indexed failure.'
    foreach ($unmeasured in $unmeasuredAdapters) {
        $matches = @($indexedFailures | Where-Object { $_.AdapterIndex -eq $unmeasured.Index })
        Assert-GateCondition ($matches.Count -eq 1) `
            'An unmeasured GPU adapter lacks exactly one indexed failure.'
    }
    foreach ($measured in $measuredAdapters) {
        $matches = @($indexedFailures | Where-Object { $_.AdapterIndex -eq $measured.Index })
        Assert-GateCondition ($matches.Count -eq 0) `
            'A measured GPU adapter also contains an indexed failure.'
    }

    $process.StandardInput.Close()
    if (-not $process.WaitForExit($processExitTimeoutMilliseconds)) {
        $process.Kill()
        throw 'NativeAOT core did not exit after stdin closed.'
    }
    try {
        if (-not $stderrTask.Wait($processExitTimeoutMilliseconds)) {
            throw 'Timed out draining NativeAOT core stderr.'
        }
        $stderr = $stderrTask.GetAwaiter().GetResult()
    } catch {
        throw 'Unable to drain NativeAOT core stderr.'
    }
    $remainingStdout = $process.StandardOutput.ReadToEnd()
    Assert-GateCondition ([string]::IsNullOrEmpty($remainingStdout)) `
        'NativeAOT core emitted unexpected trailing stdout.'
    Assert-GateCondition ([string]::IsNullOrEmpty($stderr)) `
        'NativeAOT core emitted stderr.'
    Assert-GateCondition ($process.ExitCode -eq 0) 'NativeAOT core exited with an error.'

    $coreItemAfter = Get-Item -LiteralPath $CorePath -Force
    $coreHashAfter = (Get-FileHash -LiteralPath $CorePath -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-GateCondition ($coreItemAfter.Length -eq $coreBytesBefore -and
        $coreHashAfter -ceq $coreHashBefore) 'NativeAOT core changed during the gate.'

    $failureCodes = @($usageFailures | ForEach-Object { $_.ErrorCode } |
        Sort-Object -Unique)
    $summary = [ordered]@{
        schema = 'baxy-gpu-status-gate-v1'
        status = 'passed'
        runtime = 'win-x64-nativeaot'
        core_bytes = $coreBytesBefore
        core_sha256 = $coreHashBefore
        operations = $capabilities.Count
        identity_adapters = $identityAdapters.Count
        usage_adapters = $usageAdapters.Count
        measured_adapters = $measuredAdapters.Count
        unavailable_adapters = $unmeasuredAdapters.Count
        indexed_failures = $indexedFailures.Count
        global_failures = $globalFailures.Count
        failure_codes = $failureCodes
        transport_warmup = 'malformed_json'
        stderr_bytes = 0
        exit_code = $process.ExitCode
    }
} finally {
    if ($null -ne $process) {
        try { $process.StandardInput.Close() } catch { }
        if (-not $process.HasExited) {
            $process.Kill()
            Assert-GateCondition ($process.WaitForExit($processExitTimeoutMilliseconds)) `
                'NativeAOT core survived fallback termination.'
        }
        $process.Dispose()
    }
    Remove-TreeFailClosed -AllowedRoot $allowedDataRoot -Target $dataRoot
}

Assert-GateCondition ($null -ne $summary) 'GPU gate did not produce a summary.'
Write-SanitizedJsonAtomically -Path $ArtifactPath -Value $summary -AllowedRoot $artifactRoot
$summary | ConvertTo-Json -Depth 6 -Compress
