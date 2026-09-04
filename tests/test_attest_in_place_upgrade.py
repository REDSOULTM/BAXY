from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "attest_in_place_upgrade.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


def ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def run_powershell(
    source: str,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    if POWERSHELL is None:
        raise unittest.SkipTest("Windows PowerShell is unavailable")
    encoded = base64.b64encode(source.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def dot_source_script(
    *,
    confirm: bool = False,
    continuation: bool = False,
) -> str:
    arguments = [
        "-CandidateSetup 'C:\\fixture\\Baxy.Setup.exe'",
        "-ExpectedCurrentVersion '1.0.7'",
        "-ExpectedInitialPreviousVersion '1.0.6'",
        "-CandidateVersion '1.0.8'",
        "-EvidencePath 'C:\\fixture\\unused.json'",
    ]
    if continuation:
        arguments.extend(
            [
                "-ExpectedCandidateCommit ('a' * 40)",
                "-PriorFailureEvidencePath 'C:\\fixture\\prior.json'",
                "-ExpectedPriorFailureEvidenceSha256 ('b' * 64)",
                "-ContinueRecoveredCandidate",
            ]
        )
    if confirm:
        arguments.append("-ConfirmInPlaceUpgrade")
    return f". {ps_quote(SCRIPT)} `\n    " + " `\n    ".join(arguments)


class AttestInPlaceUpgradeSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_script_has_no_powershell_parser_errors(self) -> None:
        command = f"""
$tokens = $null
$errors = $null
[Management.Automation.Language.Parser]::ParseFile(
    {ps_quote(SCRIPT)}, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -ne 0) {{
    $errors | ForEach-Object {{
        "$($_.Extent.StartLineNumber):$($_.Extent.StartColumnNumber):$($_.Message)"
    }} | Write-Error
    exit 1
}}
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_requires_explicit_versions_evidence_and_confirmation(self) -> None:
        for required in (
            "[string]$CandidateSetup",
            "[string]$ExpectedCurrentVersion",
            "[string]$ExpectedInitialPreviousVersion",
            "[string]$CandidateVersion",
            "[string]$EvidencePath",
            "[int]$TimeoutSeconds = 180",
            "[switch]$ConfirmInPlaceUpgrade",
            "Refusing an in-place lifecycle without -ConfirmInPlaceUpgrade.",
            "Compare-SemVerPrecedence",
        ):
            self.assertIn(required, self.source)

    def test_recovery_continuation_contract_is_explicitly_pinned(self) -> None:
        for required in (
            "[string]$ExpectedCandidateCommit",
            "[string]$PriorFailureEvidencePath",
            "[string]$ExpectedPriorFailureEvidenceSha256",
            "[switch]$ContinueRecoveredCandidate",
            "Read-RecoveredCandidateEvidence",
            "git -C $source.root merge-base --is-ancestor",
            "Assert-VersionInventoryEqual",
            "baxy-in-place-upgrade-continuation-attestation-v1",
            "passed_with_recovery_continuation",
        ):
            self.assertIn(required, self.source)

    def test_prior_recovery_evidence_requires_pinned_bytes_and_types(self) -> None:
        evidence_value = {
            "schema": "baxy-in-place-upgrade-attestation-v1",
            "status": "failed",
            "operation": "upgrade_rollback_reactivation",
            "started_utc": "2026-07-25T10:26:45.4833795Z",
            "completed_utc": "2026-07-25T10:52:51.9708708Z",
            "phase": "install_candidate",
            "failure_code": "in_place_upgrade_gate_failed",
            "exception_type": "System.Management.Automation.RuntimeException",
            "versions": {
                "initial_current": "1.0.7",
                "initial_previous": "1.0.6",
                "candidate": "1.0.8",
            },
            "candidate_setup_sha256": "b" * 64,
            "recovery": {
                "attempted": True,
                "status": "passed",
                "final_candidate_attested": True,
                "exception_type": None,
                "cleanup_exception_type": None,
                "observation_exception_type": None,
                "current": "1.0.8",
                "previous": "1.0.7",
                "setup_exit_code": 0,
                "setup_duration_ms": 4,
                "settle_duration_ms": 3,
                "residual_setup_processes": 0,
            },
            "privacy": {
                "local_paths_included": False,
                "exception_messages_included": False,
            },
        }
        with tempfile.TemporaryDirectory(prefix="baxy-prior-evidence-") as root:
            evidence = Path(root) / "prior.json"
            payload = (json.dumps(evidence_value, separators=(",", ":")) + "\n").encode(
                "utf-8"
            )
            evidence.write_bytes(payload)
            expected_hash = hashlib.sha256(payload).hexdigest()
            command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$candidate = [pscustomobject]@{{ sha256 = ('b' * 64) }}
$accepted = Read-RecoveredCandidateEvidence `
    -Path {ps_quote(evidence)} `
    -Candidate $candidate `
    -ExpectedCurrent '1.0.7' `
    -ExpectedInitialPrevious '1.0.6' `
    -ExpectedCandidate '1.0.8' `
    -ExpectedSha256 {ps_quote(expected_hash)}
[IO.File]::AppendAllText({ps_quote(evidence)}, ' ')
$tamperRefused = $false
try {{
    $null = Read-RecoveredCandidateEvidence `
        -Path {ps_quote(evidence)} `
        -Candidate $candidate `
        -ExpectedCurrent '1.0.7' `
        -ExpectedInitialPrevious '1.0.6' `
        -ExpectedCandidate '1.0.8' `
        -ExpectedSha256 {ps_quote(expected_hash)}
}} catch {{
    $tamperRefused = $true
}}
[ordered]@{{
    accepted_sha256 = $accepted.sha256
    tamper_refused = $tamperRefused
}} | ConvertTo-Json -Compress
"""
            result = run_powershell(command)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            diagnostic = json.loads(result.stdout.strip())
            self.assertEqual(diagnostic["accepted_sha256"], expected_hash)
            self.assertTrue(diagnostic["tamper_refused"])

            invalid_types = json.loads(json.dumps(evidence_value))
            invalid_types["recovery"]["attempted"] = 1
            invalid_payload = (
                json.dumps(invalid_types, separators=(",", ":")) + "\n"
            ).encode("utf-8")
            evidence.write_bytes(invalid_payload)
            invalid_hash = hashlib.sha256(invalid_payload).hexdigest()
            type_command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$candidate = [pscustomobject]@{{ sha256 = ('b' * 64) }}
try {{
    $null = Read-RecoveredCandidateEvidence `
        -Path {ps_quote(evidence)} `
        -Candidate $candidate `
        -ExpectedCurrent '1.0.7' `
        -ExpectedInitialPrevious '1.0.6' `
        -ExpectedCandidate '1.0.8' `
        -ExpectedSha256 {ps_quote(invalid_hash)}
    exit 2
}} catch {{
    exit 0
}}
"""
            result = run_powershell(type_command)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_validates_candidate_and_complete_installed_bytes(self) -> None:
        for required in (
            "setup-manifest.json",
            "SHA256SUMS",
            "Get-AuthenticodeSignature",
            "baxy-setup-build-v2",
            "baxy-product-build-v4",
            "baxy-installed-version-v2",
            "Get-ContentIdentity",
            "installed version file set",
            "Get-ImmutableVersionInventory",
            "baxy-immutable-version-tree-v1",
            "A pre-existing immutable version tree changed during the lifecycle.",
        ):
            self.assertIn(required, self.source)

    def test_orchestrator_calls_closed_upgrade_phases_in_order(self) -> None:
        command = f"""
{dot_source_script(confirm=True)}
$script:phaseCalls = New-Object 'Collections.Generic.List[string]'
$script:fixtureSourceState = [pscustomobject]@{{
    root = 'C:\\source'
    head = ('a' * 40)
}}
$script:fixtureCandidate = [pscustomobject]@{{
    path = 'C:\\candidate\\Baxy.Setup.exe'
    root = 'C:\\candidate'
    sha256 = ('b' * 64)
    package_sha256 = ('c' * 64)
    source_commit = ('a' * 40)
    expected_identity = [pscustomobject]@{{ marker = 'candidate' }}
}}
$script:fixturePaths = [pscustomobject]@{{
    root = 'C:\\install'
    data = 'C:\\data'
    shortcut = 'C:\\menu\\BAXY.lnk'
    start_menu_directory = 'C:\\menu'
    versions = 'C:\\install\\versions'
    stable_setup = 'C:\\install\\Baxy.Setup.exe'
    current = 'C:\\install\\current'
}}
$script:fixtureBaseline = [pscustomobject]@{{
    current = [pscustomobject]@{{ marker = 'baseline-current' }}
    previous = [pscustomobject]@{{ marker = 'baseline-previous' }}
    installation = [pscustomobject]@{{ install_id = 'install-fixture' }}
    integration = [pscustomobject]@{{
        shortcut = [pscustomobject]@{{ sha256 = ('d' * 64) }}
    }}
    summary = [pscustomobject]@{{ current = '1.0.7'; previous = '1.0.6' }}
}}
$script:fixtureInventory = [pscustomobject]@{{
    names = @('1.0.6', '1.0.7')
    snapshots = @()
}}
$script:fixturePrivateData = [pscustomobject]@{{
    schema = 'baxy-private-data-tree-v1'
    tree_sha256 = ('e' * 64)
    exists = $true
    files = 2
    directories = 1
    total_bytes = 3
}}

function Assert-NewEvidencePath {{ param($Path); return $Path }}
function Get-RepositorySourceState {{ return $script:fixtureSourceState }}
function Get-CandidateSetupArtifact {{
    param($Path, $ExpectedVersion, $ExpectedCommit)
    return $script:fixtureCandidate
}}
function Invoke-EmbeddedCandidateVerification {{
    param($Candidate, $MaximumSeconds)
    return [pscustomobject]@{{ status = 'passed' }}
}}
function Get-CanonicalProductPaths {{ return $script:fixturePaths }}
function Assert-EvidencePathOutsideProtectedRoots {{
    param($Path, $ProtectedRoots)
    return $Path
}}
function Assert-NoOwnedProductProcesses {{}}
function Get-FileSha256 {{ param($Path); return ('b' * 64) }}
function Read-InstallationPointer {{
    param($Path, $ExpectedVersion)
    return [pscustomobject]@{{ package_sha256 = ('f' * 64) }}
}}
function Get-InstalledState {{ return $script:fixtureBaseline }}
function Get-ImmutableVersionInventory {{ return $script:fixtureInventory }}
function Get-PrivateDataInventory {{ return $script:fixturePrivateData }}
function Assert-PrivateDataInventoryEqual {{ param($Actual, $Expected) }}
function Get-LifecycleAllowedSetupPaths {{ return @('C:\\candidate\\Baxy.Setup.exe') }}
function Get-PendingLifecycleArtifacts {{ return @() }}
function Invoke-RecoveredCandidateValidationPhase {{
    param(
        $Candidate,
        $Paths,
        $Baseline,
        $BaselineInventory,
        $PriorEvidence,
        $CandidateVersion,
        $MaximumSeconds
    )
    if ($mutationStarted) {{
        throw 'recovery-was-armed-before-recovered-candidate-validation'
    }}
    $script:phaseCalls.Add('validate-recovered')
    return [pscustomobject]@{{
        state = [pscustomobject]@{{
            current = [pscustomobject]@{{ marker = 'candidate' }}
        }}
        inventory = $BaselineInventory
        step = [ordered]@{{
            name = 'validate_recovered_candidate'
            status = 'passed'
        }}
    }}
}}
function Invoke-CandidateInstallPhase {{
    param(
        $Candidate,
        $Paths,
        $Baseline,
        $BaselineInventory,
        $BaselineInstallId,
        $BaselineShortcutSha256,
        $AllowedSetupPaths,
        $CandidateVersion,
        $ExpectedCurrentVersion,
        $MaximumSeconds
    )
    if (-not $mutationStarted -or $mutationStartedUtc -isnot [DateTime]) {{
        throw 'recovery-was-not-armed-before-install'
    }}
    $script:phaseCalls.Add('install')
    return [pscustomobject]@{{
        state = [pscustomobject]@{{ current = [pscustomobject]@{{ marker = 'candidate' }} }}
        inventory = [pscustomobject]@{{ names = @('1.0.6', '1.0.7', '1.0.8') }}
        step = [ordered]@{{ name = 'install_candidate'; status = 'passed' }}
    }}
}}
function Invoke-CandidateRollbackPhase {{
    param(
        $Candidate,
        $Paths,
        $Baseline,
        $BaselineInventory,
        $InstalledCandidate,
        $BaselineInstallId,
        $BaselineShortcutSha256,
        $AllowedSetupPaths,
        $CandidateVersion,
        $ExpectedCurrentVersion,
        [switch]$Continuation,
        $MaximumSeconds
    )
    if ($InstalledCandidate.current.marker -cne 'candidate') {{
        throw 'rollback-received-invalid-context'
    }}
    $script:phaseCalls.Add('rollback')
    $expectedMarker = if ($Continuation.IsPresent) {{
        'baseline-previous'
    }} else {{
        'baseline-current'
    }}
    return [pscustomobject]@{{
        state = [pscustomobject]@{{ marker = 'rollback' }}
        inventory = [pscustomobject]@{{ names = @('1.0.6', '1.0.7', '1.0.8') }}
        step = [ordered]@{{ name = 'rollback'; status = 'passed' }}
        expected_rollback_identity = [pscustomobject]@{{ marker = $expectedMarker }}
    }}
}}
function Invoke-CandidateReactivationPhase {{
    param(
        $Candidate,
        $Paths,
        $Baseline,
        $BaselineInventory,
        $InstalledCandidate,
        $ExpectedRollbackIdentity,
        $BaselineInstallId,
        $BaselineShortcutSha256,
        $AllowedSetupPaths,
        $CandidateVersion,
        $ExpectedCurrentVersion,
        [switch]$Continuation,
        $MaximumSeconds
    )
    $expectedMarker = if ($Continuation.IsPresent) {{
        'baseline-previous'
    }} else {{
        'baseline-current'
    }}
    if ($ExpectedRollbackIdentity.marker -cne $expectedMarker) {{
        throw 'reactivation-received-invalid-context'
    }}
    $script:phaseCalls.Add('reactivate')
    return [pscustomobject]@{{
        state = [pscustomobject]@{{ marker = 'final' }}
        inventory = [pscustomobject]@{{ names = @('1.0.6', '1.0.7', '1.0.8') }}
        step = [ordered]@{{ name = 'reactivate_candidate'; status = 'passed' }}
    }}
}}
function New-InPlaceUpgradeSuccessEvidence {{
    param(
        [switch]$Continuation,
        $StartedUtc,
        $TimeoutSeconds,
        $Source,
        $Candidate,
        $EmbeddedVerification,
        $Baseline,
        $Steps,
        $ExpectedCurrentVersion,
        $ExpectedInitialPreviousVersion,
        $CandidateVersion,
        $BaselineInstallId,
        $BaselineInventory,
        $FinalInventory,
        $BaselinePrivateData,
        $FinalPrivateData,
        $PriorEvidence
    )
    $script:phaseCalls.Add('evidence')
    return [ordered]@{{
        status = 'passed'
        step_names = @($Steps | ForEach-Object {{ $_.name }})
    }}
}}
function Write-AtomicEvidence {{
    param($Path, $Value, $ForbiddenPaths)
    $script:phaseCalls.Add('publish')
}}

$normalResult = Invoke-InPlaceUpgradeAttestation
$normalCalls = $script:phaseCalls.ToArray()
$normalStepNames = @($normalResult.step_names)

$script:phaseCalls.Clear()
$ContinueRecoveredCandidate = $true
$ExpectedCandidateCommit = ('a' * 40)
$PriorFailureEvidencePath = 'C:\\fixture\\prior.json'
$ExpectedPriorFailureEvidenceSha256 = ('b' * 64)
$EvidencePath = 'C:\\fixture\\continuation.json'
function git {{ $global:LASTEXITCODE = 0 }}
function Test-Path {{ return $true }}
function Read-RecoveredCandidateEvidence {{
    return [pscustomobject]@{{
        path = 'C:\\fixture\\prior.json'
        sha256 = ('b' * 64)
        value = [pscustomobject]@{{
            recovery = [pscustomobject]@{{
                setup_exit_code = 0
                setup_duration_ms = 3
                settle_duration_ms = 4
            }}
        }}
    }}
}}
$continuationResult = Invoke-InPlaceUpgradeAttestation
$continuationCalls = $script:phaseCalls.ToArray()
$continuationStepNames = @($continuationResult.step_names)

$script:phaseCalls.Clear()
$ContinueRecoveredCandidate = $false
$ExpectedCandidateCommit = $null
$PriorFailureEvidencePath = $null
$ExpectedPriorFailureEvidenceSha256 = $null
$EvidencePath = 'C:\\fixture\\failed-install.json'
function Test-Path {{ return $false }}
function Invoke-CandidateInstallPhase {{
    $script:phaseCalls.Add('install-fail')
    throw 'simulated-install-phase-failure'
}}
function Invoke-InPlaceUpgradeRecovery {{
    $script:phaseCalls.Add('recovery')
    return New-InPlaceUpgradeRecoveryResult
}}
function New-InPlaceUpgradeFailureEvidence {{
    param(
        [switch]$Continuation,
        $StartedUtc,
        $FailedPhase,
        $Caught,
        $ExpectedCurrentVersion,
        $ExpectedInitialPreviousVersion,
        $CandidateVersion,
        $Candidate,
        $Recovery,
        $PriorEvidence,
        $ExpectedCandidateCommit
    )
    $script:phaseCalls.Add("failure:$FailedPhase")
    return [ordered]@{{ status = 'failed'; phase = $FailedPhase }}
}}
try {{
    $null = Invoke-InPlaceUpgradeAttestation
}} catch {{
}}
$failedInstallCalls = $script:phaseCalls.ToArray()

$script:phaseCalls.Clear()
$EvidencePath = 'C:\\fixture\\failed-preflight.json'
function Get-CandidateSetupArtifact {{
    throw 'simulated-preflight-failure'
}}
try {{
    $null = Invoke-InPlaceUpgradeAttestation
}} catch {{
}}
$failedPreflightCalls = $script:phaseCalls.ToArray()

[ordered]@{{
    normal_calls = $normalCalls
    normal_step_names = $normalStepNames
    continuation_calls = $continuationCalls
    continuation_step_names = $continuationStepNames
    failed_install_calls = $failedInstallCalls
    failed_preflight_calls = $failedPreflightCalls
}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic["normal_calls"],
            ["install", "rollback", "reactivate", "evidence", "publish"],
        )
        self.assertEqual(
            diagnostic["normal_step_names"],
            ["install_candidate", "rollback", "reactivate_candidate"],
        )
        self.assertEqual(
            diagnostic["continuation_calls"],
            [
                "validate-recovered",
                "rollback",
                "reactivate",
                "evidence",
                "publish",
            ],
        )
        self.assertEqual(
            diagnostic["continuation_step_names"],
            [
                "validate_recovered_candidate",
                "rollback",
                "reactivate_candidate",
            ],
        )
        self.assertEqual(
            diagnostic["failed_install_calls"],
            [
                "install-fail",
                "recovery",
                "failure:install_candidate",
                "publish",
            ],
        )
        self.assertEqual(
            diagnostic["failed_preflight_calls"],
            ["failure:candidate_validation", "publish"],
        )

    def test_closed_phase_helpers_preserve_exact_lifecycle_contracts(self) -> None:
        command = f"""
{dot_source_script()}
$script:calls = New-Object 'Collections.Generic.List[string]'
$candidate = [pscustomobject]@{{
    path = 'C:\\candidate\\Baxy.Setup.exe'
    sha256 = ('a' * 64)
    package_sha256 = ('b' * 64)
    expected_identity = [pscustomobject]@{{ marker = 'candidate-identity' }}
}}
$paths = [pscustomobject]@{{
    stable_setup = 'C:\\install\\Baxy.Setup.exe'
    data = 'C:\\data'
}}
$baselineCurrent = [pscustomobject]@{{ marker = 'baseline-current' }}
$baselinePrevious = [pscustomobject]@{{ marker = 'baseline-previous' }}
$candidateCurrent = [pscustomobject]@{{ marker = 'candidate-current' }}
$baseline = [pscustomobject]@{{
    current = $baselineCurrent
    previous = $baselinePrevious
    previous_version = [pscustomobject]@{{
        source_commit = ('c' * 40)
        core_sha256 = ('d' * 64)
    }}
}}
$script:fixtureInstalled = [pscustomobject]@{{
    current = $candidateCurrent
    previous = $baselineCurrent
    current_version = [pscustomobject]@{{
        core_path = 'C:\\install\\versions\\1.0.8\\baxy-core.exe'
        core_sha256 = ('e' * 64)
    }}
    installation = [pscustomobject]@{{ install_id = 'install-fixture' }}
    integration = [pscustomobject]@{{
        shortcut = [pscustomobject]@{{ sha256 = ('f' * 64) }}
    }}
    summary = [pscustomobject]@{{ current = '1.0.8'; previous = '1.0.7' }}
}}
$script:fixtureRolledBack = [pscustomobject]@{{
    current = $baselineCurrent
    previous = $candidateCurrent
    current_version = [pscustomobject]@{{
        core_path = 'C:\\install\\versions\\1.0.7\\baxy-core.exe'
        core_sha256 = ('1' * 64)
    }}
    installation = [pscustomobject]@{{ install_id = 'install-fixture' }}
    integration = [pscustomobject]@{{
        shortcut = [pscustomobject]@{{ sha256 = ('f' * 64) }}
    }}
    summary = [pscustomobject]@{{ current = '1.0.7'; previous = '1.0.8' }}
}}
$script:fixtureFinal = [pscustomobject]@{{
    current = $candidateCurrent
    previous = $baselineCurrent
    current_version = [pscustomobject]@{{
        core_path = 'C:\\install\\versions\\1.0.8\\baxy-core.exe'
        core_sha256 = ('e' * 64)
    }}
    installation = [pscustomobject]@{{ install_id = 'install-fixture' }}
    integration = [pscustomobject]@{{
        shortcut = [pscustomobject]@{{ sha256 = ('f' * 64) }}
    }}
    summary = [pscustomobject]@{{ current = '1.0.8'; previous = '1.0.7' }}
}}
$inventory = [pscustomobject]@{{ names = @('1.0.6', '1.0.7') }}
$expandedInventory = [pscustomobject]@{{
    names = @('1.0.6', '1.0.7', '1.0.8')
}}

function Invoke-HiddenSetupProcess {{
    param(
        $Path,
        [string[]]$Arguments = @(),
        $MaximumSeconds,
        $ExpectedSha256,
        $AdditionalAllowedSetupPaths
    )
    $script:calls.Add(
        "setup:$($Path):$($Arguments -join ','):$MaximumSeconds")
    return [pscustomobject]@{{ exit_code = 0; duration_ms = 3 }}
}}
function Wait-ForInstalledState {{
    param($Paths, $Expected, $MaximumSeconds)
    $identity = if ($null -eq $Expected.current_identity) {{ 'none' }} else {{ 'bound' }}
    $script:calls.Add(
        "wait:$($Expected.current):$($Expected.previous):$identity")
    $state = if ($Expected.current -ceq '1.0.7') {{
        $script:fixtureRolledBack
    }} elseif ($script:calls -contains 'smoke:1.0.8:catalog') {{
        $script:fixtureFinal
    }} else {{
        $script:fixtureInstalled
    }}
    return [pscustomobject]@{{ state = $state; settle_duration_ms = 4 }}
}}
function Get-ImmutableVersionInventory {{ return $expandedInventory }}
function Assert-VersionInventoryTransition {{
    param($Baseline, $Observed, $AddedVersion)
    $script:calls.Add("inventory:$AddedVersion")
}}
function Assert-VersionInventoryEqual {{
    throw 'continuation-inventory-assertion-was-not-expected'
}}
function Assert-IdentityEqual {{
    param($Actual, $Expected, $Description)
    if ($Actual.marker -cne $Expected.marker) {{
        throw "identity-mismatch:$Description"
    }}
    $script:calls.Add("identity:$Description")
}}
function Invoke-InstalledCoreSmoke {{
    param(
        $CorePath,
        $ExpectedVersion,
        $ExpectedSha256,
        $PrivateDataParent,
        $MaximumSeconds,
        [switch]$RequireApplicationCatalog
    )
    $catalog = if ($RequireApplicationCatalog.IsPresent) {{
        'catalog'
    }} else {{
        'no-catalog'
    }}
    $script:calls.Add("smoke:$($ExpectedVersion):$catalog")
    return [pscustomobject]@{{ version = $ExpectedVersion; catalog = $catalog }}
}}
function Get-InstalledVersionRecord {{
    param($Paths, $Pointer)
    return [pscustomobject]@{{
        source_commit = ('c' * 40)
        core_sha256 = ('d' * 64)
    }}
}}

$install = Invoke-CandidateInstallPhase `
    -Candidate $candidate `
    -Paths $paths `
    -Baseline $baseline `
    -BaselineInventory $inventory `
    -BaselineInstallId 'install-fixture' `
    -BaselineShortcutSha256 ('f' * 64) `
    -AllowedSetupPaths @($candidate.path, $paths.stable_setup) `
    -CandidateVersion '1.0.8' `
    -ExpectedCurrentVersion '1.0.7' `
    -MaximumSeconds 45
$rollback = Invoke-CandidateRollbackPhase `
    -Candidate $candidate `
    -Paths $paths `
    -Baseline $baseline `
    -BaselineInventory $inventory `
    -InstalledCandidate $install.state `
    -BaselineInstallId 'install-fixture' `
    -BaselineShortcutSha256 ('f' * 64) `
    -AllowedSetupPaths @($candidate.path, $paths.stable_setup) `
    -CandidateVersion '1.0.8' `
    -ExpectedCurrentVersion '1.0.7' `
    -MaximumSeconds 45
$reactivation = Invoke-CandidateReactivationPhase `
    -Candidate $candidate `
    -Paths $paths `
    -Baseline $baseline `
    -BaselineInventory $inventory `
    -InstalledCandidate $install.state `
    -ExpectedRollbackIdentity $rollback.expected_rollback_identity `
    -BaselineInstallId 'install-fixture' `
    -BaselineShortcutSha256 ('f' * 64) `
    -AllowedSetupPaths @($candidate.path, $paths.stable_setup) `
    -CandidateVersion '1.0.8' `
    -ExpectedCurrentVersion '1.0.7' `
    -MaximumSeconds 45

[ordered]@{{
    calls = $script:calls.ToArray()
    phase_names = @(
        $install.step.name,
        $rollback.step.name,
        $reactivation.step.name
    )
    phase_contracts = @(
        [ordered]@{{
            properties = @($install.PSObject.Properties.Name)
            type = $install.PSObject.TypeNames[0]
        }},
        [ordered]@{{
            properties = @($rollback.PSObject.Properties.Name)
            type = $rollback.PSObject.TypeNames[0]
        }},
        [ordered]@{{
            properties = @($reactivation.PSObject.Properties.Name)
            type = $reactivation.PSObject.TypeNames[0]
        }}
    )
}} | ConvertTo-Json -Depth 4 -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic["phase_names"],
            ["install_candidate", "rollback", "reactivate_candidate"],
        )
        self.assertEqual(
            diagnostic["phase_contracts"],
            [
                {
                    "properties": ["state", "step"],
                    "type": "Baxy.InPlaceUpgrade.CandidatePhase",
                },
                {
                    "properties": ["step", "expected_rollback_identity"],
                    "type": "Baxy.InPlaceUpgrade.RollbackPhase",
                },
                {
                    "properties": ["step", "inventory"],
                    "type": "Baxy.InPlaceUpgrade.ReactivationPhase",
                },
            ],
        )
        self.assertEqual(
            diagnostic["calls"],
            [
                "setup:C:\\candidate\\Baxy.Setup.exe::45",
                "wait:1.0.8:1.0.7:bound",
                "inventory:1.0.8",
                "identity:candidate update previous pointer",
                "smoke:1.0.8:catalog",
                "setup:C:\\install\\Baxy.Setup.exe:--rollback:45",
                "wait:1.0.7:1.0.8:none",
                "inventory:1.0.8",
                "identity:rollback active pointer",
                "identity:rollback previous pointer",
                "smoke:1.0.7:no-catalog",
                "setup:C:\\install\\Baxy.Setup.exe::45",
                "wait:1.0.8:1.0.7:bound",
                "inventory:1.0.8",
                "identity:reactivated candidate pointer",
                "identity:reactivated previous pointer",
                "smoke:1.0.8:catalog",
            ],
        )

    def test_hidden_setup_timeout_cleans_owned_tree_and_disposes_process(
        self,
    ) -> None:
        command = f"""
{dot_source_script()}
$script:calls = New-Object 'Collections.Generic.List[string]'
$script:disposeCalls = 0
$fakeProcess = [pscustomobject]@{{
    Id = 42
    ExitCode = 0
    HasExited = $false
}}
$fakeProcess | Add-Member ScriptMethod WaitForExit {{
    param($Milliseconds)
    $script:calls.Add("wait:$Milliseconds")
    return $false
}}
$fakeProcess | Add-Member ScriptMethod Dispose {{
    $script:disposeCalls++
}}
function Assert-RegularFile {{ param($Path); return $Path }}
function Get-FileSha256 {{ param($Path); return ('a' * 64) }}
function Start-Process {{
    param(
        $FilePath,
        $WorkingDirectory,
        [switch]$PassThru,
        $WindowStyle,
        [string[]]$ArgumentList
    )
    $script:calls.Add(
        "start:$($WindowStyle):$($PassThru.IsPresent):$($ArgumentList -join ',')")
    return $fakeProcess
}}
function Stop-OwnedSetupProcessTree {{
    param($RootProcess, $NotBeforeUtc, $AllowedPaths)
    if ($RootProcess.Id -ne 42 -or
        $AllowedPaths -cnotcontains 'C:\\install\\Baxy.Setup.next.exe') {{
        throw 'cleanup-received-invalid-process-identity'
    }}
    $script:calls.Add('cleanup')
}}
$message = $null
try {{
    $null = Invoke-HiddenSetupProcess `
        -Path 'C:\\candidate\\Baxy.Setup.exe' `
        -Arguments @('--fixture') `
        -MaximumSeconds 30 `
        -ExpectedSha256 ('a' * 64) `
        -AdditionalAllowedSetupPaths @('C:\\install\\Baxy.Setup.next.exe')
}} catch {{
    $message = $_.Exception.Message
}}
[ordered]@{{
    calls = $script:calls.ToArray()
    dispose_calls = $script:disposeCalls
    message = $message
}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic["calls"],
            ["start:Hidden:True:--fixture", "wait:30000", "cleanup"],
        )
        self.assertEqual(diagnostic["dispose_calls"], 1)
        self.assertEqual(
            diagnostic["message"],
            "A hidden Setup process exceeded its reviewed timeout.",
        )

    def test_evidence_is_disjoint_from_every_mutated_or_attested_root(self) -> None:
        for required in (
            "Assert-EvidencePathOutsideProtectedRoots",
            "$source.root",
            "$candidate.root",
            "$paths.root",
            "$paths.data",
            "$paths.start_menu_directory",
            "EvidencePath must remain outside source, build, installation, data, and Windows-integration roots.",
        ):
            self.assertIn(required, self.source)

        with tempfile.TemporaryDirectory(prefix="baxy-evidence-roots-") as root:
            base = Path(root)
            protected = [base / name for name in ("source", "build", "install", "data")]
            outside = base / "evidence" / "attestation.json"
            for path in [*protected, outside.parent]:
                path.mkdir()
            protected_ps = ", ".join(ps_quote(path) for path in protected)
            command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$protected = @({protected_ps})
$refused = 0
foreach ($root in $protected) {{
    try {{
        Assert-EvidencePathOutsideProtectedRoots `
            -Path (Join-Path $root 'evidence.json') `
            -ProtectedRoots $protected | Out-Null
    }} catch {{
        $refused++
    }}
}}
$accepted = Assert-EvidencePathOutsideProtectedRoots `
    -Path {ps_quote(outside)} `
    -ProtectedRoots $protected
[ordered]@{{
    refused = $refused
    accepted = $accepted
}} | ConvertTo-Json -Compress
"""
            result = run_powershell(command)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            diagnostic = json.loads(result.stdout.strip())
            self.assertEqual(diagnostic["refused"], len(protected))
            self.assertEqual(Path(diagnostic["accepted"]), outside)

    def test_private_data_snapshot_detects_same_size_content_change(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baxy-private-data-") as root:
            data = Path(root) / "data"
            (data / "nested").mkdir(parents=True)
            (data / "message.txt").write_text("abc", encoding="utf-8")
            (data / "nested" / "state.bin").write_bytes(b"\x00\x01\x02")
            command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$target = {ps_quote(data / "message.txt")}
$streamedMatches = (Get-StreamedFileSha256 -Path $target) -ceq
    (Get-FileSha256 -Path $target)
$stamp = (Get-Item -LiteralPath $target -Force).LastWriteTimeUtc
$before = Get-PrivateDataInventory -Root {ps_quote(data)}
[IO.File]::WriteAllText($target, 'xyz', (New-Object Text.UTF8Encoding($false)))
[IO.File]::SetLastWriteTimeUtc($target, $stamp)
$after = Get-PrivateDataInventory -Root {ps_quote(data)}
$differenceRefused = $false
try {{
    Assert-PrivateDataInventoryEqual -Actual $after -Expected $before
}} catch {{
    $differenceRefused = $true
}}
[ordered]@{{
    before = $before
    after = $after
    difference_refused = $differenceRefused
    streamed_matches = $streamedMatches
    before_properties = @($before.PSObject.Properties.Name)
}} | ConvertTo-Json -Depth 5 -Compress
"""
            result = run_powershell(command)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            diagnostic = json.loads(result.stdout.strip())
            self.assertTrue(diagnostic["difference_refused"])
            self.assertTrue(diagnostic["streamed_matches"])
            self.assertNotEqual(
                diagnostic["before"]["tree_sha256"],
                diagnostic["after"]["tree_sha256"],
            )
            self.assertEqual(diagnostic["before"]["files"], 2)
            self.assertNotIn("path", diagnostic["before_properties"])

    def test_setup_process_tree_includes_resume_image_names(self) -> None:
        command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$snapshot = @(
    [pscustomobject]@{{
        process_id = 11
        parent_process_id = 10
        name = 'Baxy.Setup.next.exe'
        executable_path = 'C:\\install\\Baxy.Setup.next.exe'
        creation_utc = [DateTime]::UtcNow
    }},
    [pscustomobject]@{{
        process_id = 12
        parent_process_id = 11
        name = 'Baxy.Setup.previous.exe'
        executable_path = 'C:\\install\\Baxy.Setup.previous.exe'
        creation_utc = [DateTime]::UtcNow
    }},
    [pscustomobject]@{{
        process_id = 13
        parent_process_id = 10
        name = 'powershell.exe'
        executable_path = 'C:\\Windows\\powershell.exe'
        creation_utc = [DateTime]::UtcNow
    }}
)
$owned = @(Get-OwnedSetupDescendants -Snapshot $snapshot -RootProcessId 10)
[ordered]@{{
    ids = @($owned.process_id)
    depths = @($owned.depth)
}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(diagnostic["ids"], [11, 12])
        self.assertEqual(diagnostic["depths"], [1, 2])

    def test_failure_reactivation_helper_is_dependency_testable(self) -> None:
        command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$script:calls = New-Object 'Collections.Generic.List[string]'
function Stop-GateOwnedSetupProcesses {{
    param($NotBeforeUtc, $AllowedPaths)
    $script:calls.Add('stop')
}}
function Invoke-HiddenSetupProcess {{
    param(
        $Path,
        $MaximumSeconds,
        $ExpectedSha256,
        $AdditionalAllowedSetupPaths
    )
    $script:calls.Add('invoke')
    [pscustomobject]@{{ exit_code = 0; duration_ms = 3 }}
}}
function Wait-ForInstalledState {{
    param($Paths, $Expected, $MaximumSeconds)
    $script:calls.Add('wait')
    [pscustomobject]@{{
        state = [pscustomobject]@{{
            summary = [pscustomobject]@{{
                current = '1.0.8'
                previous = '1.0.7'
            }}
        }}
        settle_duration_ms = 4
    }}
}}
function Get-ImmutableVersionInventory {{
    param($Paths)
    $script:calls.Add('versions')
    [pscustomobject]@{{ names = @('1.0.7', '1.0.8') }}
}}
function Assert-VersionInventoryTransition {{
    param($Baseline, $Observed, $AddedVersion)
    $script:calls.Add('versions_assert')
}}
function Get-PrivateDataInventory {{
    param($Root)
    $script:calls.Add('data')
    [pscustomobject]@{{ tree_sha256 = ('a' * 64) }}
}}
function Assert-PrivateDataInventoryEqual {{
    param($Actual, $Expected)
    $script:calls.Add('data_assert')
}}
function Assert-NoOwnedProductProcesses {{ $script:calls.Add('process_assert') }}
$candidate = [pscustomobject]@{{
    path = 'C:\\build\\Baxy.Setup.exe'
    sha256 = ('b' * 64)
    version = '1.0.8'
    package_sha256 = ('c' * 64)
    expected_identity = [pscustomobject]@{{ version = '1.0.8' }}
}}
$paths = [pscustomobject]@{{
    root = 'C:\\install'
    stable_setup = 'C:\\install\\Baxy.Setup.exe'
    data = 'C:\\data'
}}
$result = Invoke-BestEffortCandidateReactivation `
    -Candidate $candidate `
    -Paths $paths `
    -ExpectedPreviousVersion '1.0.7' `
    -BaselineInventory ([pscustomobject]@{{ names = @('1.0.7') }}) `
    -BaselinePrivateData ([pscustomobject]@{{ tree_sha256 = ('a' * 64) }}) `
    -MutationStartedUtc ([DateTime]::UtcNow) `
    -MaximumSeconds 30
[ordered]@{{
    calls = $script:calls.ToArray()
    current = $result.state.summary.current
    previous = $result.state.summary.previous
}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic["calls"],
            [
                "stop",
                "invoke",
                "wait",
                "versions",
                "versions_assert",
                "data",
                "data_assert",
                "process_assert",
            ],
        )
        self.assertEqual(
            (diagnostic["current"], diagnostic["previous"]),
            ("1.0.8", "1.0.7"),
        )

    def test_recovery_coordinator_cleans_and_observes_once_after_failure(
        self,
    ) -> None:
        command = f"""
{dot_source_script()}
$script:calls = New-Object 'Collections.Generic.List[string]'
$script:reactivationFails = $false
$script:cleanupFails = $false
$script:observationFails = $false
$script:residualObservationFails = $false
function Invoke-BestEffortCandidateReactivation {{
    param(
        $Candidate,
        $Paths,
        $ExpectedPreviousVersion,
        $BaselineInventory,
        $BaselinePrivateData,
        $MutationStartedUtc,
        [switch]$CandidateAlreadyInBaseline,
        $MaximumSeconds
    )
    $script:calls.Add(
        "reactivate:$($CandidateAlreadyInBaseline.IsPresent)")
    if ($script:reactivationFails) {{
        throw 'sensitive-reactivation-detail'
    }}
    return [pscustomobject]@{{
        state = [pscustomobject]@{{
            summary = [pscustomobject]@{{
                current = '1.0.8'
                previous = '1.0.7'
            }}
        }}
        setup_exit_code = 0
        setup_duration_ms = 17
        settle_duration_ms = 23
    }}
}}
function Get-LifecycleAllowedSetupPaths {{
    $script:calls.Add('allowed-paths')
    return @('C:\\candidate\\Baxy.Setup.exe')
}}
function Stop-GateOwnedSetupProcesses {{
    param($NotBeforeUtc, $AllowedPaths)
    $script:calls.Add('cleanup')
    if ($script:cleanupFails) {{
        throw [IO.IOException]::new('sensitive-cleanup-detail')
    }}
}}
function Get-OwnedSetupProcesses {{
    if ($script:residualObservationFails) {{
        throw 'sensitive-residual-observation-detail'
    }}
    return @(
        [pscustomobject]@{{ Id = 11 }},
        [pscustomobject]@{{ Id = 12 }}
    )
}}
function Get-InstalledState {{
    $script:calls.Add('observe')
    if ($script:observationFails) {{
        throw [UnauthorizedAccessException]::new(
            'sensitive-observation-detail')
    }}
    return [pscustomobject]@{{
        summary = [pscustomobject]@{{
            current = '1.0.8'
            previous = '1.0.7'
        }}
    }}
}}
$candidate = [pscustomobject]@{{
    path = 'C:\\candidate\\Baxy.Setup.exe'
    sha256 = ('a' * 64)
    package_sha256 = ('b' * 64)
    expected_identity = [pscustomobject]@{{ marker = 'candidate' }}
}}
$paths = [pscustomobject]@{{
    root = 'C:\\install'
    stable_setup = 'C:\\install\\Baxy.Setup.exe'
}}
$arguments = @{{
    Candidate = $candidate
    Paths = $paths
    BaselineInventory = [pscustomobject]@{{ names = @('1.0.7') }}
    BaselinePrivateData = [pscustomobject]@{{ tree_sha256 = ('c' * 64) }}
    MutationStartedUtc = [DateTime]::UtcNow
    ExpectedCurrentVersion = '1.0.7'
    CandidateVersion = '1.0.8'
    MaximumSeconds = 30
}}
$continued = Invoke-InPlaceUpgradeRecovery @arguments -Continuation
$continuedCalls = $script:calls.ToArray()

$script:calls.Clear()
$script:reactivationFails = $true
$observed = Invoke-InPlaceUpgradeRecovery @arguments
$observedCalls = $script:calls.ToArray()

$script:calls.Clear()
$script:cleanupFails = $true
$script:observationFails = $true
$unobserved = Invoke-InPlaceUpgradeRecovery @arguments
$unobservedCalls = $script:calls.ToArray()

$script:calls.Clear()
$script:observationFails = $false
$script:residualObservationFails = $true
$unknownResidual = Invoke-InPlaceUpgradeRecovery @arguments

[ordered]@{{
    continued = $continued
    continued_calls = $continuedCalls
    observed = $observed
    observed_calls = $observedCalls
    unobserved = $unobserved
    unobserved_calls = $unobservedCalls
    unknown_residual = $unknownResidual
    unknown_residual_calls = $script:calls.ToArray()
}} | ConvertTo-Json -Depth 5 -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        continued = diagnostic["continued"]
        self.assertEqual(diagnostic["continued_calls"], ["reactivate:True"])
        self.assertTrue(continued["attempted"])
        self.assertEqual(continued["status"], "passed")
        self.assertTrue(continued["final_candidate_attested"])
        self.assertEqual(
            (continued["current"], continued["previous"]),
            ("1.0.8", "1.0.7"),
        )
        self.assertEqual(continued["setup_exit_code"], 0)
        self.assertEqual(continued["setup_duration_ms"], 17)
        self.assertEqual(continued["settle_duration_ms"], 23)
        self.assertEqual(continued["residual_setup_processes"], 0)

        observed = diagnostic["observed"]
        self.assertEqual(
            diagnostic["observed_calls"],
            ["reactivate:False", "allowed-paths", "cleanup", "observe"],
        )
        self.assertTrue(observed["attempted"])
        self.assertEqual(observed["status"], "failed")
        self.assertTrue(observed["final_candidate_attested"])
        self.assertEqual(
            (observed["current"], observed["previous"]),
            ("1.0.8", "1.0.7"),
        )
        self.assertEqual(observed["residual_setup_processes"], 0)
        self.assertEqual(
            observed["exception_type"],
            "System.Management.Automation.RuntimeException",
        )
        self.assertIsNone(observed["cleanup_exception_type"])
        self.assertIsNone(observed["observation_exception_type"])

        unobserved = diagnostic["unobserved"]
        self.assertEqual(
            diagnostic["unobserved_calls"],
            ["reactivate:False", "allowed-paths", "cleanup", "observe"],
        )
        self.assertFalse(unobserved["final_candidate_attested"])
        self.assertEqual(unobserved["residual_setup_processes"], 2)
        self.assertEqual(
            unobserved["cleanup_exception_type"],
            "System.IO.IOException",
        )
        self.assertEqual(
            unobserved["observation_exception_type"],
            "System.UnauthorizedAccessException",
        )
        unknown_residual = diagnostic["unknown_residual"]
        self.assertEqual(
            diagnostic["unknown_residual_calls"],
            ["reactivate:False", "allowed-paths", "cleanup", "observe"],
        )
        self.assertTrue(unknown_residual["final_candidate_attested"])
        self.assertIsNone(unknown_residual["residual_setup_processes"])
        self.assertEqual(
            unknown_residual["cleanup_exception_type"],
            "System.IO.IOException",
        )
        self.assertIsNone(unknown_residual["observation_exception_type"])
        serialized = json.dumps(diagnostic, ensure_ascii=False)
        self.assertNotIn("sensitive-reactivation-detail", serialized)
        self.assertNotIn("sensitive-cleanup-detail", serialized)
        self.assertNotIn("sensitive-observation-detail", serialized)
        self.assertNotIn("sensitive-residual-observation-detail", serialized)

    def test_attests_identity_windows_integration_and_registry(self) -> None:
        for required in (
            "install_id_sha256",
            "data_schema_preserved",
            "shortcut_identity_preserved",
            "stable_setup_sha256",
            "RegistryView]::Registry64",
            "BaxyStableSetupSha256",
            "Assert-ShortcutExact",
            "preexisting_version_trees_unchanged",
            "versions_deleted = 0",
        ):
            self.assertIn(required, self.source)

    def test_core_smoke_is_private_headless_and_exact(self) -> None:
        for required in (
            "BAXY_DATA_DIR",
            "CreateNoWindow = $true",
            "baxy.local.v1",
            "$script:ExpectedCapabilities = 168",
            "$script:ExpectedApplicationCatalogVersion = 1",
            "Assert-ApplicationCatalog",
            "$expectedHelloProperties += 'applicationCatalog'",
            "Assert-ApplicationCatalog -Value $hello.applicationCatalog",
            "application_catalog = $applicationCatalog",
            "journal\\missions.jsonl.anchor",
            "security\\journal-hmac.v2.key",
            "$standardInput.Close()",
            "[Console]::InputEncoding = $script:StrictUtf8",
            "[Console]::InputEncoding = $previousInputEncoding",
            "$process.ExitCode -eq 0",
            "profile_removed = $true",
            "Remove-TreeFailClosed",
        ):
            self.assertIn(required, self.source)
        smoke_start = self.source.index("function Invoke-InstalledCoreSmoke")
        smoke_end = self.source.index(
            "function Get-LifecycleAllowedSetupPaths", smoke_start
        )
        smoke_source = self.source[smoke_start:smoke_end]
        self.assertIn("[string]$PrivateDataParent", smoke_source)
        self.assertIn("SpecialFolder]::LocalApplicationData", smoke_source)
        self.assertIn("'BAXY'", smoke_source)
        self.assertNotIn("GetTempPath", smoke_source)

    def test_application_catalog_validation_is_behavioral_and_fail_closed(
        self,
    ) -> None:
        command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.8' `
    -ExpectedInitialPreviousVersion '1.0.7' `
    -CandidateVersion '1.0.9' `
    -EvidencePath 'C:\\fixture\\unused.json'

$valid = '{{"version":1,"verified":true,"complete":true,"names":["7-Zip","Paint","Visual Studio Code"]}}' |
    ConvertFrom-Json
$summary = Assert-ApplicationCatalog -Value $valid

$invalid = New-Object 'Collections.Generic.List[object]'
$invalid.Add(('{{"version":2,"verified":true,"complete":true,"names":[]}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":"1","verified":true,"complete":true,"names":[]}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":1,"verified":false,"complete":true,"names":[]}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":1,"verified":true,"complete":false,"names":[]}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":1,"verified":true,"complete":true,"names":"Paint"}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":1,"verified":true,"complete":true,"names":["Spotify","Paint"]}}' |
    ConvertFrom-Json))
$invalid.Add(('{{"version":1,"verified":true,"complete":true,"names":["Cafe","Café"]}}' |
    ConvertFrom-Json))

$tooManyNames = [object[]]@(0..2048 | ForEach-Object {{ 'App {{0:D4}}' -f $_ }})
$invalid.Add([pscustomobject][ordered]@{{
    version = 1
    verified = $true
    complete = $true
    names = $tooManyNames
}})
$invalid.Add([pscustomobject][ordered]@{{
    version = 1
    verified = $true
    complete = $true
    names = [object[]]@(('a' * 513))
}})
$rawBudgetNames = [object[]]@(0..512 | ForEach-Object {{
    ('{{0:D4}} ' -f $_) + ('a' * 507)
}})
$invalid.Add([pscustomobject][ordered]@{{
    version = 1
    verified = $true
    complete = $true
    names = $rawBudgetNames
}})
$escapedBudgetNames = [object[]]@(0..255 | ForEach-Object {{
    ('{{0:D4}} ' -f $_) + (([char]0x00e9).ToString() * 190)
}})
$invalid.Add([pscustomobject][ordered]@{{
    version = 1
    verified = $true
    complete = $true
    names = $escapedBudgetNames
}})

$refused = 0
foreach ($catalog in $invalid) {{
    try {{
        $null = Assert-ApplicationCatalog -Value $catalog
    }} catch {{
        $refused++
    }}
}}
[ordered]@{{
    accepted = $summary.present
    names = $summary.name_count
    refused = $refused
    cases = $invalid.Count
}} | ConvertTo-Json -Compress
"""
        # The fail-closed budget cases build thousands of names after parsing
        # the 3k-line script. 30s is enough on a quiet host and not enough
        # when the same machine just ran Full; the assertions are unchanged.
        result = run_powershell(command, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic,
            {
                "accepted": True,
                "names": 3,
                "refused": 11,
                "cases": 11,
            },
        )

    def test_evidence_is_atomic_path_free_and_does_not_publish_messages(self) -> None:
        for required in (
            "[IO.FileMode]::CreateNew",
            "[IO.FileOptions]::WriteThrough",
            "$stream.Flush($true)",
            "[IO.File]::Move($temporary, $full)",
            "local_paths_included = $false",
            "exception_messages_included = $false",
        ):
            self.assertIn(required, self.source)
        self.assertNotIn("$caught.Exception.Message", self.source)

    def test_evidence_builders_preserve_closed_schemas_without_messages(
        self,
    ) -> None:
        command = f"""
{dot_source_script()}
$candidate = [pscustomobject]@{{
    sha256 = ('a' * 64)
    bytes = 101
    manifest_sha256 = ('b' * 64)
    package_sha256 = ('c' * 64)
    package_bytes = 202
    package_manifest_sha256 = ('d' * 64)
    content_id = ('e' * 64)
    source_commit = ('f' * 40)
}}
$inventory = [pscustomobject]@{{ names = @('1.0.6', '1.0.7') }}
$finalInventory = [pscustomobject]@{{
    names = @('1.0.6', '1.0.7', '1.0.8')
}}
$privateData = [pscustomobject]@{{
    schema = 'baxy-private-data-tree-v1'
    tree_sha256 = ('1' * 64)
    exists = $true
    files = 3
    directories = 2
    total_bytes = 4
}}
$finalPrivateData = [pscustomobject]@{{
    schema = 'baxy-private-data-tree-v1'
    tree_sha256 = ('1' * 64)
    exists = $true
    files = 3
    directories = 2
    total_bytes = 4
}}
$prior = [pscustomobject]@{{ sha256 = ('2' * 64) }}
$common = @{{
    StartedUtc = '2026-07-28T00:00:00.0000000Z'
    TimeoutSeconds = 180
    Source = [pscustomobject]@{{ head = ('3' * 40) }}
    Candidate = $candidate
    EmbeddedVerification = [pscustomobject]@{{ status = 'passed' }}
    Baseline = [pscustomobject]@{{
        summary = [pscustomobject]@{{
            current = '1.0.7'
            previous = '1.0.6'
        }}
    }}
    Steps = @(
        [ordered]@{{ name = 'install_candidate'; status = 'passed' }},
        [ordered]@{{ name = 'rollback'; status = 'passed' }},
        [ordered]@{{ name = 'reactivate_candidate'; status = 'passed' }}
    )
    ExpectedCurrentVersion = '1.0.7'
    ExpectedInitialPreviousVersion = '1.0.6'
    CandidateVersion = '1.0.8'
    BaselineInstallId = 'install-fixture'
    BaselineInventory = $inventory
    FinalInventory = $finalInventory
    BaselinePrivateData = $privateData
    FinalPrivateData = $finalPrivateData
    PriorEvidence = $prior
}}
$passed = New-InPlaceUpgradeSuccessEvidence @common
$continued = New-InPlaceUpgradeSuccessEvidence @common -Continuation
$caught = $null
try {{
    throw 'sensitive-failure-message'
}} catch {{
    $caught = $_
}}
$recovery = New-InPlaceUpgradeRecoveryResult
$failed = New-InPlaceUpgradeFailureEvidence `
    -StartedUtc '2026-07-28T00:00:00.0000000Z' `
    -FailedPhase 'rollback' `
    -Caught $caught `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -Candidate $candidate `
    -Recovery $recovery
$continuedFailure = New-InPlaceUpgradeFailureEvidence `
    -Continuation `
    -StartedUtc '2026-07-28T00:00:00.0000000Z' `
    -FailedPhase 'rollback' `
    -Caught $caught `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -Candidate $candidate `
    -Recovery $recovery `
    -PriorEvidence $prior `
    -ExpectedCandidateCommit ('f' * 40)
[ordered]@{{
    passed = $passed
    passed_properties = @($passed.Keys)
    continued = $continued
    continued_properties = @($continued.Keys)
    failed = $failed
    failed_properties = @($failed.Keys)
    continued_failure = $continuedFailure
    continued_failure_properties = @($continuedFailure.Keys)
}} | ConvertTo-Json -Depth 10 -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(
            diagnostic["passed_properties"],
            [
                "schema",
                "status",
                "operation",
                "started_utc",
                "completed_utc",
                "timeout_seconds",
                "source",
                "versions",
                "candidate",
                "baseline",
                "steps",
                "preservation",
                "privacy",
                "limitations",
            ],
        )
        self.assertEqual(
            diagnostic["continued_properties"],
            [
                *diagnostic["passed_properties"],
                "aggregate_status",
                "continuation",
            ],
        )
        self.assertEqual(
            diagnostic["failed_properties"],
            [
                "schema",
                "status",
                "operation",
                "started_utc",
                "completed_utc",
                "phase",
                "failure_code",
                "exception_type",
                "versions",
                "candidate_setup_sha256",
                "recovery",
                "privacy",
            ],
        )
        self.assertEqual(
            diagnostic["continued_failure_properties"],
            [*diagnostic["failed_properties"], "continuation"],
        )
        self.assertEqual(
            diagnostic["passed"]["schema"],
            "baxy-in-place-upgrade-attestation-v1",
        )
        self.assertEqual(
            diagnostic["continued"]["schema"],
            "baxy-in-place-upgrade-continuation-attestation-v1",
        )
        self.assertEqual(
            diagnostic["continued"]["aggregate_status"],
            "passed_with_recovery_continuation",
        )
        self.assertEqual(
            diagnostic["failed"]["exception_type"],
            "System.Management.Automation.RuntimeException",
        )
        self.assertEqual(diagnostic["failed"]["phase"], "rollback")
        self.assertEqual(
            diagnostic["continued_failure"]["continuation"],
            {
                "prior_failure_evidence_sha256": "2" * 64,
                "candidate_source_commit": "f" * 40,
            },
        )
        self.assertNotIn(
            "sensitive-failure-message",
            json.dumps(diagnostic, ensure_ascii=False),
        )

    def test_scope_does_not_launch_gui_uninstall_or_purge(self) -> None:
        self.assertEqual(self.source.count("--launch"), 1)
        self.assertEqual(self.source.count("--uninstall"), 2)
        self.assertNotIn("--purge-data", self.source)
        self.assertIn("$shortcut.Arguments -ceq '--launch'", self.source)
        self.assertIn('value = "$quotedSetup --uninstall"', self.source)
        self.assertIn(
            'value = "$quotedSetup --uninstall --keep-data --quiet"',
            self.source,
        )

    def test_dot_source_helpers_are_pure_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="baxy-attest-contract-") as root:
            evidence = Path(root) / "evidence.json"
            command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$largeNumeric = Compare-SemVerPrecedence `
    -Left '2.0.0-999999999999999999999999999999' `
    -Right '2.0.0-9'
$value = [ordered]@{{
    schema = 'baxy-test-evidence-v1'
    status = 'passed'
}}
Write-AtomicEvidence `
    -Path {ps_quote(evidence)} `
    -Value $value `
    -ForbiddenPaths @('C:\\private')
$duplicateRefused = $false
try {{
    Write-AtomicEvidence `
        -Path {ps_quote(evidence)} `
        -Value $value `
        -ForbiddenPaths @('C:\\private')
}} catch {{
    $duplicateRefused = $true
}}
$privatePathRefused = $false
try {{
    $null = ConvertTo-SafeEvidenceJson `
        -Value ([ordered]@{{ leaked = 'C:\\private\\secret' }}) `
        -ForbiddenPaths @('C:\\private')
}} catch {{
    $privatePathRefused = $true
}}
[ordered]@{{
    large_numeric = $largeNumeric
    duplicate_refused = $duplicateRefused
    private_path_refused = $privatePathRefused
}} | ConvertTo-Json -Compress
"""
            result = run_powershell(command)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            diagnostic = json.loads(result.stdout.strip())
            self.assertEqual(diagnostic["large_numeric"], 1)
            self.assertTrue(diagnostic["duplicate_refused"])
            self.assertTrue(diagnostic["private_path_refused"])

            raw = evidence.read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
            self.assertTrue(raw.endswith(b"\n"))
            self.assertNotIn(b":\\", raw)
            self.assertEqual(
                json.loads(raw),
                {"schema": "baxy-test-evidence-v1", "status": "passed"},
            )

    def test_semver_rejects_trailing_lf_crlf_and_space(self) -> None:
        command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$valid = Get-SemVerParts -Version '1.0.8'
$cases = [ordered]@{{
    lf = "1.0.8`n"
    crlf = "1.0.8`r`n"
    space = '1.0.8 '
}}
$rejected = [ordered]@{{}}
foreach ($case in $cases.GetEnumerator()) {{
    try {{
        $null = Get-SemVerParts -Version ([string]$case.Value)
        $rejected[$case.Key] = $false
    }} catch {{
        $rejected[$case.Key] = $true
    }}
}}
[ordered]@{{
    valid = "$($valid.major).$($valid.minor).$($valid.patch)"
    rejected = $rejected
}} | ConvertTo-Json -Depth 4 -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(diagnostic["valid"], "1.0.8")
        self.assertEqual(
            diagnostic["rejected"],
            {"lf": True, "crlf": True, "space": True},
        )

    def test_wait_retries_parent_child_resume_race(self) -> None:
        command = f"""
. {ps_quote(SCRIPT)} `
    -CandidateSetup 'C:\\fixture\\Baxy.Setup.exe' `
    -ExpectedCurrentVersion '1.0.7' `
    -ExpectedInitialPreviousVersion '1.0.6' `
    -CandidateVersion '1.0.8' `
    -EvidencePath 'C:\\fixture\\unused.json'
$script:stateCalls = 0
function Get-Process {{
    [CmdletBinding()]
    param([string[]]$Name)
    return @()
}}
function Get-PendingLifecycleArtifacts {{
    param($Paths)
    return @()
}}
function Get-InstalledState {{
    param(
        $Paths,
        $ExpectedCurrent,
        $ExpectedPrevious,
        $ExpectedStableVersion,
        $ExpectedStableSetupSha256,
        $ExpectedStablePackageSha256,
        $ExpectedCurrentIdentity
    )
    $script:stateCalls++
    if ($script:stateCalls -eq 1) {{
        throw 'simulated gap before resume child'
    }}
    return [pscustomobject]@{{ marker = 'committed' }}
}}
function Start-Sleep {{
    param([int]$Milliseconds)
}}
$waited = Wait-ForInstalledState `
    -Paths ([pscustomobject]@{{}}) `
    -Expected @{{
        current = '1.0.8'
        previous = '1.0.7'
        stable_version = '1.0.8'
        stable_setup_sha256 = ('a' * 64)
        stable_package_sha256 = ('b' * 64)
        current_identity = $null
    }} `
    -MaximumSeconds 30
[ordered]@{{
    calls = $script:stateCalls
    marker = $waited.state.marker
}} | ConvertTo-Json -Compress
"""
        result = run_powershell(command)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        diagnostic = json.loads(result.stdout.strip())
        self.assertEqual(diagnostic, {"calls": 2, "marker": "committed"})


if __name__ == "__main__":
    unittest.main()
