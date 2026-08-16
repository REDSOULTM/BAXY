using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Baxy.Setup;

internal sealed record StableSetupHostIdentity(string Sha256, long Bytes);

internal sealed record StableSetupHostPaths(
    string Stable,
    string Next,
    string Previous);

internal enum StableSetupHostArtifactState
{
    Missing,
    Before,
    Target,
    Foreign,
}

internal enum StableSetupHostRecoveryState
{
    Empty,
    BeforeStable,
    FirstInstallStaged,
    UpdateStaged,
    UpdateBackupReady,
    TargetPublished,
    UpdateReplaced,
    RestoreBackupReady,
    Foreign,
    Contradictory,
}

internal sealed record StableSetupHostInspection(
    StableSetupHostRecoveryState State,
    StableSetupHostArtifactState Stable,
    StableSetupHostArtifactState Next,
    StableSetupHostArtifactState Previous);

internal enum StableSetupHostFaultPoint
{
    NextDurable,
    FirstInstallMoved,
    PreviousBackupDurable,
    UpdateReplaced,
    PreviousDeleted,
    StagedTargetDeleted,
    RestoreTargetBackupDurable,
    PreviousRestored,
}

internal interface IStableSetupHostFaultInjector
{
    void Checkpoint(StableSetupHostFaultPoint point);
}

internal sealed partial class StableSetupHostManager
{
    private const int BufferSize = 1024 * 1024;
    private const uint MoveFileReplaceExisting = 0x1;
    private const uint MoveFileWriteThrough = 0x8;

    private readonly StableSetupHostPaths _paths;
    private readonly IStableSetupHostFaultInjector? _faultInjector;

    internal StableSetupHostManager(
        StableSetupHostPaths paths,
        IStableSetupHostFaultInjector? faultInjector = null)
    {
        _paths = ValidatePaths(paths);
        _faultInjector = faultInjector;
    }

    internal StableSetupHostPaths Paths => _paths;

    internal static void VerifyExact(string path, StableSetupHostIdentity expected)
    {
        string fullPath = ValidateAbsolutePath(path, "Setup host verification path");
        StableSetupHostIdentity validated = ValidateIdentity(expected, nameof(expected));
        StableSetupHostIdentity actual;
        try
        {
            actual = ReadIdentity(fullPath);
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or CryptographicException)
        {
            throw new InstallationSafetyException(
                "The Setup host could not be verified as an exact regular file.",
                exception);
        }

        if (!IdentityEquals(actual, validated))
        {
            throw new InstallationSafetyException(
                "The Setup host does not match its declared SHA-256 and byte length.");
        }
    }

    internal void VerifyStableExact(StableSetupHostIdentity expected) =>
        VerifyExact(_paths.Stable, expected);

    internal void VerifyUnchangedStableExact(StableSetupHostIdentity expected)
    {
        StableSetupHostIdentity validated = ValidateIdentity(expected, nameof(expected));
        RequireState(
            Inspect(before: null, validated),
            StableSetupHostRecoveryState.TargetPublished,
            "verify an unchanged stable Setup host with no transaction artifacts");
        VerifyStableExact(validated);
    }

    internal StableSetupHostInspection Inspect(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        StableSetupHostIdentity? validatedBefore = before is null
            ? null
            : ValidateIdentity(before, nameof(before));
        AssertDistinctIdentities(validatedBefore, validatedTarget);

        StableSetupHostArtifactState stable = ClassifyArtifact(
            _paths.Stable,
            validatedBefore,
            validatedTarget);
        StableSetupHostArtifactState next = ClassifyArtifact(
            _paths.Next,
            validatedBefore,
            validatedTarget);
        StableSetupHostArtifactState previous = ClassifyArtifact(
            _paths.Previous,
            validatedBefore,
            validatedTarget);

        StableSetupHostRecoveryState state = ClassifyRecoveryState(
            validatedBefore is not null,
            stable,
            next,
            previous);
        return new StableSetupHostInspection(state, stable, next, previous);
    }

    internal void StageCandidate(
        string sourcePath,
        StableSetupHostIdentity target,
        StableSetupHostIdentity? before = null)
    {
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        StableSetupHostIdentity? validatedBefore = before is null
            ? null
            : ValidateIdentity(before, nameof(before));
        AssertDistinctIdentities(validatedBefore, validatedTarget);

        StableSetupHostRecoveryState required = validatedBefore is null
            ? StableSetupHostRecoveryState.Empty
            : StableSetupHostRecoveryState.BeforeStable;
        RequireState(Inspect(validatedBefore, validatedTarget), required, "stage a Setup host candidate");

        string source = ValidateExistingSource(sourcePath);
        if (PathsEqual(source, _paths.Stable) ||
            PathsEqual(source, _paths.Next) ||
            PathsEqual(source, _paths.Previous))
        {
            throw new InstallationSafetyException(
                "A Setup host candidate source cannot alias a stable transaction path; use exact verification for stable-host idempotence.");
        }

        CopyExactCreateNew(source, _paths.Next, validatedTarget, "Setup host candidate");
        StableSetupHostRecoveryState expectedState = validatedBefore is null
            ? StableSetupHostRecoveryState.FirstInstallStaged
            : StableSetupHostRecoveryState.UpdateStaged;
        RequireState(Inspect(validatedBefore, validatedTarget), expectedState, "verify the staged Setup host candidate");
        Checkpoint(StableSetupHostFaultPoint.NextDurable);
    }

    internal void PublishFirstInstall(StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        RequireState(
            Inspect(before: null, validatedTarget),
            StableSetupHostRecoveryState.FirstInstallStaged,
            "publish a first-install Setup host");

        MoveFileVerified(
            _paths.Next,
            _paths.Stable,
            MoveFileWriteThrough,
            "publish the first-install Setup host");
        Checkpoint(StableSetupHostFaultPoint.FirstInstallMoved);
        VerifyStableExact(validatedTarget);
        RequireState(
            Inspect(before: null, validatedTarget),
            StableSetupHostRecoveryState.TargetPublished,
            "verify a first-install Setup host publication");
    }

    internal void PublishUpdate(
        StableSetupHostIdentity before,
        StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedBefore = ValidateIdentity(before, nameof(before));
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        AssertDistinctIdentities(validatedBefore, validatedTarget);
        StableSetupHostInspection inspection = Inspect(validatedBefore, validatedTarget);
        if (inspection.State == StableSetupHostRecoveryState.UpdateStaged)
        {
            CopyExactCreateNew(
                _paths.Stable,
                _paths.Previous,
                validatedBefore,
                "previous Setup host backup");
            Checkpoint(StableSetupHostFaultPoint.PreviousBackupDurable);
            inspection = Inspect(validatedBefore, validatedTarget);
        }

        RequireState(
            inspection,
            StableSetupHostRecoveryState.UpdateBackupReady,
            "publish an updated Setup host");
        MoveFileVerified(
            _paths.Next,
            _paths.Stable,
            MoveFileReplaceExisting | MoveFileWriteThrough,
            "replace the stable Setup host");
        Checkpoint(StableSetupHostFaultPoint.UpdateReplaced);
        VerifyStableExact(validatedTarget);
        VerifyExact(_paths.Previous, validatedBefore);
        RequireState(
            Inspect(validatedBefore, validatedTarget),
            StableSetupHostRecoveryState.UpdateReplaced,
            "verify an updated Setup host publication");
    }

    internal bool FinalizePublishedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        StableSetupHostIdentity? validatedBefore = before is null
            ? null
            : ValidateIdentity(before, nameof(before));
        AssertDistinctIdentities(validatedBefore, validatedTarget);
        StableSetupHostInspection inspection = Inspect(validatedBefore, validatedTarget);
        if (inspection.State == StableSetupHostRecoveryState.TargetPublished)
        {
            VerifyStableExact(validatedTarget);
            return false;
        }

        if (validatedBefore is null ||
            inspection.State != StableSetupHostRecoveryState.UpdateReplaced)
        {
            throw UnexpectedState("finalize a published Setup host", inspection);
        }

        VerifyStableExact(validatedTarget);
        VerifyExact(_paths.Previous, validatedBefore);
        File.Delete(_paths.Previous);
        Checkpoint(StableSetupHostFaultPoint.PreviousDeleted);
        RequireState(
            Inspect(validatedBefore, validatedTarget),
            StableSetupHostRecoveryState.TargetPublished,
            "verify finalized Setup host state");
        return true;
    }

    internal bool DeleteStagedTarget(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        StableSetupHostIdentity? validatedBefore = before is null
            ? null
            : ValidateIdentity(before, nameof(before));
        AssertDistinctIdentities(validatedBefore, validatedTarget);
        StableSetupHostInspection inspection = Inspect(validatedBefore, validatedTarget);
        StableSetupHostRecoveryState emptyState = validatedBefore is null
            ? StableSetupHostRecoveryState.Empty
            : StableSetupHostRecoveryState.BeforeStable;
        if (inspection.State == emptyState)
        {
            return false;
        }

        StableSetupHostRecoveryState stagedState = validatedBefore is null
            ? StableSetupHostRecoveryState.FirstInstallStaged
            : StableSetupHostRecoveryState.UpdateStaged;
        if (inspection.State != stagedState)
        {
            throw UnexpectedState("delete a staged Setup host target", inspection);
        }

        VerifyExact(_paths.Next, validatedTarget);
        File.Delete(_paths.Next);
        Checkpoint(StableSetupHostFaultPoint.StagedTargetDeleted);
        RequireState(
            Inspect(validatedBefore, validatedTarget),
            emptyState,
            "verify deletion of a staged Setup host target");
        return true;
    }

    internal void RestorePrevious(
        StableSetupHostIdentity before,
        StableSetupHostIdentity target)
    {
        StableSetupHostIdentity validatedBefore = ValidateIdentity(before, nameof(before));
        StableSetupHostIdentity validatedTarget = ValidateIdentity(target, nameof(target));
        AssertDistinctIdentities(validatedBefore, validatedTarget);
        StableSetupHostInspection inspection = Inspect(validatedBefore, validatedTarget);
        if (inspection.State == StableSetupHostRecoveryState.UpdateReplaced)
        {
            CopyExactCreateNew(
                _paths.Stable,
                _paths.Next,
                validatedTarget,
                "restored Setup host rollback target");
            Checkpoint(StableSetupHostFaultPoint.RestoreTargetBackupDurable);
            inspection = Inspect(validatedBefore, validatedTarget);
        }

        RequireState(
            inspection,
            StableSetupHostRecoveryState.RestoreBackupReady,
            "restore a previous Setup host");
        VerifyStableExact(validatedTarget);
        VerifyExact(_paths.Previous, validatedBefore);
        VerifyExact(_paths.Next, validatedTarget);
        MoveFileVerified(
            _paths.Previous,
            _paths.Stable,
            MoveFileReplaceExisting | MoveFileWriteThrough,
            "restore the previous Setup host");
        Checkpoint(StableSetupHostFaultPoint.PreviousRestored);
        VerifyStableExact(validatedBefore);
        VerifyExact(_paths.Next, validatedTarget);
        RequireState(
            Inspect(validatedBefore, validatedTarget),
            StableSetupHostRecoveryState.UpdateStaged,
            "verify restoration of a previous Setup host");
    }

    private static StableSetupHostPaths ValidatePaths(StableSetupHostPaths paths)
    {
        ArgumentNullException.ThrowIfNull(paths);
        string stable = ValidateAbsolutePath(paths.Stable, "stable Setup host path");
        string next = ValidateAbsolutePath(paths.Next, "next Setup host path");
        string previous = ValidateAbsolutePath(paths.Previous, "previous Setup host path");
        if (!string.Equals(Path.GetFileName(stable), "Baxy.Setup.exe", StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The stable Setup host destination must be named exactly Baxy.Setup.exe.");
        }

        string parent = RequireSafeParent(stable);
        if (!string.Equals(parent, RequireSafeParent(next), StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(parent, RequireSafeParent(previous), StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException(
                "Stable Setup transaction paths must be siblings in one safe directory.");
        }

        if (PathsEqual(stable, next) || PathsEqual(stable, previous) || PathsEqual(next, previous))
        {
            throw new InstallationSafetyException(
                "Stable Setup transaction paths must be distinct.");
        }

        return new StableSetupHostPaths(stable, next, previous);
    }

    private static string ValidateExistingSource(string path)
    {
        string fullPath = ValidateAbsolutePath(path, "Setup host candidate source");
        try
        {
            PathSafety.AssertRegularFile(fullPath);
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                "The Setup host candidate source is not an existing safe regular file.",
                exception);
        }

        return fullPath;
    }

    private static string ValidateAbsolutePath(string path, string field)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path) || path.Contains('\0'))
        {
            throw new InstallationSafetyException($"The {field} must be an absolute Windows path.");
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch (Exception exception)
        {
            throw new InstallationSafetyException($"The {field} is invalid.", exception);
        }

        if (Path.GetFileName(fullPath).Contains(':', StringComparison.Ordinal))
        {
            throw new InstallationSafetyException($"The {field} cannot address an alternate data stream.");
        }

        return fullPath;
    }

    private static string RequireSafeParent(string path)
    {
        string? parent = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(parent))
        {
            throw new InstallationSafetyException("A stable Setup transaction path has no parent directory.");
        }

        PathSafety.AssertExistingChainHasNoReparsePoint(parent);
        if (!Directory.Exists(parent))
        {
            throw new InstallationSafetyException(
                "The stable Setup transaction directory must already exist.");
        }

        FileAttributes attributes = File.GetAttributes(parent);
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != FileAttributes.Directory)
        {
            throw new InstallationSafetyException(
                "The stable Setup transaction directory is unsafe.");
        }

        return parent;
    }

    private static StableSetupHostIdentity ValidateIdentity(
        StableSetupHostIdentity identity,
        string field)
    {
        ArgumentNullException.ThrowIfNull(identity);
        if (identity.Bytes <= 0 || !IsLowercaseSha256(identity.Sha256))
        {
            throw new InstallationSafetyException(
                $"The {field} Setup host identity must contain a positive byte length and lowercase SHA-256.");
        }

        return identity;
    }

    private static void AssertDistinctIdentities(
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target)
    {
        if (before is not null && IdentityEquals(before, target))
        {
            throw new InstallationSafetyException(
                "Stable Setup update identities must differ; exact idempotence uses VerifyStableExact.");
        }
    }

    private static StableSetupHostIdentity ReadIdentity(string path)
    {
        PathSafety.AssertRegularFile(path);
        using FileStream stream = new(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            BufferSize,
            FileOptions.SequentialScan);
        long bytes = stream.Length;
        string sha256 = Convert.ToHexStringLower(SHA256.HashData(stream));
        if (stream.Length != bytes)
        {
            throw new InstallationSafetyException(
                "The Setup host byte length changed during verification.");
        }

        PathSafety.AssertRegularFile(path);
        return new StableSetupHostIdentity(sha256, bytes);
    }

    private static StableSetupHostArtifactState ClassifyArtifact(
        string path,
        StableSetupHostIdentity? before,
        StableSetupHostIdentity target)
    {
        if (!FileSystemEntryExists(path))
        {
            return StableSetupHostArtifactState.Missing;
        }

        StableSetupHostIdentity actual;
        try
        {
            actual = ReadIdentity(path);
        }
        catch (Exception exception) when (
            exception is InstallationSafetyException or IOException or UnauthorizedAccessException or CryptographicException)
        {
            return StableSetupHostArtifactState.Foreign;
        }

        if (IdentityEquals(actual, target))
        {
            return StableSetupHostArtifactState.Target;
        }

        return before is not null && IdentityEquals(actual, before)
            ? StableSetupHostArtifactState.Before
            : StableSetupHostArtifactState.Foreign;
    }

    private static StableSetupHostRecoveryState ClassifyRecoveryState(
        bool hasBefore,
        StableSetupHostArtifactState stable,
        StableSetupHostArtifactState next,
        StableSetupHostArtifactState previous)
    {
        if (stable == StableSetupHostArtifactState.Foreign ||
            next == StableSetupHostArtifactState.Foreign ||
            previous == StableSetupHostArtifactState.Foreign)
        {
            return StableSetupHostRecoveryState.Foreign;
        }

        if (!hasBefore &&
            stable == StableSetupHostArtifactState.Missing &&
            next == StableSetupHostArtifactState.Missing &&
            previous == StableSetupHostArtifactState.Missing)
        {
            return StableSetupHostRecoveryState.Empty;
        }

        if (!hasBefore &&
            stable == StableSetupHostArtifactState.Missing &&
            next == StableSetupHostArtifactState.Target &&
            previous == StableSetupHostArtifactState.Missing)
        {
            return StableSetupHostRecoveryState.FirstInstallStaged;
        }

        if (stable == StableSetupHostArtifactState.Target &&
            next == StableSetupHostArtifactState.Missing &&
            previous == StableSetupHostArtifactState.Missing)
        {
            return StableSetupHostRecoveryState.TargetPublished;
        }

        if (hasBefore &&
            stable == StableSetupHostArtifactState.Before &&
            next == StableSetupHostArtifactState.Missing &&
            previous == StableSetupHostArtifactState.Missing)
        {
            return StableSetupHostRecoveryState.BeforeStable;
        }

        if (hasBefore &&
            stable == StableSetupHostArtifactState.Before &&
            next == StableSetupHostArtifactState.Target &&
            previous == StableSetupHostArtifactState.Missing)
        {
            return StableSetupHostRecoveryState.UpdateStaged;
        }

        if (hasBefore &&
            stable == StableSetupHostArtifactState.Before &&
            next == StableSetupHostArtifactState.Target &&
            previous == StableSetupHostArtifactState.Before)
        {
            return StableSetupHostRecoveryState.UpdateBackupReady;
        }

        if (hasBefore &&
            stable == StableSetupHostArtifactState.Target &&
            next == StableSetupHostArtifactState.Missing &&
            previous == StableSetupHostArtifactState.Before)
        {
            return StableSetupHostRecoveryState.UpdateReplaced;
        }

        if (hasBefore &&
            stable == StableSetupHostArtifactState.Target &&
            next == StableSetupHostArtifactState.Target &&
            previous == StableSetupHostArtifactState.Before)
        {
            return StableSetupHostRecoveryState.RestoreBackupReady;
        }

        return StableSetupHostRecoveryState.Contradictory;
    }

    private static void RequireState(
        StableSetupHostInspection inspection,
        StableSetupHostRecoveryState expected,
        string operation)
    {
        if (inspection.State != expected)
        {
            throw UnexpectedState(operation, inspection);
        }
    }

    private static InstallationSafetyException UnexpectedState(
        string operation,
        StableSetupHostInspection inspection) =>
        new(
            $"Refusing to {operation} from {inspection.State} state " +
            $"(stable={inspection.Stable}, next={inspection.Next}, previous={inspection.Previous}).");

    private static void CopyExactCreateNew(
        string source,
        string destination,
        StableSetupHostIdentity expected,
        string description)
    {
        bool destinationCreated = false;
        bool copyCompleted = false;
        try
        {
            VerifyExact(source, expected);
            using FileStream input = new(
                source,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                BufferSize,
                FileOptions.SequentialScan);
            PathSafety.AssertRegularFile(source);
            if (input.Length != expected.Bytes)
            {
                throw new InstallationSafetyException(
                    $"The {description} source has an unexpected byte length.");
            }

            byte[] buffer = new byte[BufferSize];
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            using (FileStream output = new(destination, new FileStreamOptions
            {
                Mode = FileMode.CreateNew,
                Access = FileAccess.Write,
                Share = FileShare.None,
                BufferSize = BufferSize,
                Options = FileOptions.SequentialScan | FileOptions.WriteThrough,
            }))
            {
                destinationCreated = true;
                long copied = 0;
                while (true)
                {
                    int read = input.Read(buffer, 0, buffer.Length);
                    if (read == 0)
                    {
                        break;
                    }

                    copied = checked(copied + read);
                    if (copied > expected.Bytes)
                    {
                        throw new InstallationSafetyException(
                            $"The {description} source grew beyond its declared byte length.");
                    }

                    hash.AppendData(buffer.AsSpan(0, read));
                    output.Write(buffer, 0, read);
                }

                if (copied != expected.Bytes ||
                    !string.Equals(
                        Convert.ToHexStringLower(hash.GetHashAndReset()),
                        expected.Sha256,
                        StringComparison.Ordinal))
                {
                    throw new InstallationSafetyException(
                        $"The {description} source does not match its declared identity.");
                }

                output.Flush(flushToDisk: true);
                copyCompleted = true;
            }

            PathSafety.AssertRegularFile(source);
        }
        catch (Exception exception) when (!copyCompleted && destinationCreated)
        {
            DeleteNewlyCreatedFailedCopy(destination, description, exception);
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or CryptographicException or OverflowException)
        {
            throw new InstallationSafetyException(
                $"The {description} could not be copied safely.",
                exception);
        }

        VerifyExact(destination, expected);
    }

    private static void DeleteNewlyCreatedFailedCopy(
        string destination,
        string description,
        Exception original)
    {
        try
        {
            if (FileSystemEntryExists(destination))
            {
                PathSafety.AssertRegularFile(destination);
                File.Delete(destination);
            }
        }
        catch (Exception cleanupException)
        {
            throw new InstallationSafetyException(
                $"Copying the {description} failed and its newly created destination could not be removed safely.",
                new AggregateException(original, cleanupException));
        }
    }

    private static void MoveFileVerified(
        string source,
        string destination,
        uint flags,
        string operation)
    {
        if (!MoveFileEx(source, destination, flags))
        {
            throw new InstallationSafetyException(
                $"Windows could not {operation} with the reviewed durable move contract.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }
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

    private static bool IsLowercaseSha256(string? value) =>
        value is { Length: 64 } &&
        value.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f');

    private static bool IdentityEquals(
        StableSetupHostIdentity left,
        StableSetupHostIdentity right) =>
        left.Bytes == right.Bytes &&
        string.Equals(left.Sha256, right.Sha256, StringComparison.Ordinal);

    private static bool PathsEqual(string left, string right) =>
        string.Equals(left, right, StringComparison.OrdinalIgnoreCase);

    private void Checkpoint(StableSetupHostFaultPoint point) =>
        _faultInjector?.Checkpoint(point);

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "MoveFileExW",
        SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool MoveFileEx(
        string existingFileName,
        string newFileName,
        uint flags);
}
