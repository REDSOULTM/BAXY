using System.ComponentModel;
using System.Diagnostics;

namespace Baxy.Setup;

internal sealed class SetupUninstallExecutor
{
    private const string ShortcutDescription = "BAXY";
    private const string ShortcutArguments = "--launch";
    private const string TombstonePrefix = ".BAXY-uninstall-";
    private const string TombstoneEnvironmentVariable = "BAXY_UNINSTALL_TOMBSTONE";
    private const string DelayEnvironmentVariable = "BAXY_UNINSTALL_DELAY";

    private readonly CanonicalWindowsPaths _paths;

    private SetupUninstallExecutor(CanonicalWindowsPaths paths)
    {
        _paths = paths ?? throw new ArgumentNullException(nameof(paths));
    }

    internal static SetupUninstallExecutor CreateProduction(CanonicalWindowsPaths paths) =>
        new(paths);

    internal int Execute(SetupCommand command)
    {
        UninstallDataPolicy policy = RequireCanonicalCommand(command);
        using ProductOperationGate productGate =
            ProductOperationGate.Acquire(_paths.InstallationRoot);
        using InstallationOperationGate installationGate =
            InstallationOperationGate.Acquire(_paths.InstallationRoot);

        VerifiedUninstall verified = VerifyInstalledProduct(productGate);
        if (policy == UninstallDataPolicy.PurgeData)
        {
            PreflightDataRoot();
        }

        string tombstone = BuildTombstonePath(
            _paths.InstallationRoot,
            Guid.NewGuid());
        MoveInstallationRoot(_paths.InstallationRoot, tombstone);

        _ = verified.Shortcut.DeleteOwnedVerifiedAfterInstallationMove(
            verified.State.Shortcut.Sha256,
            verified.State.Shortcut.Bytes);
        _ = verified.Registry.DeleteCapturedOwned(verified.RegistryDeletion);

        if (policy == UninstallDataPolicy.PurgeData)
        {
            string parent = Directory.GetParent(_paths.DataRoot)?.FullName ??
                throw new InstallationSafetyException(
                    "The canonical BAXY data directory has no parent.");
            PathSafety.DeleteTreeFailClosed(parent, _paths.DataRoot);
        }

        _ = LaunchTombstoneCleanup(_paths.InstallationRoot, tombstone);
        return 0;
    }

    private VerifiedUninstall VerifyInstalledProduct(ProductOperationGate productGate)
    {
        VerifyCurrentProcessPath();
        using ProductOperationLease productLease =
            ProductOperationLease.AcquireWithHeldGate(
                _paths.InstallationRoot,
                productGate,
                requireExistingRootAndLock: true);

        InstallationEngine engine = new(_paths.InstallationRoot);
        WindowsIntegrationState state = engine.UseExclusiveInstallation(
            requireExistingRootAndLock: true,
            session => ReadVerifiedCommittedState(
                new WindowsIntegrationStore(_paths.InstallationRoot),
                session.GetVerifiedCurrentIdentity()));

        StableSetupHostManager.VerifyExact(
            _paths.StableSetupHost,
            new StableSetupHostIdentity(
                state.StableSetup.HostSha256,
                state.StableSetup.HostBytes));

        OwnedStartMenuShortcut shortcut = CreateShortcut();
        OwnedStartMenuShortcutSnapshot shortcutSnapshot = shortcut.Probe();
        if (shortcutSnapshot.State != OwnedStartMenuShortcutState.Exact ||
            !string.Equals(
                shortcutSnapshot.Sha256,
                state.Shortcut.Sha256,
                StringComparison.Ordinal) ||
            shortcutSnapshot.Bytes != state.Shortcut.Bytes)
        {
            throw new InstallationSafetyException(
                "The installed BAXY Start Menu shortcut does not match committed state.");
        }

        WindowsUninstallRegistry registry = new();
        WindowsUninstallRegistryDeletionIntent deletion =
            registry.CaptureOwnedForDeletion(BuildRegistrySpecification(state));
        return new VerifiedUninstall(state, shortcut, registry, deletion);
    }

    private WindowsIntegrationState ReadVerifiedCommittedState(
        WindowsIntegrationStore store,
        VerifiedInstallationIdentity current)
    {
        WindowsInstallationIdentity identity = store.ReadInstallationIdentity() ??
            throw new InstallationSafetyException(
                "The installed BAXY identity is missing.");
        if (!string.Equals(
                identity.InstallationRoot,
                _paths.InstallationRoot,
                StringComparison.Ordinal) ||
            HasIntegrationTransactionArtifact())
        {
            throw new InstallationSafetyException(
                "BAXY cannot be uninstalled during an incomplete product transition.");
        }

        WindowsIntegrationState state = store.ReadCommittedState() ??
            throw new InstallationSafetyException(
                "The committed BAXY Windows integration state is missing.");
        WindowsIntegrationActiveIdentity active = state.Active;
        if (!string.Equals(active.Version, current.Version, StringComparison.Ordinal) ||
            active.DataSchema != current.DataSchema ||
            !string.Equals(
                active.PackageSha256,
                current.PackageSha256,
                StringComparison.Ordinal) ||
            !string.Equals(
                active.ManifestSha256,
                current.ManifestSha256,
                StringComparison.Ordinal) ||
            !string.Equals(active.ContentId, current.ContentId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The current BAXY version does not match committed Windows integration state.");
        }

        return state;
    }

    private bool HasIntegrationTransactionArtifact()
    {
        string[] names =
        [
            WindowsIntegrationStore.TransactionFileName,
            WindowsIntegrationStore.TransactionNextFileName,
            WindowsIntegrationStore.TransactionPreviousFileName,
        ];
        foreach (string name in names)
        {
            string path = Path.Combine(_paths.InstallationRoot, name);
            if (File.Exists(path) || Directory.Exists(path))
            {
                return true;
            }
        }

        return false;
    }

    private void VerifyCurrentProcessPath()
    {
        string? processPath = Environment.ProcessPath;
        if (string.IsNullOrWhiteSpace(processPath) ||
            !Path.IsPathFullyQualified(processPath) ||
            !string.Equals(
                Path.GetFullPath(processPath),
                _paths.StableSetupHost,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException(
                "Uninstall must run from the installed Baxy.Setup.exe host.");
        }
    }

    private OwnedStartMenuShortcut CreateShortcut() =>
        new(
            _paths.StartMenuDirectory,
            _paths.StartMenuShortcut,
            new ShellLinkSpecification(
                _paths.StableSetupHost,
                _paths.InstallationRoot,
                ShortcutDescription,
                ShortcutArguments,
                _paths.StableSetupHost,
                IconIndex: 0,
                ShowCommand: 1));

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

    private void PreflightDataRoot()
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(_paths.DataRoot);
        if (File.Exists(_paths.DataRoot) && !Directory.Exists(_paths.DataRoot))
        {
            throw new InstallationSafetyException(
                "The canonical BAXY data path is occupied by a file.");
        }

        if (Directory.Exists(_paths.DataRoot))
        {
            PathSafety.AssertRegularDirectory(_paths.DataRoot);
        }
    }

    internal static string BuildTombstonePath(string installationRoot, Guid identifier)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        if (identifier == Guid.Empty)
        {
            throw new InstallationSafetyException(
                "The uninstall tombstone identifier cannot be empty.");
        }

        string parent = Directory.GetParent(root)?.FullName ??
            throw new InstallationSafetyException(
                "The BAXY installation root has no parent directory.");
        string tombstone = Path.Combine(
            parent,
            TombstonePrefix + identifier.ToString("N"));
        PathSafety.AssertExistingChainHasNoReparsePoint(tombstone);
        return tombstone;
    }

    internal static void MoveInstallationRoot(string installationRoot, string tombstone)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        ValidateTombstone(root, tombstone);
        if (!Directory.Exists(root) || File.Exists(root))
        {
            throw new InstallationSafetyException(
                "The BAXY installation root is not an existing directory.");
        }

        if (Directory.Exists(tombstone) || File.Exists(tombstone))
        {
            throw new InstallationSafetyException(
                "The unique BAXY uninstall tombstone is already occupied.");
        }

        LeaveInstallationWorkingDirectory(root);
        try
        {
            Directory.Move(root, tombstone);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                "Windows could not move the BAXY installation out of its canonical path.",
                exception);
        }

        if (Directory.Exists(root) || File.Exists(root) || !Directory.Exists(tombstone))
        {
            throw new InstallationSafetyException(
                "Windows did not complete the BAXY installation move.");
        }
    }

    private static void LeaveInstallationWorkingDirectory(string root)
    {
        string parent = Directory.GetParent(root)?.FullName ??
            throw new InstallationSafetyException(
                "The BAXY installation root has no parent directory.");
        PathSafety.AssertExistingChainHasNoReparsePoint(parent);
        try
        {
            Directory.SetCurrentDirectory(parent);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                "BAXY could not leave its installation working directory before uninstall.",
                exception);
        }
    }

    internal static uint LaunchTombstoneCleanup(
        string installationRoot,
        string tombstone)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        ValidateTombstone(root, tombstone);
        string systemDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System);
        string commandProcessor = RequireSystemExecutable(systemDirectory, "cmd.exe");
        string delay = RequireSystemExecutable(systemDirectory, "ping.exe");

        ProcessStartInfo startInfo = new()
        {
            FileName = commandProcessor,
            WorkingDirectory = Path.GetTempPath(),
            UseShellExecute = false,
            CreateNoWindow = true,
            Arguments = $"/d /e:on /q /v:off /s /c \"{BuildCleanupCommand()}\"",
        };
        startInfo.Environment[TombstoneEnvironmentVariable] = tombstone;
        startInfo.Environment[DelayEnvironmentVariable] = delay;

        try
        {
            using Process process = Process.Start(startInfo) ??
                throw new InstallationSafetyException(
                    "Windows returned no uninstall cleanup process.");
            return checked((uint)process.Id);
        }
        catch (Exception exception) when (
            exception is Win32Exception or InvalidOperationException or IOException or
                OverflowException)
        {
            throw new InstallationSafetyException(
                "Windows could not start the minimal uninstall cleanup command.",
                exception);
        }
    }

    internal static string BuildCleanupCommand() =>
        $"for /l %i in (1,1,3) do (rd /s /q \"%{TombstoneEnvironmentVariable}%\" 2>nul & " +
        $"\"%{DelayEnvironmentVariable}%\" -n 2 127.0.0.1 >nul 2>nul) & " +
        $"rd /s /q \"%{TombstoneEnvironmentVariable}%\" 2>nul";

    private static void ValidateTombstone(string root, string tombstone)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tombstone);
        if (!Path.IsPathFullyQualified(tombstone))
        {
            throw new InstallationSafetyException(
                "The BAXY uninstall tombstone must be absolute.");
        }

        string full = Path.GetFullPath(tombstone);
        string? rootParent = Directory.GetParent(root)?.FullName;
        string? tombstoneParent = Directory.GetParent(full)?.FullName;
        string name = Path.GetFileName(full);
        string suffix = name.StartsWith(TombstonePrefix, StringComparison.Ordinal)
            ? name[TombstonePrefix.Length..]
            : string.Empty;
        if (rootParent is null || tombstoneParent is null ||
            !string.Equals(rootParent, tombstoneParent, StringComparison.OrdinalIgnoreCase) ||
            !Guid.TryParseExact(suffix, "N", out Guid identifier) ||
            identifier == Guid.Empty ||
            !string.Equals(
                name,
                TombstonePrefix + identifier.ToString("N"),
                StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The BAXY uninstall tombstone is not an exact sibling path.");
        }

        PathSafety.AssertExistingChainHasNoReparsePoint(full);
    }

    private static string RequireSystemExecutable(string systemDirectory, string fileName)
    {
        if (string.IsNullOrWhiteSpace(systemDirectory) ||
            !Path.IsPathFullyQualified(systemDirectory))
        {
            throw new InstallationSafetyException(
                "Windows did not provide its absolute system directory.");
        }

        string executable = Path.GetFullPath(Path.Combine(systemDirectory, fileName));
        FileAttributes attributes;
        try
        {
            attributes = File.GetAttributes(executable);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                $"The Windows system executable {fileName} is unavailable.",
                exception);
        }

        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0)
        {
            throw new InstallationSafetyException(
                $"The Windows system executable {fileName} is unsafe.");
        }

        return executable;
    }

    private static UninstallDataPolicy RequireCanonicalCommand(SetupCommand? command)
    {
        if (command is null ||
            command.Kind != SetupCommandKind.Uninstall ||
            command.EvidencePath is not null ||
            command.DataPolicy is not UninstallDataPolicy policy ||
            policy is not (UninstallDataPolicy.KeepData or UninstallDataPolicy.PurgeData) ||
            policy == UninstallDataPolicy.PurgeData && !command.Quiet)
        {
            throw new ArgumentException(
                "Only a canonical uninstall command may use the uninstall executor.",
                nameof(command));
        }

        return policy;
    }

    private sealed record VerifiedUninstall(
        WindowsIntegrationState State,
        OwnedStartMenuShortcut Shortcut,
        WindowsUninstallRegistry Registry,
        WindowsUninstallRegistryDeletionIntent RegistryDeletion);
}
