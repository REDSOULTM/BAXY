namespace Baxy.Setup;

internal enum WindowsProductLifecycleOperation
{
    InstallOrUpdate,
    Rollback,
    Reconcile,
}

internal enum WindowsProductLifecycleDisposition
{
    Installed,
    Updated,
    RolledBack,
    Reconciled,
    Recovered,
    AlreadyCurrent,
    RequiresTargetSetup,
}

internal sealed record WindowsProductLifecycleRequest(
    WindowsProductLifecycleOperation Operation,
    CapturedSetupHost CapturedHost,
    VerifiedProductPackage ParentPackage,
    Func<Stream>? OpenPackageStream);

internal sealed record WindowsProductLifecycleResumeRequirement(
    string TransactionId,
    string? VerifiedTargetSetupPath,
    StableSetupHostIdentity TargetSetupIdentity);

internal sealed record WindowsProductLifecycleResult(
    WindowsProductLifecycleDisposition Disposition,
    string Version,
    string? TransactionId,
    WindowsProductLifecycleResumeRequirement? ResumeRequirement = null);

internal enum WindowsProductLifecycleFaultPoint
{
    PreparedDurable,
    HostReadyBeforeJournal,
    HostStagedDurable,
    ProductReadyBeforeJournal,
    ProductCommittedDurable,
    HostPublishedBeforeJournal,
    HostCommittedDurable,
    ShortcutReadyBeforeJournal,
    ShortcutCommittedDurable,
    RegistryIntentDurable,
    RegistryReadyBeforeIntegration,
    IntegrationReadyBeforeJournal,
    IntegrationCommittedDurable,
    CleanupComplete,
    CompleteDurable,
    AbortCleanupComplete,
}

internal interface IWindowsProductLifecycleFaultInjector
{
    void Checkpoint(WindowsProductLifecycleFaultPoint point);
}

internal interface IWindowsProductLifecycleRegistry
{
    void EnsureAbsentVerified();

    WindowsUninstallRegistryProbe ProbeOwnedVerified(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null);

    void ReconcileOwnedFromJournal(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null);
}

internal interface IWindowsProductLifecycleShortcut
{
    OwnedStartMenuShortcutSnapshot Probe();

    OwnedStartMenuShortcutSnapshot EnsureFromJournal(string transactionId);
}

internal interface IWindowsProductLifecycleHost
{
    StableSetupHostPaths Paths { get; }

    StableSetupHostInspection Inspect(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target);

    void VerifyUnchangedStableExact(StableSetupHostIdentity expected);

    void StageCandidate(
        string sourcePath,
        StableSetupHostIdentity target,
        StableSetupHostIdentity? before = null);

    void PublishFirstInstall(StableSetupHostIdentity target);

    void PublishUpdate(
        StableSetupHostIdentity before,
        StableSetupHostIdentity target);

    bool FinalizePublishedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target);

    bool DeleteStagedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target);

    void VerifyExact(string path, StableSetupHostIdentity expected);
}

internal interface IWindowsProductLifecycleCandidateVerifier
{
    VerifiedSetupHostCandidate VerifyStagedCandidate(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage);

    VerifiedSetupHostEvidence? RecoverVerifiedEvidenceIfPresent(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage);

    bool DeleteVerifiedEvidence(
        VerifiedSetupHostEvidence evidence,
        VerifiedProductPackage parentPackage);
}

internal sealed record WindowsProductLifecycleFactories(
    Func<InstallationEngine> CreateEngine,
    Func<WindowsIntegrationStore> CreateStore,
    Func<IWindowsProductLifecycleRegistry> CreateRegistry,
    Func<IWindowsProductLifecycleShortcut> CreateShortcut,
    Func<IWindowsProductLifecycleHost> CreateHost,
    Func<IWindowsProductLifecycleCandidateVerifier> CreateCandidateVerifier);

internal sealed record WindowsProductLifecyclePreparedPlan(
    string Operation,
    WindowsIntegrationState? Before,
    WindowsIntegrationActiveIdentity TargetActive,
    WindowsIntegrationStableSetupState TargetStableSetup);

internal sealed class WindowsProductLifecycle
{
    private const string ShortcutDescription = "BAXY";
    private const string ShortcutArguments = "--launch";
    private const int MaximumInstalledTreeEntries = 64;

    private readonly string _root;
    private readonly WindowsProductLifecycleFactories _factories;
    private readonly IWindowsProductLifecycleFaultInjector? _faultInjector;

    internal WindowsProductLifecycle(
        string installationRoot,
        WindowsProductLifecycleFactories factories,
        IWindowsProductLifecycleFaultInjector? faultInjector = null)
    {
        _root = PathSafety.ValidateInstallationRoot(installationRoot);
        _factories = ValidateFactories(factories);
        _faultInjector = faultInjector;
    }

    internal static WindowsProductLifecycle CreateProduction(
        CanonicalWindowsPaths paths,
        IWindowsProductLifecycleFaultInjector? faultInjector = null)
    {
        ArgumentNullException.ThrowIfNull(paths);
        StableSetupHostPaths hostPaths = new(
            paths.StableSetupHost,
            Path.Combine(paths.InstallationRoot, "Baxy.Setup.next.exe"),
            Path.Combine(paths.InstallationRoot, "Baxy.Setup.previous.exe"));
        ShellLinkSpecification shortcutSpecification = new(
            paths.StableSetupHost,
            paths.InstallationRoot,
            ShortcutDescription,
            ShortcutArguments,
            paths.StableSetupHost,
            IconIndex: 0,
            ShowCommand: 1);
        WindowsProductLifecycleFactories factories = new(
            () => new InstallationEngine(paths.InstallationRoot),
            () => new WindowsIntegrationStore(paths.InstallationRoot),
            static () => new WindowsProductLifecycleRegistryAdapter(
                new WindowsUninstallRegistry()),
            () => new WindowsProductLifecycleShortcutAdapter(
                new OwnedStartMenuShortcut(
                    paths.StartMenuDirectory,
                    paths.StartMenuShortcut,
                    shortcutSpecification)),
            () => new WindowsProductLifecycleHostAdapter(
                new StableSetupHostManager(hostPaths)),
            static () => new WindowsProductLifecycleCandidateVerifierAdapter(
                new SetupHostCandidateVerifier()));
        return new WindowsProductLifecycle(
            paths.InstallationRoot,
            factories,
            faultInjector);
    }

    internal WindowsProductLifecycleResult Execute(WindowsProductLifecycleRequest request)
    {
        ValidateRequest(request);
        using ProductOperationGate productGate = ProductOperationGate.Acquire(_root);

        if (!FileSystemEntryExists(_root))
        {
            PreflightMissingInstallationRoot(request);
        }

        using ProductOperationLease productLease = ProductOperationLease.AcquireWithHeldGate(
            _root,
            productGate,
            requireExistingRootAndLock: false);
        InstallationEngine engine = RequireFactoryResult(
            _factories.CreateEngine,
            "installation engine");
        if (!string.Equals(engine.InstallationRoot, _root, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The lifecycle installation engine changed the canonical installation root.");
        }

        return engine.UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            session => ExecuteExclusive(session, request));
    }

    private void PreflightMissingInstallationRoot(
        WindowsProductLifecycleRequest request)
    {
        if (request.Operation != WindowsProductLifecycleOperation.InstallOrUpdate)
        {
            throw new InstallationSafetyException(
                "Rollback and reconcile require an existing verified BAXY installation root.");
        }

        StableSetupHostManager.VerifyExact(
            request.CapturedHost.Path,
            request.CapturedHost.Identity);
        VerifyReopenablePackageSource(request);
        IWindowsProductLifecycleRegistry registry = RequireFactoryResult(
            _factories.CreateRegistry,
            "uninstall registry preflight");
        IWindowsProductLifecycleShortcut shortcut = RequireFactoryResult(
            _factories.CreateShortcut,
            "Start Menu shortcut preflight");
        registry.EnsureAbsentVerified();
        if (shortcut.Probe().State != OwnedStartMenuShortcutState.Missing)
        {
            throw new InstallationSafetyException(
                "A first-install preflight found an occupied BAXY Start Menu shortcut.");
        }

        if (FileSystemEntryExists(_root))
        {
            throw new InstallationSafetyException(
                "The missing BAXY installation root appeared during its read-only preflight.");
        }
    }

    private WindowsProductLifecycleResult ExecuteExclusive(
        InstallationEngine.ExclusiveInstallationSession session,
        WindowsProductLifecycleRequest request)
    {
        WindowsIntegrationStore store = RequireFactoryResult(
            _factories.CreateStore,
            "Windows integration store");
        if (!string.Equals(store.InstallationRoot, _root, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The lifecycle integration store changed the canonical installation root.");
        }

        IWindowsProductLifecycleRegistry registry = RequireFactoryResult(
            _factories.CreateRegistry,
            "uninstall registry integration");
        IWindowsProductLifecycleShortcut shortcut = RequireFactoryResult(
            _factories.CreateShortcut,
            "Start Menu shortcut integration");
        IWindowsProductLifecycleHost host = RequireFactoryResult(
            _factories.CreateHost,
            "stable Setup host integration");
        IWindowsProductLifecycleCandidateVerifier candidateVerifier = RequireFactoryResult(
            _factories.CreateCandidateVerifier,
            "Setup candidate verifier");
        RequireCanonicalHostPaths(host.Paths);
        host.VerifyExact(request.CapturedHost.Path, request.CapturedHost.Identity);

        WindowsInstallationIdentity? installationIdentity =
            store.RecoverAndReadInstallationIdentity();
        if (installationIdentity is null)
        {
            store.AssertInstallationIdentityMayBeInitialized();
        }

        WindowsIntegrationTransaction? transaction = installationIdentity is null
            ? null
            : store.RecoverAndReadTransaction();
        VerifiedInstallationIdentity? current = GetCurrentIdentityOrNull(session);
        bool recoveredExistingTransaction = transaction is not null;
        if (transaction is not null)
        {
            if (!InvocationMatchesTransaction(request, transaction))
            {
                return BuildRequiresTargetSetup(host, transaction);
            }

            WindowsIntegrationRecoveryDecision decision =
                WindowsIntegrationStore.DecideRecovery(ToActiveOrNull(current), transaction);
            if (decision == WindowsIntegrationRecoveryDecision.Abort)
            {
                AbortBeforeProductTransition(
                    store,
                    registry,
                    shortcut,
                    host,
                    candidateVerifier,
                    transaction,
                    request.ParentPackage);
                Checkpoint(WindowsProductLifecycleFaultPoint.AbortCleanupComplete);
                store.AbortTransaction(transaction);
                transaction = null;
                recoveredExistingTransaction = true;
                current = GetCurrentIdentityOrNull(session);
            }
        }

        if (transaction is null)
        {
            WindowsIntegrationState? before = store.ReadCommittedState();
            WindowsProductLifecycleResult? alreadyCurrent = TryCompleteReadOnlyIdempotence(
                session,
                store,
                registry,
                shortcut,
                host,
                before,
                request);
            if (alreadyCurrent is not null)
            {
                return alreadyCurrent;
            }

            WindowsProductLifecyclePreparedPlan plan = PrepareNewTransaction(
                session,
                registry,
                shortcut,
                host,
                before,
                current,
                request);
            installationIdentity ??= store.EnsureInstallationIdentity(
                new WindowsInstallationIdentity
                {
                    InstallId = Guid.NewGuid().ToString("N"),
                    InstallationRoot = _root,
                });
            transaction = new WindowsIntegrationTransaction
            {
                TransactionId = Guid.NewGuid().ToString("N"),
                Operation = plan.Operation,
                InstallId = installationIdentity.InstallId,
                DataSchema = installationIdentity.DataSchema,
                InstallationRoot = installationIdentity.InstallationRoot,
                Before = plan.Before,
                TargetActive = plan.TargetActive,
                TargetStableSetup = plan.TargetStableSetup,
            };
            store.BeginTransaction(transaction);
            Checkpoint(WindowsProductLifecycleFaultPoint.PreparedDurable);
        }

        RollForward(
            session,
            store,
            registry,
            shortcut,
            host,
            candidateVerifier,
            request,
            ref transaction);

        WindowsProductLifecycleDisposition disposition = recoveredExistingTransaction
            ? WindowsProductLifecycleDisposition.Recovered
            : DispositionFor(request.Operation, transaction.Before);
        string transactionId = transaction.TransactionId;
        string version = transaction.TargetActive.Version;
        store.CompleteTransaction(transaction);
        return new WindowsProductLifecycleResult(
            disposition,
            version,
            transactionId);
    }

    private static WindowsProductLifecyclePreparedPlan PrepareNewTransaction(
        InstallationEngine.ExclusiveInstallationSession session,
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationState? before,
        VerifiedInstallationIdentity? current,
        WindowsProductLifecycleRequest request)
    {
        WindowsIntegrationActiveIdentity targetActive;
        WindowsIntegrationStableSetupState targetStable;
        string operation;
        switch (request.Operation)
        {
            case WindowsProductLifecycleOperation.InstallOrUpdate:
                VerifyReopenablePackageSource(request);
                targetActive = ToActive(request.ParentPackage);
                targetStable = ToStable(request.CapturedHost, request.ParentPackage);
                operation = WindowsIntegrationOperation.InstallUpdate;
                if (before is null)
                {
                    if (current is not null)
                    {
                        throw new InstallationSafetyException(
                            "An existing verified engine installation without Windows integration state must be reconciled explicitly.");
                    }
                }
                else
                {
                    RequireActiveEquals(current, before.Active, "installed pre-update product");
                }

                break;

            case WindowsProductLifecycleOperation.Rollback:
                if (before is null)
                {
                    throw new InstallationSafetyException(
                        "Rollback requires an exact committed Windows integration state.");
                }

                RequireActiveEquals(current, before.Active, "installed pre-rollback product");
                VerifiedInstallationIdentity rollbackTarget =
                    session.GetVerifiedRollbackTargetIdentity();
                targetActive = ToActive(rollbackTarget);
                targetStable = before.StableSetup;
                RequireCapturedSetupMatchesStable(
                    request.CapturedHost,
                    request.ParentPackage,
                    targetStable);
                RequireRollbackParentPackage(
                    request.ParentPackage,
                    before.Active,
                    targetActive,
                    targetStable);
                operation = WindowsIntegrationOperation.Rollback;
                break;

            case WindowsProductLifecycleOperation.Reconcile:
                if (before is not null)
                {
                    throw new InstallationSafetyException(
                        "Reconcile cannot replace an existing committed Windows integration state.");
                }

                targetActive = ToActive(request.ParentPackage);
                RequireActiveEquals(current, targetActive, "verified engine product to reconcile");
                targetStable = ToStable(request.CapturedHost, request.ParentPackage);
                operation = WindowsIntegrationOperation.Reconcile;
                break;

            default:
                throw new InstallationSafetyException("The Windows product lifecycle operation is unsupported.");
        }

        RequireCapturedSetupMatchesStable(
            request.CapturedHost,
            request.ParentPackage,
            targetStable);
        PreflightExternalState(registry, shortcut, host, before, targetStable, request.Operation);
        return new WindowsProductLifecyclePreparedPlan(
            operation,
            before,
            targetActive,
            targetStable);
    }

    private void RollForward(
        InstallationEngine.ExclusiveInstallationSession session,
        WindowsIntegrationStore store,
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        IWindowsProductLifecycleCandidateVerifier candidateVerifier,
        WindowsProductLifecycleRequest request,
        ref WindowsIntegrationTransaction transaction)
    {
        if (PhaseEquals(transaction, WindowsIntegrationPhase.Prepared))
        {
            EnsureHostReadyBeforeProduct(
                host,
                candidateVerifier,
                transaction,
                request);
            Checkpoint(WindowsProductLifecycleFaultPoint.HostReadyBeforeJournal);
            transaction = Advance(store, transaction, WindowsIntegrationPhase.HostStaged);
            Checkpoint(WindowsProductLifecycleFaultPoint.HostStagedDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.HostStaged))
        {
            EnsureProductTarget(session, transaction, request);
            Checkpoint(WindowsProductLifecycleFaultPoint.ProductReadyBeforeJournal);
            transaction = Advance(store, transaction, WindowsIntegrationPhase.ProductCommitted);
            Checkpoint(WindowsProductLifecycleFaultPoint.ProductCommittedDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.ProductCommitted))
        {
            EnsureHostPublished(host, transaction);
            Checkpoint(WindowsProductLifecycleFaultPoint.HostPublishedBeforeJournal);
            transaction = Advance(store, transaction, WindowsIntegrationPhase.HostCommitted);
            Checkpoint(WindowsProductLifecycleFaultPoint.HostCommittedDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.HostCommitted))
        {
            OwnedStartMenuShortcutSnapshot shortcutSnapshot =
                shortcut.EnsureFromJournal(transaction.TransactionId);
            RequireExactShortcut(shortcutSnapshot, expected: null);
            WindowsIntegrationState target = BuildTargetState(
                session,
                transaction,
                shortcutSnapshot);
            Checkpoint(WindowsProductLifecycleFaultPoint.ShortcutReadyBeforeJournal);
            transaction = Advance(
                store,
                transaction,
                WindowsIntegrationPhase.ShortcutCommitted,
                target);
            Checkpoint(WindowsProductLifecycleFaultPoint.ShortcutCommittedDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.ShortcutCommitted))
        {
            transaction = Advance(store, transaction, WindowsIntegrationPhase.RegistryIntent);
            Checkpoint(WindowsProductLifecycleFaultPoint.RegistryIntentDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.RegistryIntent))
        {
            WindowsIntegrationState target = transaction.Target ??
                throw new InstallationSafetyException(
                    "The registry intent lacks its exact integration target.");
            registry.ReconcileOwnedFromJournal(
                BuildRegistrySpecification(target),
                BuildExpectedRegistry(transaction.Before));
            Checkpoint(WindowsProductLifecycleFaultPoint.RegistryReadyBeforeIntegration);
            _ = store.ApplyTransactionTarget(transaction);
            Checkpoint(WindowsProductLifecycleFaultPoint.IntegrationReadyBeforeJournal);
            transaction = Advance(
                store,
                transaction,
                WindowsIntegrationPhase.IntegrationCommitted);
            Checkpoint(WindowsProductLifecycleFaultPoint.IntegrationCommittedDurable);
        }

        if (PhaseEquals(transaction, WindowsIntegrationPhase.IntegrationCommitted))
        {
            CleanupPublishedHostAndEvidence(
                host,
                candidateVerifier,
                transaction,
                request.ParentPackage);
            Checkpoint(WindowsProductLifecycleFaultPoint.CleanupComplete);
            transaction = Advance(store, transaction, WindowsIntegrationPhase.Complete);
            Checkpoint(WindowsProductLifecycleFaultPoint.CompleteDurable);
        }

        if (!PhaseEquals(transaction, WindowsIntegrationPhase.Complete))
        {
            throw new InstallationSafetyException(
                "The Windows product lifecycle could not converge to its complete phase.");
        }

        AssertCommittedExterior(registry, shortcut, host, store, transaction);
    }

    private static void EnsureHostReadyBeforeProduct(
        IWindowsProductLifecycleHost host,
        IWindowsProductLifecycleCandidateVerifier candidateVerifier,
        WindowsIntegrationTransaction transaction,
        WindowsProductLifecycleRequest request)
    {
        StableSetupHostIdentity? beforeIdentity = ToHostIdentityOrNull(transaction.Before?.StableSetup);
        StableSetupHostIdentity targetIdentity = ToHostIdentity(transaction.TargetStableSetup);
        if (HostIdentitiesEqual(beforeIdentity, targetIdentity))
        {
            host.VerifyUnchangedStableExact(targetIdentity);
            return;
        }

        StableSetupHostInspection inspection = host.Inspect(beforeIdentity, targetIdentity);
        string candidatePath;
        if (beforeIdentity is null)
        {
            if (inspection.State == StableSetupHostRecoveryState.Empty)
            {
                host.StageCandidate(request.CapturedHost.Path, targetIdentity);
                inspection = host.Inspect(before: null, targetIdentity);
            }

            if (inspection.State == StableSetupHostRecoveryState.TargetPublished)
            {
                host.VerifyUnchangedStableExact(targetIdentity);
                return;
            }

            if (inspection.State != StableSetupHostRecoveryState.FirstInstallStaged)
            {
                throw UnexpectedHostState("prepare a first-install Setup host", inspection);
            }

            candidatePath = host.Paths.Next;
        }
        else
        {
            if (inspection.State == StableSetupHostRecoveryState.BeforeStable)
            {
                host.StageCandidate(request.CapturedHost.Path, targetIdentity, beforeIdentity);
                inspection = host.Inspect(beforeIdentity, targetIdentity);
            }

            candidatePath = inspection.State switch
            {
                StableSetupHostRecoveryState.UpdateStaged or
                StableSetupHostRecoveryState.UpdateBackupReady => host.Paths.Next,
                StableSetupHostRecoveryState.UpdateReplaced or
                StableSetupHostRecoveryState.TargetPublished => host.Paths.Stable,
                _ => throw UnexpectedHostState("prepare an updated Setup host", inspection),
            };
        }

        _ = candidateVerifier.VerifyStagedCandidate(
            candidatePath,
            targetIdentity,
            transaction.TransactionId,
            request.ParentPackage);
    }

    private static void EnsureProductTarget(
        InstallationEngine.ExclusiveInstallationSession session,
        WindowsIntegrationTransaction transaction,
        WindowsProductLifecycleRequest request)
    {
        VerifiedInstallationIdentity? current = GetCurrentIdentityOrNull(session);
        if (ActiveEquals(ToActiveOrNull(current), transaction.TargetActive))
        {
            return;
        }

        RequireActiveEquals(current, transaction.Before?.Active, "journaled product before mutation");
        switch (transaction.Operation)
        {
            case WindowsIntegrationOperation.InstallUpdate:
                Func<Stream> open = request.OpenPackageStream ??
                    throw new InstallationSafetyException(
                        "Install/update requires a safely reopenable verified package stream.");
                using (Stream stream = RequireReadableStream(open()))
                {
                    _ = session.InstallOrUpdate(stream);
                }

                break;

            case WindowsIntegrationOperation.Rollback:
                _ = session.Rollback();
                break;

            case WindowsIntegrationOperation.Reconcile:
                throw new InstallationSafetyException(
                    "Reconcile cannot mutate the product engine to manufacture its target.");

            default:
                throw new InstallationSafetyException("The journaled product operation is unsupported.");
        }

        RequireActiveEquals(
            GetCurrentIdentityOrNull(session),
            transaction.TargetActive,
            "journaled product target after mutation");
    }

    private static void EnsureHostPublished(
        IWindowsProductLifecycleHost host,
        WindowsIntegrationTransaction transaction)
    {
        StableSetupHostIdentity? before = ToHostIdentityOrNull(transaction.Before?.StableSetup);
        StableSetupHostIdentity target = ToHostIdentity(transaction.TargetStableSetup);
        if (HostIdentitiesEqual(before, target))
        {
            host.VerifyUnchangedStableExact(target);
            return;
        }

        StableSetupHostInspection inspection = host.Inspect(before, target);
        if (before is null)
        {
            if (inspection.State == StableSetupHostRecoveryState.FirstInstallStaged)
            {
                host.PublishFirstInstall(target);
                return;
            }

            if (inspection.State == StableSetupHostRecoveryState.TargetPublished)
            {
                host.VerifyUnchangedStableExact(target);
                return;
            }

            throw UnexpectedHostState("publish a first-install Setup host", inspection);
        }

        if (inspection.State is StableSetupHostRecoveryState.UpdateStaged or
            StableSetupHostRecoveryState.UpdateBackupReady)
        {
            host.PublishUpdate(before, target);
            return;
        }

        if (inspection.State == StableSetupHostRecoveryState.UpdateReplaced)
        {
            host.VerifyExact(host.Paths.Stable, target);
            host.VerifyExact(host.Paths.Previous, before);
            return;
        }

        if (inspection.State == StableSetupHostRecoveryState.TargetPublished)
        {
            host.VerifyUnchangedStableExact(target);
            return;
        }

        throw UnexpectedHostState("publish an updated Setup host", inspection);
    }

    private static void CleanupPublishedHostAndEvidence(
        IWindowsProductLifecycleHost host,
        IWindowsProductLifecycleCandidateVerifier candidateVerifier,
        WindowsIntegrationTransaction transaction,
        VerifiedProductPackage parentPackage)
    {
        StableSetupHostIdentity? before = ToHostIdentityOrNull(transaction.Before?.StableSetup);
        StableSetupHostIdentity target = ToHostIdentity(transaction.TargetStableSetup);
        bool unchanged = HostIdentitiesEqual(before, target);
        if (unchanged)
        {
            host.VerifyUnchangedStableExact(target);
            return;
        }

        _ = host.FinalizePublishedTarget(before, target);
        VerifiedSetupHostEvidence? evidence =
            candidateVerifier.RecoverVerifiedEvidenceIfPresent(
                host.Paths.Stable,
                target,
                transaction.TransactionId,
                parentPackage);
        if (evidence is not null)
        {
            _ = candidateVerifier.DeleteVerifiedEvidence(evidence, parentPackage);
        }

        host.VerifyUnchangedStableExact(target);
    }

    private static void AbortBeforeProductTransition(
        WindowsIntegrationStore store,
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        IWindowsProductLifecycleCandidateVerifier candidateVerifier,
        WindowsIntegrationTransaction transaction,
        VerifiedProductPackage parentPackage)
    {
        StableSetupHostIdentity? before = ToHostIdentityOrNull(transaction.Before?.StableSetup);
        StableSetupHostIdentity target = ToHostIdentity(transaction.TargetStableSetup);
        if (HostIdentitiesEqual(before, target))
        {
            host.VerifyUnchangedStableExact(target);
        }
        else
        {
            StableSetupHostInspection inspection = host.Inspect(before, target);
            StableSetupHostRecoveryState clean = before is null
                ? StableSetupHostRecoveryState.Empty
                : StableSetupHostRecoveryState.BeforeStable;
            StableSetupHostRecoveryState staged = before is null
                ? StableSetupHostRecoveryState.FirstInstallStaged
                : StableSetupHostRecoveryState.UpdateStaged;
            if (inspection.State == staged)
            {
                VerifiedSetupHostEvidence? evidence =
                    candidateVerifier.RecoverVerifiedEvidenceIfPresent(
                        host.Paths.Next,
                        target,
                        transaction.TransactionId,
                        parentPackage);
                if (evidence is not null)
                {
                    _ = candidateVerifier.DeleteVerifiedEvidence(evidence, parentPackage);
                }

                _ = host.DeleteStagedTarget(before, target);
                inspection = host.Inspect(before, target);
            }

            if (inspection.State != clean)
            {
                throw UnexpectedHostState("abort a pre-product Setup host", inspection);
            }
        }

        AssertBeforeExterior(registry, shortcut, host, transaction.Before);
        _ = store.ReadCommittedState();
    }

    private static void PreflightExternalState(
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationState? before,
        WindowsIntegrationStableSetupState targetStable,
        WindowsProductLifecycleOperation operation)
    {
        AssertBeforeExterior(registry, shortcut, host, before);
        StableSetupHostIdentity? beforeHost = ToHostIdentityOrNull(before?.StableSetup);
        StableSetupHostIdentity targetHost = ToHostIdentity(targetStable);
        if (HostIdentitiesEqual(beforeHost, targetHost))
        {
            host.VerifyUnchangedStableExact(targetHost);
            return;
        }

        StableSetupHostInspection inspection = host.Inspect(beforeHost, targetHost);
        StableSetupHostRecoveryState expected = beforeHost is null
            ? StableSetupHostRecoveryState.Empty
            : StableSetupHostRecoveryState.BeforeStable;
        if (operation == WindowsProductLifecycleOperation.Reconcile &&
            inspection.State == StableSetupHostRecoveryState.TargetPublished)
        {
            host.VerifyUnchangedStableExact(targetHost);
            return;
        }

        if (inspection.State != expected)
        {
            throw UnexpectedHostState("preflight the stable Setup host", inspection);
        }
    }

    private static void AssertBeforeExterior(
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationState? before)
    {
        OwnedStartMenuShortcutSnapshot observedShortcut = shortcut.Probe();
        if (before is null)
        {
            registry.EnsureAbsentVerified();
            if (observedShortcut.State != OwnedStartMenuShortcutState.Missing)
            {
                throw new InstallationSafetyException(
                    "A first-install lifecycle found an occupied BAXY Start Menu shortcut.");
            }

            return;
        }

        WindowsUninstallRegistryProbe registryProbe = registry.ProbeOwnedVerified(
            BuildRegistrySpecification(before));
        if (registryProbe != WindowsUninstallRegistryProbe.ExactTarget)
        {
            throw new InstallationSafetyException(
                "The existing uninstall registry does not match committed integration state.");
        }

        RequireExactShortcut(observedShortcut, before.Shortcut);
        host.VerifyExact(host.Paths.Stable, ToHostIdentity(before.StableSetup));
    }

    private static void AssertCommittedExterior(
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationStore store,
        WindowsIntegrationTransaction transaction)
    {
        WindowsIntegrationState target = transaction.Target ??
            throw new InstallationSafetyException("A complete lifecycle target is missing.");
        AssertCommittedExterior(registry, shortcut, host, store, target);
    }

    private static void AssertCommittedExterior(
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationStore store,
        WindowsIntegrationState target)
    {
        WindowsIntegrationState actual = store.ReadCommittedState() ??
            throw new InstallationSafetyException("The committed Windows integration state is missing.");
        if (actual != target)
        {
            throw new InstallationSafetyException(
                "The committed Windows integration state changed after publication.");
        }

        if (registry.ProbeOwnedVerified(BuildRegistrySpecification(target)) !=
            WindowsUninstallRegistryProbe.ExactTarget)
        {
            throw new InstallationSafetyException("The committed uninstall registry is not exact.");
        }

        RequireExactShortcut(shortcut.Probe(), target.Shortcut);
        host.VerifyUnchangedStableExact(ToHostIdentity(target.StableSetup));
    }

    private static WindowsProductLifecycleResult? TryCompleteReadOnlyIdempotence(
        InstallationEngine.ExclusiveInstallationSession session,
        WindowsIntegrationStore store,
        IWindowsProductLifecycleRegistry registry,
        IWindowsProductLifecycleShortcut shortcut,
        IWindowsProductLifecycleHost host,
        WindowsIntegrationState? before,
        WindowsProductLifecycleRequest request)
    {
        if (request.Operation != WindowsProductLifecycleOperation.InstallOrUpdate ||
            before is null)
        {
            return null;
        }

        WindowsIntegrationActiveIdentity invokedActive = ToActive(request.ParentPackage);
        if (invokedActive != before.Active)
        {
            return null;
        }

        RequireActiveEquals(
            GetCurrentIdentityOrNull(session),
            before.Active,
            "idempotent installed product");
        WindowsIntegrationStableSetupState invokedStable =
            ToStable(request.CapturedHost, request.ParentPackage);
        if (invokedStable != before.StableSetup)
        {
            throw new InstallationSafetyException(
                "An idempotent install cannot replace the same product version with different Setup host bytes.");
        }

        RequireCapturedSetupMatchesStable(
            request.CapturedHost,
            request.ParentPackage,
            before.StableSetup);
        AssertCommittedExterior(registry, shortcut, host, store, before);
        return new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.AlreadyCurrent,
            before.Active.Version,
            TransactionId: null);
    }

    private static WindowsIntegrationState BuildTargetState(
        InstallationEngine.ExclusiveInstallationSession session,
        WindowsIntegrationTransaction transaction,
        OwnedStartMenuShortcutSnapshot shortcut)
    {
        long installedBytes = session.UseVerifiedCurrentApplication(application =>
        {
            if (!string.Equals(
                    application.Version,
                    transaction.TargetActive.Version,
                    StringComparison.Ordinal))
            {
                throw new InstallationSafetyException(
                    "The verified installed application is not the journal target.");
            }

            SafeFileTree tree = PathSafety.InspectTree(
                application.WorkingDirectory,
                MaximumInstalledTreeEntries);
            long total = 0;
            foreach (string relative in tree.Files)
            {
                string path = PathSafety.GetStrictDescendantPath(
                    application.WorkingDirectory,
                    relative);
                PathSafety.AssertRegularFile(path);
                total = checked(total + new FileInfo(path).Length);
                PathSafety.AssertRegularFile(path);
            }

            return total;
        });
        long totalBytes = checked(
            installedBytes +
            transaction.TargetStableSetup.HostBytes +
            shortcut.Bytes);
        long estimatedKilobytes = Math.Max(1, checked((totalBytes + 1023) / 1024));
        if (estimatedKilobytes > int.MaxValue)
        {
            throw new InstallationSafetyException(
                "The verified installation size exceeds the Windows registry contract.");
        }

        return new WindowsIntegrationState
        {
            InstallId = transaction.InstallId,
            DataSchema = transaction.DataSchema,
            InstallationRoot = transaction.InstallationRoot,
            Active = transaction.TargetActive,
            StableSetup = transaction.TargetStableSetup,
            Shortcut = new WindowsIntegrationShortcutState
            {
                Sha256 = shortcut.Sha256!,
                Bytes = shortcut.Bytes,
            },
            EstimatedSizeKilobytes = checked((int)estimatedKilobytes),
        };
    }

    private static WindowsIntegrationTransaction Advance(
        WindowsIntegrationStore store,
        WindowsIntegrationTransaction current,
        string phase,
        WindowsIntegrationState? target = null)
    {
        WindowsIntegrationTransaction advanced = current with
        {
            Phase = phase,
            Target = target ?? current.Target,
        };
        store.AdvanceTransaction(current, advanced);
        return advanced;
    }

    private static WindowsProductLifecycleResult BuildRequiresTargetSetup(
        IWindowsProductLifecycleHost host,
        WindowsIntegrationTransaction transaction)
    {
        StableSetupHostIdentity? before = ToHostIdentityOrNull(transaction.Before?.StableSetup);
        StableSetupHostIdentity target = ToHostIdentity(transaction.TargetStableSetup);
        string? targetPath = null;
        if (HostIdentitiesEqual(before, target))
        {
            host.VerifyUnchangedStableExact(target);
            targetPath = host.Paths.Stable;
        }
        else
        {
            StableSetupHostInspection inspection = host.Inspect(before, target);
            if (inspection.Next == StableSetupHostArtifactState.Target)
            {
                host.VerifyExact(host.Paths.Next, target);
                targetPath = host.Paths.Next;
            }
            else if (inspection.Stable == StableSetupHostArtifactState.Target)
            {
                host.VerifyExact(host.Paths.Stable, target);
                targetPath = host.Paths.Stable;
            }
            else if (inspection.State is StableSetupHostRecoveryState.Foreign or
                     StableSetupHostRecoveryState.Contradictory)
            {
                throw UnexpectedHostState("locate the journal target Setup host", inspection);
            }
        }

        return new WindowsProductLifecycleResult(
            WindowsProductLifecycleDisposition.RequiresTargetSetup,
            transaction.TargetActive.Version,
            transaction.TransactionId,
            new WindowsProductLifecycleResumeRequirement(
                transaction.TransactionId,
                targetPath,
                target));
    }

    private static void VerifyReopenablePackageSource(
        WindowsProductLifecycleRequest request)
    {
        Func<Stream> open = request.OpenPackageStream ??
            throw new InstallationSafetyException(
                "Install/update requires a safely reopenable verified package stream.");
        using Stream stream = RequireReadableStream(open());
        VerifiedProductPackage reopened = new ProductPackageVerifier().Verify(stream);
        RequirePackageEquals(
            reopened,
            request.ParentPackage,
            "The reopened product package differs from the verified parent Setup package.");
    }

    private static Stream RequireReadableStream(Stream? stream)
    {
        if (stream is null || !stream.CanRead)
        {
            stream?.Dispose();
            throw new InstallationSafetyException(
                "The reopenable product package factory returned no readable stream.");
        }

        return stream;
    }

    private static void ValidateRequest(WindowsProductLifecycleRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(request.CapturedHost);
        ArgumentNullException.ThrowIfNull(request.CapturedHost.Identity);
        ArgumentNullException.ThrowIfNull(request.ParentPackage);
        _ = Path.GetFullPath(request.CapturedHost.Path);
        _ = ToActive(request.ParentPackage);
        _ = ToStable(request.CapturedHost, request.ParentPackage);
    }

    private static bool InvocationMatchesTransaction(
        WindowsProductLifecycleRequest request,
        WindowsIntegrationTransaction transaction)
    {
        string expectedOperation = request.Operation switch
        {
            WindowsProductLifecycleOperation.InstallOrUpdate => WindowsIntegrationOperation.InstallUpdate,
            WindowsProductLifecycleOperation.Rollback => WindowsIntegrationOperation.Rollback,
            WindowsProductLifecycleOperation.Reconcile => WindowsIntegrationOperation.Reconcile,
            _ => string.Empty,
        };
        if (!string.Equals(transaction.Operation, expectedOperation, StringComparison.Ordinal))
        {
            return false;
        }

        WindowsIntegrationStableSetupState invokedStable =
            ToStable(request.CapturedHost, request.ParentPackage);
        if (invokedStable != transaction.TargetStableSetup)
        {
            return false;
        }

        if (transaction.Operation == WindowsIntegrationOperation.Rollback)
        {
            return RollbackParentPackageMatches(
                request.ParentPackage,
                transaction.Before!.Active,
                transaction.TargetActive,
                transaction.TargetStableSetup);
        }

        return ActiveEquals(ToActive(request.ParentPackage), transaction.TargetActive);
    }

    private static void RequireCapturedSetupMatchesStable(
        CapturedSetupHost captured,
        VerifiedProductPackage package,
        WindowsIntegrationStableSetupState stable)
    {
        if (captured.Identity.Bytes != stable.HostBytes ||
            !string.Equals(captured.Identity.Sha256, stable.HostSha256, StringComparison.Ordinal) ||
            !string.Equals(package.Version, stable.Version, StringComparison.Ordinal) ||
            !string.Equals(
                package.PackageSha256,
                stable.EmbeddedPackageSha256,
                StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The captured Setup host and verified embedded package do not match the stable-host plan.");
        }
    }

    private static void RequireRollbackParentPackage(
        VerifiedProductPackage package,
        WindowsIntegrationActiveIdentity before,
        WindowsIntegrationActiveIdentity target,
        WindowsIntegrationStableSetupState stable)
    {
        if (!RollbackParentPackageMatches(package, before, target, stable))
        {
            throw new InstallationSafetyException(
                "The rollback Setup embedded package does not match either verified product side associated with the preserved stable host.");
        }
    }

    private static bool RollbackParentPackageMatches(
        VerifiedProductPackage package,
        WindowsIntegrationActiveIdentity before,
        WindowsIntegrationActiveIdentity target,
        WindowsIntegrationStableSetupState stable)
    {
        WindowsIntegrationActiveIdentity invoked = ToActive(package);
        bool stableMatchesBefore = StableEmbedsActive(stable, before);
        bool stableMatchesTarget = StableEmbedsActive(stable, target);
        return (stableMatchesBefore && invoked == before) ||
            (stableMatchesTarget && invoked == target);
    }

    private static bool StableEmbedsActive(
        WindowsIntegrationStableSetupState stable,
        WindowsIntegrationActiveIdentity active) =>
        string.Equals(stable.Version, active.Version, StringComparison.Ordinal) &&
        string.Equals(
            stable.EmbeddedPackageSha256,
            active.PackageSha256,
            StringComparison.Ordinal);

    private static WindowsIntegrationActiveIdentity ToActive(VerifiedProductPackage package) =>
        new()
        {
            Version = package.Version,
            DataSchema = package.DataSchema,
            PackageSha256 = package.PackageSha256,
            ManifestSha256 = package.ManifestSha256,
            ContentId = package.ContentId,
        };

    private static WindowsIntegrationActiveIdentity ToActive(
        VerifiedInstallationIdentity identity) =>
        new()
        {
            Version = identity.Version,
            DataSchema = identity.DataSchema,
            PackageSha256 = identity.PackageSha256,
            ManifestSha256 = identity.ManifestSha256,
            ContentId = identity.ContentId,
        };

    private static WindowsIntegrationActiveIdentity? ToActiveOrNull(
        VerifiedInstallationIdentity? identity) =>
        identity is null ? null : ToActive(identity);

    private static WindowsIntegrationStableSetupState ToStable(
        CapturedSetupHost captured,
        VerifiedProductPackage package) =>
        new()
        {
            Version = package.Version,
            EmbeddedPackageSha256 = package.PackageSha256,
            HostSha256 = captured.Identity.Sha256,
            HostBytes = captured.Identity.Bytes,
        };

    private static StableSetupHostIdentity ToHostIdentity(
        WindowsIntegrationStableSetupState state) =>
        new(state.HostSha256, state.HostBytes);

    private static StableSetupHostIdentity? ToHostIdentityOrNull(
        WindowsIntegrationStableSetupState? state) =>
        state is null ? null : ToHostIdentity(state);

    private static VerifiedInstallationIdentity? GetCurrentIdentityOrNull(
        InstallationEngine.ExclusiveInstallationSession session) =>
        session.GetCurrentVersion() is null
            ? null
            : session.GetVerifiedCurrentIdentity();

    private static WindowsUninstallRegistrySpecification BuildRegistrySpecification(
        WindowsIntegrationState state) =>
        new(
            state.InstallId,
            state.Active.Version,
            state.DataSchema,
            state.InstallationRoot,
            Path.Combine(state.InstallationRoot, "Baxy.Setup.exe"),
            state.StableSetup.HostSha256,
            state.EstimatedSizeKilobytes);

    private static WindowsUninstallRegistryExpectedExisting? BuildExpectedRegistry(
        WindowsIntegrationState? before) =>
        before is null
            ? null
            : new WindowsUninstallRegistryExpectedExisting(
                before.Active.Version,
                before.StableSetup.HostSha256,
                before.EstimatedSizeKilobytes);

    private static void RequireActiveEquals(
        VerifiedInstallationIdentity? actual,
        WindowsIntegrationActiveIdentity? expected,
        string description)
    {
        if (!ActiveEquals(ToActiveOrNull(actual), expected))
        {
            throw new InstallationSafetyException(
                $"The {description} does not match its exact verified identity.");
        }
    }

    private static bool ActiveEquals(
        WindowsIntegrationActiveIdentity? left,
        WindowsIntegrationActiveIdentity? right) =>
        left is null ? right is null : left == right;

    private static bool HostIdentitiesEqual(
        StableSetupHostIdentity? left,
        StableSetupHostIdentity right) =>
        left is not null && left == right;

    private static void RequireExactShortcut(
        OwnedStartMenuShortcutSnapshot actual,
        WindowsIntegrationShortcutState? expected)
    {
        if (actual.State != OwnedStartMenuShortcutState.Exact ||
            !IsLowercaseSha256(actual.Sha256) ||
            actual.Bytes <= 0 ||
            (expected is not null &&
             (!string.Equals(actual.Sha256, expected.Sha256, StringComparison.Ordinal) ||
              actual.Bytes != expected.Bytes)))
        {
            throw new InstallationSafetyException(
                "The BAXY Start Menu shortcut does not match its exact owned identity.");
        }
    }

    private static bool IsLowercaseSha256(string? value) =>
        value is { Length: 64 } &&
        value.All(static character =>
            character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static void RequirePackageEquals(
        VerifiedProductPackage actual,
        VerifiedProductPackage expected,
        string message)
    {
        if (actual.DataSchema != expected.DataSchema ||
            !string.Equals(actual.Version, expected.Version, StringComparison.Ordinal) ||
            !string.Equals(actual.PackageSha256, expected.PackageSha256, StringComparison.Ordinal) ||
            !string.Equals(actual.ManifestSha256, expected.ManifestSha256, StringComparison.Ordinal) ||
            !string.Equals(actual.ContentId, expected.ContentId, StringComparison.Ordinal) ||
            !string.Equals(actual.Commit, expected.Commit, StringComparison.Ordinal) ||
            actual.PackageLength != expected.PackageLength ||
            actual.SourceDateEpoch != expected.SourceDateEpoch)
        {
            throw new InstallationSafetyException(message);
        }
    }

    private static bool PhaseEquals(
        WindowsIntegrationTransaction transaction,
        string phase) =>
        string.Equals(transaction.Phase, phase, StringComparison.Ordinal);

    private static bool FileSystemEntryExists(string path)
    {
        try
        {
            _ = File.GetAttributes(path);
            return true;
        }
        catch (FileNotFoundException)
        {
            return false;
        }
        catch (DirectoryNotFoundException)
        {
            return false;
        }
    }

    private static WindowsProductLifecycleDisposition DispositionFor(
        WindowsProductLifecycleOperation operation,
        WindowsIntegrationState? before) =>
        operation switch
        {
            WindowsProductLifecycleOperation.InstallOrUpdate when before is null =>
                WindowsProductLifecycleDisposition.Installed,
            WindowsProductLifecycleOperation.InstallOrUpdate =>
                WindowsProductLifecycleDisposition.Updated,
            WindowsProductLifecycleOperation.Rollback =>
                WindowsProductLifecycleDisposition.RolledBack,
            WindowsProductLifecycleOperation.Reconcile =>
                WindowsProductLifecycleDisposition.Reconciled,
            _ => throw new InstallationSafetyException("The lifecycle disposition is unsupported."),
        };

    private static InstallationSafetyException UnexpectedHostState(
        string operation,
        StableSetupHostInspection inspection) =>
        new(
            $"Cannot {operation}: stable={inspection.Stable}, next={inspection.Next}, " +
            $"previous={inspection.Previous}, recovery={inspection.State}.");

    private void RequireCanonicalHostPaths(StableSetupHostPaths paths)
    {
        StableSetupHostPaths expected = new(
            Path.Combine(_root, "Baxy.Setup.exe"),
            Path.Combine(_root, "Baxy.Setup.next.exe"),
            Path.Combine(_root, "Baxy.Setup.previous.exe"));
        if (!string.Equals(paths.Stable, expected.Stable, StringComparison.Ordinal) ||
            !string.Equals(paths.Next, expected.Next, StringComparison.Ordinal) ||
            !string.Equals(paths.Previous, expected.Previous, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The stable Setup lifecycle paths are not the exact canonical siblings.");
        }
    }

    private static WindowsProductLifecycleFactories ValidateFactories(
        WindowsProductLifecycleFactories factories)
    {
        ArgumentNullException.ThrowIfNull(factories);
        ArgumentNullException.ThrowIfNull(factories.CreateEngine);
        ArgumentNullException.ThrowIfNull(factories.CreateStore);
        ArgumentNullException.ThrowIfNull(factories.CreateRegistry);
        ArgumentNullException.ThrowIfNull(factories.CreateShortcut);
        ArgumentNullException.ThrowIfNull(factories.CreateHost);
        ArgumentNullException.ThrowIfNull(factories.CreateCandidateVerifier);
        return factories;
    }

    private static T RequireFactoryResult<T>(Func<T> factory, string description)
        where T : class =>
        factory() ?? throw new InstallationSafetyException(
            $"The lifecycle {description} factory returned null.");

    private void Checkpoint(WindowsProductLifecycleFaultPoint point) =>
        _faultInjector?.Checkpoint(point);
}
