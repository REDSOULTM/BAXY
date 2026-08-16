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
            return InvalidArguments();
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
            return InvalidArguments();
        }

        if (arguments.Level is < 0 or > 100)
        {
            return InvalidArguments();
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
            return AudioControlEvidence.VerificationFailure(receipt);
        }

        JsonElement serialized = AudioControlEvidence.SerializeVerified(receipt);
        return OperationOutcome.Success(serialized);
    }

    private static OperationOutcome InvalidArguments() =>
        OperationOutcome.Failure("invalid_arguments");
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
                effectMayHaveOccurred: effectMayHaveOccurred);
    }

    internal static OperationOutcome VerificationFailure(AudioControlReceipt? receipt) =>
        OperationOutcome.Failure(
            AudioControlErrorCodes.VerificationFailed,
            effectMayHaveOccurred: receipt is not null && MayHaveChanged(receipt));

    private static bool IsValidState(AudioEndpointState state) =>
        state.VolumePercent is >= 0 and <= 100;

    private static bool IsLowerHexSha256(string value)
    {
        if (value.Length != 64)
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
