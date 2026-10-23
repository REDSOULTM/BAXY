using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Core.Operations;

internal sealed class AudioVolumeHandler(IAudioControlProvider provider) : IOperationHandler
{
    private readonly IAudioControlProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition(AudioOperationIds.Volume);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!AudioControlEvidence.HasExactArgument(
                invocation.Arguments,
                "level",
                JsonValueKind.Number))
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        AudioVolumeArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.AudioVolumeArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        if (arguments.Level is < 0 or > 100)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        AudioControlReceipt receipt = await _provider.SetVolumeAsync(
            new AudioVolumeCommand(invocation.InvocationId, arguments.Level),
            cancellationToken).ConfigureAwait(false);
        if (!AudioControlEvidence.HasConsistentEnvelope(
                receipt,
                invocation.InvocationId,
                AudioOperationIds.Volume,
                arguments.Level,
                requestedState: null))
        {
            return AudioControlEvidence.VerificationFailure(receipt);
        }

        if (!receipt.Verified)
        {
            return AudioControlEvidence.ProviderFailure(receipt);
        }

        AudioEndpointState baseline = receipt.Baseline!;
        AudioEndpointState final = receipt.Final!;
        if (Math.Abs(final.VolumePercent - arguments.Level)
                > AudioControlEvidence.MaximumVolumeTolerance
            || baseline.Muted != final.Muted)
        {
            return AudioControlEvidence.VerificationFailure(receipt, final);
        }

        AudioStatusReceipt observed = await _provider.GetStatusAsync(
            new AudioStatusQuery(invocation.InvocationId),
            cancellationToken).ConfigureAwait(false);
        if (!AudioControlEvidence.MatchesIndependentStatus(receipt, observed))
        {
            return AudioControlEvidence.VerificationFailure(receipt, AudioControlEvidence.ReadAfter(receipt, observed));
        }

        JsonElement serialized = AudioControlEvidence.SerializeVerified(receipt);
        return OperationOutcome.Success(serialized);
    }
}

internal static class AudioControlEvidence
{
    internal const int MaximumVolumeTolerance = 2;

    internal static bool HasExactArgument(
        JsonElement arguments,
        string expectedName,
        params JsonValueKind[] expectedKinds)
    {
        if (arguments.ValueKind != JsonValueKind.Object || expectedKinds.Length == 0)
        {
            return false;
        }

        int propertyCount = 0;
        foreach (JsonProperty property in arguments.EnumerateObject())
        {
            propertyCount++;
            if (propertyCount > 1
                || !string.Equals(property.Name, expectedName, StringComparison.Ordinal)
                || Array.IndexOf(expectedKinds, property.Value.ValueKind) < 0)
            {
                return false;
            }
        }

        return propertyCount == 1;
    }

    internal static bool HasConsistentEnvelope(
        AudioControlReceipt? receipt,
        string invocationId,
        string operation,
        int? requestedLevel,
        bool? requestedState)
    {
        if (receipt is null
            || !string.Equals(receipt.InvocationId, invocationId, StringComparison.Ordinal)
            || !string.Equals(receipt.Operation, operation, StringComparison.Ordinal)
            || !string.Equals(
                receipt.TargetId,
                AudioTargetIds.DefaultOutput,
                StringComparison.Ordinal)
            || receipt.RequestedLevel != requestedLevel
            || receipt.RequestedState != requestedState
            || receipt.Applied && receipt.Reconciled
            || receipt.ErrorCode is not null && !IsKnownErrorCode(receipt.ErrorCode))
        {
            return false;
        }

        bool hasEndpointHash = receipt.EndpointIdHash is not null;
        bool hasBaseline = receipt.Baseline is not null;
        bool hasFinal = receipt.Final is not null;
        if (hasEndpointHash != hasBaseline
            || hasFinal && !hasBaseline
            || receipt.EndpointIdHash is not null
                && !IsLowerHexSha256(receipt.EndpointIdHash)
            || receipt.Baseline is not null && !IsValidState(receipt.Baseline)
            || receipt.Final is not null && !IsValidState(receipt.Final)
            || receipt.Applied && !hasBaseline
            || receipt.Reconciled && !hasFinal
            || receipt.Retryable
                && (!hasEndpointHash
                    || !hasBaseline
                    || receipt.Reconciled
                    || !IsRetryableErrorCode(receipt.ErrorCode)))
        {
            return false;
        }

        if (receipt.Verified)
        {
            if (receipt.Retryable
                || receipt.ErrorCode is not null
                || !hasEndpointHash
                || !hasBaseline
                || !hasFinal)
            {
                return false;
            }

            if (!receipt.Applied
                && !receipt.Reconciled
                && receipt.Baseline != receipt.Final)
            {
                return false;
            }

            return true;
        }

        return receipt.ErrorCode is not null && !receipt.Reconciled;
    }

    internal static JsonElement SerializeVerified(AudioControlReceipt receipt)
    {
        AudioEndpointState baseline = receipt.Baseline!;
        AudioEndpointState final = receipt.Final!;
        var result = new AudioControlResult(
            receipt.Operation,
            receipt.TargetId,
            receipt.EndpointIdHash!,
            new AudioEndpointStateResult(baseline.VolumePercent, baseline.Muted),
            new AudioEndpointStateResult(final.VolumePercent, final.Muted),
            receipt.Applied,
            receipt.Reconciled);
        return JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.AudioControlResult);
    }

    internal static OperationOutcome ProviderFailure(AudioControlReceipt receipt)
    {
        string errorCode = receipt.ErrorCode!;
        bool effectMayHaveOccurred = MayHaveChanged(receipt);
        return receipt.Retryable
            ? OperationOutcome.RetryableFailure(
                AudioControlErrorCodes.ReconciliationRequired,
                effectMayHaveOccurred: effectMayHaveOccurred,
                causeCode: errorCode)
            : OperationOutcome.Failure(
                errorCode,
                result: StateAfter(receipt),
                effectMayHaveOccurred: effectMayHaveOccurred);
    }

    // Renew al máximo: a set the provider could not verify still read the endpoint after it; that final reading was
    // dropped, so the mind only heard «could not» without the level and mute it left. It travels beside the failure
    // as stateAfter, never as a success; any other failure, or one with no final reading, stays bare.
    private static JsonElement? StateAfter(AudioControlReceipt receipt) =>
        receipt.ErrorCode == AudioControlErrorCodes.VerificationFailed && receipt.Final is { } final
            ? StateAfter(receipt, final)
            : null;

    // Auditoría del Core (w8): the endpoint as read after a set that did not hold, in the shape of audio.volume.adjust's
    // stateAfter (WindowsAudioAdjustmentAdapter.VolumeState) and with requestedStateReached, which the mind reads as
    // «releído después: quedó / no quedó como se pidió»: the level within the post-read's tolerance and the mute as it
    // was (a volume), or the mute asked and the level as it was (a mute).
    private static JsonElement StateAfter(AudioControlReceipt receipt, AudioEndpointState after)
    {
        bool reached = receipt.RequestedLevel is int level
            ? Math.Abs(after.VolumePercent - level) <= MaximumVolumeTolerance && receipt.Baseline?.Muted == after.Muted
            : receipt.RequestedState is bool muted
                && after.Muted == muted && receipt.Baseline?.VolumePercent == after.VolumePercent;
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteStartObject("stateAfter");
            writer.WriteNumber("level", after.VolumePercent);
            writer.WriteBoolean("muted", after.Muted);
            if (receipt.RequestedLevel is int requested)
                writer.WriteNumber("requestedLevel", requested);
            writer.WriteBoolean("requestedStateReached", reached);
            writer.WriteString("authority", "windows_core_audio_output_endpoint_postread");
            writer.WriteEndObject();
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    /// <summary>
    /// The endpoint as last read after a set: the independent status read when it is a verified read of the same
    /// endpoint, else the provider's own final reading.
    /// </summary>
    internal static AudioEndpointState? ReadAfter(AudioControlReceipt receipt, AudioStatusReceipt status) =>
        status is { Verified: true, ErrorCode: null, State: { } state }
        && string.Equals(status.TargetId, receipt.TargetId, StringComparison.Ordinal)
        && string.Equals(status.EndpointIdHash, receipt.EndpointIdHash, StringComparison.Ordinal)
            ? state
            : receipt.Final;

    internal static bool MatchesIndependentStatus(
        AudioControlReceipt receipt,
        AudioStatusReceipt status)
    {
        AudioEndpointState? claimed = receipt.Final;
        AudioEndpointState? observed = status.State;
        return status.Verified
            && status.ErrorCode is null
            && claimed is not null
            && observed is not null
            && string.Equals(status.Operation, AudioOperationIds.Status, StringComparison.Ordinal)
            && string.Equals(status.TargetId, receipt.TargetId, StringComparison.Ordinal)
            && string.Equals(status.EndpointIdHash, receipt.EndpointIdHash, StringComparison.Ordinal)
            && Math.Abs(observed.VolumePercent - claimed.VolumePercent) <= MaximumVolumeTolerance
            && observed.Muted == claimed.Muted;
    }

    // Auditoría del Core (w8): a verified set whose final reading, or the independent read after it, is not what was
    // asked failed bare, while the provider's own unverified set carried its stateAfter; with a reading after, it
    // goes beside the failure too.
    internal static OperationOutcome VerificationFailure(AudioControlReceipt? receipt, AudioEndpointState? after = null) =>
        OperationOutcome.Failure(
            AudioControlErrorCodes.VerificationFailed,
            result: receipt is not null && after is not null ? StateAfter(receipt, after) : null,
            effectMayHaveOccurred: receipt is not null && MayHaveChanged(receipt));

    private static bool IsValidState(AudioEndpointState state) =>
        state.VolumePercent is >= 0 and <= 100;

    // The endpoint hash both audio handlers check (one copy: revisión 2026-10-22, C-9).
    internal static bool IsLowerHexSha256(string? value)
    {
        if (value is null || value.Length != 64)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9')
                and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsKnownErrorCode(string errorCode) => errorCode is
        AudioControlErrorCodes.InvalidInvocation
        or AudioControlErrorCodes.InvalidLevel
        or AudioControlErrorCodes.AudioBusy
        or AudioControlErrorCodes.NoDefaultOutput
        or AudioControlErrorCodes.AudioServiceUnavailable
        or AudioControlErrorCodes.EndpointUnavailable
        or AudioControlErrorCodes.EndpointChanged
        or AudioControlErrorCodes.OperationFailed
        or AudioControlErrorCodes.VerificationFailed
        or AudioControlErrorCodes.EffectUncertain
        or AudioControlErrorCodes.StateCorrupt
        or AudioControlErrorCodes.StateCapacityReached
        or AudioControlErrorCodes.StateUnavailable;

    private static bool IsRetryableErrorCode(string? errorCode) => errorCode is
        AudioControlErrorCodes.NoDefaultOutput
        or AudioControlErrorCodes.AudioServiceUnavailable
        or AudioControlErrorCodes.EndpointUnavailable
        or AudioControlErrorCodes.EffectUncertain
        or AudioControlErrorCodes.StateCorrupt
        or AudioControlErrorCodes.StateCapacityReached
        or AudioControlErrorCodes.StateUnavailable;

    private static bool MayHaveChanged(AudioControlReceipt receipt) =>
        receipt.Applied
        || receipt.Reconciled
        || string.Equals(
            receipt.ErrorCode,
            AudioControlErrorCodes.EffectUncertain,
            StringComparison.Ordinal)
        || receipt.Baseline is not null
            && receipt.Final is not null
            && receipt.Baseline != receipt.Final
        || receipt.Baseline is not null
            && receipt.ErrorCode is
                AudioControlErrorCodes.NoDefaultOutput
                or AudioControlErrorCodes.AudioServiceUnavailable
                or AudioControlErrorCodes.EndpointUnavailable
                or AudioControlErrorCodes.EndpointChanged;

}
