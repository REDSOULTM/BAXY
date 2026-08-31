[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ModelPath,
    [Parameter(Mandatory = $true)]
    [string]$CalibrationReport,
    [string]$DestinationDirectory,
    [switch]$Replace
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'asset_resolver.ps1')

if ([string]::IsNullOrWhiteSpace($DestinationDirectory)) {
    $resolution = Resolve-BaxyAsset -Name 'wake_manifest'
    if ($resolution.Candidates.Count -eq 0) {
        throw 'No hay una ubicación declarada para instalar el modelo wake.'
    }
    $DestinationDirectory = Split-Path -Parent $resolution.Candidates[0]
}

function Resolve-ExistingFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description is missing: $Path"
    }
    return [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path)
}

function Get-RequiredProperty {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Context
    )
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) {
        throw "$Context is missing '$Name'."
    }
    return $property.Value
}

function Get-Sha256File {
    param([Parameter(Mandatory = $true)][string]$Path)

    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = New-Object IO.FileStream(
        $Path,
        [IO.FileMode]::Open,
        [IO.FileAccess]::Read,
        [IO.FileShare]::Read,
        1048576,
        [IO.FileOptions]::SequentialScan)
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace(
            '-',
            '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Require-String {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$MaximumLength = 4096
    )
    if ($Value -isnot [string]) {
        throw "$Name must be a string."
    }
    $text = $Value.Trim()
    if ([string]::IsNullOrWhiteSpace($text) -or $text.Length -gt $MaximumLength) {
        throw "$Name is empty or too long."
    }
    return $text
}

function Require-Number {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][double]$Minimum,
        [Parameter(Mandatory = $true)][double]$Maximum
    )
    if ($Value -is [bool]) {
        throw "$Name must be numeric."
    }
    try {
        $number = [Convert]::ToDouble($Value, [Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "$Name must be numeric."
    }
    if (
        [double]::IsNaN($number) -or [double]::IsInfinity($number) -or
        $number -lt $Minimum -or $number -gt $Maximum
    ) {
        throw "$Name is outside its allowed range."
    }
    return $number
}

function Require-Integer {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][int]$Minimum,
        [Parameter(Mandatory = $true)][int]$Maximum
    )
    $number = Require-Number -Value $Value -Name $Name -Minimum $Minimum -Maximum $Maximum
    if ($number -ne [math]::Truncate($number)) {
        throw "$Name must be an integer."
    }
    return [int]$number
}

function Require-True {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if ($Value -isnot [bool] -or $Value -ne $true) {
        throw "$Name must be true."
    }
}

$modelFull = Resolve-ExistingFile -Path $ModelPath -Description 'Wake-word ONNX model'
$reportFull = Resolve-ExistingFile -Path $CalibrationReport -Description 'Wake calibration report'
if (-not $modelFull.EndsWith('.onnx', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The wake-word model must be an ONNX file.'
}

try {
    $report = Get-Content -LiteralPath $reportFull -Raw -Encoding utf8 | ConvertFrom-Json
}
catch {
    throw "The wake calibration report is not valid JSON: $($_.Exception.Message)"
}

$reportSchema = Require-String -Value (Get-RequiredProperty $report 'schema' 'Calibration report') -Name 'report.schema' -MaximumLength 64
$mode = Require-String -Value (Get-RequiredProperty $report 'mode' 'Calibration report') -Name 'report.mode' -MaximumLength 32
Require-True -Value (Get-RequiredProperty $report 'promotable' 'Calibration report') -Name 'report.promotable'
Require-True -Value (Get-RequiredProperty $report 'corpus_sufficient' 'Calibration report') -Name 'report.corpus_sufficient'
if ($reportSchema -ne 'baxy-wake-corpus-gate-v3' -or $mode -ne 'acoustic') {
    throw 'The calibration report does not approve the current acoustic KWS gate.'
}

$measuredAt = Require-String -Value (Get-RequiredProperty $report 'measured_at' 'Calibration report') -Name 'report.measured_at' -MaximumLength 64
try {
    $null = [DateTimeOffset]::Parse($measuredAt, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind)
}
catch {
    throw 'The calibration report has an invalid measured_at timestamp.'
}

$reportModel = Get-RequiredProperty $report 'model' 'Calibration report'
$far = Get-RequiredProperty $report 'far' 'Calibration report'
$criteria = Get-RequiredProperty $report 'promotion_criteria' 'Calibration report'
if ($reportModel -is [string] -or $far -is [string] -or $criteria -is [string]) {
    throw 'The calibration report has invalid nested objects.'
}
if ((Require-String -Value (Get-RequiredProperty $reportModel 'backend' 'model') -Name 'model.backend' -MaximumLength 64) -ne 'livekit-wakeword') {
    throw 'The calibration report does not identify the LiveKit wake-word backend.'
}

$modelName = Require-String -Value (Get-RequiredProperty $reportModel 'model' 'model') -Name 'model.model' -MaximumLength 64
$phrase = Require-String -Value (Get-RequiredProperty $reportModel 'phrase' 'model') -Name 'model.phrase' -MaximumLength 80
$expectedHash = (Require-String -Value (Get-RequiredProperty $reportModel 'model_sha256' 'model') -Name 'model.model_sha256' -MaximumLength 64).ToLowerInvariant()
$sampleRate = Require-Integer -Value (Get-RequiredProperty $reportModel 'sample_rate' 'model') -Name 'model.sample_rate' -Minimum 16000 -Maximum 16000
$windowSamples = Require-Integer -Value (Get-RequiredProperty $reportModel 'window_samples' 'model') -Name 'model.window_samples' -Minimum 32000 -Maximum 32000
$hopSamples = Require-Integer -Value (Get-RequiredProperty $reportModel 'hop_samples' 'model') -Name 'model.hop_samples' -Minimum 256 -Maximum 32000
$threshold = Require-Number -Value (Get-RequiredProperty $reportModel 'threshold' 'model') -Name 'model.threshold' -Minimum 0.001 -Maximum 0.999
$debounceSeconds = Require-Number -Value (Get-RequiredProperty $reportModel 'debounce_seconds' 'model') -Name 'model.debounce_seconds' -Minimum 0.5 -Maximum 10.0
if ($modelName -notmatch '^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$' -or $expectedHash -notmatch '^[0-9a-f]{64}$') {
    throw 'The calibration report has invalid model identity or SHA-256.'
}

$falseRejectRate = Require-Number -Value (Get-RequiredProperty $report 'false_reject_rate' 'Calibration report') -Name 'false_reject_rate' -Minimum 0.0 -Maximum 1.0
$farMethod = Require-String -Value (Get-RequiredProperty $far 'method' 'far') -Name 'far.method' -MaximumLength 64
$farConfidence = Require-Number -Value (Get-RequiredProperty $far 'confidence' 'far') -Name 'far.confidence' -Minimum 0.95 -Maximum 0.999999
$farUpper = Require-Number -Value (Get-RequiredProperty $far 'upper_confidence_per_hour' 'far') -Name 'far.upper_confidence_per_hour' -Minimum 0.0 -Maximum 1000000.0
$maximumFrr = Require-Number -Value (Get-RequiredProperty $criteria 'false_reject_rate_lte' 'promotion_criteria') -Name 'criteria.false_reject_rate_lte' -Minimum 0.0 -Maximum 0.05
$maximumFar = Require-Number -Value (Get-RequiredProperty $criteria 'false_activations_per_hour_lte' 'promotion_criteria') -Name 'criteria.false_activations_per_hour_lte' -Minimum 0.000001 -Maximum 0.1
$requiredFarConfidence = Require-Number -Value (Get-RequiredProperty $criteria 'far_confidence_gte' 'promotion_criteria') -Name 'criteria.far_confidence_gte' -Minimum 0.95 -Maximum 0.999999
if ($farMethod -ne 'poisson_one_sided_upper_exact') {
    throw 'The calibration report does not use the required one-sided exact Poisson FAR bound.'
}
if ($falseRejectRate -gt $maximumFrr -or $farUpper -gt $maximumFar -or $farConfidence -lt $requiredFarConfidence) {
    throw 'The calibration report metrics do not satisfy its promotion criteria.'
}

$actualHash = Get-Sha256File -Path $modelFull
if ($actualHash -ne $expectedHash) {
    throw 'The ONNX SHA-256 does not match the calibrated model.'
}
$reportHash = Get-Sha256File -Path $reportFull

$destination = [IO.Path]::GetFullPath($DestinationDirectory)
$null = New-Item -ItemType Directory -Path $destination -Force
$targetModel = Join-Path $destination 'baxy.onnx'
$targetReport = Join-Path $destination 'baxy-wake-corpus-gate-v3.json'
$targetManifest = Join-Path $destination 'baxy-wakeword-v1.json'
if (
    ((Test-Path -LiteralPath $targetModel -PathType Leaf) -or
        (Test-Path -LiteralPath $targetReport -PathType Leaf) -or
        (Test-Path -LiteralPath $targetManifest -PathType Leaf)) -and
    -not $Replace.IsPresent
) {
    throw "A wake model is already installed in $destination. Pass -Replace only after preserving its calibration evidence."
}

$modelTemporary = Join-Path $destination ('.baxy-' + [Guid]::NewGuid().ToString('N') + '.onnx.tmp')
$reportTemporary = Join-Path $destination ('.baxy-' + [Guid]::NewGuid().ToString('N') + '.json.tmp')
$manifestTemporary = Join-Path $destination ('.baxy-' + [Guid]::NewGuid().ToString('N') + '.json.tmp')
try {
    Copy-Item -LiteralPath $modelFull -Destination $modelTemporary -ErrorAction Stop
    $copiedModelHash = Get-Sha256File -Path $modelTemporary
    if ($copiedModelHash -ne $actualHash) {
        throw 'The copied ONNX hash differs from the calibrated model.'
    }
    Copy-Item -LiteralPath $reportFull -Destination $reportTemporary -ErrorAction Stop
    $copiedReportHash = Get-Sha256File -Path $reportTemporary
    if ($copiedReportHash -ne $reportHash) {
        throw 'The copied calibration report hash differs from its approved evidence.'
    }

    $calibration = [ordered]@{
        schema = 'baxy-wake-calibration-v1'
        approved = $true
        gate_schema = $reportSchema
        report = 'baxy-wake-corpus-gate-v3.json'
        report_sha256 = $reportHash
        report_model_sha256 = $actualHash
        measured_at = $measuredAt
        false_reject_rate = $falseRejectRate
        far_confidence = $farConfidence
        far_upper_confidence_per_hour = $farUpper
        corpus_sufficient = $true
    }
    $manifest = [ordered]@{
        schema = 'baxy-wakeword-v1'
        model = 'baxy.onnx'
        modelName = $modelName
        phrase = $phrase
        sampleRate = $sampleRate
        windowSamples = $windowSamples
        hopSamples = $hopSamples
        threshold = $threshold
        debounceSeconds = $debounceSeconds
        sha256 = $actualHash
        calibration = $calibration
    }
    $json = $manifest | ConvertTo-Json -Depth 6
    [IO.File]::WriteAllText(
        $manifestTemporary,
        $json + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))

    # A partial replacement is fail-closed: the prior manifest's report/model
    # hashes cannot match a newly moved asset.  The manifest is moved last so
    # it becomes authoritative only after all referenced bytes are present.
    foreach ($target in @($targetModel, $targetReport, $targetManifest)) {
        if (Test-Path -LiteralPath $target -PathType Leaf) {
            Remove-Item -LiteralPath $target -Force
        }
    }
    Move-Item -LiteralPath $modelTemporary -Destination $targetModel
    Move-Item -LiteralPath $reportTemporary -Destination $targetReport
    Move-Item -LiteralPath $manifestTemporary -Destination $targetManifest
}
finally {
    foreach ($temporary in @($modelTemporary, $reportTemporary, $manifestTemporary)) {
        if (Test-Path -LiteralPath $temporary -PathType Leaf) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

[pscustomobject]@{
    installed = $true
    backend = 'livekit-wakeword'
    model = $modelName
    phrase = $phrase
    manifest = $targetManifest
    calibration_report = $targetReport
    model_sha256 = $actualHash
    calibration_report_sha256 = $reportHash
    threshold = $threshold
    far_upper_confidence_per_hour = $farUpper
    far_confidence = $farConfidence
    recall = 1.0 - $falseRejectRate
}
