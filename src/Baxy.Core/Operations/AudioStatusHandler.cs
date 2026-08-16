using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Core.Operations;

internal sealed class AudioStatusHandler(IAudioControlProvider provider) : IOperationHandler
{
    private readonly IAudioControlProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition(AudioOperationIds.Status);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            _ = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.EmptyArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return InvalidArguments();
        }

        AudioStatusReceipt receipt = await _provider.GetStatusAsync(
            new AudioStatusQuery(invocation.InvocationId),
            cancellationToken).ConfigureAwait(false);
        if (!HasConsistentEnvelope(receipt, invocation.InvocationId))
        {
            return OperationOutcome.Failure(AudioControlErrorCodes.VerificationFailed);
        }

        if (!receipt.Verified)
        {
            return OperationOutcome.Failure(receipt.ErrorCode!);
        }

        AudioEndpointState state = receipt.State!;
        var result = new AudioStatusResult(
            receipt.Operation,
            receipt.TargetId,
            receipt.EndpointIdHash!,
            new AudioEndpointStateResult(state.VolumePercent, state.Muted));
        JsonElement serialized = JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.AudioStatusResult);
        return OperationOutcome.Success(serialized);
    }

    private static bool HasConsistentEnvelope(
        AudioStatusReceipt? receipt,
        string invocationId)
    {
        if (receipt is null
            || !string.Equals(receipt.InvocationId, invocationId, StringComparison.Ordinal)
            || !string.Equals(receipt.Operation, AudioOperationIds.Status, StringComparison.Ordinal)
            || !string.Equals(receipt.TargetId, AudioTargetIds.DefaultOutput, StringComparison.Ordinal))
        {
            return false;
        }

        if (receipt.Verified)
        {
            return receipt.ErrorCode is null
                && IsLowerHexSha256(receipt.EndpointIdHash)
                && receipt.State is { VolumePercent: >= 0 and <= 100 };
        }

        return receipt.EndpointIdHash is null
            && receipt.State is null
            && receipt.ErrorCode is
                AudioControlErrorCodes.InvalidInvocation
                or AudioControlErrorCodes.AudioBusy
                or AudioControlErrorCodes.NoDefaultOutput
                or AudioControlErrorCodes.AudioServiceUnavailable
                or AudioControlErrorCodes.EndpointUnavailable;
    }

    private static bool IsLowerHexSha256(string? value)
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

    private static OperationOutcome InvalidArguments() =>
        OperationOutcome.Failure("invalid_arguments");
}
