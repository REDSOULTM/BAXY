using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Providers.Windows.Audio;

public sealed class WindowsAudioControlProvider : IAudioControlProvider
{
    internal const int VolumeTolerancePoints = 2;
    private const float ScalarPreservationTolerance = 0.0001f;
    private const int MaximumInvocationIdUtf8Bytes = 256;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    private readonly IWindowsAudioPlatform _platform;
    private readonly AudioInvocationStore _store;
    private readonly IAudioOperationLock _operationLock;
    private readonly Action? _afterIntentPersisted;
    private readonly Action? _afterEffectIssued;

    public WindowsAudioControlProvider()
        : this(GetDefaultStateDirectory())
    {
    }

    public WindowsAudioControlProvider(string stateDirectory)
        : this(
            new WindowsCoreAudioPlatform(),
            new AudioInvocationStore(stateDirectory),
            new NamedAudioOperationLock(),
            afterIntentPersisted: null,
            afterEffectIssued: null)
    {
    }

    internal WindowsAudioControlProvider(
        IWindowsAudioPlatform platform,
        AudioInvocationStore store,
        IAudioOperationLock operationLock,
        Action? afterIntentPersisted = null,
        Action? afterEffectIssued = null)
    {
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _store = store ?? throw new ArgumentNullException(nameof(store));
        _operationLock = operationLock ?? throw new ArgumentNullException(nameof(operationLock));
        _afterIntentPersisted = afterIntentPersisted;
        _afterEffectIssued = afterEffectIssued;
    }

    public ValueTask<AudioStatusReceipt> GetStatusAsync(
        AudioStatusQuery query,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);
        if (!IsValidInvocationId(query.InvocationId))
        {
            return ValueTask.FromResult(StatusErrorReceipt(
                query.InvocationId ?? string.Empty,
                AudioControlErrorCodes.InvalidInvocation));
        }

        cancellationToken.ThrowIfCancellationRequested();
        IDisposable? operationLease;
        try
        {
            operationLease = _operationLock.TryAcquire(cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception) when (IsExpectedLockFailure(exception))
        {
            return ValueTask.FromResult(StatusErrorReceipt(
                query.InvocationId,
                AudioControlErrorCodes.AudioBusy));
        }

        if (operationLease is null)
        {
            return ValueTask.FromResult(StatusErrorReceipt(
                query.InvocationId,
                AudioControlErrorCodes.AudioBusy));
        }

        using (operationLease)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                using IWindowsAudioEndpoint endpoint = _platform.OpenDefaultOutput();
                AudioObservation observation = Observe(endpoint);
                return ValueTask.FromResult(new AudioStatusReceipt(
                    query.InvocationId,
                    AudioOperationIds.Status,
                    AudioTargetIds.DefaultOutput,
                    observation.EndpointIdHash,
                    observation.State,
                    Verified: true,
                    ErrorCode: null));
            }
            catch (AudioPlatformException exception)
            {
                return ValueTask.FromResult(StatusErrorReceipt(
                    query.InvocationId,
                    exception.ErrorCode));
            }
            catch (Exception exception) when (IsExpectedPlatformFailure(exception))
            {
                return ValueTask.FromResult(StatusErrorReceipt(
                    query.InvocationId,
                    AudioControlErrorCodes.EndpointUnavailable));
            }
        }
    }

    public ValueTask<AudioControlReceipt> SetVolumeAsync(
        AudioVolumeCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);
        if (!IsValidInvocationId(command.InvocationId))
        {
            return ValueTask.FromResult(ErrorReceipt(
                command.InvocationId ?? string.Empty,
                AudioOperationIds.Volume,
                command.Level,
                requestedState: null,
                AudioControlErrorCodes.InvalidInvocation));
        }

        if (command.Level is < 0 or > 100)
        {
            return ValueTask.FromResult(ErrorReceipt(
                command.InvocationId,
                AudioOperationIds.Volume,
                command.Level,
                requestedState: null,
                AudioControlErrorCodes.InvalidLevel));
        }

        return ValueTask.FromResult(Apply(
            new AudioMutation(
                command.InvocationId,
                AudioOperationIds.Volume,
                command.Level,
                RequestedState: null),
            cancellationToken));
    }

    public ValueTask<AudioControlReceipt> SetMuteAsync(
        AudioMuteCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);
        if (!IsValidInvocationId(command.InvocationId))
        {
            return ValueTask.FromResult(ErrorReceipt(
                command.InvocationId ?? string.Empty,
                AudioOperationIds.Mute,
                requestedLevel: null,
                command.State,
                AudioControlErrorCodes.InvalidInvocation));
        }

        return ValueTask.FromResult(Apply(
            new AudioMutation(
                command.InvocationId,
                AudioOperationIds.Mute,
                RequestedLevel: null,
                command.State),
            cancellationToken));
    }

    private AudioControlReceipt Apply(
        AudioMutation mutation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        IDisposable? operationLease;
        try
        {
            operationLease = _operationLock.TryAcquire(cancellationToken);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (Exception exception) when (IsExpectedLockFailure(exception))
        {
            return ErrorReceipt(mutation, AudioControlErrorCodes.AudioBusy);
        }

        if (operationLease is null)
        {
            return ErrorReceipt(mutation, AudioControlErrorCodes.AudioBusy);
        }

        using (operationLease)
        {
            cancellationToken.ThrowIfCancellationRequested();
            AudioInvocationState? state;
            try
            {
                state = _store.Load(mutation.InvocationId);
            }
            catch (AudioStateCorruptException)
            {
                return ErrorReceipt(mutation, AudioControlErrorCodes.StateCorrupt);
            }
            catch (Exception exception) when (IsExpectedStateFailure(exception))
            {
                return ErrorReceipt(mutation, AudioControlErrorCodes.StateUnavailable);
            }

            if (state is not null && !Matches(state, mutation))
            {
                return ErrorReceipt(mutation, AudioControlErrorCodes.StateCorrupt);
            }

            if (state?.Receipt is { } priorReceipt)
            {
                return priorReceipt;
            }

            if (state is not null)
            {
                return ReconcileIntent(state, mutation);
            }

            return ApplyNewIntent(mutation);
        }
    }

    private AudioControlReceipt ApplyNewIntent(AudioMutation mutation)
    {
        AudioObservation baseline;
        try
        {
            using IWindowsAudioEndpoint endpoint = _platform.OpenDefaultOutput();
            baseline = Observe(endpoint);
        }
        catch (AudioPlatformException exception)
        {
            return ErrorReceipt(mutation, exception.ErrorCode);
        }
        catch (Exception exception) when (IsExpectedPlatformFailure(exception))
        {
            return ErrorReceipt(mutation, AudioControlErrorCodes.EndpointUnavailable);
        }

        AudioInvocationState intent = new(
            mutation.InvocationId,
            mutation.Operation,
            AudioTargetIds.DefaultOutput,
            baseline.EndpointIdHash,
            mutation.RequestedLevel,
            mutation.RequestedState,
            baseline.State,
            baseline.VolumeScalar,
            _platform.UtcNow.UtcTicks,
            Receipt: null,
            FinalVolumeScalar: null);
        string? stateError = TryPersistIntent(intent);
        if (stateError is not null)
        {
            return ReceiptFromIntent(intent, stateError);
        }

        _afterIntentPersisted?.Invoke();
        return ApplyPreparedIntent(intent, mutation);
    }

    private AudioControlReceipt ApplyPreparedIntent(
        AudioInvocationState intent,
        AudioMutation mutation)
    {
        try
        {
            using IWindowsAudioEndpoint endpoint = _platform.OpenDefaultOutput();
            AudioObservation preflight = Observe(endpoint);
            if (!string.Equals(
                    preflight.EndpointIdHash,
                    intent.EndpointIdHash,
                    StringComparison.Ordinal))
            {
                AudioControlReceipt changed = ReceiptFromIntent(
                    intent,
                    AudioControlErrorCodes.EndpointChanged);
                return PersistReceipt(intent, finalVolumeScalar: null, changed);
            }

            AudioObservation baseline = Baseline(intent);
            if (!PreservesOtherDimension(mutation, baseline, preflight))
            {
                AudioControlReceipt uncertain = ReceiptFromIntent(
                    intent,
                    AudioControlErrorCodes.EffectUncertain,
                    preflight);
                return PersistReceipt(intent, preflight.VolumeScalar, uncertain);
            }

            if (SatisfiesTargetBeforeEffect(mutation, preflight))
            {
                bool unchanged = SameObservation(baseline, preflight);
                AudioControlReceipt satisfied = VerifiedReceipt(
                    intent,
                    preflight,
                    applied: false,
                    reconciled: !unchanged);
                return PersistReceipt(intent, preflight.VolumeScalar, satisfied);
            }

            if (!TargetDimensionUnchanged(mutation, baseline, preflight))
            {
                AudioControlReceipt uncertain = ReceiptFromIntent(
                    intent,
                    AudioControlErrorCodes.EffectUncertain,
                    preflight);
                return PersistReceipt(intent, preflight.VolumeScalar, uncertain);
            }

            string? operationError = null;
            try
            {
                Guid eventContext = CreateEventContext(mutation.InvocationId);
                if (mutation.Operation == AudioOperationIds.Volume)
                {
                    endpoint.SetVolumeScalar(mutation.RequestedLevel!.Value / 100f, eventContext);
                }
                else
                {
                    endpoint.SetMuted(mutation.RequestedState!.Value, eventContext);
                }
            }
            catch (AudioPlatformException exception)
            {
                operationError = exception.ErrorCode;
            }
            catch (Exception exception) when (IsExpectedPlatformFailure(exception))
            {
                operationError = AudioControlErrorCodes.OperationFailed;
            }

            if (operationError is null)
            {
                _afterEffectIssued?.Invoke();
            }

            return VerifyAfterEffect(intent, mutation, operationError);
        }
        catch (AudioPlatformException exception)
        {
            return ReceiptFromIntent(intent, exception.ErrorCode, retryable: true);
        }
        catch (Exception exception) when (IsExpectedPlatformFailure(exception))
        {
            return ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EndpointUnavailable,
                retryable: true);
        }
    }

    private AudioControlReceipt VerifyAfterEffect(
        AudioInvocationState intent,
        AudioMutation mutation,
        string? operationError)
    {
        AudioObservation final;
        try
        {
            using IWindowsAudioEndpoint verifier = _platform.OpenDefaultOutput();
            final = Observe(verifier);
        }
        catch (AudioPlatformException)
        {
            return ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EffectUncertain,
                applied: true,
                retryable: true);
        }
        catch (Exception exception) when (IsExpectedPlatformFailure(exception))
        {
            return ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EffectUncertain,
                applied: true,
                retryable: true);
        }

        if (!string.Equals(
                final.EndpointIdHash,
                intent.EndpointIdHash,
                StringComparison.Ordinal))
        {
            AudioControlReceipt changed = ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EndpointChanged,
                applied: true);
            return PersistReceipt(intent, finalVolumeScalar: null, changed);
        }

        AudioControlReceipt receipt;
        if (SatisfiesTargetAfterEffect(mutation, final)
            && PreservesOtherDimension(mutation, Baseline(intent), final))
        {
            bool setterConfirmed = operationError is null;
            receipt = VerifiedReceipt(
                intent,
                final,
                applied: setterConfirmed,
                reconciled: !setterConfirmed);
        }
        else
        {
            receipt = ReceiptFromIntent(
                intent,
                operationError ?? AudioControlErrorCodes.VerificationFailed,
                final,
                applied: true);
        }

        return PersistReceipt(intent, final.VolumeScalar, receipt);
    }

    private AudioControlReceipt ReconcileIntent(
        AudioInvocationState intent,
        AudioMutation mutation)
    {
        AudioObservation current;
        try
        {
            using IWindowsAudioEndpoint endpoint = _platform.OpenDefaultOutput();
            current = Observe(endpoint);
        }
        catch (AudioPlatformException exception)
        {
            return ReceiptFromIntent(intent, exception.ErrorCode, retryable: true);
        }
        catch (Exception exception) when (IsExpectedPlatformFailure(exception))
        {
            return ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EndpointUnavailable,
                retryable: true);
        }

        if (!string.Equals(
                current.EndpointIdHash,
                intent.EndpointIdHash,
                StringComparison.Ordinal))
        {
            AudioControlReceipt changed = ReceiptFromIntent(
                intent,
                AudioControlErrorCodes.EndpointChanged);
            return PersistReceipt(intent, finalVolumeScalar: null, changed);
        }

        AudioControlReceipt receipt = SatisfiesTargetAfterEffect(mutation, current)
            && PreservesOtherDimension(mutation, Baseline(intent), current)
                ? VerifiedReceipt(
                    intent,
                    current,
                    applied: false,
                    reconciled: true)
                : ReceiptFromIntent(
                    intent,
                    AudioControlErrorCodes.EffectUncertain,
                    current);
        return PersistReceipt(intent, current.VolumeScalar, receipt);
    }

    private string? TryPersistIntent(AudioInvocationState intent)
    {
        try
        {
            _store.EnsureCompletionCapacity(intent);
            _store.Save(intent);
            return null;
        }
        catch (AudioStateCapacityException)
        {
            return AudioControlErrorCodes.StateCapacityReached;
        }
        catch (AudioStateCorruptException)
        {
            return AudioControlErrorCodes.StateCorrupt;
        }
        catch (Exception exception) when (IsExpectedStateFailure(exception))
        {
            return AudioControlErrorCodes.StateUnavailable;
        }
    }

    private AudioControlReceipt PersistReceipt(
        AudioInvocationState intent,
        float? finalVolumeScalar,
        AudioControlReceipt receipt)
    {
        try
        {
            _store.Save(intent with
            {
                Receipt = receipt,
                FinalVolumeScalar = finalVolumeScalar,
            });
            return receipt;
        }
        catch (AudioStateCapacityException)
        {
            return PersistenceFailure(receipt, AudioControlErrorCodes.StateCapacityReached);
        }
        catch (AudioStateCorruptException)
        {
            return PersistenceFailure(receipt, AudioControlErrorCodes.StateCorrupt);
        }
        catch (Exception exception) when (IsExpectedStateFailure(exception))
        {
            return PersistenceFailure(receipt, AudioControlErrorCodes.StateUnavailable);
        }
    }

    private static AudioControlReceipt PersistenceFailure(
        AudioControlReceipt receipt,
        string errorCode) => receipt with
        {
            Reconciled = false,
            Verified = false,
            ErrorCode = errorCode,
            Retryable = true,
        };

    private static AudioControlReceipt VerifiedReceipt(
        AudioInvocationState intent,
        AudioObservation final,
        bool applied,
        bool reconciled) => new(
            intent.InvocationId,
            intent.Operation,
            intent.TargetId,
            intent.EndpointIdHash,
            intent.RequestedLevel,
            intent.RequestedState,
            intent.Baseline,
            final.State,
            applied,
            reconciled,
            Verified: true,
            ErrorCode: null);

    private static AudioControlReceipt ReceiptFromIntent(
        AudioInvocationState intent,
        string errorCode,
        AudioObservation? final = null,
        bool applied = false,
        bool retryable = false) => new(
            intent.InvocationId,
            intent.Operation,
            intent.TargetId,
            intent.EndpointIdHash,
            intent.RequestedLevel,
            intent.RequestedState,
            intent.Baseline,
            final?.State,
            applied,
            Reconciled: false,
            Verified: false,
            errorCode)
        {
            Retryable = retryable,
        };

    private static AudioControlReceipt ErrorReceipt(
        AudioMutation mutation,
        string errorCode) => ErrorReceipt(
            mutation.InvocationId,
            mutation.Operation,
            mutation.RequestedLevel,
            mutation.RequestedState,
            errorCode);

    private static AudioControlReceipt ErrorReceipt(
        string invocationId,
        string operation,
        int? requestedLevel,
        bool? requestedState,
        string errorCode) => new(
            invocationId,
            operation,
            AudioTargetIds.DefaultOutput,
            EndpointIdHash: null,
            requestedLevel,
            requestedState,
            Baseline: null,
            Final: null,
            Applied: false,
            Reconciled: false,
            Verified: false,
            errorCode);

    private static AudioStatusReceipt StatusErrorReceipt(
        string invocationId,
        string errorCode) => new(
            invocationId,
            AudioOperationIds.Status,
            AudioTargetIds.DefaultOutput,
            EndpointIdHash: null,
            State: null,
            Verified: false,
            errorCode);

    private static AudioObservation Observe(IWindowsAudioEndpoint endpoint)
    {
        float scalar = endpoint.ReadVolumeScalar();
        if (!float.IsFinite(scalar) || scalar is < 0f or > 1f)
        {
            throw new AudioPlatformException(AudioControlErrorCodes.EndpointUnavailable);
        }

        bool muted = endpoint.ReadMuted();
        string hash = AudioEndpointIdentity.Hash(endpoint.EndpointId);
        return new AudioObservation(
            hash,
            scalar,
            new AudioEndpointState(PercentFromScalar(scalar), muted));
    }

    private static AudioObservation Baseline(AudioInvocationState intent) =>
        new(intent.EndpointIdHash, intent.BaselineVolumeScalar, intent.Baseline);

    private static bool SatisfiesTargetBeforeEffect(
        AudioMutation mutation,
        AudioObservation observation) => mutation.Operation switch
        {
            // An absolute request may skip the setter only when the public,
            // independently observed percentage is already exact. Hardware
            // tolerance belongs to the postread, not to no-op detection.
            AudioOperationIds.Volume =>
                observation.State.VolumePercent == mutation.RequestedLevel!.Value,
            AudioOperationIds.Mute =>
                observation.State.Muted == mutation.RequestedState!.Value,
            _ => false,
        };

    private static bool SatisfiesTargetAfterEffect(
        AudioMutation mutation,
        AudioObservation observation) => mutation.Operation switch
        {
            AudioOperationIds.Volume => Math.Abs(
                observation.State.VolumePercent - mutation.RequestedLevel!.Value)
                <= VolumeTolerancePoints,
            AudioOperationIds.Mute =>
                observation.State.Muted == mutation.RequestedState!.Value,
            _ => false,
        };

    private static bool PreservesOtherDimension(
        AudioMutation mutation,
        AudioObservation baseline,
        AudioObservation final) => mutation.Operation switch
        {
            AudioOperationIds.Volume => final.State.Muted == baseline.State.Muted,
            AudioOperationIds.Mute =>
                Math.Abs(final.VolumeScalar - baseline.VolumeScalar)
                <= ScalarPreservationTolerance,
            _ => false,
        };

    private static bool TargetDimensionUnchanged(
        AudioMutation mutation,
        AudioObservation baseline,
        AudioObservation current) => mutation.Operation switch
        {
            AudioOperationIds.Volume =>
                Math.Abs(current.VolumeScalar - baseline.VolumeScalar)
                <= ScalarPreservationTolerance,
            AudioOperationIds.Mute => current.State.Muted == baseline.State.Muted,
            _ => false,
        };

    private static bool SameObservation(
        AudioObservation baseline,
        AudioObservation current) =>
        baseline.State.Muted == current.State.Muted
        && Math.Abs(current.VolumeScalar - baseline.VolumeScalar)
            <= ScalarPreservationTolerance;

    private static bool Matches(AudioInvocationState state, AudioMutation mutation) =>
        string.Equals(state.Operation, mutation.Operation, StringComparison.Ordinal)
        && string.Equals(
            state.TargetId,
            AudioTargetIds.DefaultOutput,
            StringComparison.Ordinal)
        && state.RequestedLevel == mutation.RequestedLevel
        && state.RequestedState == mutation.RequestedState;

    private static Guid CreateEventContext(string invocationId)
    {
        byte[] digest = SHA256.HashData(StrictUtf8.GetBytes(invocationId));
        return new Guid(digest.AsSpan(0, 16));
    }

    private static int PercentFromScalar(float scalar) =>
        Math.Clamp(
            (int)Math.Round(scalar * 100f, MidpointRounding.AwayFromZero),
            0,
            100);

    private static bool IsValidInvocationId(string? invocationId) =>
        !string.IsNullOrWhiteSpace(invocationId)
        && Guid.TryParseExact(invocationId, "D", out Guid parsed)
        && string.Equals(parsed.ToString("D"), invocationId, StringComparison.Ordinal)
        && StrictUtf8.GetByteCount(invocationId) <= MaximumInvocationIdUtf8Bytes
        && !invocationId.Any(char.IsControl);

    private static bool IsExpectedLockFailure(Exception exception) => exception is
        IOException
        or UnauthorizedAccessException
        or WaitHandleCannotBeOpenedException;

    private static bool IsExpectedStateFailure(Exception exception) => exception is
        IOException
        or UnauthorizedAccessException
        or SecurityException;

    private static bool IsExpectedPlatformFailure(Exception exception) => exception is
        ArgumentException
        or ArithmeticException
        or COMException
        or InvalidOperationException
        or IOException
        or NotSupportedException
        or PlatformNotSupportedException
        or SecurityException
        or UnauthorizedAccessException
        or Win32Exception;

    private static string GetDefaultStateDirectory()
    {
        string localApplicationData = Environment.GetFolderPath(
            Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(localApplicationData, "BAXY", "audio-default-output-state");
    }

    private sealed record AudioMutation(
        string InvocationId,
        string Operation,
        int? RequestedLevel,
        bool? RequestedState);

    private sealed record AudioObservation(
        string EndpointIdHash,
        float VolumeScalar,
        AudioEndpointState State);
}
