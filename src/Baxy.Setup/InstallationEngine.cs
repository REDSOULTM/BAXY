using System.Text;
using System.Text.Json;

namespace Baxy.Setup;

public enum SetupFaultPoint
{
    PackageCopied,
    PackageVerified,
    StagingExtracted,
    VersionPublished,
    PointerNextDurable,
    CurrentReplaced,
    PreviousPromoted,
    OperationCompleted,
}

public interface ISetupFaultInjector
{
    void Checkpoint(SetupFaultPoint point);
}

public enum InstallationDisposition
{
    Installed,
    Updated,
    Idempotent,
    RolledBack,
}

public sealed record InstallationResult(
    InstallationDisposition Disposition,
    string Version,
    string PackageSha256,
    string? PreviousVersion);

internal sealed record VerifiedInstallationIdentity(
    string Version,
    int DataSchema,
    string PackageSha256,
    string ManifestSha256,
    string ContentId);

public sealed class InstallationEngine
{
    private const string CurrentFileName = "current";
    private const string PreviousFileName = "current.previous";
    private const string NextFileName = "current.next";
    private const string RollbackFileName = "current.rollback";
    private const string JournalFileName = "transaction.v1.json";
    private const string JournalNextFileName = "transaction.next";
    private const string LockFileName = "setup.lock";

    private const string InstallOperation = "install_update";
    private const string RollbackOperation = "rollback";
    private const string PreparedPhase = "prepared";
    private const string PackageCopiedPhase = "package_copied";
    private const string PackageVerifiedPhase = "package_verified";
    private const string StagingExtractedPhase = "staging_extracted";
    private const string PublishIntentPhase = "publish_intent";
    private const string VersionPublishedPhase = "version_published";
    private const string PointerIntentPhase = "pointer_intent";
    private const string PointerSwitchedPhase = "pointer_switched";
    private const string ActivationUnchangedPhase = "activation_unchanged";
    private const string CompletePhase = "complete";

    private static readonly byte[] LockFileBytes = Encoding.ASCII.GetBytes("BAXY setup lock v1\n");
    private readonly string _root;
    private readonly string _versionsRoot;
    private readonly string _stagingRoot;
    private readonly ProductPackageVerifier _verifier;
    private readonly ISetupFaultInjector? _faultInjector;

    public InstallationEngine(
        string installationRoot,
        ProductPackageVerifier? verifier = null,
        ISetupFaultInjector? faultInjector = null)
    {
        _root = PathSafety.ValidateInstallationRoot(installationRoot);
        _versionsRoot = Path.Combine(_root, "versions");
        _stagingRoot = Path.Combine(_root, "staging");
        _verifier = verifier ?? new ProductPackageVerifier();
        _faultInjector = faultInjector;
    }

    public string InstallationRoot => _root;

    public InstallationResult InstallOrUpdate(Stream packageStream)
    {
        ArgumentNullException.ThrowIfNull(packageStream);
        return UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            session => session.InstallOrUpdate(packageStream));
    }

    private InstallationResult InstallOrUpdateCore(Stream packageStream)
    {
        (InstallationPointer? beforeCurrent, _) = ReadAndVerifyStablePointerState();

        string transactionId = Guid.NewGuid().ToString("N");
        InstallTransaction transaction = new()
        {
            TransactionId = transactionId,
            StagingId = transactionId,
            Operation = InstallOperation,
            Phase = PreparedPhase,
            BeforeCurrent = beforeCurrent,
        };
        WriteJournal(transaction);

        string transactionRoot = Path.Combine(_stagingRoot, transactionId);
        PathSafety.EnsureOwnedDirectory(_root, transactionRoot);
        bool retainJournal = false;
        bool simulatedCrash = false;
        try
        {
            string stagedPackagePath = Path.Combine(transactionRoot, "package.zip");
            CopyPackageToOwnedFile(packageStream, stagedPackagePath);
            transaction = AdvanceJournal(transaction, PackageCopiedPhase);
            Checkpoint(SetupFaultPoint.PackageCopied);

            VerifiedProductPackage package;
            using (FileStream stablePackage = new(stagedPackagePath, FileMode.Open, FileAccess.Read, FileShare.None))
            {
                package = _verifier.Verify(stablePackage);
                InstallationPointer target = PointerFrom(package);
                AssertCompatibleDataSchema(
                    beforeCurrent,
                    target,
                    "Install/update cannot cross the installed data schema.");
                transaction = AdvanceJournal(transaction, PackageVerifiedPhase, target);
                if (beforeCurrent is not null &&
                    !string.Equals(beforeCurrent.Version, target.Version, StringComparison.Ordinal) &&
                    SemanticVersionComparer.ComparePrecedence(target.Version, beforeCurrent.Version) <= 0)
                {
                    throw new InstallationSafetyException(
                        "Install/update cannot publish a lower or equal-precedence semantic version; use verified rollback instead.");
                }

                Checkpoint(SetupFaultPoint.PackageVerified);

                string stagedVersion = Path.Combine(transactionRoot, "version");
                _verifier.ExtractVerified(stablePackage, package, _root, stagedVersion);
                _verifier.WriteVersionAttestation(stagedVersion, package);
                VerifiedInstalledVersion stagedAttestation = _verifier.VerifyInstalledVersion(stagedVersion);
                AssertSameIdentity(stagedAttestation, package, "The staged installed version does not match its package.");
                transaction = AdvanceJournal(transaction, StagingExtractedPhase, target);
                Checkpoint(SetupFaultPoint.StagingExtracted);

                string destinationVersion = PathSafety.GetStrictDescendantPath(_versionsRoot, package.Version);
                if (Directory.Exists(destinationVersion) || File.Exists(destinationVersion))
                {
                    if (!Directory.Exists(destinationVersion))
                    {
                        throw new InstallationSafetyException("The immutable version path is not a directory.");
                    }

                    VerifiedInstalledVersion existing = _verifier.VerifyInstalledVersion(destinationVersion);
                    AssertSameIdentity(existing, package, "The same semantic version is already installed with different bytes.");
                    PathSafety.DeleteTreeFailClosed(_root, stagedVersion);
                }
                else
                {
                    transaction = AdvanceJournal(transaction, PublishIntentPhase, target);
                    retainJournal = true;
                    PathSafety.AssertExistingChainHasNoReparsePoint(destinationVersion);
                    MoveDirectoryWithRetry(stagedVersion, destinationVersion);
                    VerifiedInstalledVersion published = _verifier.VerifyInstalledVersion(destinationVersion);
                    AssertSameIdentity(published, package, "The published version failed post-move verification.");
                }

                transaction = AdvanceJournal(transaction, VersionPublishedPhase, target);
                retainJournal = true;
                Checkpoint(SetupFaultPoint.VersionPublished);
            }

            InstallationPointer activationTarget = transaction.Target ??
                throw new InstallationSafetyException("The transaction target is missing after package verification.");
            InstallationPointer? current = ReadPointerIfPresent(CurrentFileName);
            InstallationDisposition disposition;
            string? previousVersion = current?.Version;
            if (current is null)
            {
                if (FileSystemEntryExists(PointerPath(PreviousFileName)))
                {
                    throw new InstallationSafetyException("current.previous exists without current.");
                }

                transaction = AdvanceJournal(transaction, PointerIntentPhase, activationTarget);
                SwapCurrent(activationTarget, hasCurrent: false, injectFaults: true);
                transaction = AdvanceJournal(transaction, PointerSwitchedPhase, activationTarget);
                disposition = InstallationDisposition.Installed;
            }
            else if (PointerEquals(current, activationTarget))
            {
                VerifyPointerTarget(current);
                disposition = InstallationDisposition.Idempotent;
            }
            else
            {
                if (string.Equals(current.Version, activationTarget.Version, StringComparison.Ordinal))
                {
                    throw new InstallationSafetyException("The same semantic version cannot be activated with different package bytes.");
                }

                if (!PointerEquals(current, transaction.BeforeCurrent))
                {
                    throw new InstallationSafetyException("The current pointer changed after the transaction began.");
                }

                VerifyPointerTarget(current);
                if (SemanticVersionComparer.ComparePrecedence(activationTarget.Version, current.Version) <= 0)
                {
                    throw new InstallationSafetyException(
                        "Install/update cannot activate a lower or equal-precedence semantic version; use verified rollback instead.");
                }

                transaction = AdvanceJournal(transaction, PointerIntentPhase, activationTarget);
                SwapCurrent(activationTarget, hasCurrent: true, injectFaults: true);
                transaction = AdvanceJournal(transaction, PointerSwitchedPhase, activationTarget);
                disposition = InstallationDisposition.Updated;
            }

            transaction = disposition == InstallationDisposition.Idempotent
                ? AdvanceJournal(transaction, ActivationUnchangedPhase, activationTarget)
                : AdvanceJournal(transaction, CompletePhase, activationTarget);
            retainJournal = true;
            Checkpoint(SetupFaultPoint.OperationCompleted);
            CleanupJournalOwnedStaging(transaction);
            DeleteJournal();
            retainJournal = false;
            return new InstallationResult(disposition, activationTarget.Version, activationTarget.PackageSha256, previousVersion);
        }
        catch (SetupSimulatedCrashException)
        {
            simulatedCrash = true;
            throw;
        }
        finally
        {
            if (!simulatedCrash && !retainJournal && File.Exists(JournalPath()))
            {
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
            }
        }
    }

    public InstallationResult Rollback()
    {
        return UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            static session => session.Rollback());
    }

    private InstallationResult RollbackCore()
    {
        (InstallationPointer? stableCurrent, InstallationPointer? stablePrevious) =
            ReadAndVerifyStablePointerState();
        InstallationPointer current = stableCurrent ??
            throw new InstallationSafetyException("No current BAXY version is installed.");
        InstallationPointer previous = stablePrevious ??
            throw new InstallationSafetyException("No verified previous BAXY version is available.");
        AssertCompatibleDataSchema(current, previous, "Rollback cannot cross the installed data schema.");

        InstallTransaction transaction = new()
        {
            TransactionId = Guid.NewGuid().ToString("N"),
            StagingId = null,
            Operation = RollbackOperation,
            Phase = PointerIntentPhase,
            Target = previous,
            BeforeCurrent = current,
        };
        WriteJournal(transaction);
        SwapCurrent(previous, hasCurrent: true, injectFaults: true);
        transaction = AdvanceJournal(transaction, PointerSwitchedPhase, previous);
        transaction = AdvanceJournal(transaction, CompletePhase, previous);
        Checkpoint(SetupFaultPoint.OperationCompleted);
        DeleteJournal();
        return new InstallationResult(
            InstallationDisposition.RolledBack,
            previous.Version,
            previous.PackageSha256,
            current.Version);
    }

    public string? GetCurrentVersion()
    {
        return UseExclusiveInstallation(
            requireExistingRootAndLock: false,
            static session => session.GetCurrentVersion());
    }

    internal TResult UseExclusiveInstallation<TResult>(
        bool requireExistingRootAndLock,
        Func<ExclusiveInstallationSession, TResult> callback)
    {
        ArgumentNullException.ThrowIfNull(callback);
        using OperationLease lease = AcquireOperationLease(requireExistingRootAndLock);
        if (requireExistingRootAndLock)
        {
            AssertExistingOwnedLayout();
        }
        else
        {
            PrepareOwnedLayout();
        }

        RecoverExistingTransaction();
        ExclusiveInstallationSession session = new(this);
        try
        {
            return callback(session);
        }
        finally
        {
            session.Close();
        }
    }

    private string? GetCurrentVersionCore()
    {
        (InstallationPointer? current, _) = ReadAndVerifyStablePointerState();
        return current?.Version;
    }

    private VerifiedInstallationIdentity GetVerifiedCurrentIdentityCore()
    {
        (InstallationPointer? current, _) = ReadAndVerifyStablePointerState();
        InstallationPointer verified = current ??
            throw new InstallationSafetyException("No current BAXY version is installed.");
        return IdentityFrom(verified);
    }

    private VerifiedInstallationIdentity GetVerifiedRollbackTargetIdentityCore()
    {
        (InstallationPointer? current, InstallationPointer? previous) =
            ReadAndVerifyStablePointerState();
        _ = current ??
            throw new InstallationSafetyException("No current BAXY version is installed.");
        InstallationPointer verifiedPrevious = previous ??
            throw new InstallationSafetyException(
                "No verified previous BAXY version is available for rollback.");
        return IdentityFrom(verifiedPrevious);
    }

    internal TResult UseVerifiedCurrentApplication<TResult>(
        Func<VerifiedInstalledApplication, TResult> callback)
    {
        ArgumentNullException.ThrowIfNull(callback);
        return UseExclusiveInstallation(
            requireExistingRootAndLock: true,
            session => session.UseVerifiedCurrentApplication(callback));
    }

    private TResult UseVerifiedCurrentApplicationCore<TResult>(
        Func<VerifiedInstalledApplication, TResult> callback)
    {
        (InstallationPointer? current, _) = ReadAndVerifyStablePointerState();
        if (current is null)
        {
            throw new InstallationSafetyException("No current BAXY version is installed.");
        }

        string versionRoot = PathSafety.GetStrictDescendantPath(_versionsRoot, current.Version);
        string applicationName = PathSafety.GetStrictDescendantPath(versionRoot, "Baxy.exe");
        PathSafety.AssertRegularFile(applicationName);

        return callback(new VerifiedInstalledApplication(
            current.Version,
            applicationName,
            versionRoot));
    }

    private OperationLease AcquireOperationLease(bool requireExistingRootAndLock = false)
    {
        InstallationOperationGate gate = InstallationOperationGate.Acquire(_root);
        try
        {
            if (requireExistingRootAndLock)
            {
                AssertExistingOwnedDirectory(_root, "installation root");
            }
            else
            {
                PathSafety.EnsureOwnedDirectory(_root, _root);
            }

            string lockPath = Path.Combine(_root, LockFileName);
            bool existing = FileSystemEntryExists(lockPath);
            if (requireExistingRootAndLock && !existing)
            {
                throw new InstallationSafetyException("The persistent Setup lock file is missing.");
            }

            if (existing)
            {
                PathSafety.AssertRegularFile(lockPath);
            }

            FileStream lockStream;
            try
            {
                lockStream = new FileStream(
                    lockPath,
                    requireExistingRootAndLock ? FileMode.Open : FileMode.OpenOrCreate,
                    FileAccess.ReadWrite,
                    FileShare.None);
            }
            catch (IOException exception)
            {
                throw new InstallationSafetyException("Another Setup process holds the installation lock file.", exception);
            }

            try
            {
                if (lockStream.Length == 0)
                {
                    lockStream.Write(LockFileBytes);
                    lockStream.Flush(flushToDisk: true);
                }
                else
                {
                    if (lockStream.Length != LockFileBytes.Length)
                    {
                        throw new InstallationSafetyException("The persistent Setup lock file is malformed.");
                    }

                    byte[] actual = new byte[LockFileBytes.Length];
                    lockStream.Position = 0;
                    lockStream.ReadExactly(actual);
                    if (!actual.AsSpan().SequenceEqual(LockFileBytes))
                    {
                        throw new InstallationSafetyException("The persistent Setup lock file is malformed.");
                    }
                }

                return new OperationLease(gate, lockStream);
            }
            catch
            {
                lockStream.Dispose();
                throw;
            }
        }
        catch
        {
            gate.Dispose();
            throw;
        }
    }

    private void AssertExistingOwnedLayout()
    {
        AssertExistingOwnedDirectory(_root, "installation root");
        AssertExistingOwnedDirectory(_versionsRoot, "versions root");
        AssertExistingOwnedDirectory(_stagingRoot, "staging root");
    }

    private static void AssertExistingOwnedDirectory(string path, string description)
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(path);
        if (!Directory.Exists(path))
        {
            throw new InstallationSafetyException($"The existing BAXY {description} is missing.");
        }

        FileAttributes attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException($"The existing BAXY {description} is unsafe.");
        }
    }

    private void PrepareOwnedLayout()
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(_root);
        PathSafety.EnsureOwnedDirectory(_root, _versionsRoot);
        PathSafety.EnsureOwnedDirectory(_root, _stagingRoot);
    }

    private void RecoverExistingTransaction()
    {
        if (FileSystemEntryExists(Path.Combine(_root, JournalNextFileName)))
        {
            string interruptedNext = Path.Combine(_root, JournalNextFileName);
            PathSafety.AssertRegularFile(interruptedNext);
            File.Delete(interruptedNext);
        }

        InstallTransaction? transaction = ReadJournalIfPresent();
        if (transaction is null)
        {
            AssertNoPointerArtifacts();
            AssertStagingOwnedBy(null);
            return;
        }

        AssertStagingOwnedBy(transaction.StagingId);
        switch (transaction.Phase)
        {
            case PreparedPhase:
            case PackageCopiedPhase:
            case PackageVerifiedPhase:
            case StagingExtractedPhase:
                AssertNoPointerArtifacts();
                AssertCurrentMatches(transaction.BeforeCurrent);
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            case PublishIntentPhase:
                AssertNoPointerArtifacts();
                AssertCurrentMatches(transaction.BeforeCurrent);
                if (transaction.Target is not null)
                {
                    string targetRoot = PathSafety.GetStrictDescendantPath(_versionsRoot, transaction.Target.Version);
                    if (Directory.Exists(targetRoot))
                    {
                        VerifyPointerTarget(transaction.Target);
                    }
                }

                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            case VersionPublishedPhase:
                RequireTarget(transaction);
                AssertNoPointerArtifacts();
                VerifyPointerTarget(transaction.Target!);
                AssertCurrentMatches(transaction.BeforeCurrent);
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            case PointerIntentPhase:
                RequireTarget(transaction);
                VerifyPointerTarget(transaction.Target!);
                RecoverPointerTransition(transaction);
                transaction = AdvanceJournal(transaction, PointerSwitchedPhase, transaction.Target);
                ValidateCompletedPointerTransition(transaction.Target!, transaction.BeforeCurrent);
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            case PointerSwitchedPhase:
            case CompletePhase:
                RequireTarget(transaction);
                AssertNoPointerArtifacts();
                ValidateCompletedPointerTransition(transaction.Target!, transaction.BeforeCurrent);
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            case ActivationUnchangedPhase:
                RequireTarget(transaction);
                AssertNoPointerArtifacts();
                AssertCurrentMatches(transaction.Target);
                CleanupJournalOwnedStaging(transaction);
                DeleteJournal();
                return;

            default:
                throw new InstallationSafetyException("The transaction journal phase is unsupported.");
        }
    }

    private void RecoverPointerTransition(InstallTransaction transaction)
    {
        InstallationPointer target = transaction.Target ??
            throw new InstallationSafetyException("A pointer transition is missing its target.");
        InstallationPointer? beforeCurrent = transaction.BeforeCurrent;
        bool isRollback = string.Equals(transaction.Operation, RollbackOperation, StringComparison.Ordinal);
        string nextPath = PointerPath(NextFileName);
        string rollbackPath = PointerPath(RollbackFileName);
        bool nextExists = FileSystemEntryExists(nextPath);
        bool rollbackExists = FileSystemEntryExists(rollbackPath);
        if (nextExists && rollbackExists)
        {
            throw new InstallationSafetyException("Contradictory pointer artifacts require manual repair.");
        }

        if (rollbackExists)
        {
            InstallationPointer current = ReadPointerIfPresent(CurrentFileName) ??
                throw new InstallationSafetyException("current.rollback exists without current.");
            InstallationPointer rollback = ReadPointer(rollbackPath);
            if (!PointerEquals(current, target) || !PointerEquals(rollback, beforeCurrent))
            {
                throw new InstallationSafetyException("Pointer rollback bytes contradict the transaction journal.");
            }

            VerifyPointerTarget(current);
            VerifyPointerTarget(rollback);
            if (isRollback)
            {
                AssertPreviousMatches(target);
            }

            PromoteRollbackToPrevious();
        }
        else if (nextExists)
        {
            InstallationPointer next = ReadPointer(nextPath);
            if (!PointerEquals(next, target))
            {
                throw new InstallationSafetyException("current.next contradicts the transaction target.");
            }

            AssertCurrentMatches(beforeCurrent);
            if (isRollback)
            {
                AssertPreviousMatches(target);
            }

            ReplaceCurrentFromExistingNext(beforeCurrent is not null);
        }
        else
        {
            InstallationPointer? current = ReadPointerIfPresent(CurrentFileName);
            if (!PointerEquals(current, target))
            {
                AssertCurrentMatches(beforeCurrent);
                if (isRollback)
                {
                    AssertPreviousMatches(target);
                }

                SwapCurrent(target, beforeCurrent is not null, injectFaults: false);
            }
        }

        ValidateCompletedPointerTransition(target, beforeCurrent);
    }

    private void ValidateCompletedPointerTransition(InstallationPointer target, InstallationPointer? beforeCurrent)
    {
        if (beforeCurrent is not null && PointerEquals(target, beforeCurrent))
        {
            throw new InstallationSafetyException("A completed pointer transition cannot retain the original current identity.");
        }

        InstallationPointer current = ReadPointerIfPresent(CurrentFileName) ??
            throw new InstallationSafetyException("The completed transaction has no current pointer.");
        if (!PointerEquals(current, target))
        {
            throw new InstallationSafetyException("Current does not match the completed transaction target.");
        }

        VerifyPointerTarget(current);
        InstallationPointer? previous = ReadPointerIfPresent(PreviousFileName);
        if (beforeCurrent is null)
        {
            if (previous is not null)
            {
                throw new InstallationSafetyException("A first install unexpectedly produced current.previous.");
            }
        }
        else if (!PointerEquals(previous, beforeCurrent))
        {
            throw new InstallationSafetyException("current.previous does not match the journaled pre-transaction current.");
        }
        else
        {
            VerifyPointerTarget(previous!);
        }
    }

    private void SwapCurrent(InstallationPointer target, bool hasCurrent, bool injectFaults)
    {
        VerifyPointerTarget(target);
        string nextPath = PointerPath(NextFileName);
        string rollbackPath = PointerPath(RollbackFileName);
        if (FileSystemEntryExists(nextPath) || FileSystemEntryExists(rollbackPath))
        {
            throw new InstallationSafetyException("A prior pointer transaction has not been recovered.");
        }

        WritePointerNew(nextPath, target);
        if (injectFaults)
        {
            Checkpoint(SetupFaultPoint.PointerNextDurable);
        }

        ReplaceCurrentFromExistingNext(hasCurrent, injectFaults);
    }

    private void ReplaceCurrentFromExistingNext(bool hasCurrent, bool injectFaults = false)
    {
        string nextPath = PointerPath(NextFileName);
        string currentPath = PointerPath(CurrentFileName);
        string rollbackPath = PointerPath(RollbackFileName);
        PathSafety.AssertRegularFile(nextPath);
        if (!hasCurrent)
        {
            if (FileSystemEntryExists(currentPath) || FileSystemEntryExists(PointerPath(PreviousFileName)))
            {
                throw new InstallationSafetyException("First-install pointer state is contradictory.");
            }

            File.Move(nextPath, currentPath);
            PathSafety.AssertRegularFile(currentPath);
            if (injectFaults)
            {
                Checkpoint(SetupFaultPoint.CurrentReplaced);
            }

            return;
        }

        InstallationPointer? existingPrevious = null;
        if (FileSystemEntryExists(PointerPath(PreviousFileName)))
        {
            existingPrevious = ReadPointer(PointerPath(PreviousFileName));
            VerifyPointerTarget(existingPrevious);
        }

        if (FileSystemEntryExists(rollbackPath))
        {
            throw new InstallationSafetyException("A durable rollback artifact already occupies the replacement path.");
        }

        InstallationPointer originalCurrent = ReadPointer(currentPath);
        VerifyPointerTarget(originalCurrent);
        if (existingPrevious is not null && PointerEquals(existingPrevious, originalCurrent))
        {
            throw new InstallationSafetyException("current.previous cannot identify the same version as current.");
        }

        ReplaceFileWithRetry(nextPath, currentPath, rollbackPath, ignoreMetadataErrors: true);
        PathSafety.AssertRegularFile(currentPath);
        PathSafety.AssertRegularFile(rollbackPath);
        InstallationPointer durableRollback = ReadPointer(rollbackPath);
        VerifyPointerTarget(durableRollback);
        if (!PointerEquals(durableRollback, originalCurrent))
        {
            throw new InstallationSafetyException("current.rollback does not match the pre-replacement current pointer.");
        }

        if (injectFaults)
        {
            Checkpoint(SetupFaultPoint.CurrentReplaced);
        }

        PromoteRollbackToPrevious();
        if (injectFaults)
        {
            Checkpoint(SetupFaultPoint.PreviousPromoted);
        }
    }

    private void PromoteRollbackToPrevious()
    {
        string rollbackPath = PointerPath(RollbackFileName);
        string previousPath = PointerPath(PreviousFileName);
        if (!FileSystemEntryExists(rollbackPath))
        {
            throw new InstallationSafetyException("The durable rollback pointer is missing.");
        }

        InstallationPointer rollback = ReadPointer(rollbackPath);
        VerifyPointerTarget(rollback);

        if (FileSystemEntryExists(previousPath))
        {
            InstallationPointer existingPrevious = ReadPointer(previousPath);
            VerifyPointerTarget(existingPrevious);
            ReplaceFileWithRetry(rollbackPath, previousPath, destinationBackupFileName: null, ignoreMetadataErrors: true);
        }
        else
        {
            File.Move(rollbackPath, previousPath);
        }

        PathSafety.AssertRegularFile(previousPath);
    }

    private void AssertStagingOwnedBy(string? stagingId)
    {
        foreach (string entry in Directory.EnumerateFileSystemEntries(_stagingRoot))
        {
            FileAttributes attributes = File.GetAttributes(entry);
            if ((attributes & FileAttributes.ReparsePoint) != 0 || (attributes & FileAttributes.Directory) == 0)
            {
                throw new InstallationSafetyException("The staging root contains an unsafe entry.");
            }

            string name = Path.GetFileName(entry);
            if (stagingId is null || !string.Equals(name, stagingId, StringComparison.Ordinal))
            {
                throw new InstallationSafetyException("The staging root contains a transaction not attested by the journal.");
            }

            _ = PathSafety.InspectTree(entry);
        }
    }

    private void CleanupJournalOwnedStaging(InstallTransaction transaction)
    {
        if (transaction.StagingId is null)
        {
            AssertStagingOwnedBy(null);
            return;
        }

        AssertStagingOwnedBy(transaction.StagingId);
        string path = Path.Combine(_stagingRoot, transaction.StagingId);
        if (Directory.Exists(path))
        {
            PathSafety.DeleteTreeFailClosed(_root, path);
        }
    }

    private void AssertNoPointerArtifacts()
    {
        if (FileSystemEntryExists(PointerPath(NextFileName)) ||
            FileSystemEntryExists(PointerPath(RollbackFileName)))
        {
            throw new InstallationSafetyException("Pointer artifacts exist without a matching pointer-intent journal phase.");
        }
    }

    private void AssertCurrentMatches(InstallationPointer? expected)
    {
        (InstallationPointer? current, _) = ReadAndVerifyStablePointerState();
        if (!PointerEquals(current, expected))
        {
            throw new InstallationSafetyException("Current changed outside the journaled transaction.");
        }
    }

    private (InstallationPointer? Current, InstallationPointer? Previous) ReadAndVerifyStablePointerState()
    {
        InstallationPointer? current = ReadPointerIfPresent(CurrentFileName);
        if (current is not null)
        {
            VerifyPointerTarget(current);
        }

        InstallationPointer? previous = ReadPointerIfPresent(PreviousFileName);
        if (previous is null)
        {
            return (current, null);
        }

        if (current is null)
        {
            throw new InstallationSafetyException("current.previous exists without current.");
        }

        VerifyPointerTarget(previous);
        AssertCompatibleDataSchema(current, previous, "Stable installation pointers cannot cross the installed data schema.");
        if (PointerEquals(current, previous))
        {
            throw new InstallationSafetyException("current.previous cannot identify the same version as current.");
        }

        return (current, previous);
    }

    private void AssertPreviousMatches(InstallationPointer expected)
    {
        InstallationPointer previous = ReadPointerIfPresent(PreviousFileName) ??
            throw new InstallationSafetyException("A rollback transaction has no current.previous pointer.");
        VerifyPointerTarget(previous);
        if (!PointerEquals(previous, expected))
        {
            throw new InstallationSafetyException("A rollback transaction target does not match current.previous.");
        }
    }

    private InstallTransaction AdvanceJournal(
        InstallTransaction transaction,
        string phase,
        InstallationPointer? target = null)
    {
        InstallTransaction advanced = new()
        {
            TransactionId = transaction.TransactionId,
            StagingId = transaction.StagingId,
            Operation = transaction.Operation,
            Phase = phase,
            Target = target ?? transaction.Target,
            BeforeCurrent = transaction.BeforeCurrent,
        };
        WriteJournal(advanced);
        return advanced;
    }

    private void WriteJournal(InstallTransaction transaction)
    {
        ValidateTransaction(transaction);
        byte[] bytes = SerializeDurable(transaction, SetupJsonContext.Default.InstallTransaction);
        string nextPath = Path.Combine(_root, JournalNextFileName);
        string journalPath = JournalPath();
        if (FileSystemEntryExists(nextPath))
        {
            throw new InstallationSafetyException("A journal replacement artifact already exists.");
        }

        WriteNewDurableFile(nextPath, bytes);
        if (FileSystemEntryExists(journalPath))
        {
            PathSafety.AssertRegularFile(journalPath);
            ReplaceFileWithRetry(nextPath, journalPath, destinationBackupFileName: null, ignoreMetadataErrors: true);
        }
        else
        {
            File.Move(nextPath, journalPath);
        }

        PathSafety.AssertRegularFile(journalPath);
    }

    private InstallTransaction? ReadJournalIfPresent()
    {
        string path = JournalPath();
        if (!FileSystemEntryExists(path))
        {
            return null;
        }

        PathSafety.AssertRegularFile(path);
        FileInfo info = new(path);
        if (info.Length is <= 0 or > 8192)
        {
            throw new InstallationSafetyException("The transaction journal has an invalid length.");
        }

        byte[] bytes = File.ReadAllBytes(path);
        try
        {
            using JsonDocument document = JsonDocument.Parse(bytes);
            AssertJsonPropertySequence(document.RootElement,
                ["schema", "transaction_id", "staging_id", "operation", "phase", "target", "before_current"],
                "transaction journal");
            JsonElement target = document.RootElement.GetProperty("target");
            if (target.ValueKind != JsonValueKind.Null)
            {
                AssertPointerJsonShape(target);
            }

            JsonElement beforeCurrent = document.RootElement.GetProperty("before_current");
            if (beforeCurrent.ValueKind != JsonValueKind.Null)
            {
                AssertPointerJsonShape(beforeCurrent);
            }

            InstallTransaction? transaction = JsonSerializer.Deserialize(bytes, SetupJsonContext.Default.InstallTransaction);
            if (transaction is null)
            {
                throw new InstallationSafetyException("The transaction journal is null.");
            }

            ValidateTransaction(transaction);
            byte[] canonical = SerializeDurable(transaction, SetupJsonContext.Default.InstallTransaction);
            if (!bytes.AsSpan().SequenceEqual(canonical))
            {
                throw new InstallationSafetyException("The transaction journal is not canonical JSON.");
            }

            return transaction;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException or IOException)
        {
            throw new InstallationSafetyException("The transaction journal is malformed.", exception);
        }
    }

    private static void ReplaceFileWithRetry(
        string sourcePath,
        string destinationPath,
        string? destinationBackupFileName,
        bool ignoreMetadataErrors)
    {
        const int maximumAttempts = 200;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                File.Replace(
                    sourcePath,
                    destinationPath,
                    destinationBackupFileName,
                    ignoreMetadataErrors);
                return;
            }
            catch (IOException) when (attempt < maximumAttempts)
            {
                Thread.Sleep(10);
            }
        }
    }

    private static void MoveDirectoryWithRetry(
        string sourcePath,
        string destinationPath)
    {
        const int maximumAttempts = 200;
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                Directory.Move(sourcePath, destinationPath);
                return;
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException
                && attempt < maximumAttempts)
            {
                if (!Directory.Exists(sourcePath)
                    || FileSystemEntryExists(destinationPath))
                {
                    throw;
                }

                Thread.Sleep(10);
            }
        }
    }

    private void DeleteJournal()
    {
        string path = JournalPath();
        if (!FileSystemEntryExists(path))
        {
            throw new InstallationSafetyException("The transaction journal disappeared before completion.");
        }

        PathSafety.AssertRegularFile(path);
        File.Delete(path);
    }

    private static void ValidateTransaction(InstallTransaction transaction)
    {
        if (!string.Equals(transaction.Schema, PackageContract.TransactionSchema, StringComparison.Ordinal) ||
            !IsCanonicalGuid(transaction.TransactionId) ||
            (transaction.StagingId is not null && !IsCanonicalGuid(transaction.StagingId)) ||
            transaction.Operation is not (InstallOperation or RollbackOperation) ||
            transaction.Phase is not (PreparedPhase or PackageCopiedPhase or PackageVerifiedPhase or
                StagingExtractedPhase or PublishIntentPhase or VersionPublishedPhase or PointerIntentPhase or
                PointerSwitchedPhase or ActivationUnchangedPhase or CompletePhase))
        {
            throw new InstallationSafetyException("The transaction journal contains an invalid identity, operation, or phase.");
        }

        if (transaction.Operation == InstallOperation &&
            !string.Equals(transaction.StagingId, transaction.TransactionId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException("An install transaction staging identity must equal its transaction identity.");
        }

        if (transaction.Operation == RollbackOperation &&
            (transaction.StagingId is not null || transaction.BeforeCurrent is null || transaction.Target is null ||
             transaction.Phase is not (PointerIntentPhase or PointerSwitchedPhase or CompletePhase)))
        {
            throw new InstallationSafetyException("A rollback transaction has an invalid staging, target, or phase combination.");
        }

        bool phaseRequiresTarget = transaction.Phase is PackageVerifiedPhase or StagingExtractedPhase or
            PublishIntentPhase or VersionPublishedPhase or PointerIntentPhase or PointerSwitchedPhase or
            ActivationUnchangedPhase or CompletePhase;
        if (phaseRequiresTarget != (transaction.Target is not null))
        {
            throw new InstallationSafetyException("The transaction target does not match its journal phase.");
        }

        if (transaction.Operation == InstallOperation && transaction.Phase == ActivationUnchangedPhase &&
            !PointerEquals(transaction.BeforeCurrent, transaction.Target))
        {
            throw new InstallationSafetyException("An unchanged activation must retain the original current identity.");
        }

        if (transaction.Target is not null)
        {
            ValidatePointerValues(transaction.Target);
        }

        if (transaction.BeforeCurrent is not null)
        {
            ValidatePointerValues(transaction.BeforeCurrent);
        }

        if (transaction.Target is not null)
        {
            AssertCompatibleDataSchema(
                transaction.BeforeCurrent,
                transaction.Target,
                "A transaction cannot cross the installed data schema.");
        }

        bool isPointerTransition = transaction.Phase is PointerIntentPhase or PointerSwitchedPhase or CompletePhase;
        if (transaction.Operation == RollbackOperation &&
            PointerEquals(transaction.Target, transaction.BeforeCurrent))
        {
            throw new InstallationSafetyException("A rollback transaction must change the current identity.");
        }

        if (transaction.Operation == InstallOperation && isPointerTransition &&
            transaction.BeforeCurrent is not null &&
            SemanticVersionComparer.ComparePrecedence(
                transaction.Target!.Version,
                transaction.BeforeCurrent.Version) <= 0)
        {
            throw new InstallationSafetyException("An install/update pointer transition must advance semantic-version precedence.");
        }
    }

    private InstallationPointer? ReadPointerIfPresent(string fileName)
    {
        string path = PointerPath(fileName);
        return FileSystemEntryExists(path) ? ReadPointer(path) : null;
    }

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

    private static InstallationPointer ReadPointer(string path)
    {
        PathSafety.AssertRegularFile(path);
        FileInfo info = new(path);
        if (info.Length is <= 0 or > 2048)
        {
            throw new InstallationSafetyException("An installation pointer has an invalid length.");
        }

        byte[] bytes = File.ReadAllBytes(path);
        try
        {
            using JsonDocument document = JsonDocument.Parse(bytes);
            AssertPointerJsonShape(document.RootElement);
            InstallationPointer? pointer = JsonSerializer.Deserialize(bytes, SetupJsonContext.Default.InstallationPointer);
            if (pointer is null)
            {
                throw new InstallationSafetyException("An installation pointer is null.");
            }

            ValidatePointerValues(pointer);
            byte[] canonical = SerializeDurable(pointer, SetupJsonContext.Default.InstallationPointer);
            if (!bytes.AsSpan().SequenceEqual(canonical))
            {
                throw new InstallationSafetyException("An installation pointer is not canonical JSON.");
            }

            return pointer;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException or IOException)
        {
            throw new InstallationSafetyException("An installation pointer is malformed.", exception);
        }
    }

    private static void ValidatePointerValues(InstallationPointer pointer)
    {
        if (!string.Equals(pointer.Schema, PackageContract.PointerSchema, StringComparison.Ordinal) ||
            pointer.DataSchema != PackageContract.DataSchema ||
            !SemanticVersionComparer.IsValid(pointer.Version) ||
            !IsLowerHex(pointer.PackageSha256) || !IsLowerHex(pointer.ManifestSha256) || !IsLowerHex(pointer.ContentId))
        {
            throw new InstallationSafetyException("An installation pointer value is invalid or null.");
        }

        try
        {
            PathSafety.ValidateRelativePath(pointer.Version);
        }
        catch (ProductPackageException exception)
        {
            throw new InstallationSafetyException("An installation pointer version is unsafe.", exception);
        }
    }

    private static void AssertPointerJsonShape(JsonElement element) => AssertJsonPropertySequence(
        element,
        ["schema", "version", "data_schema", "package_sha256", "manifest_sha256", "content_id"],
        "installation pointer");

    private static void AssertJsonPropertySequence(JsonElement element, string[] expected, string context)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            throw new InstallationSafetyException($"The {context} must be a JSON object.");
        }

        int index = 0;
        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (index >= expected.Length || !string.Equals(property.Name, expected[index], StringComparison.Ordinal))
            {
                throw new InstallationSafetyException($"The {context} property set is non-canonical.");
            }

            index++;
        }

        if (index != expected.Length)
        {
            throw new InstallationSafetyException($"The {context} property set is incomplete.");
        }
    }

    private void VerifyPointerTarget(InstallationPointer pointer)
    {
        string versionRoot = PathSafety.GetStrictDescendantPath(_versionsRoot, pointer.Version);
        if (!Directory.Exists(versionRoot))
        {
            throw new InstallationSafetyException("An installation pointer targets a missing version.");
        }

        VerifiedInstalledVersion installed = _verifier.VerifyInstalledVersion(versionRoot);
        if (pointer.DataSchema != installed.DataSchema ||
            !string.Equals(pointer.Version, installed.Version, StringComparison.Ordinal) ||
            !string.Equals(pointer.PackageSha256, installed.PackageSha256, StringComparison.Ordinal) ||
            !string.Equals(pointer.ManifestSha256, installed.ManifestSha256, StringComparison.Ordinal) ||
            !string.Equals(pointer.ContentId, installed.ContentId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException("An installation pointer does not match its immutable version.");
        }
    }

    private static void AssertSameIdentity(
        VerifiedInstalledVersion installed,
        VerifiedProductPackage package,
        string failureMessage)
    {
        if (installed.DataSchema != package.DataSchema ||
            !string.Equals(installed.Version, package.Version, StringComparison.Ordinal) ||
            !string.Equals(installed.PackageSha256, package.PackageSha256, StringComparison.Ordinal) ||
            !string.Equals(installed.ManifestSha256, package.ManifestSha256, StringComparison.Ordinal) ||
            !string.Equals(installed.ContentId, package.ContentId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(failureMessage);
        }
    }

    private static InstallationPointer PointerFrom(VerifiedProductPackage package) => new()
    {
        DataSchema = package.DataSchema,
        Version = package.Version,
        PackageSha256 = package.PackageSha256,
        ManifestSha256 = package.ManifestSha256,
        ContentId = package.ContentId,
    };

    private static VerifiedInstallationIdentity IdentityFrom(InstallationPointer pointer) =>
        new(
            pointer.Version,
            pointer.DataSchema,
            pointer.PackageSha256,
            pointer.ManifestSha256,
            pointer.ContentId);

    private static bool PointerEquals(InstallationPointer? left, InstallationPointer? right)
    {
        if (left is null || right is null)
        {
            return left is null && right is null;
        }

        return left.DataSchema == right.DataSchema &&
            string.Equals(left.Version, right.Version, StringComparison.Ordinal) &&
            string.Equals(left.PackageSha256, right.PackageSha256, StringComparison.Ordinal) &&
            string.Equals(left.ManifestSha256, right.ManifestSha256, StringComparison.Ordinal) &&
            string.Equals(left.ContentId, right.ContentId, StringComparison.Ordinal);
    }

    private static void AssertCompatibleDataSchema(
        InstallationPointer? left,
        InstallationPointer right,
        string failureMessage)
    {
        if (left is not null && left.DataSchema != right.DataSchema)
        {
            throw new InstallationSafetyException(failureMessage);
        }
    }

    private static void WritePointerNew(string path, InstallationPointer pointer) =>
        WriteNewDurableFile(path, SerializeDurable(pointer, SetupJsonContext.Default.InstallationPointer));

    private static void CopyPackageToOwnedFile(Stream source, string destination)
    {
        byte[] buffer = new byte[1024 * 1024];
        long total = 0;
        using FileStream output = new(destination, new FileStreamOptions
        {
            Mode = FileMode.CreateNew,
            Access = FileAccess.Write,
            Share = FileShare.None,
            BufferSize = buffer.Length,
            Options = FileOptions.SequentialScan | FileOptions.WriteThrough,
        });
        while (true)
        {
            int read = source.Read(buffer, 0, buffer.Length);
            if (read == 0)
            {
                break;
            }

            total = checked(total + read);
            if (total > PackageContract.MaximumPackageBytes)
            {
                throw new ProductPackageException("The input package exceeds the reviewed size limit.");
            }

            output.Write(buffer, 0, read);
        }

        output.Flush(flushToDisk: true);
    }

    private static byte[] SerializeDurable<T>(T value, System.Text.Json.Serialization.Metadata.JsonTypeInfo<T> typeInfo)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(value, typeInfo);
        byte[] durable = new byte[json.Length + 1];
        json.CopyTo(durable, 0);
        durable[^1] = (byte)'\n';
        return durable;
    }

    private static void WriteNewDurableFile(string path, byte[] bytes)
    {
        using FileStream stream = new(path, new FileStreamOptions
        {
            Mode = FileMode.CreateNew,
            Access = FileAccess.Write,
            Share = FileShare.None,
            BufferSize = 4096,
            Options = FileOptions.WriteThrough,
        });
        stream.Write(bytes);
        stream.Flush(flushToDisk: true);
    }

    private static void RequireTarget(InstallTransaction transaction)
    {
        if (transaction.Target is null)
        {
            throw new InstallationSafetyException("The transaction phase requires a target identity.");
        }
    }

    private string PointerPath(string fileName) => Path.Combine(_root, fileName);

    private string JournalPath() => Path.Combine(_root, JournalFileName);

    private void Checkpoint(SetupFaultPoint point) => _faultInjector?.Checkpoint(point);

    private static bool IsCanonicalGuid(string? value) =>
        value is not null && Guid.TryParseExact(value, "N", out Guid parsed) &&
        string.Equals(value, parsed.ToString("N"), StringComparison.Ordinal);

    private static bool IsLowerHex(string? value)
    {
        if (value is null || value.Length != 64)
        {
            return false;
        }

        return value.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f');
    }

    internal sealed class ExclusiveInstallationSession
    {
        private readonly InstallationEngine _owner;
        private bool _active = true;

        internal ExclusiveInstallationSession(InstallationEngine owner)
        {
            _owner = owner;
        }

        internal InstallationResult InstallOrUpdate(Stream packageStream)
        {
            EnsureActive();
            ArgumentNullException.ThrowIfNull(packageStream);
            return _owner.InstallOrUpdateCore(packageStream);
        }

        internal InstallationResult Rollback()
        {
            EnsureActive();
            return _owner.RollbackCore();
        }

        internal string? GetCurrentVersion()
        {
            EnsureActive();
            return _owner.GetCurrentVersionCore();
        }

        internal VerifiedInstallationIdentity GetVerifiedCurrentIdentity()
        {
            EnsureActive();
            return _owner.GetVerifiedCurrentIdentityCore();
        }

        internal VerifiedInstallationIdentity GetVerifiedRollbackTargetIdentity()
        {
            EnsureActive();
            return _owner.GetVerifiedRollbackTargetIdentityCore();
        }

        internal TResult UseVerifiedCurrentApplication<TResult>(
            Func<VerifiedInstalledApplication, TResult> callback)
        {
            EnsureActive();
            ArgumentNullException.ThrowIfNull(callback);
            return _owner.UseVerifiedCurrentApplicationCore(callback);
        }

        internal void Close()
        {
            _active = false;
        }

        private void EnsureActive()
        {
            if (!_active)
            {
                throw new InstallationSafetyException(
                    "The exclusive BAXY installation session is no longer active.");
            }
        }
    }

    private sealed class OperationLease : IDisposable
    {
        private readonly InstallationOperationGate _gate;
        private readonly FileStream _lockStream;
        private bool _disposed;

        internal OperationLease(
            InstallationOperationGate gate,
            FileStream lockStream)
        {
            _gate = gate;
            _lockStream = lockStream;
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _lockStream.Dispose();
            _gate.Dispose();
            _disposed = true;
        }
    }
}
