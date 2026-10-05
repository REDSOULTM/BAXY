using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class SpotifyDesktopAdapter : IExternalOperationAdapter
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _scriptPath;
    private readonly string _controlScriptPath;
    private readonly Func<string, bool> _processExists;
    private readonly TimeProvider _time;

    // The script has bounded 12.5 s discovery, 12 s search convergence (20 s
    // with one re-issued search when the page shows nothing playable, M169),
    // 12 s detail discovery and 15 s playback postread stages: 59.5 s. The
    // process budget must cover that verified path instead of aborting midway
    // through it. M86: the script's single re-press of a press that left no
    // trace happens inside the 15 s postread.
    internal static readonly TimeSpan ScriptBudget = TimeSpan.FromSeconds(65);

    // M169: the App waits 20 s for the core's answer and then 70 s more before
    // it drops the core (CoreProcessClient), so the whole call, the exact
    // retry included, ends inside 85 s.
    internal static readonly TimeSpan CallBudget = TimeSpan.FromSeconds(85);

    // A retry with less than this left could not finish even a warm search
    // (about 10 s) plus its playback postread; it is not started.
    internal static readonly TimeSpan MinimumRetryBudget = TimeSpan.FromSeconds(30);

    internal SpotifyDesktopAdapter()
        : this(new ExternalProcessRunner(), Path.Combine(
            AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1"), Path.Combine(
            AppContext.BaseDirectory, "SpotifyMediaControl.ps1"),
            static name => System.Diagnostics.Process.GetProcessesByName(name).Length > 0)
    {
    }

    internal SpotifyDesktopAdapter(
        IExternalProcessRunner runner,
        string? scriptPath = null,
        string? controlScriptPath = null,
        Func<string, bool>? processExists = null,
        TimeProvider? time = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _scriptPath = scriptPath ?? "SpotifyDesktopAutomation.ps1";
        _controlScriptPath = controlScriptPath ?? "SpotifyMediaControl.ps1";
        // Test doubles drive the script with fixture output; only the product
        // constructor looks for the real client.
        _processExists = processExists ?? (static _ => true);
        _time = time ?? TimeProvider.System;
    }

    public bool CanHandle(string operation) => operation is
        "media.play.exact" or "media.play.query" or "media.control";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation, JsonElement arguments, CancellationToken cancellationToken)
    {
        if (operation == "media.control")
        {
            return await ControlAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        }
        string provider;
        string title;
        bool exactSelection = operation == "media.play.exact";
        try
        {
            provider = ExternalJson.RequiredString(arguments, "provider");
            title = ExternalJson.RequiredString(
                arguments, exactSelection ? "title" : "query");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "spotify_uia_argument_invalid");
        }
        if (provider != "spotify") return ExternalJson.Failure(operation, "media_provider_not_supported");
        if (!File.Exists(_scriptPath)) return ExternalJson.Failure(operation, "spotify_uia_script_missing");
        var effectBoundary = new ExternalEffectBoundary();
        long started = _time.GetTimestamp();
        TimeSpan processBudget = ScriptBudget;
        try
        {
            for (int attempt = 0; attempt < 2; attempt++)
            {
                effectBoundary.Cross(cancellationToken);
                ExternalProcessResult process = await _runner.RunAsync(
                    "powershell.exe",
                    ["-NoProfile", "-NonInteractive", "-STA", "-File", _scriptPath,
                        Convert.ToBase64String(Encoding.UTF8.GetBytes(title)),
                        exactSelection ? "exact" : "query"],
                    processBudget,
                    cancellationToken).ConfigureAwait(false);
                string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                    .LastOrDefault();
                if (line is null)
                    return effectBoundary.Failure(operation, "spotify_uia_process_failed");
                using JsonDocument response = JsonDocument.Parse(line);
                bool effect = response.RootElement.TryGetProperty("effectObserved", out JsonElement observed)
                    && observed.ValueKind == JsonValueKind.True;
                if (!response.RootElement.TryGetProperty("ok", out JsonElement ok)
                    || ok.ValueKind != JsonValueKind.True)
                {
                    string error = response.RootElement.TryGetProperty("error", out JsonElement errorValue)
                        ? errorValue.GetString() ?? "spotify_exact_selection_not_verified"
                        : "spotify_exact_selection_not_verified";
                    TimeSpan retryBudget = CallBudget
                        - _time.GetElapsedTime(started)
                        - TimeSpan.FromMilliseconds(400);
                    if (attempt == 0
                        && exactSelection
                        && !effect
                        && IsRetryableExactDiscoveryError(error)
                        && retryBudget >= MinimumRetryBudget)
                    {
                        // M169: the retry gets only what is left of the call
                        // budget, never a second full script budget.
                        processBudget = retryBudget < ScriptBudget ? retryBudget : ScriptBudget;
                        // The child process exposes no cheaper readiness
                        // predicate after a terminal discovery failure. Keep
                        // this single bounded backoff instead of issuing a
                        // second UIA process probe against the same snapshot.
                        await Task.Delay(400, cancellationToken).ConfigureAwait(false);
                        continue;
                    }
                    return effectBoundary.Failure(operation, error, effect);
                }
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("provider", "spotify");
                    writer.WriteString("title", response.RootElement.TryGetProperty("title", out JsonElement observedTitle)
                        ? observedTitle.GetString() ?? title : title);
                    if (!exactSelection) writer.WriteString("query", title);
                    writer.WriteString("playbackStatus", "playing");
                    writer.WriteNumber("processId", response.RootElement.GetProperty("processId").GetInt32());
                    writer.WriteString("authority", "spotify_windows_uia_postread"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }
            return effectBoundary.Failure(
                operation, "spotify_exact_selection_not_verified");
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "spotify_uia_adapter_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "spotify_uia_adapter_failed");
        }
    }

    private static bool IsRetryableExactDiscoveryError(string error) => error is
        "spotify_exact_result_not_found"
        or "spotify_exact_play_control_not_found"
        or "spotify_uia_failed";

    private async ValueTask<ExternalCapabilityReceipt> ControlAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string action;
        try
        {
            action = ExternalJson.RequiredString(arguments, "action");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(
                operation, "media_control_action_invalid");
        }
        bool spotifyNamed = false;
        if (arguments.TryGetProperty("sourceApp", out JsonElement sourceApp)
            && sourceApp.ValueKind == JsonValueKind.String)
        {
            if (!sourceApp.GetString()!.Contains("spotify", StringComparison.OrdinalIgnoreCase))
            {
                return ExternalJson.Failure(operation, "media_source_app_not_spotify");
            }
            spotifyNamed = true;
        }
        if (action is not ("play" or "pause" or "next" or "previous" or "stop" or "toggle"))
        {
            return ExternalJson.Failure(operation, "media_control_action_invalid");
        }
        if (!File.Exists(_controlScriptPath))
        {
            return ExternalJson.Failure(operation, "spotify_uia_control_script_missing");
        }
        // 2026-09-22 (owner's turn 148): with no Spotify process the script died at
        // its first stage after the boundary was crossed, and the failure travelled
        // as an ambiguous effect that held the whole conversation. Nothing can have
        // happened in a client that is not running.
        // Tanda 6 «pasar al siguiente episodio» with nothing playing was told «el
        // cliente de Spotify no estaba abierto»: this automation is the last player
        // of the chain, reached only when no media session, local player or YouTube
        // tab answered. With Spotify not named and not running, what was found is
        // that nothing is playing; Spotify's absence is the answer only when the
        // person asked for Spotify.
        if (!_processExists("Spotify"))
        {
            return ExternalJson.FailureBeforeEffect(
                operation, spotifyNamed ? "spotify_client_not_running" : "media_session_not_found");
        }
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            effectBoundary.Cross(cancellationToken);
            ExternalProcessResult process = await _runner.RunAsync(
                "powershell.exe",
                ["-NoProfile", "-NonInteractive", "-STA", "-File", _controlScriptPath, action],
                TimeSpan.FromSeconds(20),
                cancellationToken).ConfigureAwait(false);
            string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                .LastOrDefault();
            if (line is null)
            {
                return effectBoundary.Failure(operation, "spotify_uia_control_process_failed");
            }
            using JsonDocument response = JsonDocument.Parse(line);
            bool effect = response.RootElement.TryGetProperty(
                "effectObserved", out JsonElement observed)
                && observed.ValueKind == JsonValueKind.True;
            if (!response.RootElement.TryGetProperty("ok", out JsonElement ok)
                || ok.ValueKind != JsonValueKind.True)
            {
                string error = response.RootElement.TryGetProperty(
                    "error", out JsonElement errorValue)
                    ? errorValue.GetString() ?? "spotify_uia_control_not_verified"
                    : "spotify_uia_control_not_verified";
                return effectBoundary.Failure(operation, error, effect);
            }
            string playbackStatus = response.RootElement.TryGetProperty(
                "playbackStatus", out JsonElement status)
                ? status.GetString() ?? "unknown"
                : "unknown";
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("provider", "spotify"); writer.WriteString("action", action);
                writer.WriteString("playbackStatus", playbackStatus);
                writer.WriteNumber("processId", response.RootElement.GetProperty("processId").GetInt32());
                writer.WriteString("authority", "spotify_windows_uia_postread"); writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effect);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "spotify_uia_control_adapter_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "spotify_uia_control_adapter_failed");
        }
    }
}
