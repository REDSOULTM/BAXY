using System.Runtime.InteropServices;
using System.Security;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsAudioAdjustmentAdapter : IExternalOperationAdapter
{
    private readonly Func<IWindowsAudioEndpoint> _openDefaultOutput;

    internal WindowsAudioAdjustmentAdapter()
    {
        _openDefaultOutput = static () => new WindowsCoreAudioPlatform().OpenDefaultOutput();
    }

    internal WindowsAudioAdjustmentAdapter(Func<IWindowsAudioEndpoint> openDefaultOutput) =>
        _openDefaultOutput = openDefaultOutput
            ?? throw new ArgumentNullException(nameof(openDefaultOutput));

    public bool CanHandle(string operation) => operation == "audio.volume.adjust";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string direction;
        try
        {
            direction = ExternalJson.RequiredString(arguments, "direction");
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                operation, "volume_adjustment_invalid"));
        }
        int amount = ExternalJson.OptionalInt(arguments, "amount", -1);
        if (direction is not ("up" or "down") || amount is < 1 or > 100)
            return ValueTask.FromResult(ExternalJson.Failure(operation, "volume_adjustment_invalid"));

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            using IWindowsAudioEndpoint endpoint = _openDefaultOutput();
            int baseline = Percent(endpoint.ReadVolumeScalar());
            bool baselineMuted = endpoint.ReadMuted();
            int requested = Math.Clamp(
                baseline + (direction == "up" ? amount : -amount), 0, 100);
            effectBoundary.Cross(cancellationToken);
            endpoint.SetVolumeScalar(requested / 100f, Guid.NewGuid());
            int observed = Percent(endpoint.ReadVolumeScalar());
            bool observedMuted = endpoint.ReadMuted();
            if (Math.Abs(observed - requested) > 2 || observedMuted != baselineMuted)
            {
                return ValueTask.FromResult(effectBoundary.Failure(
                    operation, "volume_adjustment_postread_mismatch", baseline != observed));
            }
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("direction", direction);
                writer.WriteNumber("amount", amount);
                writer.WriteNumber("baselineLevel", baseline);
                writer.WriteNumber("level", observed);
                writer.WriteBoolean("muted", observedMuted);
                writer.WriteString("endpointIdHash", AudioEndpointIdentity.Hash(endpoint.EndpointId));
                writer.WriteString("authority", "windows_core_audio_output_endpoint_postread");
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: baseline != observed));
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "audio_output_endpoint_unavailable"));
        }
        catch (AudioPlatformException exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, exception.ErrorCode));
        }
        catch (Exception exception) when (exception is COMException
            or InvalidComObjectException or UnauthorizedAccessException
            or SecurityException or ObjectDisposedException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "audio_output_endpoint_unavailable"));
        }
    }

    private static int Percent(float scalar) =>
        Math.Clamp((int)Math.Round(scalar * 100f, MidpointRounding.AwayFromZero), 0, 100);
}
