using System.Runtime.InteropServices;
using System.Security;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Infrastructure;

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

    internal const string StatusOperation = "audio.microphone.status";

    public bool CanHandle(string operation) => operation is "audio.microphone.mute" or StatusOperation;

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (operation == StatusOperation)
        {
            return ValueTask.FromResult(ReadStatus(operation));
        }

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
                ExternalCapabilityReceipt already = ExternalJson.FailureBeforeEffect(
                    operation,
                    requested ? "microphone_already_muted" : "microphone_already_unmuted");
                return ValueTask.FromResult(ModelAids.On(ModelAids.MicrophoneScope)
                    ? already with { Result = Scope(writer => writer.WriteBoolean("muted", baseline)) }
                    : already);
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
                if (ModelAids.On(ModelAids.MicrophoneScope)) writer.WriteString("next", ScopeNext);
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

    // noche P1.1 (d): the state, read with no boundary crossed (the mute call found it out only by trying to change it).
    private ExternalCapabilityReceipt ReadStatus(string operation)
    {
        try
        {
            using IWindowsAudioEndpoint endpoint = _openDefaultInput();
            bool muted = endpoint.ReadMuted();
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("muted", muted);
                writer.WriteString("endpointIdHash", AudioEndpointIdentity.Hash(endpoint.EndpointId));
                writer.WriteString("authority", "windows_core_audio_capture_endpoint_read");
                if (ModelAids.On(ModelAids.MicrophoneScope)) writer.WriteString("next", ScopeNext);
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: false);
        }
        catch (AudioPlatformException exception)
        {
            return ExternalJson.FailureBeforeEffect(operation, exception.ErrorCode);
        }
        catch (Exception exception) when (exception is COMException
            or InvalidComObjectException or UnauthorizedAccessException
            or SecurityException or ObjectDisposedException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "microphone_endpoint_unavailable");
        }
    }

    // BAXY Renew cu (C14): this is Windows' own switch of the default microphone; an application's own mute (the
    // microphone button of a call or chat app) is another switch, in that application's window. Said, never acted on
    // («desmutea mi micrófono en <app>» was answered «it was not muted» by Windows' state alone).
    private const string ScopeNext = "this is Windows' switch of the default microphone; an application's own mute (its "
        + "microphone button in a call or chat app) is a separate switch in its window, which input_visible_controls can look at";

    private static JsonElement Scope(Action<Utf8JsonWriter> state) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("version", 1);
        state(writer);
        writer.WriteString("next", ScopeNext);
        writer.WriteEndObject();
    });
}
