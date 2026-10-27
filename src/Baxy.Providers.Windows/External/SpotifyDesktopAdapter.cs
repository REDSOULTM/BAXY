using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class SpotifyDesktopAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly IExternalProcessRunner _runner;
    private readonly string _scriptPath;
    private readonly Func<nint> _clientWindow;
    private readonly TimeProvider _time;
    private readonly bool _ownsRunner;

    private const string ClientProcess = "Spotify";

    // Revisión nb-q-apps2: the script's last line was not the object it answers with, or lacked its fields.
    internal const string ResponseUnreadable = "spotify_uia_response_unreadable";

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
        : this(Path.Combine(AppContext.BaseDirectory, "SpotifyDesktopAutomation.ps1"))
    {
    }

    // Renew al máximo (rendimiento): the script runs in one persistent PowerShell (PowerShellScriptWorker), so a call
    // after the first pays neither the PowerShell start nor its Add-Types (about half a second of each call).
    private SpotifyDesktopAdapter(string scriptPath)
        : this(new PowerShellScriptWorker(scriptPath), scriptPath, clientWindow: ClientMainWindow)
    {
        InputLease = ForegroundLease.Shared;
        _ownsRunner = true;
    }

    /// <summary>What runs the script (the tests check the product's is the persistent worker).</summary>
    internal IExternalProcessRunner ScriptRunner => _runner;

    /// <summary>Ends the script worker this adapter started (never a runner a test handed it).</summary>
    public void Dispose()
    {
        if (_ownsRunner && _runner is IDisposable runner)
            runner.Dispose();
    }

    /// <summary>
    /// v3 point 0, fix 3: the script brings the client up and drives it with real keys and clicks, so each call runs in
    /// one helper burst of this lease (after the person's pause; the front and the cursor given back after). Null runs
    /// them directly (the test seams, whose runners are fakes).
    /// </summary>
    internal IForegroundLease? InputLease { get; init; }

    internal SpotifyDesktopAdapter(
        IExternalProcessRunner runner,
        string? scriptPath = null,
        TimeProvider? time = null,
        Func<nint>? clientWindow = null)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _scriptPath = scriptPath ?? "SpotifyDesktopAutomation.ps1";
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
        "media.play.exact" or "media.play.query";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation, JsonElement arguments, CancellationToken cancellationToken)
    {
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
                // Revisión nb-q-apps2: a last line that is JSON but not the script's object (a stray value a module
                // printed) is a response the call cannot read, never an InvalidOperationException out of the adapter.
                if (response.RootElement.ValueKind != JsonValueKind.Object)
                    return effectBoundary.Failure(operation, ResponseUnreadable);
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
                // BAXY Renew audit 2026-10-15 (S4): an exact title the client was already playing is answered with
                // nothing pressed: the request already reached (alreadyPlaying, changed:false), never a press.
                bool alreadyPlaying = response.RootElement.TryGetProperty("alreadyPlaying", out JsonElement already)
                    && already.ValueKind == JsonValueKind.True;
                // Revisión nb-q-apps2: a success without the client's process id (or with one that is not a number) is
                // not the script's postread; what it pressed may have played, unconfirmed.
                if (!response.RootElement.TryGetProperty("processId", out JsonElement processValue)
                    || processValue.ValueKind != JsonValueKind.Number
                    || !processValue.TryGetInt32(out int processId))
                {
                    return WithDiagnostic(effectBoundary.Failure(operation, ResponseUnreadable, effect), response.RootElement);
                }
                // Uso real 2026-10-26 («Pon una canción de Queen»): the script told a search played while the
                // now-playing line still showed the track loaded before the press (La Chica de Humo), and that was
                // told as the search's result. A search's playback is verified only when what plays is another than
                // what showed before the press or holds a word of the search; otherwise it may be the loaded track
                // resumed: unconfirmed, with what plays carried for the model to tell.
                if (!exactSelection && !QueryPlaybackShown(title, response.RootElement))
                {
                    return WithDiagnostic(
                        effectBoundary.Failure(operation, QueryResultNotConfirmed, effect), response.RootElement);
                }
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("provider", "spotify");
                    if (!exactSelection) writer.WriteString("query", title);
                    // BAXY Renew audit 2026-10-15 (S2, S5, S7): only what the script observed, as it read it: the
                    // client's window title, the control it pressed, the now-playing line and, for a search, the
                    // observation that told the playback started. A field the script did not observe is left out,
                    // never filled with the requested title, and nothing says whether it is what was asked for.
                    bool changedPlaying = StringField(response.RootElement, "playbackEvidence") == NowPlayingChanged;
                    foreach (string field in ObservedFields)
                    {
                        if (response.RootElement.TryGetProperty(field, out JsonElement value)
                            && value.ValueKind == JsonValueKind.String
                            && !string.IsNullOrWhiteSpace(value.GetString()))
                        {
                            writer.WriteString(field, value.GetString());
                        }
                        // Auditoría de falsedades (F014, nb-t2-C-fals-s0): «now_playing_changed» with a now-playing
                        // that missed the query was told «ya estaba reproduciendo Around the World, así que no cambié
                        // nada»; what showed before the press is the change's other half, null when the line showed
                        // nothing.
                        else if (field == "beforeNowPlaying" && changedPlaying)
                        {
                            writer.WriteNull(field);
                        }
                    }
                    if (alreadyPlaying) writer.WriteBoolean("alreadyPlaying", true);
                    // e2e nb-29 («otra canción de los Bunkers»): the leftmost play control was a playlist's and Romeo
                    // Santos played, told as done. What plays is said when it holds none of the words searched.
                    if (!exactSelection && !QueryHeard(title, StringField(response.RootElement, "observedNowPlaying"),
                            StringField(response.RootElement, "title")))
                        writer.WriteBoolean("queryMatched", false);
                    writer.WriteString("playbackStatus", "playing");
                    writer.WriteNumber("processId", processId);
                    writer.WriteString("authority", "spotify_windows_uia_postread"); writer.WriteEndObject();
                });
                return alreadyPlaying
                    ? ExternalJson.Switched(operation, result, effect)
                    : ExternalJson.Success(operation, result, effectObserved: effect);
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

    // What a failure carries from the script: where it stopped (stage) and why (detail: the exception or code it
    // caught), private codes for the log, never a sentence for the person; and, once it pressed, what it pressed and
    // what the client showed playing before and after, as it read them.
    private static readonly string[] FailureFields =
        ["stage", "detail", "timings", "selectedControl", "beforeNowPlaying", "observedNowPlaying", "title"];

    /// <summary>
    /// Ronda 19 (t1-c07 #1 «pon lo-fi para estudiar en spotify plis» → spotify_uia_failed with nothing to tell why):
    /// a failure carries the script's stage and detail as its result. Round A (fault 2): every failure after the press
    /// (an unconfirmed search, a press the client never showed playing) says what was pressed and what played, so the
    /// model can tell the person what is sounding instead of a bare code. A failure with none of them keeps no result.
    /// </summary>
    internal static ExternalCapabilityReceipt WithDiagnostic(ExternalCapabilityReceipt failure, JsonElement response)
    {
        if (FailureFields.All(field => !response.TryGetProperty(field, out JsonElement value)
                || value.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(value.GetString())))
        {
            return failure;
        }

        JsonElement diagnostic = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("provider", "spotify");
            foreach (string field in FailureFields)
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

    // What a verified playback's receipt carries from the script, each only when the script observed it: the window's
    // title, the control pressed, the now-playing line before the press and after it (folded, as the script compares
    // them) and, in query mode, the observation that told the press started playback (BAXY Renew audit 2026-10-15, S2,
    // S5, S7; the line before, auditoría de falsedades F014).
    private static readonly string[] ObservedFields =
        ["title", "selectedControl", "beforeNowPlaying", "observedNowPlaying", "playbackEvidence"];

    // The script's playbackEvidence when what plays is another than what showed before the press.
    private const string NowPlayingChanged = "now_playing_changed";

    // The script's own code for a search whose press only resumed what the client had loaded (ronda 19).
    private const string QueryResultNotConfirmed = "spotify_query_result_not_confirmed";

    /// <summary>
    /// Whether a search's verified response shows the search playing: the now-playing line after the press is another
    /// than the one before it (both folded by the script), or what plays holds a word of the search (<see cref="QueryHeard"/>).
    /// </summary>
    internal static bool QueryPlaybackShown(string query, JsonElement response)
    {
        string observed = StringField(response, "observedNowPlaying").Trim();
        return !string.Equals(observed, StringField(response, "beforeNowPlaying").Trim(), StringComparison.Ordinal)
            || QueryHeard(query, observed, StringField(response, "title"));
    }

    private static string StringField(JsonElement response, string name) =>
        response.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    /// <summary>
    /// Whether what plays (the now-playing line and the window's title) holds a word of the search of four letters or
    /// more («los», «de» left out); true when the search has none or nothing was read.
    /// </summary>
    internal static bool QueryHeard(string query, string nowPlaying, string windowTitle)
    {
        string heard = Fold(nowPlaying + " " + windowTitle);
        string[] words = Fold(query).Split(' ', StringSplitOptions.RemoveEmptyEntries).Where(word => word.Length >= 4).ToArray();
        return words.Length == 0 || heard.Trim().Length == 0 || words.Any(word => heard.Contains(word, StringComparison.Ordinal));
    }

    private static string Fold(string value)
    {
        string form = value.Normalize(System.Text.NormalizationForm.FormD).ToLowerInvariant();
        var builder = new System.Text.StringBuilder(form.Length);
        foreach (char character in form)
        {
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                != System.Globalization.UnicodeCategory.NonSpacingMark)
                builder.Append(char.IsLetterOrDigit(character) ? character : ' ');
        }

        return builder.ToString();
    }

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
}
