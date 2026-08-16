using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Providers.Windows.Applications;

internal sealed record ApplicationInvocationState(
    string InvocationId,
    string ApplicationId,
    long IntentCreatedUtcTicks,
    string[] BaselineProcessKeys,
    ApplicationLaunchReceipt? Receipt);

internal sealed record ApplicationInvocationDocument(
    int Version,
    ApplicationInvocationState State,
    string Checksum);

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    WriteIndented = false)]
[JsonSerializable(typeof(ApplicationInvocationState))]
[JsonSerializable(typeof(ApplicationInvocationDocument))]
internal sealed partial class ApplicationInvocationJsonContext : JsonSerializerContext;

internal sealed class ApplicationStateCorruptException : Exception
{
    public ApplicationStateCorruptException(string message)
        : base(message)
    {
    }

    public ApplicationStateCorruptException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal sealed class ApplicationStateCapacityException : Exception
{
    public ApplicationStateCapacityException()
        : base("The durable application-open state capacity was reached.")
    {
    }
}

internal sealed class ApplicationInvocationStore
{
    private const int CurrentVersion = 1;
    private const long MaximumStateBytes = 1024 * 1024;
    private const int MaximumInvocationCount = 16_384;
    private const long MaximumTotalStateBytes = 64 * 1024 * 1024;
    private const int MaximumBaselineProcesses = 1024;
    private const int MaximumInvocationIdUtf8Bytes = 256;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, SemaphoreSlim> Coordinators =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string _stateDirectory;
    private readonly string _coordinatorPath;
    private readonly SemaphoreSlim _coordinator;

    public ApplicationInvocationStore(string stateDirectory)
    {
        _stateDirectory = SafePathPolicy.NormalizeAndCreatePrivateDirectory(stateDirectory);
        _coordinatorPath = GetContainedPath(_stateDirectory, ".app-open.lock");
        _coordinator = Coordinators.GetOrAdd(_stateDirectory, static _ => new SemaphoreSlim(1, 1));
    }

    public async ValueTask<IDisposable> AcquireAsync(CancellationToken cancellationToken)
    {
        EnsureStateRootSafe();
        await _coordinator.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            while (true)
            {
                cancellationToken.ThrowIfCancellationRequested();

                try
                {
                    FileStream fileLock = new(
                        _coordinatorPath,
                        FileMode.OpenOrCreate,
                        FileAccess.ReadWrite,
                        FileShare.None,
                        bufferSize: 1,
                        FileOptions.None);

                    EnsureStateRootSafe();
                    if ((File.GetAttributes(_coordinatorPath) & FileAttributes.ReparsePoint) != 0)
                    {
                        fileLock.Dispose();
                        throw new ApplicationStateCorruptException(
                            "The launch coordinator is a reparse point.");
                    }

                    return new CoordinatorLease(fileLock, _coordinator);
                }
                catch (IOException exception) when (
                    IsSharingViolation(exception)
                    && !cancellationToken.IsCancellationRequested)
                {
                    await Task.Delay(25, cancellationToken).ConfigureAwait(false);
                }
            }
        }
        catch
        {
            _coordinator.Release();
            throw;
        }
    }

    public ApplicationInvocationState? Load(string invocationId)
    {
        ValidateInvocationId(invocationId);
        EnsureStateRootSafe();
        string path = GetStatePath(invocationId);
        if (!File.Exists(path))
        {
            return null;
        }

        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
        {
            throw new ApplicationStateCorruptException("The invocation state is a reparse point.");
        }

        return ReadAndValidate(path, invocationId);
    }

    public void Save(ApplicationInvocationState state)
    {
        ValidateState(state, state.InvocationId);
        EnsureStateRootSafe();
        string targetPath = GetStatePath(state.InvocationId);
        string temporaryPath = GetContainedPath(
            _stateDirectory,
            $".app-open-{Guid.NewGuid():N}.tmp");
        string checksum = ComputeChecksum(state);
        ApplicationInvocationDocument document = new(CurrentVersion, state, checksum);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            document,
            ApplicationInvocationJsonContext.Default.ApplicationInvocationDocument);

        if (bytes.LongLength > MaximumStateBytes)
        {
            throw new IOException("The invocation state exceeds its size limit.");
        }

        EnsureCapacity(targetPath, bytes.LongLength);

        try
        {
            using (FileStream stream = new(
                temporaryPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                bufferSize: 4096,
                FileOptions.WriteThrough))
            {
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }

            _ = ReadAndValidate(temporaryPath, state.InvocationId);

            if (File.Exists(targetPath))
            {
                if ((File.GetAttributes(targetPath) & FileAttributes.ReparsePoint) != 0)
                {
                    throw new ApplicationStateCorruptException(
                        "The invocation state is a reparse point.");
                }

                global::Baxy.Providers.Windows.AtomicFileReplacement.Replace(
                    temporaryPath,
                    targetPath);
            }
            else
            {
                File.Move(temporaryPath, targetPath);
            }
        }
        finally
        {
            TryDeleteTemporaryFile(temporaryPath);
        }
    }

    public void EnsureCompletionCapacity(ApplicationInvocationState state)
    {
        ValidateState(state, state.InvocationId);
        EnsureStateRootSafe();
        EnsureCapacity(GetStatePath(state.InvocationId), MaximumStateBytes);
    }

    internal string GetStatePath(string invocationId)
    {
        ValidateInvocationId(invocationId);
        byte[] idBytes = StrictUtf8.GetBytes(invocationId);
        string fileName = $"{Convert.ToHexStringLower(SHA256.HashData(idBytes))}.json";
        return GetContainedPath(_stateDirectory, fileName);
    }

    private static string ComputeChecksum(ApplicationInvocationState state)
    {
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(
            state,
            ApplicationInvocationJsonContext.Default.ApplicationInvocationState);
        return Convert.ToHexStringLower(SHA256.HashData(payload));
    }

    private static void ValidateState(ApplicationInvocationState state, string invocationId)
    {
        ValidateInvocationId(invocationId);
        if (!string.Equals(state.InvocationId, invocationId, StringComparison.Ordinal)
            || !string.Equals(
                state.ApplicationId,
                ApplicationIds.Notepad,
                StringComparison.Ordinal)
            || state.IntentCreatedUtcTicks <= 0
            || state.IntentCreatedUtcTicks > DateTime.MaxValue.Ticks
            || state.BaselineProcessKeys is null
            || state.BaselineProcessKeys.Length > MaximumBaselineProcesses
            || state.BaselineProcessKeys.Any(static value =>
                !IsValidProcessKey(value))
            || state.BaselineProcessKeys.Distinct(StringComparer.Ordinal).Count()
                != state.BaselineProcessKeys.Length)
        {
            throw new ApplicationStateCorruptException("The invocation state is invalid.");
        }

        ApplicationLaunchReceipt? receipt = state.Receipt;
        if (receipt is not null
            && (!string.Equals(receipt.InvocationId, state.InvocationId, StringComparison.Ordinal)
                || !string.Equals(
                    receipt.ApplicationId,
                    state.ApplicationId,
                    StringComparison.Ordinal)
                || !IsValidReceipt(receipt)))
        {
            throw new ApplicationStateCorruptException(
                "The persisted receipt does not match its invocation.");
        }
    }

    private void EnsureCapacity(string targetPath, long replacementBytes)
    {
        switch (InvocationStateCapacityPolicy.Evaluate(
            _stateDirectory,
            targetPath,
            replacementBytes,
            MaximumInvocationCount,
            MaximumTotalStateBytes))
        {
            case InvocationStateCapacityViolation.ReparsePoint:
                throw new ApplicationStateCorruptException(
                    "A durable invocation entry is a reparse point.");
            case InvocationStateCapacityViolation.Capacity:
                throw new ApplicationStateCapacityException();
            case InvocationStateCapacityViolation.None:
                return;
            default:
                throw new UnreachableException();
        }
    }

    private void EnsureStateRootSafe()
    {
        if (!Directory.Exists(_stateDirectory)
            || !SafePathPolicy.IsExistingPathWithoutReparse(_stateDirectory))
        {
            throw new ApplicationStateCorruptException(
                "The durable state directory is no longer trusted.");
        }
    }

    private static bool IsSharingViolation(IOException exception)
    {
        int nativeError = exception.HResult & 0xFFFF;
        return nativeError is 32 or 33;
    }

    private static bool IsValidProcessKey(string value)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > 64)
        {
            return false;
        }

        string[] fields = value.Split(':');
        return fields.Length == 2
            && int.TryParse(
                fields[0],
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out int processId)
            && processId > 0
            && long.TryParse(
                fields[1],
                NumberStyles.None,
                CultureInfo.InvariantCulture,
                out long creationTime)
            && creationTime > 0
            && creationTime <= DateTime.MaxValue.Ticks;
    }

    private static bool IsValidReceipt(ApplicationLaunchReceipt receipt)
    {
        if (receipt.LaunchIssued && receipt.ReusedExisting
            || receipt.ProcessId is <= 0
            || receipt.ProcessCreationTimeUtcTicks is long creationTime
                && (creationTime <= 0 || creationTime > DateTime.MaxValue.Ticks)
            || receipt.ExecutablePath is { Length: > 32_768 }
            || receipt.PackageFamilyName is { Length: > 256 }
            || receipt.PackageFullName is { Length: > 256 }
            || receipt.WindowHandle == 0
            || !IsKnownErrorCode(receipt.ErrorCode))
        {
            return false;
        }

        bool hasProcess = receipt.ProcessId.HasValue;
        bool hasCreationTime = receipt.ProcessCreationTimeUtcTicks.HasValue;
        bool hasPath = !string.IsNullOrWhiteSpace(receipt.ExecutablePath);
        bool hasFamily = !string.IsNullOrWhiteSpace(receipt.PackageFamilyName);
        bool hasFullName = !string.IsNullOrWhiteSpace(receipt.PackageFullName);
        if (hasProcess != hasCreationTime
            || hasProcess != hasPath
            || hasFamily != hasFullName
            || (hasProcess && receipt.LaunchIssued == receipt.ReusedExisting)
            || (!hasProcess && receipt.ReusedExisting)
            || (!hasProcess && receipt.WindowHandle.HasValue)
            || (hasPath && !Path.IsPathFullyQualified(receipt.ExecutablePath!)))
        {
            return false;
        }

        if (hasFamily
            && (!string.Equals(
                    receipt.PackageFamilyName,
                    NotepadIdentityPolicy.PackageFamilyName,
                    StringComparison.Ordinal)
                || receipt.PackageFullName!.IndexOfAny(['\\', '/']) >= 0
                || !receipt.PackageFullName.StartsWith(
                    NotepadIdentityPolicy.PackageNamePrefix,
                    StringComparison.Ordinal)
                || !receipt.PackageFullName.EndsWith(
                    $"_{NotepadIdentityPolicy.MicrosoftPublisherId}",
                    StringComparison.Ordinal)))
        {
            return false;
        }

        return true;
    }

    private static bool IsKnownErrorCode(string? errorCode) =>
        errorCode is null
            or ApplicationOpenErrorCodes.ApplicationNotFound
            or ApplicationOpenErrorCodes.InventoryFailed
            or ApplicationOpenErrorCodes.LaunchFailed
            or ApplicationOpenErrorCodes.VerificationFailed
            or ApplicationOpenErrorCodes.StateCorrupt
            or ApplicationOpenErrorCodes.StateCapacityReached
            or ApplicationOpenErrorCodes.StateUnavailable;

    private static void ValidateInvocationId(string invocationId)
    {
        if (string.IsNullOrWhiteSpace(invocationId)
            || !Guid.TryParseExact(invocationId, "D", out Guid parsed)
            || !string.Equals(parsed.ToString("D"), invocationId, StringComparison.Ordinal)
            || StrictUtf8.GetByteCount(invocationId) > MaximumInvocationIdUtf8Bytes
            || invocationId.Any(char.IsControl))
        {
            throw new ArgumentException("The invocation id is invalid.", nameof(invocationId));
        }
    }

    private static string GetContainedPath(string directory, string fileName)
    {
        string path = Path.GetFullPath(Path.Combine(directory, fileName));
        string relative = Path.GetRelativePath(directory, path);
        if (Path.IsPathRooted(relative)
            || relative.Equals("..", StringComparison.Ordinal)
            || relative.StartsWith($"..{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
        {
            throw new IOException("The state path escapes its private directory.");
        }

        return path;
    }

    private static void TryDeleteTemporaryFile(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static ApplicationInvocationState ReadAndValidate(
        string path,
        string invocationId)
    {
        try
        {
            using FileStream stream = new(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                bufferSize: 4096,
                FileOptions.SequentialScan);
            if (stream.Length is <= 0 or > MaximumStateBytes)
            {
                throw new ApplicationStateCorruptException(
                    "The invocation state has an invalid length.");
            }

            byte[] bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            stream.ReadExactly(bytes);
            ApplicationInvocationDocument? document = JsonSerializer.Deserialize(
                bytes,
                ApplicationInvocationJsonContext.Default.ApplicationInvocationDocument);

            if (document is null
                || document.Version != CurrentVersion
                || document.State is null)
            {
                throw new ApplicationStateCorruptException(
                    "The invocation state version is invalid.");
            }

            ValidateState(document.State, invocationId);
            string expectedChecksum = ComputeChecksum(document.State);
            byte[] expectedBytes = StrictUtf8.GetBytes(expectedChecksum);
            byte[] actualBytes = StrictUtf8.GetBytes(document.Checksum ?? string.Empty);
            if (expectedBytes.Length != actualBytes.Length
                || !CryptographicOperations.FixedTimeEquals(expectedBytes, actualBytes))
            {
                throw new ApplicationStateCorruptException(
                    "The invocation state checksum is invalid.");
            }

            return document.State;
        }
        catch (ApplicationStateCorruptException)
        {
            throw;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or JsonException
            or DecoderFallbackException
            or ArgumentException)
        {
            throw new ApplicationStateCorruptException(
                "The invocation state cannot be read safely.",
                exception);
        }
    }

    private sealed class CoordinatorLease(
        FileStream fileLock,
        SemaphoreSlim coordinator) : IDisposable
    {
        private FileStream? _fileLock = fileLock;
        private SemaphoreSlim? _coordinator = coordinator;

        public void Dispose()
        {
            FileStream? file = Interlocked.Exchange(ref _fileLock, null);
            SemaphoreSlim? gate = Interlocked.Exchange(ref _coordinator, null);
            file?.Dispose();
            gate?.Release();
        }
    }
}
