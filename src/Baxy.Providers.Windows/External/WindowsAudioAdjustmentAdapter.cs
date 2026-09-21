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

/// <summary>
/// AUDIO1787 «subí el volumen de spotify»: audio.app.volume.adjust raises or lowers
/// one application's own audio sessions (the per-app slider of the volume mixer)
/// by a bounded amount and verifies the post-read; the system endpoint is untouched.
/// General: any application with an audio session on the default output.
/// </summary>
internal sealed class WindowsAppVolumeAdapter : IExternalOperationAdapter
{
    private readonly Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> _adjust;

    internal WindowsAppVolumeAdapter()
    {
        _adjust = static (application, delta, beforeEffect, cancellationToken) =>
            WindowsCoreAudioPlatform.AdjustApplicationSessions(application, delta, beforeEffect, cancellationToken);
    }

    internal WindowsAppVolumeAdapter(
        Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> adjust) =>
        _adjust = adjust ?? throw new ArgumentNullException(nameof(adjust));

    public bool CanHandle(string operation) => operation == "audio.app.volume.adjust";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string direction;
        string application;
        try
        {
            direction = ExternalJson.RequiredString(arguments, "direction");
            application = ExternalJson.RequiredString(arguments, "app");
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                operation, "volume_adjustment_invalid"));
        }
        int amount = ExternalJson.OptionalInt(arguments, "amount", -1);
        if (direction is not ("up" or "down") || amount is < 1 or > 100 || string.IsNullOrWhiteSpace(application))
            return ValueTask.FromResult(ExternalJson.Failure(operation, "volume_adjustment_invalid"));

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            ApplicationSessionAdjustment? adjusted = _adjust(
                application,
                direction == "up" ? amount : -amount,
                () =>
                {
                    effectBoundary.Cross(cancellationToken);
                    return cancellationToken;
                },
                cancellationToken);
            if (adjusted is null)
            {
                return ValueTask.FromResult(ExternalJson.Failure(
                    operation, "app_audio_session_not_found"));
            }
            int requested = Math.Clamp(
                adjusted.BaselineLevel + (direction == "up" ? amount : -amount), 0, 100);
            if (Math.Abs(adjusted.Level - requested) > 2)
            {
                return ValueTask.FromResult(effectBoundary.Failure(
                    operation, "volume_adjustment_postread_mismatch", adjusted.BaselineLevel != adjusted.Level));
            }
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("app", application);
                writer.WriteString("processName", adjusted.ProcessName);
                writer.WriteNumber("sessionCount", adjusted.SessionCount);
                writer.WriteString("direction", direction);
                writer.WriteNumber("amount", amount);
                writer.WriteNumber("baselineLevel", adjusted.BaselineLevel);
                writer.WriteNumber("level", adjusted.Level);
                writer.WriteBoolean("muted", adjusted.Muted);
                writer.WriteString("endpointIdHash", AudioEndpointIdentity.Hash(adjusted.EndpointId));
                writer.WriteString("authority", "windows_core_audio_session_postread");
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: adjusted.BaselineLevel != adjusted.Level));
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
}

/// <summary>
/// Fase 8 (D18) «poné Spotify al 40»: audio.app.volume.set fixes one application's
/// own audio sessions (the per-app slider of the volume mixer) at an absolute level,
/// paused sessions included, and verifies the post-read; the system endpoint is
/// untouched. General: any application with an audio session on the default output.
/// </summary>
internal sealed class WindowsAppVolumeSetAdapter : IExternalOperationAdapter
{
    private readonly Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> _set;

    internal WindowsAppVolumeSetAdapter()
    {
        _set = static (application, level, beforeEffect, cancellationToken) =>
            WindowsCoreAudioPlatform.SetApplicationSessions(application, level, beforeEffect, cancellationToken);
    }

    internal WindowsAppVolumeSetAdapter(
        Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> set) =>
        _set = set ?? throw new ArgumentNullException(nameof(set));

    public bool CanHandle(string operation) => operation == "audio.app.volume.set";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string application;
        try
        {
            application = ExternalJson.RequiredString(arguments, "app");
        }
        catch (InvalidDataException)
        {
            return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                operation, "volume_level_invalid"));
        }
        int level = ExternalJson.OptionalInt(arguments, "level", -1);
        if (level is < 0 or > 100 || string.IsNullOrWhiteSpace(application))
            return ValueTask.FromResult(ExternalJson.Failure(operation, "volume_level_invalid"));

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            ApplicationSessionAdjustment? adjusted = _set(
                application,
                level,
                () =>
                {
                    effectBoundary.Cross(cancellationToken);
                    return cancellationToken;
                },
                cancellationToken);
            if (adjusted is null)
            {
                return ValueTask.FromResult(ExternalJson.Failure(
                    operation, "app_audio_session_not_found"));
            }
            if (Math.Abs(adjusted.Level - level) > 2)
            {
                return ValueTask.FromResult(effectBoundary.Failure(
                    operation, "volume_postread_mismatch", adjusted.BaselineLevel != adjusted.Level));
            }
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("app", application);
                writer.WriteString("processName", adjusted.ProcessName);
                writer.WriteNumber("sessionCount", adjusted.SessionCount);
                writer.WriteNumber("requestedLevel", level);
                writer.WriteNumber("baselineLevel", adjusted.BaselineLevel);
                writer.WriteNumber("level", adjusted.Level);
                writer.WriteBoolean("muted", adjusted.Muted);
                writer.WriteString("endpointIdHash", AudioEndpointIdentity.Hash(adjusted.EndpointId));
                writer.WriteString("authority", "windows_core_audio_session_postread");
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: adjusted.BaselineLevel != adjusted.Level));
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
}
