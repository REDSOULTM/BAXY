using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Core.Operations;

internal sealed class AudioMuteHandler(IAudioControlProvider provider) : IOperationHandler
{
    private readonly IAudioControlProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition(AudioOperationIds.Mute);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!AudioControlEvidence.HasExactArgument(
                invocation.Arguments,
                "state",
                JsonValueKind.True,
                JsonValueKind.False))
        {
            return InvalidArguments();
        }

        AudioMuteArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.AudioMuteArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return InvalidArguments();
        }

        AudioControlReceipt receipt = await _provider.SetMuteAsync(
            new AudioMuteCommand(invocation.InvocationId, arguments.State),
            cancellationToken).ConfigureAwait(false);
        if (!AudioControlEvidence.HasConsistentEnvelope(
                receipt,
                invocation.InvocationId,
                AudioOperationIds.Mute,
                requestedLevel: null,
                arguments.State))
        {
            return AudioControlEvidence.VerificationFailure(receipt);
        }

        if (!receipt.Verified)
        {
            return AudioControlEvidence.ProviderFailure(receipt);
        }

        AudioEndpointState baseline = receipt.Baseline!;
        AudioEndpointState final = receipt.Final!;
        if (final.Muted != arguments.State
            || baseline.VolumePercent != final.VolumePercent)
        {
            return AudioControlEvidence.VerificationFailure(receipt);
        }

        JsonElement serialized = AudioControlEvidence.SerializeVerified(receipt);
        return OperationOutcome.Success(serialized);
    }

    private static OperationOutcome InvalidArguments() =>
        OperationOutcome.Failure("invalid_arguments");
}
