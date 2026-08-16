namespace Baxy.Setup;

internal sealed class WindowsProductLifecycleRegistryAdapter(
    WindowsUninstallRegistry registry) : IWindowsProductLifecycleRegistry
{
    private readonly WindowsUninstallRegistry _registry = registry ??
        throw new ArgumentNullException(nameof(registry));

    public void EnsureAbsentVerified() => _registry.EnsureAbsentVerified();

    public WindowsUninstallRegistryProbe ProbeOwnedVerified(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null) =>
        _registry.ProbeOwnedVerified(target, expectedExisting);

    public void ReconcileOwnedFromJournal(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null) =>
        _registry.ReconcileOwnedFromJournal(target, expectedExisting);
}

internal sealed class WindowsProductLifecycleShortcutAdapter(
    OwnedStartMenuShortcut shortcut) : IWindowsProductLifecycleShortcut
{
    private readonly OwnedStartMenuShortcut _shortcut = shortcut ??
        throw new ArgumentNullException(nameof(shortcut));

    public OwnedStartMenuShortcutSnapshot Probe() => _shortcut.Probe();

    public OwnedStartMenuShortcutSnapshot EnsureFromJournal(string transactionId) =>
        _shortcut.EnsureFromJournal(transactionId);
}

internal sealed class WindowsProductLifecycleHostAdapter(
    StableSetupHostManager host) : IWindowsProductLifecycleHost
{
    private readonly StableSetupHostManager _host = host ??
        throw new ArgumentNullException(nameof(host));

    public StableSetupHostPaths Paths => _host.Paths;

    public StableSetupHostInspection Inspect(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target) =>
        _host.Inspect(before, target);

    public void VerifyUnchangedStableExact(StableSetupHostIdentity expected) =>
        _host.VerifyUnchangedStableExact(expected);

    public void StageCandidate(
        string sourcePath,
        StableSetupHostIdentity target,
        StableSetupHostIdentity? before = null) =>
        _host.StageCandidate(sourcePath, target, before);

    public void PublishFirstInstall(StableSetupHostIdentity target) =>
        _host.PublishFirstInstall(target);

    public void PublishUpdate(
        StableSetupHostIdentity before,
        StableSetupHostIdentity target) =>
        _host.PublishUpdate(before, target);

    public bool FinalizePublishedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target) =>
        _host.FinalizePublishedTarget(before, target);

    public bool DeleteStagedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target) =>
        _host.DeleteStagedTarget(before, target);

    public void VerifyExact(string path, StableSetupHostIdentity expected) =>
        StableSetupHostManager.VerifyExact(path, expected);
}

internal sealed class WindowsProductLifecycleCandidateVerifierAdapter(
    SetupHostCandidateVerifier verifier) : IWindowsProductLifecycleCandidateVerifier
{
    private readonly SetupHostCandidateVerifier _verifier = verifier ??
        throw new ArgumentNullException(nameof(verifier));

    public VerifiedSetupHostCandidate VerifyStagedCandidate(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage) =>
        _verifier.VerifyStagedCandidate(
            applicationPath,
            expectedIdentity,
            transactionId,
            parentPackage);

    public VerifiedSetupHostEvidence? RecoverVerifiedEvidenceIfPresent(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage) =>
        _verifier.RecoverVerifiedEvidenceIfPresent(
            applicationPath,
            expectedIdentity,
            transactionId,
            parentPackage);

    public bool DeleteVerifiedEvidence(
        VerifiedSetupHostEvidence evidence,
        VerifiedProductPackage parentPackage) =>
        SetupHostCandidateVerifier.DeleteVerifiedEvidence(evidence, parentPackage);
}
