using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Providers.Windows.Audio;

internal sealed record AudioInvocationState(
    string InvocationId,
    string Operation,
    string TargetId,
    string EndpointIdHash,
    int? RequestedLevel,
    bool? RequestedState,
    AudioEndpointState Baseline,
    float BaselineVolumeScalar,
    long IntentCreatedUtcTicks,
    AudioControlReceipt? Receipt,
    float? FinalVolumeScalar);

internal sealed record AudioInvocationDocument(
    int Version,
    AudioInvocationState State,
    string Checksum);

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    WriteIndented = false)]
[JsonSerializable(typeof(AudioEndpointState))]
[JsonSerializable(typeof(AudioControlReceipt))]
[JsonSerializable(typeof(AudioInvocationState))]
[JsonSerializable(typeof(AudioInvocationDocument))]
internal sealed partial class AudioInvocationJsonContext : JsonSerializerContext;

internal sealed class AudioStateCorruptException : Exception
{
    public AudioStateCorruptException(string message)
        : base(message)
    {
    }

    public AudioStateCorruptException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal sealed class AudioStateCapacityException : Exception
{
    public AudioStateCapacityException()
        : base("The durable audio state capacity was reached.")
    {
    }
}

internal sealed class AudioInvocationStore
{
    private const int CurrentVersion = 1;
    private const long MaximumStateBytes = 64 * 1024;
    private const int MaximumInvocationCount = 16_384;
    private const long MaximumTotalStateBytes = 64 * 1024 * 1024;
    private const int MaximumInvocationIdUtf8Bytes = 256;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    private readonly string _stateDirectory;

    public AudioInvocationStore(string stateDirectory)
    {
        RejectAlternateDataStream(stateDirectory);
        _stateDirectory = SafePathPolicy.NormalizeAndCreatePrivateDirectory(stateDirectory);
    }

    public AudioInvocationState? Load(string invocationId)
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
            throw new AudioStateCorruptException("The invocation state is a reparse point.");
        }

        return ReadAndValidate(path, invocationId);
    }

    public void Save(AudioInvocationState state)
    {
        ValidateState(state, state.InvocationId);
        EnsureStateRootSafe();
        string targetPath = GetStatePath(state.InvocationId);
        string temporaryPath = GetContainedPath(
            _stateDirectory,
            $".audio-{Guid.NewGuid():N}.tmp");
        string checksum = ComputeChecksum(state);
        AudioInvocationDocument document = new(CurrentVersion, state, checksum);
        byte[] bytes = JsonSerializer.SerializeToUtf8Bytes(
            document,
            AudioInvocationJsonContext.Default.AudioInvocationDocument);
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
                    throw new AudioStateCorruptException(
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

    public void EnsureCompletionCapacity(AudioInvocationState state)
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

    private static string ComputeChecksum(AudioInvocationState state)
    {
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(
            state,
            AudioInvocationJsonContext.Default.AudioInvocationState);
        return Convert.ToHexStringLower(SHA256.HashData(payload));
    }

    private static void ValidateState(AudioInvocationState state, string invocationId)
    {
        ValidateInvocationId(invocationId);
        if (!string.Equals(state.InvocationId, invocationId, StringComparison.Ordinal)
            || !IsKnownOperation(state.Operation)
            || !string.Equals(
                state.TargetId,
                AudioTargetIds.DefaultOutput,
                StringComparison.Ordinal)
            || !IsValidHash(state.EndpointIdHash)
            || !IsValidRequest(state.Operation, state.RequestedLevel, state.RequestedState)
            || !IsValidEndpointState(state.Baseline)
            || !IsValidScalar(state.BaselineVolumeScalar)
            || PercentFromScalar(state.BaselineVolumeScalar) != state.Baseline.VolumePercent
            || state.IntentCreatedUtcTicks <= 0
            || state.IntentCreatedUtcTicks > DateTime.MaxValue.Ticks
            || state.FinalVolumeScalar is float finalScalar && !IsValidScalar(finalScalar))
        {
            throw new AudioStateCorruptException("The invocation state is invalid.");
        }

        AudioControlReceipt? receipt = state.Receipt;
        if (receipt is null)
        {
            if (state.FinalVolumeScalar.HasValue)
            {
                throw new AudioStateCorruptException("An intent cannot contain a final scalar.");
            }

            return;
        }

        if (!string.Equals(receipt.InvocationId, state.InvocationId, StringComparison.Ordinal)
            || !string.Equals(receipt.Operation, state.Operation, StringComparison.Ordinal)
            || !string.Equals(receipt.TargetId, state.TargetId, StringComparison.Ordinal)
            || !string.Equals(
                receipt.EndpointIdHash,
                state.EndpointIdHash,
                StringComparison.Ordinal)
            || receipt.RequestedLevel != state.RequestedLevel
            || receipt.RequestedState != state.RequestedState
            || receipt.Baseline != state.Baseline
            || !IsValidReceipt(
                receipt,
                state.BaselineVolumeScalar,
                state.FinalVolumeScalar))
        {
            throw new AudioStateCorruptException(
                "The persisted receipt does not match its invocation.");
        }
    }

    private static bool IsValidReceipt(
        AudioControlReceipt receipt,
        float baselineVolumeScalar,
        float? finalVolumeScalar)
    {
        if (receipt.Retryable
            || receipt.Applied && receipt.Reconciled
            || receipt.Reconciled && !receipt.Verified
            || receipt.Verified != (receipt.ErrorCode is null)
            || !IsKnownErrorCode(receipt.ErrorCode)
            || receipt.EndpointIdHash is null
            || receipt.Baseline is null
            || !IsValidEndpointState(receipt.Baseline))
        {
            return false;
        }

        if (receipt.Final is null)
        {
            return !receipt.Verified
                && !receipt.Reconciled
                && !finalVolumeScalar.HasValue
                && receipt.ErrorCode == AudioControlErrorCodes.EndpointChanged;
        }

        if (!IsValidEndpointState(receipt.Final)
            || finalVolumeScalar is not float scalar
            || PercentFromScalar(scalar) != receipt.Final.VolumePercent)
        {
            return false;
        }

        if (!receipt.Verified)
        {
            return true;
        }

        return receipt.Operation switch
        {
            AudioOperationIds.Volume => receipt.RequestedLevel is int requested
                && Math.Abs(receipt.Final.VolumePercent - requested) <= 2
                && receipt.Final.Muted == receipt.Baseline.Muted,
            AudioOperationIds.Mute => receipt.RequestedState is bool requested
                && receipt.Final.Muted == requested
                && ScalarEquals(scalar, baselineVolumeScalar),
            _ => false,
        };
    }

    private static bool ScalarEquals(float left, float right) =>
        Math.Abs(left - right) <= 0.0001f;

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
                throw new AudioStateCorruptException(
                    "A durable invocation entry is a reparse point.");
            case InvocationStateCapacityViolation.Capacity:
                throw new AudioStateCapacityException();
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
            throw new AudioStateCorruptException(
                "The durable state directory is no longer trusted.");
        }
    }

    private static AudioInvocationState ReadAndValidate(string path, string invocationId)
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
                throw new AudioStateCorruptException(
                    "The invocation state has an invalid length.");
            }

            byte[] bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            stream.ReadExactly(bytes);
            AudioInvocationDocument? document = JsonSerializer.Deserialize(
                bytes,
                AudioInvocationJsonContext.Default.AudioInvocationDocument);
            if (document is null
                || document.Version != CurrentVersion
                || document.State is null)
            {
                throw new AudioStateCorruptException(
                    "The invocation state version is invalid.");
            }

            ValidateState(document.State, invocationId);
            byte[] expected = StrictUtf8.GetBytes(ComputeChecksum(document.State));
            byte[] actual = StrictUtf8.GetBytes(document.Checksum ?? string.Empty);
            if (expected.Length != actual.Length
                || !CryptographicOperations.FixedTimeEquals(expected, actual))
            {
                throw new AudioStateCorruptException(
                    "The invocation state checksum is invalid.");
            }

            return document.State;
        }
        catch (AudioStateCorruptException)
        {
            throw;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or JsonException
            or DecoderFallbackException
            or ArgumentException
            or OverflowException)
        {
            throw new AudioStateCorruptException(
                "The invocation state cannot be read safely.",
                exception);
        }
    }

    private static bool IsValidRequest(
        string? operation,
        int? requestedLevel,
        bool? requestedState) => operation switch
        {
            AudioOperationIds.Volume => requestedLevel is >= 0 and <= 100
                && requestedState is null,
            AudioOperationIds.Mute => requestedLevel is null && requestedState.HasValue,
            _ => false,
        };

    private static bool IsKnownOperation(string? operation) =>
        operation is AudioOperationIds.Volume or AudioOperationIds.Mute;

    private static bool IsKnownErrorCode(string? errorCode) => errorCode is null
        or AudioControlErrorCodes.NoDefaultOutput
        or AudioControlErrorCodes.AudioServiceUnavailable
        or AudioControlErrorCodes.EndpointUnavailable
        or AudioControlErrorCodes.EndpointChanged
        or AudioControlErrorCodes.OperationFailed
        or AudioControlErrorCodes.VerificationFailed
        or AudioControlErrorCodes.EffectUncertain
        or AudioControlErrorCodes.StateCapacityReached
        or AudioControlErrorCodes.StateCorrupt
        or AudioControlErrorCodes.StateUnavailable;

    private static bool IsValidHash(string? value) =>
        value is { Length: 64 }
        && value.All(static character => character is >= '0' and <= '9'
            or >= 'a' and <= 'f');

    private static bool IsValidEndpointState(AudioEndpointState? state) =>
        state is not null && state.VolumePercent is >= 0 and <= 100;

    private static bool IsValidScalar(float value) =>
        float.IsFinite(value) && value is >= 0f and <= 1f;

    private static int PercentFromScalar(float scalar) =>
        Math.Clamp(
            (int)Math.Round(scalar * 100f, MidpointRounding.AwayFromZero),
            0,
            100);

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

    private static void RejectAlternateDataStream(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        string fullPath = Path.GetFullPath(path);
        if (fullPath.StartsWith(@"\\", StringComparison.Ordinal))
        {
            throw new IOException("Network paths are not valid state roots.");
        }

        string root = Path.GetPathRoot(fullPath) ?? string.Empty;
        if (fullPath.AsSpan(root.Length).Contains(':'))
        {
            throw new IOException("Alternate data streams are not valid state roots.");
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
}
