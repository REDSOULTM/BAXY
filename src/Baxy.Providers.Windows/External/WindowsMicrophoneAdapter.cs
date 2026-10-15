using System.Runtime.InteropServices;
using System.Security;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsMicrophoneAdapter : IExternalOperationAdapter
{
    private readonly Func<IWindowsAudioEndpoint> _openDefaultInput;

    internal WindowsMicrophoneAdapter()
    {
        _openDefaultInput = WindowsCoreAudioPlatform.OpenDefaultInput;
    }

    internal WindowsMicrophoneAdapter(Func<IWindowsAudioEndpoint> openDefaultInput) =>
        _openDefaultInput = openDefaultInput
            ?? throw new ArgumentNullException(nameof(openDefaultInput));

    public bool CanHandle(string operation) => operation == "audio.microphone.mute";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!arguments.TryGetProperty("state", out JsonElement stateValue)
            || stateValue.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
        {
            return ValueTask.FromResult(ExternalJson.Failure(
                operation, "microphone_state_invalid"));
        }

        bool requested = stateValue.GetBoolean();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            using IWindowsAudioEndpoint endpoint = _openDefaultInput();
            bool baseline = endpoint.ReadMuted();
            if (baseline == requested)
            {
                // Owner's test 2026-09-21 (turn 205): setting the state the
                // endpoint already has cannot be observed as an effect; the
                // honest fact is the state, said before any boundary is crossed.
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                    operation,
                    requested ? "microphone_already_muted" : "microphone_already_unmuted"));
            }
            effectBoundary.Cross(cancellationToken);
            endpoint.SetMuted(requested, Guid.NewGuid());
            bool observed = endpoint.ReadMuted();
            if (observed != requested)
            {
                return ValueTask.FromResult(effectBoundary.Failure(
                    operation, "microphone_mute_postread_mismatch", baseline != observed));
            }
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("baselineMuted", baseline);
                writer.WriteBoolean("muted", observed);
                writer.WriteString("endpointIdHash", AudioEndpointIdentity.Hash(endpoint.EndpointId));
                writer.WriteString("authority", "windows_core_audio_capture_endpoint_postread");
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: baseline != observed));
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "microphone_endpoint_unavailable"));
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
                operation, "microphone_endpoint_unavailable"));
        }
    }
}
