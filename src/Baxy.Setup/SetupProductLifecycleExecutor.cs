namespace Baxy.Setup;

internal sealed record SetupProductLifecycleExecutorFactories(
    Func<CapturedSetupHost> CaptureCurrentHost,
    Func<VerifiedProductPackage> VerifyEmbeddedPackage,
    Func<Stream> OpenEmbeddedPackage,
    Func<WindowsProductLifecycleRequest, WindowsProductLifecycleResult> ExecuteLifecycle,
    Func<
        WindowsProductLifecycleResumeRequirement,
        WindowsProductLifecycleOperation,
        uint> LaunchResume);

internal sealed class SetupProductLifecycleExecutor
{
    private readonly SetupProductLifecycleExecutorFactories _factories;

    internal SetupProductLifecycleExecutor(
        SetupProductLifecycleExecutorFactories factories)
    {
        ArgumentNullException.ThrowIfNull(factories);
        ArgumentNullException.ThrowIfNull(factories.CaptureCurrentHost);
        ArgumentNullException.ThrowIfNull(factories.VerifyEmbeddedPackage);
        ArgumentNullException.ThrowIfNull(factories.OpenEmbeddedPackage);
        ArgumentNullException.ThrowIfNull(factories.ExecuteLifecycle);
        ArgumentNullException.ThrowIfNull(factories.LaunchResume);
        _factories = factories;
    }

    internal static SetupProductLifecycleExecutor CreateProduction(
        CanonicalWindowsPaths paths)
    {
        ArgumentNullException.ThrowIfNull(paths);
        SetupHostCandidateVerifier hostVerifier = new();
        WindowsProductLifecycle lifecycle = WindowsProductLifecycle.CreateProduction(paths);
        WindowsSetupResumeLauncher resumeLauncher = new(paths);
        return new SetupProductLifecycleExecutor(
            new SetupProductLifecycleExecutorFactories(
                hostVerifier.CaptureCurrentHost,
                static () => EmbeddedPackageSource.Verify(),
                static () => EmbeddedPackageSource.OpenPayload(),
                lifecycle.Execute,
                resumeLauncher.Launch));
    }

    internal int Execute(SetupCommandKind command)
    {
        WindowsProductLifecycleOperation operation = command switch
        {
            SetupCommandKind.Install => WindowsProductLifecycleOperation.InstallOrUpdate,
            SetupCommandKind.Rollback => WindowsProductLifecycleOperation.Rollback,
            _ => throw new ArgumentException(
                "Only install/update or rollback may use the product lifecycle executor.",
                nameof(command)),
        };

        CapturedSetupHost capturedHost = _factories.CaptureCurrentHost() ??
            throw new InstallationSafetyException(
                "The current Setup host capture returned no identity.");
        VerifiedProductPackage embeddedPackage = _factories.VerifyEmbeddedPackage() ??
            throw new ProductPackageException(
                "The current Setup host returned no verified embedded package.");
        Func<Stream>? openPackage = operation == WindowsProductLifecycleOperation.InstallOrUpdate
            ? _factories.OpenEmbeddedPackage
            : null;
        WindowsProductLifecycleResult result = _factories.ExecuteLifecycle(
            new WindowsProductLifecycleRequest(
                operation,
                capturedHost,
                embeddedPackage,
                openPackage)) ??
            throw new InstallationSafetyException(
                "The Windows product lifecycle returned no result.");

        if (result.Disposition is
            WindowsProductLifecycleDisposition.Installed or
            WindowsProductLifecycleDisposition.Updated or
            WindowsProductLifecycleDisposition.RolledBack or
            WindowsProductLifecycleDisposition.Reconciled or
            WindowsProductLifecycleDisposition.Recovered or
            WindowsProductLifecycleDisposition.AlreadyCurrent)
        {
            if (result.ResumeRequirement is not null)
            {
                throw new InstallationSafetyException(
                    "A completed Windows product lifecycle returned a contradictory resume target.");
            }

            return 0;
        }

        if (result.Disposition != WindowsProductLifecycleDisposition.RequiresTargetSetup)
        {
            throw new InstallationSafetyException(
                "The Windows product lifecycle returned an unsupported disposition.");
        }

        WindowsProductLifecycleResumeRequirement requirement = result.ResumeRequirement ??
            throw new InstallationSafetyException(
                "The Windows product lifecycle omitted its required Setup-resume target.");
        if (!string.Equals(
                result.TransactionId,
                requirement.TransactionId,
                StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The Windows product lifecycle changed its Setup-resume transaction identity.");
        }

        uint processId = _factories.LaunchResume(requirement, operation);
        if (processId == 0)
        {
            throw new InstallationSafetyException(
                "The verified Setup-resume launch returned no process identity.");
        }

        return 0;
    }
}
