using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.Json.Serialization.Metadata;

namespace Baxy.Setup;

internal sealed record WindowsInstallationIdentity
{
    [JsonPropertyName("schema")]
    [JsonPropertyOrder(0)]
    public string Schema { get; init; } = PackageContract.InstallationIdentitySchema;

    [JsonPropertyName("install_id")]
    [JsonPropertyOrder(1)]
    public string InstallId { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    [JsonPropertyOrder(2)]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("installation_root")]
    [JsonPropertyOrder(3)]
    public string InstallationRoot { get; init; } = string.Empty;
}

internal sealed record WindowsIntegrationActiveIdentity
{
    [JsonPropertyName("schema")]
    [JsonPropertyOrder(0)]
    public string Schema { get; init; } = PackageContract.PointerSchema;

    [JsonPropertyName("version")]
    [JsonPropertyOrder(1)]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    [JsonPropertyOrder(2)]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("package_sha256")]
    [JsonPropertyOrder(3)]
    public string PackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("manifest_sha256")]
    [JsonPropertyOrder(4)]
    public string ManifestSha256 { get; init; } = string.Empty;

    [JsonPropertyName("content_id")]
    [JsonPropertyOrder(5)]
    public string ContentId { get; init; } = string.Empty;
}

internal sealed record WindowsIntegrationStableSetupState
{
    [JsonPropertyName("version")]
    [JsonPropertyOrder(0)]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("embedded_package_sha256")]
    [JsonPropertyOrder(1)]
    public string EmbeddedPackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("host_sha256")]
    [JsonPropertyOrder(2)]
    public string HostSha256 { get; init; } = string.Empty;

    [JsonPropertyName("host_bytes")]
    [JsonPropertyOrder(3)]
    public long HostBytes { get; init; }
}

internal sealed record WindowsIntegrationShortcutState
{
    [JsonPropertyName("sha256")]
    [JsonPropertyOrder(0)]
    public string Sha256 { get; init; } = string.Empty;

    [JsonPropertyName("bytes")]
    [JsonPropertyOrder(1)]
    public long Bytes { get; init; }
}

internal sealed record WindowsIntegrationState
{
    [JsonPropertyName("schema")]
    [JsonPropertyOrder(0)]
    public string Schema { get; init; } = PackageContract.WindowsIntegrationSchema;

    [JsonPropertyName("install_id")]
    [JsonPropertyOrder(1)]
    public string InstallId { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    [JsonPropertyOrder(2)]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("installation_root")]
    [JsonPropertyOrder(3)]
    public string InstallationRoot { get; init; } = string.Empty;

    [JsonPropertyName("active")]
    [JsonPropertyOrder(4)]
    public WindowsIntegrationActiveIdentity Active { get; init; } = new();

    [JsonPropertyName("stable_setup")]
    [JsonPropertyOrder(5)]
    public WindowsIntegrationStableSetupState StableSetup { get; init; } = new();

    [JsonPropertyName("shortcut")]
    [JsonPropertyOrder(6)]
    public WindowsIntegrationShortcutState Shortcut { get; init; } = new();

    [JsonPropertyName("estimated_size_kilobytes")]
    [JsonPropertyOrder(7)]
    public int EstimatedSizeKilobytes { get; init; }
}

internal static class WindowsIntegrationOperation
{
    internal const string InstallUpdate = "install_update";
    internal const string Rollback = "rollback";
    internal const string Reconcile = "reconcile";
}

internal static class WindowsIntegrationPhase
{
    internal const string Prepared = "prepared";
    internal const string HostStaged = "host_staged";
    internal const string ProductCommitted = "product_committed";
    internal const string HostCommitted = "host_committed";
    internal const string ShortcutCommitted = "shortcut_committed";
    internal const string RegistryIntent = "registry_intent";
    internal const string IntegrationCommitted = "integration_committed";
    internal const string Complete = "complete";

    internal static readonly string[] Ordered =
    [
        Prepared,
        HostStaged,
        ProductCommitted,
        HostCommitted,
        ShortcutCommitted,
        RegistryIntent,
        IntegrationCommitted,
        Complete,
    ];
}

internal sealed record WindowsIntegrationTransaction
{
    [JsonPropertyName("schema")]
    [JsonPropertyOrder(0)]
    public string Schema { get; init; } = PackageContract.WindowsIntegrationTransactionSchema;

    [JsonPropertyName("transaction_id")]
    [JsonPropertyOrder(1)]
    public string TransactionId { get; init; } = string.Empty;

    [JsonPropertyName("operation")]
    [JsonPropertyOrder(2)]
    public string Operation { get; init; } = string.Empty;

    [JsonPropertyName("phase")]
    [JsonPropertyOrder(3)]
    public string Phase { get; init; } = WindowsIntegrationPhase.Prepared;

    [JsonPropertyName("install_id")]
    [JsonPropertyOrder(4)]
    public string InstallId { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    [JsonPropertyOrder(5)]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("installation_root")]
    [JsonPropertyOrder(6)]
    public string InstallationRoot { get; init; } = string.Empty;

    [JsonPropertyName("before")]
    [JsonPropertyOrder(7)]
    public WindowsIntegrationState? Before { get; init; }

    [JsonPropertyName("target_active")]
    [JsonPropertyOrder(8)]
    public WindowsIntegrationActiveIdentity TargetActive { get; init; } = new();

    [JsonPropertyName("target_stable_setup")]
    [JsonPropertyOrder(9)]
    public WindowsIntegrationStableSetupState TargetStableSetup { get; init; } = new();

    [JsonPropertyName("target")]
    [JsonPropertyOrder(10)]
    public WindowsIntegrationState? Target { get; init; }
}

internal enum WindowsIntegrationRecoveryDecision
{
    Abort,
    RollForward,
}

internal enum WindowsIntegrationStoreFaultPoint
{
    InstallationNextDurable,
    InstallationSwitched,
    TransactionNextDurable,
    TransactionPreviousDurable,
    TransactionSwitched,
    IntegrationNextDurable,
    IntegrationPreviousDurable,
    IntegrationSwitched,
}

internal interface IWindowsIntegrationStoreFaultInjector
{
    void Checkpoint(WindowsIntegrationStoreFaultPoint point);
}

internal sealed class WindowsIntegrationStore
{
    internal const string InstallationIdentityFileName = "installation.v1.json";
    internal const string InstallationIdentityNextFileName = "installation.next";
    internal const string IntegrationFileName = "windows-integration.v1.json";
    internal const string IntegrationNextFileName = "windows-integration.next";
    internal const string IntegrationPreviousFileName = "windows-integration.previous";
    internal const string TransactionFileName = "windows-integration.transaction.v1.json";
    internal const string TransactionNextFileName = "windows-integration.transaction.next";
    internal const string TransactionPreviousFileName = "windows-integration.transaction.previous";

    private const long MaximumStableSetupBytes = 512L * 1024 * 1024;
    private const long MaximumShortcutBytes = 4L * 1024 * 1024;
    private const uint MoveFileReplaceExisting = 0x1;
    private const uint MoveFileWriteThrough = 0x8;

    private readonly string _root;
    private readonly IWindowsIntegrationStoreFaultInjector? _faultInjector;

    internal WindowsIntegrationStore(
        string installationRoot,
        IWindowsIntegrationStoreFaultInjector? faultInjector = null)
    {
        _root = PathSafety.ValidateInstallationRoot(installationRoot);
        _faultInjector = faultInjector;
    }

    internal string InstallationRoot => _root;

    internal WindowsInstallationIdentity EnsureInstallationIdentity(
        WindowsInstallationIdentity expected)
    {
        AssertExistingRoot();
        ValidateInstallationIdentity(expected, _root);
        string path = OwnedPath(InstallationIdentityFileName);
        string nextPath = OwnedPath(InstallationIdentityNextFileName);

        bool exists = EntryExists(path);
        bool nextExists = EntryExists(nextPath);
        if (exists)
        {
            if (nextExists)
            {
                throw new InstallationSafetyException(
                    "An immutable installation identity cannot coexist with installation.next.");
            }

            WindowsInstallationIdentity actual = ReadInstallationIdentityFile(path);
            RequireEqual(actual, expected, "installation identity");
            return actual;
        }

        if (nextExists)
        {
            WindowsInstallationIdentity staged = ReadInstallationIdentityFile(nextPath);
            RequireEqual(staged, expected, "staged installation identity");
            PromoteNew(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.InstallationSwitched);
            WindowsInstallationIdentity promoted = ReadInstallationIdentityFile(path);
            RequireEqual(promoted, expected, "promoted installation identity");
            return promoted;
        }

        WriteNewDurable(
            nextPath,
            SerializeCanonical(expected, SetupJsonContext.Default.WindowsInstallationIdentity));
        RequireEqual(
            ReadInstallationIdentityFile(nextPath),
            expected,
            "durable staged installation identity");
        Checkpoint(WindowsIntegrationStoreFaultPoint.InstallationNextDurable);
        PromoteNew(nextPath, path);
        Checkpoint(WindowsIntegrationStoreFaultPoint.InstallationSwitched);
        WindowsInstallationIdentity created = ReadInstallationIdentityFile(path);
        RequireEqual(created, expected, "created installation identity");
        return created;
    }

    internal WindowsInstallationIdentity? ReadInstallationIdentity()
    {
        AssertExistingRoot();
        if (EntryExists(OwnedPath(InstallationIdentityNextFileName)))
        {
            throw new InstallationSafetyException(
                "installation.next requires an explicitly supplied expected identity for recovery.");
        }

        string path = OwnedPath(InstallationIdentityFileName);
        return EntryExists(path) ? ReadInstallationIdentityFile(path) : null;
    }

    internal WindowsInstallationIdentity? RecoverAndReadInstallationIdentity()
    {
        AssertExistingRoot();
        string path = OwnedPath(InstallationIdentityFileName);
        string nextPath = OwnedPath(InstallationIdentityNextFileName);
        bool exists = EntryExists(path);
        bool nextExists = EntryExists(nextPath);
        if (exists)
        {
            if (nextExists)
            {
                throw new InstallationSafetyException(
                    "An immutable installation identity cannot coexist with installation.next.");
            }

            return ReadInstallationIdentityFile(path);
        }

        if (!nextExists)
        {
            return null;
        }

        WindowsInstallationIdentity staged = ReadInstallationIdentityFile(nextPath);
        PromoteNew(nextPath, path);
        Checkpoint(WindowsIntegrationStoreFaultPoint.InstallationSwitched);
        WindowsInstallationIdentity promoted = ReadInstallationIdentityFile(path);
        RequireEqual(promoted, staged, "recovered immutable installation identity");
        return promoted;
    }

    internal void AssertInstallationIdentityMayBeInitialized()
    {
        AssertExistingRoot();
        string[] forbiddenArtifacts =
        [
            InstallationIdentityFileName,
            InstallationIdentityNextFileName,
            IntegrationFileName,
            IntegrationNextFileName,
            IntegrationPreviousFileName,
            TransactionFileName,
            TransactionNextFileName,
            TransactionPreviousFileName,
        ];
        foreach (string artifact in forbiddenArtifacts)
        {
            if (EntryExists(OwnedPath(artifact)))
            {
                throw new InstallationSafetyException(
                    "An immutable installation identity cannot be initialized while Windows integration artifacts already exist.");
            }
        }
    }

    internal WindowsIntegrationState? ReadCommittedState()
    {
        AssertExistingRoot();
        AssertNoIntegrationStaging();
        string path = OwnedPath(IntegrationFileName);
        if (!EntryExists(path))
        {
            return null;
        }

        WindowsIntegrationState state = ReadIntegrationStateFile(path);
        RequireMatchesInstalledIdentity(state);
        return state;
    }

    internal void BeginTransaction(WindowsIntegrationTransaction transaction)
    {
        AssertExistingRoot();
        ValidateTransaction(transaction, _root);
        if (!string.Equals(transaction.Phase, WindowsIntegrationPhase.Prepared, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A Windows integration transaction must begin in the prepared phase.");
        }

        WindowsInstallationIdentity identity = RequireInstalledIdentity();
        RequireTransactionMatchesIdentity(transaction, identity);
        AssertStableStateEquals(transaction.Before);

        string path = OwnedPath(TransactionFileName);
        string nextPath = OwnedPath(TransactionNextFileName);
        string previousPath = OwnedPath(TransactionPreviousFileName);
        bool exists = EntryExists(path);
        bool nextExists = EntryExists(nextPath);
        if (EntryExists(previousPath))
        {
            throw new InstallationSafetyException(
                "A Windows integration transaction cannot begin with a previous artifact.");
        }

        if (exists)
        {
            if (nextExists)
            {
                throw new InstallationSafetyException(
                    "A begun Windows integration transaction cannot coexist with transaction.next.");
            }

            RequireEqual(
                ReadTransactionFile(path),
                transaction,
                "already-created Windows integration transaction");
            return;
        }

        if (nextExists)
        {
            RequireEqual(
                ReadTransactionFile(nextPath),
                transaction,
                "staged initial Windows integration transaction");
            PromoteNew(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionSwitched);
            RequireEqual(
                ReadTransactionFile(path),
                transaction,
                "recovered initial Windows integration transaction");
            return;
        }

        WriteNewDurable(
            nextPath,
            SerializeCanonical(transaction, SetupJsonContext.Default.WindowsIntegrationTransaction));
        RequireEqual(
            ReadTransactionFile(nextPath),
            transaction,
            "durable staged initial Windows integration transaction");
        Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionNextDurable);
        PromoteNew(nextPath, path);
        Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionSwitched);
        RequireEqual(
            ReadTransactionFile(path),
            transaction,
            "created Windows integration transaction");
    }

    internal WindowsIntegrationTransaction? RecoverAndReadTransaction()
    {
        AssertExistingRoot();
        string path = OwnedPath(TransactionFileName);
        string nextPath = OwnedPath(TransactionNextFileName);
        string previousPath = OwnedPath(TransactionPreviousFileName);
        bool exists = EntryExists(path);
        bool nextExists = EntryExists(nextPath);
        bool previousExists = EntryExists(previousPath);
        if (!exists)
        {
            if (previousExists)
            {
                throw new InstallationSafetyException(
                    "A Windows integration transaction previous artifact exists without its journal.");
            }

            if (!nextExists)
            {
                return null;
            }

            WindowsIntegrationTransaction initial = ReadTransactionFile(nextPath);
            if (!string.Equals(initial.Phase, WindowsIntegrationPhase.Prepared, StringComparison.Ordinal))
            {
                throw new InstallationSafetyException(
                    "An initial transaction.next must contain the prepared phase.");
            }

            RequireTransactionMatchesIdentity(initial, RequireInstalledIdentity());
            AssertStableStateEquals(initial.Before);
            PromoteNew(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionSwitched);
            RequireEqual(
                ReadTransactionFile(path),
                initial,
                "recovered initial Windows integration transaction");
            return initial;
        }

        WindowsIntegrationTransaction current = ReadTransactionFile(path);
        RequireTransactionMatchesIdentity(current, RequireInstalledIdentity());
        if (nextExists)
        {
            WindowsIntegrationTransaction next = ReadTransactionFile(nextPath);
            ValidateAdvance(current, next);
            if (previousExists)
            {
                RequireEqual(
                    ReadTransactionFile(previousPath),
                    current,
                    "staged prior Windows integration transaction");
            }
            else
            {
                WriteNewDurable(
                    previousPath,
                    SerializeCanonical(current, SetupJsonContext.Default.WindowsIntegrationTransaction));
                RequireEqual(
                    ReadTransactionFile(previousPath),
                    current,
                    "durable prior Windows integration transaction");
                Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionPreviousDurable);
            }

            ReplaceExistingWriteThrough(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionSwitched);
            RequireEqual(
                ReadTransactionFile(path),
                next,
                "recovered Windows integration transaction");
            RequireEqual(
                ReadTransactionFile(previousPath),
                current,
                "recovered prior Windows integration transaction");
            DeleteRegularFile(previousPath);
            return next;
        }

        if (previousExists)
        {
            WindowsIntegrationTransaction previous = ReadTransactionFile(previousPath);
            ValidateAdvance(previous, current);
            DeleteRegularFile(previousPath);
        }

        return current;
    }

    internal void AdvanceTransaction(
        WindowsIntegrationTransaction expectedCurrent,
        WindowsIntegrationTransaction advanced)
    {
        ArgumentNullException.ThrowIfNull(expectedCurrent);
        ArgumentNullException.ThrowIfNull(advanced);
        WindowsIntegrationTransaction current = RecoverAndReadTransaction() ??
            throw new InstallationSafetyException("No Windows integration transaction exists to advance.");
        RequireEqual(current, expectedCurrent, "current Windows integration transaction");
        ValidateAdvance(current, advanced);

        string nextPath = OwnedPath(TransactionNextFileName);
        string path = OwnedPath(TransactionFileName);
        string previousPath = OwnedPath(TransactionPreviousFileName);
        WriteNewDurable(
            nextPath,
            SerializeCanonical(advanced, SetupJsonContext.Default.WindowsIntegrationTransaction));
        RequireEqual(
            ReadTransactionFile(nextPath),
            advanced,
            "durable next Windows integration transaction");
        Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionNextDurable);
        WriteNewDurable(
            previousPath,
            SerializeCanonical(current, SetupJsonContext.Default.WindowsIntegrationTransaction));
        RequireEqual(
            ReadTransactionFile(previousPath),
            current,
            "durable prior Windows integration transaction");
        Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionPreviousDurable);
        ReplaceExistingWriteThrough(nextPath, path);
        Checkpoint(WindowsIntegrationStoreFaultPoint.TransactionSwitched);
        RequireEqual(
            ReadTransactionFile(path),
            advanced,
            "advanced Windows integration transaction");
        RequireEqual(
            ReadTransactionFile(previousPath),
            current,
            "previous Windows integration transaction");
        DeleteRegularFile(previousPath);
    }

    internal WindowsIntegrationState? ApplyTransactionTarget(
        WindowsIntegrationTransaction expectedTransaction)
    {
        ArgumentNullException.ThrowIfNull(expectedTransaction);
        WindowsIntegrationTransaction transaction = RecoverAndReadTransaction() ??
            throw new InstallationSafetyException(
                "A committed Windows integration state cannot change without its transaction journal.");
        RequireEqual(transaction, expectedTransaction, "Windows integration transaction");
        if (!string.Equals(transaction.Phase, WindowsIntegrationPhase.RegistryIntent, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The integration state may switch only after the registry_intent phase is durable.");
        }

        RequireTransactionMatchesIdentity(transaction, RequireInstalledIdentity());
        RecoverOrApplyStateTransition(transaction);
        AssertStableStateEquals(transaction.Target);
        return transaction.Target;
    }

    internal void AbortTransaction(WindowsIntegrationTransaction expectedTransaction)
    {
        ArgumentNullException.ThrowIfNull(expectedTransaction);
        WindowsIntegrationTransaction transaction = RecoverAndReadTransaction() ??
            throw new InstallationSafetyException("No Windows integration transaction exists to abort.");
        RequireEqual(transaction, expectedTransaction, "Windows integration transaction to abort");
        AssertStableStateEquals(transaction.Before);
        DeleteRegularFile(OwnedPath(TransactionFileName));
    }

    internal void CompleteTransaction(WindowsIntegrationTransaction expectedTransaction)
    {
        ArgumentNullException.ThrowIfNull(expectedTransaction);
        WindowsIntegrationTransaction transaction = RecoverAndReadTransaction() ??
            throw new InstallationSafetyException("No Windows integration transaction exists to complete.");
        RequireEqual(transaction, expectedTransaction, "Windows integration transaction to complete");
        if (!string.Equals(transaction.Phase, WindowsIntegrationPhase.Complete, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A Windows integration transaction can be removed only from the complete phase.");
        }

        AssertStableStateEquals(transaction.Target);
        DeleteRegularFile(OwnedPath(TransactionFileName));
    }

    internal static WindowsIntegrationRecoveryDecision DecideRecovery(
        WindowsIntegrationActiveIdentity? current,
        WindowsIntegrationTransaction transaction)
    {
        ValidateTransaction(transaction, expectedRoot: null);
        if (current is not null)
        {
            ValidateActiveIdentity(current);
        }

        WindowsIntegrationActiveIdentity? before = transaction.Before?.Active;
        WindowsIntegrationActiveIdentity target = transaction.TargetActive;
        if (NullableActiveEquals(current, before))
        {
            return WindowsIntegrationRecoveryDecision.Abort;
        }

        if (NullableActiveEquals(current, target))
        {
            return WindowsIntegrationRecoveryDecision.RollForward;
        }

        throw new InstallationSafetyException(
            "The verified current product identity matches neither side of the Windows integration journal.");
    }

    private void RecoverOrApplyStateTransition(WindowsIntegrationTransaction transaction)
    {
        string path = OwnedPath(IntegrationFileName);
        string nextPath = OwnedPath(IntegrationNextFileName);
        string previousPath = OwnedPath(IntegrationPreviousFileName);
        WindowsIntegrationState? current = ReadOptionalState(path);
        WindowsIntegrationState? next = ReadOptionalState(nextPath);
        WindowsIntegrationState? previous = ReadOptionalState(previousPath);
        WindowsIntegrationState? before = transaction.Before;
        WindowsIntegrationState? target = transaction.Target;

        if (target is null)
        {
            throw new InstallationSafetyException(
                "The integration target is not fully attested at the registry_intent phase.");
        }

        if (before is null)
        {
            if (StateEquals(current, target) && next is null && previous is null)
            {
                return;
            }

            if (current is null && StateEquals(next, target) && previous is null)
            {
                PromoteNew(nextPath, path);
                Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationSwitched);
                RequireEqual(
                    ReadIntegrationStateFile(path),
                    target,
                    "promoted first integration state");
                return;
            }

            if (current is null && next is null && previous is null)
            {
                WriteNewDurable(
                    nextPath,
                    SerializeCanonical(target, SetupJsonContext.Default.WindowsIntegrationState));
                RequireEqual(
                    ReadIntegrationStateFile(nextPath),
                    target,
                    "durable first integration state");
                Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationNextDurable);
                PromoteNew(nextPath, path);
                Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationSwitched);
                RequireEqual(
                    ReadIntegrationStateFile(path),
                    target,
                    "created integration state");
                return;
            }

            throw new InstallationSafetyException(
                "The integration-state artifacts contradict the journaled first-install transition.");
        }

        if (StateEquals(current, target) && next is null && previous is null)
        {
            return;
        }

        if (StateEquals(current, target) && next is null && StateEquals(previous, before))
        {
            DeleteRegularFile(previousPath);
            return;
        }

        if (StateEquals(current, before) && StateEquals(next, target) &&
            (previous is null || StateEquals(previous, before)))
        {
            if (previous is null)
            {
                WriteNewDurable(
                    previousPath,
                    SerializeCanonical(before, SetupJsonContext.Default.WindowsIntegrationState));
                RequireEqual(
                    ReadIntegrationStateFile(previousPath),
                    before,
                    "durable prior integration state");
                Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationPreviousDurable);
            }

            ReplaceExistingWriteThrough(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationSwitched);
            RequireEqual(ReadIntegrationStateFile(path), target, "updated integration state");
            RequireEqual(ReadIntegrationStateFile(previousPath), before, "prior integration state");
            DeleteRegularFile(previousPath);
            return;
        }

        if (StateEquals(current, before) && next is null && previous is null)
        {
            WriteNewDurable(
                nextPath,
                SerializeCanonical(target, SetupJsonContext.Default.WindowsIntegrationState));
            RequireEqual(
                ReadIntegrationStateFile(nextPath),
                target,
                "durable next integration state");
            Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationNextDurable);
            WriteNewDurable(
                previousPath,
                SerializeCanonical(before, SetupJsonContext.Default.WindowsIntegrationState));
            RequireEqual(
                ReadIntegrationStateFile(previousPath),
                before,
                "durable prior integration state");
            Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationPreviousDurable);
            ReplaceExistingWriteThrough(nextPath, path);
            Checkpoint(WindowsIntegrationStoreFaultPoint.IntegrationSwitched);
            RequireEqual(ReadIntegrationStateFile(path), target, "updated integration state");
            RequireEqual(ReadIntegrationStateFile(previousPath), before, "prior integration state");
            DeleteRegularFile(previousPath);
            return;
        }

        throw new InstallationSafetyException(
            "The integration-state artifacts contradict the journaled update transition.");
    }

    private void AssertStableStateEquals(WindowsIntegrationState? expected)
    {
        AssertNoIntegrationStaging();
        WindowsIntegrationState? actual = ReadOptionalState(OwnedPath(IntegrationFileName));
        if (!StateEquals(actual, expected))
        {
            throw new InstallationSafetyException(
                "The committed Windows integration state does not match its journaled snapshot.");
        }

        if (actual is not null)
        {
            RequireMatchesInstalledIdentity(actual);
        }
    }

    private void AssertNoIntegrationStaging()
    {
        if (EntryExists(OwnedPath(IntegrationNextFileName)) ||
            EntryExists(OwnedPath(IntegrationPreviousFileName)))
        {
            throw new InstallationSafetyException(
                "Windows integration staging exists outside explicit journal recovery.");
        }
    }

    private WindowsInstallationIdentity RequireInstalledIdentity()
    {
        if (EntryExists(OwnedPath(InstallationIdentityNextFileName)))
        {
            throw new InstallationSafetyException(
                "The immutable installation identity has an unrecovered staging artifact.");
        }

        string path = OwnedPath(InstallationIdentityFileName);
        if (!EntryExists(path))
        {
            throw new InstallationSafetyException("The immutable installation identity is missing.");
        }

        return ReadInstallationIdentityFile(path);
    }

    private void RequireMatchesInstalledIdentity(WindowsIntegrationState state)
    {
        WindowsInstallationIdentity identity = RequireInstalledIdentity();
        if (!string.Equals(state.InstallId, identity.InstallId, StringComparison.Ordinal) ||
            state.DataSchema != identity.DataSchema ||
            !string.Equals(state.InstallationRoot, identity.InstallationRoot, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The Windows integration state does not match the immutable installation identity.");
        }
    }

    private static void RequireTransactionMatchesIdentity(
        WindowsIntegrationTransaction transaction,
        WindowsInstallationIdentity identity)
    {
        if (!string.Equals(transaction.InstallId, identity.InstallId, StringComparison.Ordinal) ||
            transaction.DataSchema != identity.DataSchema ||
            !string.Equals(transaction.InstallationRoot, identity.InstallationRoot, StringComparison.Ordinal) ||
            transaction.TargetActive.DataSchema != identity.DataSchema)
        {
            throw new InstallationSafetyException(
                "A Windows integration transaction changed the immutable installation identity.");
        }

        foreach (WindowsIntegrationState state in EnumerateStates(transaction))
        {
            if (!string.Equals(state.InstallId, identity.InstallId, StringComparison.Ordinal) ||
                state.DataSchema != identity.DataSchema ||
                !string.Equals(state.InstallationRoot, identity.InstallationRoot, StringComparison.Ordinal))
            {
                throw new InstallationSafetyException(
                    "A Windows integration transaction changed the immutable installation identity.");
            }
        }
    }

    private WindowsInstallationIdentity ReadInstallationIdentityFile(string path) =>
        ReadCanonical(
            path,
            PackageContract.MaximumInstallationIdentityBytes,
            SetupJsonContext.Default.WindowsInstallationIdentity,
            value => ValidateInstallationIdentity(value, _root),
            "installation identity");

    private WindowsIntegrationState ReadIntegrationStateFile(string path) =>
        ReadCanonical(
            path,
            PackageContract.MaximumWindowsIntegrationBytes,
            SetupJsonContext.Default.WindowsIntegrationState,
            value => ValidateState(value, _root),
            "Windows integration state");

    private WindowsIntegrationTransaction ReadTransactionFile(string path) =>
        ReadCanonical(
            path,
            PackageContract.MaximumWindowsIntegrationTransactionBytes,
            SetupJsonContext.Default.WindowsIntegrationTransaction,
            value => ValidateTransaction(value, _root),
            "Windows integration transaction");

    private WindowsIntegrationState? ReadOptionalState(string path) =>
        EntryExists(path) ? ReadIntegrationStateFile(path) : null;

    private static T ReadCanonical<T>(
        string path,
        int maximumBytes,
        JsonTypeInfo<T> typeInfo,
        Action<T> validate,
        string description)
        where T : class
    {
        try
        {
            byte[] first = ReadBoundedAndReattest(path, maximumBytes, description);
            byte[] bytes = ReadBoundedAndReattest(path, maximumBytes, description);
            if (!first.AsSpan().SequenceEqual(bytes))
            {
                throw new InstallationSafetyException($"The {description} changed while it was being read.");
            }

            T? value = JsonSerializer.Deserialize(bytes, typeInfo);
            if (value is null)
            {
                throw new InstallationSafetyException($"The {description} is null.");
            }

            validate(value);
            byte[] canonical = SerializeCanonical(value, typeInfo);
            if (!bytes.AsSpan().SequenceEqual(canonical))
            {
                throw new InstallationSafetyException(
                    $"The {description} is not exact canonical UTF-8 JSON.");
            }

            return value;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is JsonException or IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            throw new InstallationSafetyException($"The {description} is malformed or unreadable.", exception);
        }
    }

    private static byte[] ReadBoundedAndReattest(
        string path,
        int maximumBytes,
        string description)
    {
        PathSafety.AssertRegularFile(path);
        byte[] bytes;
        using (FileStream stream = new(
                   path,
                   FileMode.Open,
                   FileAccess.Read,
                   FileShare.Read,
                   bufferSize: 4096,
                   FileOptions.SequentialScan))
        {
            long length = stream.Length;
            if (length is <= 0 || length > maximumBytes)
            {
                throw new InstallationSafetyException($"The {description} has an invalid length.");
            }

            bytes = new byte[checked((int)length)];
            stream.ReadExactly(bytes);
            if (stream.ReadByte() != -1 || stream.Length != length)
            {
                throw new InstallationSafetyException(
                    $"The {description} changed length while it was being read.");
            }
        }

        PathSafety.AssertRegularFile(path);
        return bytes;
    }

    private static byte[] SerializeCanonical<T>(T value, JsonTypeInfo<T> typeInfo)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(value, typeInfo);
        byte[] result = new byte[json.Length + 1];
        json.CopyTo(result, 0);
        result[^1] = (byte)'\n';
        return result;
    }

    private static void ValidateInstallationIdentity(
        WindowsInstallationIdentity identity,
        string? expectedRoot)
    {
        ArgumentNullException.ThrowIfNull(identity);
        if (!string.Equals(
                identity.Schema,
                PackageContract.InstallationIdentitySchema,
                StringComparison.Ordinal) ||
            !IsCanonicalGuid(identity.InstallId) ||
            identity.DataSchema != PackageContract.DataSchema)
        {
            throw new InstallationSafetyException(
                "The immutable installation identity has an invalid schema, install_id, or data_schema.");
        }

        string root = PathSafety.ValidateInstallationRoot(identity.InstallationRoot);
        if (!string.Equals(root, identity.InstallationRoot, StringComparison.Ordinal) ||
            (expectedRoot is not null &&
             !string.Equals(identity.InstallationRoot, expectedRoot, StringComparison.Ordinal)))
        {
            throw new InstallationSafetyException(
                "The immutable installation identity changed or did not canonicalize its installation root.");
        }
    }

    private static void ValidateState(WindowsIntegrationState state, string? expectedRoot)
    {
        ArgumentNullException.ThrowIfNull(state);
        if (!string.Equals(state.Schema, PackageContract.WindowsIntegrationSchema, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException("The Windows integration state schema is unsupported.");
        }

        ValidateInstallationIdentity(
            new WindowsInstallationIdentity
            {
                InstallId = state.InstallId,
                DataSchema = state.DataSchema,
                InstallationRoot = state.InstallationRoot,
            },
            expectedRoot);
        if (state.Active is null || state.StableSetup is null || state.Shortcut is null)
        {
            throw new InstallationSafetyException("The Windows integration state is incomplete.");
        }

        ValidateActiveIdentity(state.Active);
        if (state.Active.DataSchema != state.DataSchema)
        {
            throw new InstallationSafetyException(
                "The active product identity changed the installation data schema.");
        }

        ValidateStableSetupState(state.StableSetup);

        if (!IsLowercaseSha256(state.Shortcut.Sha256) ||
            state.Shortcut.Bytes is <= 0 or > MaximumShortcutBytes)
        {
            throw new InstallationSafetyException("The Start Menu shortcut identity is invalid.");
        }

        if (state.EstimatedSizeKilobytes < 1)
        {
            throw new InstallationSafetyException("The Windows integration EstimatedSize is invalid.");
        }
    }

    private static void ValidateActiveIdentity(WindowsIntegrationActiveIdentity identity)
    {
        ArgumentNullException.ThrowIfNull(identity);
        if (!string.Equals(identity.Schema, PackageContract.PointerSchema, StringComparison.Ordinal) ||
            !SemanticVersionComparer.IsValid(identity.Version) ||
            identity.DataSchema != PackageContract.DataSchema ||
            !IsLowercaseSha256(identity.PackageSha256) ||
            !IsLowercaseSha256(identity.ManifestSha256) ||
            !IsLowercaseSha256(identity.ContentId))
        {
            throw new InstallationSafetyException("The verified active product identity is invalid.");
        }
    }

    private static void ValidateStableSetupState(WindowsIntegrationStableSetupState state)
    {
        ArgumentNullException.ThrowIfNull(state);
        if (!SemanticVersionComparer.IsValid(state.Version) ||
            !IsLowercaseSha256(state.EmbeddedPackageSha256) ||
            !IsLowercaseSha256(state.HostSha256) ||
            state.HostBytes is <= 0 or > MaximumStableSetupBytes)
        {
            throw new InstallationSafetyException("The stable Setup identity is invalid.");
        }
    }

    private static void ValidateTransaction(
        WindowsIntegrationTransaction transaction,
        string? expectedRoot)
    {
        ArgumentNullException.ThrowIfNull(transaction);
        int phaseIndex = Array.IndexOf(WindowsIntegrationPhase.Ordered, transaction.Phase);
        if (!string.Equals(
                transaction.Schema,
                PackageContract.WindowsIntegrationTransactionSchema,
                StringComparison.Ordinal) ||
            !IsCanonicalGuid(transaction.TransactionId) ||
            transaction.Operation is not (
                WindowsIntegrationOperation.InstallUpdate or
                WindowsIntegrationOperation.Rollback or
                WindowsIntegrationOperation.Reconcile) ||
            phaseIndex < 0)
        {
            throw new InstallationSafetyException(
                "The Windows integration transaction has an invalid schema, identity, operation, phase, or snapshots.");
        }

        ValidateInstallationIdentity(
            new WindowsInstallationIdentity
            {
                InstallId = transaction.InstallId,
                DataSchema = transaction.DataSchema,
                InstallationRoot = transaction.InstallationRoot,
            },
            expectedRoot);
        if (transaction.TargetActive is null || transaction.TargetStableSetup is null)
        {
            throw new InstallationSafetyException(
                "The Windows integration transaction target plan is incomplete.");
        }

        ValidateActiveIdentity(transaction.TargetActive);
        ValidateStableSetupState(transaction.TargetStableSetup);
        bool targetMustBeFull = phaseIndex >=
            Array.IndexOf(WindowsIntegrationPhase.Ordered, WindowsIntegrationPhase.ShortcutCommitted);
        if (targetMustBeFull != (transaction.Target is not null))
        {
            throw new InstallationSafetyException(
                "The full Windows integration target must appear exactly at shortcut_committed and remain thereafter.");
        }

        if (transaction.Before is not null)
        {
            ValidateState(transaction.Before, expectedRoot);
            RequireStateMatchesTransactionIdentity(transaction.Before, transaction);
        }

        if (transaction.Target is not null)
        {
            ValidateState(transaction.Target, expectedRoot);
            RequireStateMatchesTransactionIdentity(transaction.Target, transaction);
            if (transaction.Target.Active != transaction.TargetActive ||
                transaction.Target.StableSetup != transaction.TargetStableSetup)
            {
                throw new InstallationSafetyException(
                    "The full Windows integration target contradicts its durable target plan.");
            }
        }

        if (transaction.Before is not null && transaction.Target is not null)
        {
            if (transaction.Before.Active == transaction.Target.Active)
            {
                throw new InstallationSafetyException(
                    "A Windows integration transaction must have distinct before and target active identities.");
            }
        }

        switch (transaction.Operation)
        {
            case WindowsIntegrationOperation.InstallUpdate:
                if (!StableSetupEmbedsTargetProduct(transaction) ||
                    (transaction.Before is not null &&
                     (transaction.Before.Active == transaction.TargetActive ||
                      SemanticVersionComparer.ComparePrecedence(
                          transaction.TargetActive.Version,
                          transaction.Before.Active.Version) <= 0 ||
                      IsStableSetupDowngradeOrSameVersionWithDifferentBytes(
                          transaction.Before.StableSetup,
                          transaction.TargetStableSetup))))
                {
                    throw new InstallationSafetyException(
                        "An install_update integration transaction requires a new higher-precedence target.");
                }

                break;

            case WindowsIntegrationOperation.Rollback:
                if (transaction.Before is null ||
                    transaction.Before.Active == transaction.TargetActive ||
                    transaction.Before.StableSetup != transaction.TargetStableSetup ||
                    (transaction.Target is not null &&
                     transaction.Before.Shortcut != transaction.Target.Shortcut))
                {
                    throw new InstallationSafetyException(
                        "A rollback integration transaction must preserve the stable Setup host and shortcut.");
                }

                break;

            case WindowsIntegrationOperation.Reconcile:
                if (transaction.Before is not null || !StableSetupEmbedsTargetProduct(transaction))
                {
                    throw new InstallationSafetyException(
                        "A reconcile transaction adopts a verified active product only when no prior integration state exists.");
                }

                break;
        }
    }

    private static bool StableSetupEmbedsTargetProduct(WindowsIntegrationTransaction transaction) =>
        string.Equals(
            transaction.TargetStableSetup.Version,
            transaction.TargetActive.Version,
            StringComparison.Ordinal) &&
        string.Equals(
            transaction.TargetStableSetup.EmbeddedPackageSha256,
            transaction.TargetActive.PackageSha256,
            StringComparison.Ordinal);

    private static bool IsStableSetupDowngradeOrSameVersionWithDifferentBytes(
        WindowsIntegrationStableSetupState before,
        WindowsIntegrationStableSetupState target)
    {
        int comparison = SemanticVersionComparer.ComparePrecedence(target.Version, before.Version);
        return comparison < 0 || (comparison == 0 && target != before);
    }

    private static void ValidateAdvance(
        WindowsIntegrationTransaction current,
        WindowsIntegrationTransaction advanced)
    {
        ValidateTransaction(current, expectedRoot: null);
        ValidateTransaction(advanced, expectedRoot: null);
        int currentIndex = Array.IndexOf(WindowsIntegrationPhase.Ordered, current.Phase);
        int advancedIndex = Array.IndexOf(WindowsIntegrationPhase.Ordered, advanced.Phase);
        if (advancedIndex != currentIndex + 1 ||
            !string.Equals(current.TransactionId, advanced.TransactionId, StringComparison.Ordinal) ||
            !string.Equals(current.Operation, advanced.Operation, StringComparison.Ordinal) ||
            !string.Equals(current.InstallId, advanced.InstallId, StringComparison.Ordinal) ||
            current.DataSchema != advanced.DataSchema ||
            !string.Equals(current.InstallationRoot, advanced.InstallationRoot, StringComparison.Ordinal) ||
            current.Before != advanced.Before ||
            current.TargetActive != advanced.TargetActive ||
            current.TargetStableSetup != advanced.TargetStableSetup)
        {
            throw new InstallationSafetyException(
                "A Windows integration journal advance must preserve identity and move exactly one phase forward.");
        }

        bool fillsTarget =
            string.Equals(current.Phase, WindowsIntegrationPhase.HostCommitted, StringComparison.Ordinal) &&
            string.Equals(advanced.Phase, WindowsIntegrationPhase.ShortcutCommitted, StringComparison.Ordinal);
        if (fillsTarget)
        {
            if (current.Target is not null || advanced.Target is null)
            {
                throw new InstallationSafetyException(
                    "shortcut_committed must make the single null-to-full target transition.");
            }
        }
        else if (current.Target != advanced.Target)
        {
            throw new InstallationSafetyException(
                "A Windows integration journal may populate its full target only at shortcut_committed.");
        }
    }

    private static void RequireStateMatchesTransactionIdentity(
        WindowsIntegrationState state,
        WindowsIntegrationTransaction transaction)
    {
        if (!string.Equals(state.InstallId, transaction.InstallId, StringComparison.Ordinal) ||
            state.DataSchema != transaction.DataSchema ||
            !string.Equals(state.InstallationRoot, transaction.InstallationRoot, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A Windows integration transition changed the immutable installation identity.");
        }
    }

    private static IEnumerable<WindowsIntegrationState> EnumerateStates(
        WindowsIntegrationTransaction transaction)
    {
        if (transaction.Before is not null)
        {
            yield return transaction.Before;
        }

        if (transaction.Target is not null)
        {
            yield return transaction.Target;
        }
    }

    private static bool NullableActiveEquals(
        WindowsIntegrationActiveIdentity? left,
        WindowsIntegrationActiveIdentity? right) =>
        left is null ? right is null : left == right;

    private static bool StateEquals(
        WindowsIntegrationState? left,
        WindowsIntegrationState? right) =>
        left is null ? right is null : left == right;

    private static void RequireEqual<T>(T actual, T expected, string description)
    {
        if (!EqualityComparer<T>.Default.Equals(actual, expected))
        {
            throw new InstallationSafetyException($"The {description} does not match its exact expected snapshot.");
        }
    }

    private static bool IsCanonicalGuid(string? value) =>
        value is not null &&
        Guid.TryParseExact(value, "N", out Guid identifier) &&
        string.Equals(value, identifier.ToString("N"), StringComparison.Ordinal);

    private static bool IsLowercaseSha256(string? value)
    {
        if (value is null || value.Length != 64)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private void AssertExistingRoot()
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(_root);
        if (!Directory.Exists(_root))
        {
            throw new InstallationSafetyException("The Windows integration store root is missing.");
        }

        FileAttributes attributes = File.GetAttributes(_root);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException("The Windows integration store root is unsafe.");
        }
    }

    private string OwnedPath(string fileName) => Path.Combine(_root, fileName);

    private static bool EntryExists(string path) => File.Exists(path) || Directory.Exists(path);

    private static void WriteNewDurable(string path, byte[] bytes)
    {
        if (EntryExists(path))
        {
            throw new InstallationSafetyException("A durable Windows integration staging path already exists.");
        }

        using (FileStream stream = new(path, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            stream.Write(bytes);
            stream.Flush(flushToDisk: true);
        }

        PathSafety.AssertRegularFile(path);
    }

    private static void PromoteNew(string source, string destination)
    {
        PathSafety.AssertRegularFile(source);
        if (EntryExists(destination))
        {
            throw new InstallationSafetyException(
                "A create-new Windows integration promotion found an occupied destination.");
        }

        MoveWriteThrough(source, destination, replaceExisting: false);
        PathSafety.AssertRegularFile(destination);
    }

    private static void ReplaceExistingWriteThrough(string source, string destination)
    {
        PathSafety.AssertRegularFile(source);
        PathSafety.AssertRegularFile(destination);
        MoveWriteThrough(source, destination, replaceExisting: true);
        PathSafety.AssertRegularFile(destination);
    }

    private static void MoveWriteThrough(
        string source,
        string destination,
        bool replaceExisting)
    {
        uint flags = MoveFileWriteThrough |
            (replaceExisting ? MoveFileReplaceExisting : 0u);
        if (!MoveFileEx(source, destination, flags))
        {
            throw new InstallationSafetyException(
                "A durable Windows integration file promotion failed.",
                new Win32Exception(Marshal.GetLastWin32Error()));
        }
    }

    private static void DeleteRegularFile(string path)
    {
        PathSafety.AssertRegularFile(path);
        File.Delete(path);
        if (EntryExists(path))
        {
            throw new InstallationSafetyException("A Windows integration artifact survived exact deletion.");
        }
    }

    private void Checkpoint(WindowsIntegrationStoreFaultPoint point) =>
        _faultInjector?.Checkpoint(point);

    [DllImport("kernel32.dll", EntryPoint = "MoveFileExW", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool MoveFileEx(
        string existingFileName,
        string newFileName,
        uint flags);
}
