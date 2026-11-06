using System.Globalization;
using System.Runtime.InteropServices;
using System.Security;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Kernel.Operations;

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
        string? endpointId = null;
        int requested = -1;
        bool baselineMuted = false;
        try
        {
            using IWindowsAudioEndpoint endpoint = _openDefaultOutput();
            endpointId = endpoint.EndpointId;
            int baseline = Percent(endpoint.ReadVolumeScalar());
            baselineMuted = endpoint.ReadMuted();
            // M54 (v3b-final F-w02-t4, F-w11-t3 «súbele harto a la música» at 100 % and muted): a level already at
            // the end the person moves it towards cannot change, so no effect can be observed; the honest fact is
            // the state, said before any boundary is crossed (same contract as the microphone), with the mute that
            // explains why nothing is heard.
            if (direction == "up" ? baseline >= 100 : baseline <= 0)
            {
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                    operation,
                    direction == "down"
                        ? "volume_already_at_minimum"
                        : baselineMuted ? "volume_already_at_maximum_muted" : "volume_already_at_maximum"));
            }
            requested = Math.Clamp(
                baseline + (direction == "up" ? amount : -amount), 0, 100);
            effectBoundary.Cross(cancellationToken);
            endpoint.SetVolumeScalar(requested / 100f, Guid.NewGuid());
            int observed = Percent(endpoint.ReadVolumeScalar());
            bool observedMuted = endpoint.ReadMuted();
            if (Math.Abs(observed - requested) > 2 || observedMuted != baselineMuted)
            {
                // Renew al máximo (8.3): what the post-read saw is the state after, never dropped.
                return ValueTask.FromResult(ExternalJson.WithStateAfter(
                    effectBoundary.Failure(operation, "volume_adjustment_postread_mismatch", baseline != observed),
                    VolumeState(observed, observedMuted, requested, baselineMuted,
                        "windows_core_audio_output_endpoint_postread")));
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
            return ValueTask.FromResult(Reread(
                effectBoundary.Failure(operation, "audio_output_endpoint_unavailable"),
                endpointId, requested, baselineMuted));
        }
        catch (AudioPlatformException exception)
        {
            return ValueTask.FromResult(Reread(
                effectBoundary.Failure(operation, exception.ErrorCode), endpointId, requested, baselineMuted));
        }
        catch (Exception exception) when (exception is COMException
            or InvalidComObjectException or UnauthorizedAccessException
            or SecurityException or ObjectDisposedException)
        {
            return ValueTask.FromResult(Reread(
                effectBoundary.Failure(operation, "audio_output_endpoint_unavailable"),
                endpointId, requested, baselineMuted));
        }
    }

    // Renew al máximo (8.3): a level set whose post-read threw: one more read of the default output, while it is still
    // the one set, says the level it has; another output in its place, or a read that fails too, adds nothing.
    private ExternalCapabilityReceipt Reread(
        ExternalCapabilityReceipt failure, string? endpointId, int requested, bool baselineMuted)
    {
        if (!failure.EffectMayHaveOccurred || endpointId is null || requested < 0)
            return failure;
        try
        {
            using IWindowsAudioEndpoint endpoint = _openDefaultOutput();
            return string.Equals(endpoint.EndpointId, endpointId, StringComparison.Ordinal)
                ? ExternalJson.WithStateAfter(failure, VolumeState(
                    Percent(endpoint.ReadVolumeScalar()), endpoint.ReadMuted(), requested, baselineMuted,
                    "windows_core_audio_output_endpoint_postread"))
                : failure;
        }
        catch (Exception exception) when (exception is AudioPlatformException or COMException
            or InvalidComObjectException or UnauthorizedAccessException
            or SecurityException or ObjectDisposedException)
        {
            return failure;
        }
    }

    // Renew al máximo (8.3): the level and mute read after an ambiguous change, and whether they are the ones asked
    // (the level within the post-read's tolerance, the mute as it was).
    internal static JsonElement VolumeState(
        int level, bool muted, int requested, bool requestedMuted, string authority) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("level", level);
        writer.WriteBoolean("muted", muted);
        writer.WriteNumber("requestedLevel", requested);
        writer.WriteBoolean("requestedStateReached", Math.Abs(level - requested) <= 2 && muted == requestedMuted);
        writer.WriteString("authority", authority);
        writer.WriteEndObject();
    });

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
    private readonly Func<IReadOnlyList<AudioSessionProgram>> _sessionNames;
    private readonly Func<(string Name, string Process)?> _browser;

    internal WindowsAppVolumeAdapter()
    {
        _adjust = static (application, delta, beforeEffect, cancellationToken) =>
            WindowsCoreAudioPlatform.AdjustApplicationSessions(application, delta, beforeEffect, cancellationToken);
        _sessionNames = WindowsCoreAudioPlatform.ApplicationSessionPrograms;
        _browser = Windows.DesktopWindowNames.PersonBrowser;
    }

    internal WindowsAppVolumeAdapter(
        Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> adjust,
        Func<IReadOnlyList<AudioSessionProgram>>? sessionNames = null,
        Func<(string Name, string Process)?>? browser = null)
    {
        _adjust = adjust ?? throw new ArgumentNullException(nameof(adjust));
        _sessionNames = sessionNames ?? (static () => []);
        _browser = browser ?? (static () => null);
    }

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
                return ValueTask.FromResult(AppSessionNotFound.Receipt(operation, application,
                    new JsonObject { ["amount"] = amount, ["direction"] = direction },
                    $"turns the volume of {{0}} {direction} by {amount}", _sessionNames, _browser,
                    WireNames.Of("audio.volume.adjust"), $"amount {amount} and direction \"{direction}\""));
            }
            // FT/proveedores goal (review): an application already at the end it is moved towards, with no session
            // changed, says that state, as the system volume does (M54); it was a success with no observed effect,
            // which the handler turns into an opaque external_effect_unobserved.
            if (!adjusted.Changed && (direction == "up" ? adjusted.BaselineLevel >= 100 : adjusted.BaselineLevel <= 0))
            {
                return ValueTask.FromResult(ExternalJson.FailureBeforeEffect(
                    operation,
                    direction == "down"
                        ? "volume_already_at_minimum"
                        : adjusted.Muted ? "volume_already_at_maximum_muted" : "volume_already_at_maximum"));
            }
            int requested = Math.Clamp(
                adjusted.BaselineLevel + (direction == "up" ? amount : -amount), 0, 100);
            if (Math.Abs(adjusted.Level - requested) > 2)
            {
                // Renew al máximo (8.3): the application's level read after is the state after, never dropped.
                return ValueTask.FromResult(ExternalJson.WithStateAfter(
                    effectBoundary.Failure(operation, "volume_adjustment_postread_mismatch", adjusted.Changed),
                    WindowsAudioAdjustmentAdapter.VolumeState(adjusted.Level, adjusted.Muted, requested, adjusted.Muted,
                        "windows_core_audio_session_postread")));
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
                operation, result, effectObserved: adjusted.Changed));
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
    private readonly Func<IReadOnlyList<AudioSessionProgram>> _sessionNames;
    private readonly Func<(string Name, string Process)?> _browser;

    internal WindowsAppVolumeSetAdapter()
    {
        _set = static (application, level, beforeEffect, cancellationToken) =>
            WindowsCoreAudioPlatform.SetApplicationSessions(application, level, beforeEffect, cancellationToken);
        _sessionNames = WindowsCoreAudioPlatform.ApplicationSessionPrograms;
        _browser = Windows.DesktopWindowNames.PersonBrowser;
    }

    internal WindowsAppVolumeSetAdapter(
        Func<string, int, Func<CancellationToken>?, CancellationToken, ApplicationSessionAdjustment?> set,
        Func<IReadOnlyList<AudioSessionProgram>>? sessionNames = null,
        Func<(string Name, string Process)?>? browser = null)
    {
        _set = set ?? throw new ArgumentNullException(nameof(set));
        _sessionNames = sessionNames ?? (static () => []);
        _browser = browser ?? (static () => null);
    }

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
                return ValueTask.FromResult(AppSessionNotFound.Receipt(operation, application,
                    new JsonObject { ["level"] = level }, $"sets the volume of {{0}} to {level}", _sessionNames, _browser,
                    WireNames.Of("audio.volume"),
                    $"level {level}"));
            }
            if (Math.Abs(adjusted.Level - level) > 2)
            {
                // Renew al máximo (8.3): the application's level read after is the state after, never dropped.
                return ValueTask.FromResult(ExternalJson.WithStateAfter(
                    effectBoundary.Failure(operation, "volume_postread_mismatch", adjusted.Changed),
                    WindowsAudioAdjustmentAdapter.VolumeState(adjusted.Level, adjusted.Muted, level, adjusted.Muted,
                        "windows_core_audio_session_postread")));
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
            return ValueTask.FromResult(ExternalJson.Switched(
                operation, result, effectObserved: adjusted.Changed));
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
/// Renew al máximo (auditoría de flujos, P257 «deja el volumen en 20» → audio.app.volume.set {app:"volumen"}): an
/// application with no audio session on the default output fails before any effect, and (model aid) the failure names
/// the applications that have one, few and by their process names, and the operation of the PC's own volume. Holdout v6
/// V6E064 («el volumen déjamelo en treinta mientras veo la serie» set Netflix's volume, 4 of 4 runs then answered in
/// words): that operation is said as the call it would be, with the person's level or amount. Banco de uso 03-11 (R09,
/// «baja el volumen del navegador a 20»): the model named one browser, the processes with audio held another and it
/// asked which; the failure says which browser is the person's own (Windows' default), as a window's does
/// (WindowControlHandlers). Uso 81 (banco de decisiones e35-H-R09a, 16/20 → 9/20 with a new catalog: after this
/// failure the model answered in words): when one application with audio, and only one, has a name that matches what
/// was said by form (<see cref="NameHolder"/>), the next leads with the same call naming it (a failure's next that leads
/// with the exact call is followed: encargos 28 and 48).
/// </summary>
internal static class AppSessionNotFound
{
    internal const string ErrorCode = "app_audio_session_not_found_on_default_output";

    internal const int NameLimit = 8;

    /// <param name="sameArguments">The call's other arguments (level, or amount and direction), as the model gave them.</param>
    /// <param name="effect">What the call does to the application named by its one placeholder, «{0}».</param>
    internal static ExternalCapabilityReceipt Receipt(
        string operation,
        string application,
        JsonObject sameArguments,
        string effect,
        Func<IReadOnlyList<AudioSessionProgram>> sessionNames,
        Func<(string Name, string Process)?> browser,
        string systemOperation,
        string systemArguments)
    {
        ExternalCapabilityReceipt failure = ExternalJson.FailureBeforeEffect(operation, ErrorCode);
        if (!ModelAids.On(ModelAids.AppVolumeCandidates))
            return failure;
        AudioSessionProgram[] programs;
        try
        {
            programs = sessionNames()
                .Where(static program => !string.IsNullOrWhiteSpace(program.Process))
                .DistinctBy(static program => program.Process, StringComparer.OrdinalIgnoreCase)
                .Take(NameLimit)
                .ToArray();
        }
        catch (Exception exception) when (exception is AudioPlatformException or COMException
            or InvalidComObjectException or UnauthorizedAccessException or SecurityException)
        {
            // An unread list is no list: the code alone stands.
            return failure;
        }

        (string Name, string Process)? own = browser();
        AudioSessionProgram? holder = ModelAids.On(ModelAids.AppVolumeNameHolder) ? NameHolder(application, programs) : null;

        return failure with
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteStartArray("appsWithAudio");
                foreach (AudioSessionProgram program in programs)
                    writer.WriteStringValue(program.Process);
                writer.WriteEndArray();
                if (own is { } known)
                {
                    writer.WriteStartObject("personBrowser");
                    writer.WriteString("name", known.Name);
                    writer.WriteString("process", known.Process);
                    writer.WriteEndObject();
                }
                // Uso 81: the name Windows shows is said beside the process only in the next (a list of shown names
                // beside appsWithAudio took e35-H-R09a from 5/10 to 2/10 and R09 from 6/10 to 1/10).
                // Encargo 82 (vivo del 81, 2 of 2): the application said is the one that holds the name: the call that leads
                // would be this same one, which the model made, failed again and then moved the whole PC's volume.
                writer.WriteString("next", holder is { } said
                        && WindowsCoreAudioPlatform.FoldToken(said.Process) == WindowsCoreAudioPlatform.FoldToken(application)
                    ? $"this call changed nothing and the same call would not do more: {said.Process} has audio, and its "
                        + "session did not take the change; the person asked for this application's volume, not the "
                        + "whole PC's"
                    : holder is { } one
                    ? $"{WireNames.Call(operation, WithApp(sameArguments, one.Process))} "
                        + string.Format(CultureInfo.InvariantCulture, effect, one.Process
                            + (one.Name is { } name && WindowsCoreAudioPlatform.FoldToken(name)
                                != WindowsCoreAudioPlatform.FoldToken(one.Process) ? $" ({name})" : ""))
                        + $"; this call changed nothing: no application with audio is named \"{application}\", and "
                        + $"{one.Process} is the one whose names match it"
                    : "only these applications have a volume of their own now (app takes one of "
                        + $"them); the volume of the whole PC is {systemOperation}, not an application: if the person "
                        + $"meant the whole PC, call {systemOperation} with {systemArguments}");
                writer.WriteEndObject();
            }),
        };
    }

    private static JsonObject WithApp(JsonObject sameArguments, string process)
    {
        var arguments = new JsonObject { ["app"] = process };
        foreach ((string name, JsonNode? value) in sameArguments)
            arguments[name] = value?.DeepClone();
        return arguments;
    }

    /// <summary>
    /// Uso 81: the one application with audio whose names match what was said, by form only: a word said (four letters
    /// or more) inside one of its names, or one of its names (three or more) inside what was said, folded (lower case,
    /// no accents, letters and digits). Its names are its process, the name Windows shows for it and that name's forms in
    /// the name-equivalence data (<see cref="ApplicationAliases.FormsOf"/>). Null when none matches, or more than one.
    /// </summary>
    internal static AudioSessionProgram? NameHolder(string said, IReadOnlyList<AudioSessionProgram> programs)
    {
        string whole = WindowsCoreAudioPlatform.FoldToken(said);
        string[] words = [.. said.Split(' ', '-', '_', '.', ',', '(', ')', '\'')
            .Select(WindowsCoreAudioPlatform.FoldToken)
            .Where(static word => word.Length >= 4)];
        if (whole.Length < 3)
            return null;
        AudioSessionProgram[] holders = [.. programs.Where(program => NamesOf(program)
            .Select(WindowsCoreAudioPlatform.FoldToken)
            .Any(name => name.Length >= 3 && (whole.Contains(name, StringComparison.Ordinal)
                || words.Any(word => name.Contains(word, StringComparison.Ordinal)))))];
        return holders.Length == 1 ? holders[0] : null;
    }

    private static IEnumerable<string> NamesOf(AudioSessionProgram program)
    {
        yield return program.Process;
        if (program.Name is not { } shown)
            yield break;
        yield return shown;
        foreach (string form in ApplicationAliases.FormsOf(shown))
            yield return form;
    }
}
