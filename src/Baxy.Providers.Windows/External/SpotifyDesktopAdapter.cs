using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class SpotifyDesktopAdapter : IExternalOperationAdapter
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _scriptPath;
    private readonly string _controlScriptPath;
    private readonly Func<string, bool> _processExists;
    private readonly Func<nint> _clientWindow;
    private readonly TimeProvider _time;

    private const string ClientProcess = "Spotify";

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

    // SP2 (tandas n3 del notebook: every search killed at this budget, its stage and its times lost with it): the script
    // ends its waits and says where it was this long before the budget, the margin covering its start and its answer.
    internal static readonly TimeSpan DeadlineMargin = TimeSpan.FromSeconds(5);

    internal static string ScriptDeadlineMs(TimeSpan budget) =>
        ((long)Math.Max(1, (budget - DeadlineMargin).TotalMilliseconds)).ToString(CultureInfo.InvariantCulture);

    internal SpotifyDesktopAdapter()
        : this(new ExternalProcessRunner(), Path.Combine(
            AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1"), Path.Combine(
            AppContext.BaseDirectory, "SpotifyMediaControl.ps1"),
            static name => Process.GetProcessesByName(name).Length > 0,
            clientWindow: ClientMainWindow)
    {
        InputLease = ForegroundLease.Shared;
    }

    /// <summary>
    /// v3 point 0, fix 3: both scripts bring the client up and drive it with real keys and clicks, so each call runs in
    /// one helper burst of this lease (after the person's pause; the front and the cursor given back after). Null runs
    /// them directly (the test seams, whose runners are fakes).
    /// </summary>
    internal IForegroundLease? InputLease { get; init; }

    internal SpotifyDesktopAdapter(
        IExternalProcessRunner runner,
        string? scriptPath = null,
        string? controlScriptPath = null,
        Func<string, bool>? processExists = null,
        TimeProvider? time = null,
        Func<nint>? clientWindow = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _scriptPath = scriptPath ?? "SpotifyDesktopAutomation.ps1";
        _controlScriptPath = controlScriptPath ?? "SpotifyMediaControl.ps1";
        // Test doubles drive the script with fixture output; only the product
        // constructor looks for the real client.
        _processExists = processExists ?? (static _ => true);
        _clientWindow = clientWindow ?? (static () => 0);
        _time = time ?? TimeProvider.System;
    }

    // The client's main window, which the host brings up before a retry (the script finds it by itself the same way).
    private static nint ClientMainWindow()
    {
        Process[] processes = Process.GetProcessesByName(ClientProcess);
        try
        {
            return processes.Select(static process => process.MainWindowHandle).FirstOrDefault(static handle => handle != 0);
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
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
        IInputBurst? burst = await LeasedInput.HelperBurstAsync(InputLease, cancellationToken).ConfigureAwait(false);
        if (burst?.Refusal is string refusal)
        {
            _ = burst.Restore();
            return ExternalJson.FailureBeforeEffect(operation, refusal);
        }

        using var restore = new BurstRestore(burst);
        var effectBoundary = new ExternalEffectBoundary();
        long started = _time.GetTimestamp();
        TimeSpan processBudget = ScriptBudget;
        bool searched = false;
        try
        {
            for (int attempt = 0; attempt < 2; attempt++)
            {
                effectBoundary.Cross(cancellationToken);
                TimeSpan budget = processBudget;
                (ExternalProcessResult? watched, bool interrupted) = await LeasedInput.WatchHelperAsync(
                    burst,
                    run => _runner.RunAsync(
                        "powershell.exe",
                        ["-NoProfile", "-NonInteractive", "-STA", "-File", _scriptPath,
                            .. (exactSelection ? [] : new[] { "-QueryWordsBase64", QueryWordsBase64.Value }),
                            "-DeadlineMs", ScriptDeadlineMs(budget),
                            Convert.ToBase64String(Encoding.UTF8.GetBytes(title)),
                            exactSelection ? "exact" : "query"],
                        budget,
                        run),
                    cancellationToken).ConfigureAwait(false);
                if (interrupted || watched is not { } process)
                    return effectBoundary.Failure(operation, LeasedInput.Interrupted, true);
                string? line = process.Output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
                    .LastOrDefault();
                if (line is null)
                    return effectBoundary.Failure(operation, "spotify_uia_process_failed");
                using JsonDocument response = JsonDocument.Parse(line);
                bool effect = response.RootElement.TryGetProperty("effectObserved", out JsonElement observed)
                    && observed.ValueKind == JsonValueKind.True;
                bool beforeSearch = StoppedBeforeSearch(response.RootElement);
                searched |= !beforeSearch;
                if (!response.RootElement.TryGetProperty("ok", out JsonElement ok)
                    || ok.ValueKind != JsonValueKind.True)
                {
                    string error = response.RootElement.TryGetProperty("error", out JsonElement errorValue)
                        ? errorValue.GetString() ?? "spotify_exact_selection_not_verified"
                        : "spotify_exact_selection_not_verified";
                    TimeSpan retryBudget = CallBudget
                        - _time.GetElapsedTime(started)
                        - TimeSpan.FromMilliseconds(400);
                    // The one retry of a call: a script stopped before its search (both modes; estab G4, the client's
                    // window never came to the front), or an exact selection's discovery that pressed nothing.
                    if (attempt == 0
                        && !effect
                        && (beforeSearch || (exactSelection && IsRetryableExactDiscoveryError(error)))
                        && retryBudget >= MinimumRetryBudget)
                    {
                        // M169: the retry gets only what is left of the call
                        // budget, never a second full script budget.
                        processBudget = retryBudget < ScriptBudget ? retryBudget : ScriptBudget;
                        // Estab G4: the script cannot win the right to set the foreground by itself; the host brings
                        // the client's window up the way a mission's act takes it, and the burst gives the person
                        // their front back when the call ends.
                        if (burst is not null)
                            _ = await burst.BringUpAsync(_clientWindow(), cancellationToken).ConfigureAwait(false);
                        // The child process exposes no cheaper readiness
                        // predicate after a terminal discovery failure. Keep
                        // this single bounded backoff instead of issuing a
                        // second UIA process probe against the same snapshot.
                        await Task.Delay(400, cancellationToken).ConfigureAwait(false);
                        continue;
                    }
                    // Estab G4: a call whose scripts all stopped before searching pressed nothing and changed nothing
                    // it was asked for: nothing can have played («no lo puse», never «no sé si se puso»).
                    ExternalCapabilityReceipt failure = !searched && !effect
                        ? ExternalJson.FailureBeforeEffect(operation, error)
                        : effectBoundary.Failure(operation, error, effect);
                    return WithDiagnostic(failure, response.RootElement);
                }
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("provider", "spotify");
                    writer.WriteString("title", response.RootElement.TryGetProperty("title", out JsonElement observedTitle)
                        ? observedTitle.GetString() ?? title : title);
                    if (!exactSelection) writer.WriteString("query", title);
                    // Ronda 23 (t2-c01 «Fother Muckers» told as «los bunkers»): whether what plays was shown to be
                    // what the query asked for. False is a fact for the composer, never the request achieved; a
                    // script that does not say keeps the receipt without it.
                    if (!exactSelection && QueryMatch(response.RootElement) is bool matchesQuery)
                        writer.WriteBoolean("matchesQuery", matchesQuery);
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

    // The script's own diagnostic fields: where it stopped (stage) and why (detail: the exception or code it caught).
    // Private codes for the log, never a sentence for the person.
    private static readonly string[] DiagnosticFields = ["stage", "detail", "timings"];

    // A search whose press only resumed what the client had loaded also says what was pressed and what played.
    private static readonly string[] NotConfirmedFields =
        ["stage", "detail", "selectedControl", "beforeNowPlaying", "observedNowPlaying", "title"];

    internal const string QueryResultNotConfirmed = "spotify_query_result_not_confirmed";

    /// <summary>
    /// Ronda 19 (t1-c07 #1 «pon lo-fi para estudiar en spotify plis» → spotify_uia_failed with nothing to tell why):
    /// a failure carries the script's stage and detail as its result, and an unconfirmed search what was pressed and
    /// what played. A failure with none of them keeps no result.
    /// </summary>
    internal static ExternalCapabilityReceipt WithDiagnostic(ExternalCapabilityReceipt failure, JsonElement response)
    {
        string[] fields = failure.ErrorCode == QueryResultNotConfirmed ? NotConfirmedFields : DiagnosticFields;
        if (fields.All(field => !response.TryGetProperty(field, out JsonElement value)
                || value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString())))
        {
            return failure;
        }

        JsonElement diagnostic = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "spotify");
            foreach (string field in fields)
            {
                if (response.TryGetProperty(field, out JsonElement value)
                    && value.ValueKind == JsonValueKind.String
                    && !string.IsNullOrWhiteSpace(value.GetString()))
                {
                    string text = value.GetString()!.Trim();
                    writer.WriteString(field, text.Length > 300 ? text[..300] : text);
                }
            }

            writer.WriteEndObject();
        });
        return failure with { Result = diagnostic };
    }

    /// <summary>
    /// Ronda 24, revisión 2: the function words, medium words and purpose markers a query is compared with in the
    /// script (data query_function_words.v1.json, embedded), as the base64 of its UTF-8 text.
    /// </summary>
    internal static readonly Lazy<string> QueryWordsBase64 = new(static () =>
    {
        using Stream stream = typeof(SpotifyDesktopAdapter).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.QueryFunctionWords.json")
            ?? throw new InvalidOperationException("query_function_words_missing");
        using var buffer = new MemoryStream();
        stream.CopyTo(buffer);
        return Convert.ToBase64String(buffer.ToArray());
    });

    internal static bool? QueryMatch(JsonElement response) =>
        response.TryGetProperty("matchesQuery", out JsonElement value)
        && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            ? value.GetBoolean()
            : null;

    // The script's stage before it searches (and so before it presses anything): it only brought the client up and
    // looked for its search box.
    private const string StageBeforeSearch = "started";

    private static bool StoppedBeforeSearch(JsonElement response) =>
        response.TryGetProperty("stage", out JsonElement stage)
        && stage.ValueKind == JsonValueKind.String
        && stage.GetString() == StageBeforeSearch;

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
        if (!_processExists(ClientProcess))
        {
            return ExternalJson.FailureBeforeEffect(
                operation, spotifyNamed ? "spotify_client_not_running" : "media_session_not_found");
        }
        IInputBurst? burst = await LeasedInput.HelperBurstAsync(InputLease, cancellationToken).ConfigureAwait(false);
        if (burst?.Refusal is string refusal)
        {
            _ = burst.Restore();
            return ExternalJson.FailureBeforeEffect(operation, refusal);
        }

        using var restore = new BurstRestore(burst);
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            effectBoundary.Cross(cancellationToken);
            (ExternalProcessResult? watched, bool interrupted) = await LeasedInput.WatchHelperAsync(
                burst,
                run => _runner.RunAsync(
                    "powershell.exe",
                    ["-NoProfile", "-NonInteractive", "-STA", "-File", _controlScriptPath, action],
                    TimeSpan.FromSeconds(20),
                    run),
                cancellationToken).ConfigureAwait(false);
            if (interrupted || watched is not { } process)
                return effectBoundary.Failure(operation, LeasedInput.Interrupted, true);
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
