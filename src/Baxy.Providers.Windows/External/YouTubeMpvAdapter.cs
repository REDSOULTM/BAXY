using System.Diagnostics;
using System.IO.Pipes;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class YouTubeMpvAdapter : IExternalOperationAdapter, IDisposable
{
    private readonly string? _mpvPath;
    private readonly string? _nodePath;
    private readonly Func<string, CancellationToken, ValueTask<Uri?>>? _streamResolver;
    private readonly string? _ytDlpPath;
    private readonly SemaphoreSlim _gate = new(1, 1);
    private Process? _activePlayer;
    private string? _activePipe;
    private string? _activeTitle;
    private string? _activeQuery;

    internal YouTubeMpvAdapter()
        : this(ResolveTool("BAXY_MPV_PATH", "mpv", "mpv.exe"),
            ResolveTool("BAXY_YTDLP_PATH", "yt-dlp", "yt-dlp.exe"),
            ResolveNode())
    {
    }

    internal YouTubeMpvAdapter(string? mpvPath, string? ytDlpPath, string? nodePath)
        : this(mpvPath, ytDlpPath, nodePath, streamResolver: null)
    {
    }

    internal YouTubeMpvAdapter(
        string? mpvPath,
        string? ytDlpPath,
        string? nodePath,
        Func<string, CancellationToken, ValueTask<Uri?>>? streamResolver)
    {
        _mpvPath = ExistingFullPath(mpvPath);
        _ytDlpPath = ExistingFullPath(ytDlpPath);
        _nodePath = ExistingFullPath(nodePath);
        _streamResolver = streamResolver;
    }

    // Renew al máximo (B-APP-7): how the player is started; a test reads its arguments or starts a stand-in.
    internal Func<ProcessStartInfo, Process?> StartPlayer { get; init; } = Process.Start;

    // Renew al máximo (B-APP-2): yt-dlp's own deadline and the one for the player's IPC to open; a test shortens them.
    internal TimeSpan ResolveTimeout { get; init; } = TimeSpan.FromSeconds(45);

    internal TimeSpan PlayerConnectTimeout { get; init; } = TimeSpan.FromSeconds(15);

    // Renew al máximo (6.7): one budget for the whole act (resolution, player, check and retry). yt-dlp's 45 s, the
    // IPC's 15 s and the ~30 s check, repeated by the retry, outlasted the App's wait for the core (20 + 70 s), which
    // then dropped it; 60 s keeps the act inside it with time for the browser, the next adapter, to try. A test
    // shortens it.
    internal TimeSpan PlaybackBudget { get; init; } = TimeSpan.FromSeconds(60);

    // Renew al máximo (6.7): the retry starts only with this much of the budget left; a fresh resolution and the first
    // half second of progress take about that, and with less it would only be cut before it could verify.
    private static readonly TimeSpan MinimumLeftForRetry = TimeSpan.FromSeconds(20);

    // Renew al máximo (B-APP-1): whether a system media session plays now; a test gives its own answer.
    internal Func<CancellationToken, ValueTask<bool>> SystemSessionPlays { get; init; } = SystemSessionPlaysAsync;

    // Renew al máximo (auditoría de flujos): the system media sessions its status names besides itself; a test gives
    // its own.
    internal Func<CancellationToken, ValueTask<IReadOnlyList<UserMediaSession>>> SystemSessions { get; init; } =
        static async cancellationToken => await MediaSessionCalls.ReadAsync(cancellationToken).ConfigureAwait(false);

    private static async ValueTask<bool> SystemSessionPlaysAsync(CancellationToken cancellationToken) =>
        (await MediaSessionCalls.ReadAsync(cancellationToken).ConfigureAwait(false))
            .Any(static session => session.PlaybackStatus == "playing");

    public bool CanHandle(string operation) =>
        operation is "media.play.youtube" or "media.status" or "media.control";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "media.status")
            return await StatusAsync(operation, cancellationToken).ConfigureAwait(false);
        if (operation == "media.control")
            return await ControlAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        string query;
        try
        {
            query = ExternalJson.RequiredString(arguments, "query");
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_query_invalid");
        }
        if (_mpvPath is null || _ytDlpPath is null)
            return ExternalJson.Failure(operation, "youtube_local_player_dependency_missing");
        if (Encoding.UTF8.GetByteCount(query) > 1_024)
            return ExternalJson.Failure(operation, "youtube_query_invalid");

        var effectBoundary = new ExternalEffectBoundary();
        using var budget = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        budget.CancelAfter(PlaybackBudget);
        var spent = Stopwatch.StartNew();
        try
        {
            await _gate.WaitAsync(budget.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            // Renew al máximo (6.7): the budget spent waiting for another playback: nothing was resolved or played.
            return ExternalJson.FailureBeforeEffect(operation, "youtube_stream_not_resolved");
        }
        try
        {
            Uri? stream;
            string? title = null;
            if (_streamResolver is null)
                (stream, title) = await ResolveStreamAsync(query, budget.Token).ConfigureAwait(false);
            else
                stream = await _streamResolver(query, budget.Token).ConfigureAwait(false);
            if (stream is null)
                return ExternalJson.FailureBeforeEffect(
                    operation, "youtube_stream_not_resolved");
            effectBoundary.Cross(budget.Token);
            StopActivePlayer();
            ExternalCapabilityReceipt receipt = await StartAndVerifyAsync(
                operation, query, title, stream, budget.Token).ConfigureAwait(false);
            if (!receipt.Verified && _streamResolver is null && PlaybackBudget - spent.Elapsed >= MinimumLeftForRetry)
            {
                // MUSIC1563: the same query that plays by hand stalled twice inside a
                // tanda; a fresh resolution lands on another media server. One retry.
                (Uri? again, string? againTitle) = await ResolveStreamAsync(query, budget.Token)
                    .ConfigureAwait(false);
                if (again is not null)
                {
                    StopActivePlayer();
                    receipt = await StartAndVerifyAsync(
                        operation, query, againTitle ?? title, again, budget.Token).ConfigureAwait(false);
                }
            }
            return receipt;
        }
        // Renew al máximo (B-APP-2): past the boundary, the player's own IPC deadline is the local player's failure as
        // much as the caller's cancel; it used to leave as an uncaught cancellation. (6.7) So is the budget's end.
        catch (OperationCanceledException) when (effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "youtube_local_player_failed");
        }
        // Renew al máximo (6.7): the budget spent before anything played is a stream not resolved: the browser tries.
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.FailureBeforeEffect(operation, "youtube_stream_not_resolved");
        }
        // Revisión de calidad (nb-q-apps): a yt-dlp or mpv that Windows refuses to run (Smart App Control, a file
        // quarantined, not an executable) throws Win32Exception from Process.Start; it left the adapter, the dispatch
        // never tried the browser, and the turn failed with an exception instead of a receipt.
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception)
        {
            return effectBoundary.Failure(operation, "youtube_local_player_failed");
        }
        finally
        {
            _gate.Release();
        }
    }

    public void Dispose()
    {
        _gate.Wait();
        try { StopActivePlayer(); }
        finally { _gate.Release(); _gate.Dispose(); }
    }

    // MUSIC1553: the receipt used to carry the query as the title; the reply
    // then could only echo the request. yt-dlp prints the resolved video's
    // title before the stream URL, so the reply can name what is playing.
    private async ValueTask<(Uri? Stream, string? Title)> ResolveStreamAsync(
        string query,
        CancellationToken cancellationToken)
    {
        var start = new ProcessStartInfo(_ytDlpPath!)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        start.ArgumentList.Add("--no-warnings");
        start.ArgumentList.Add("--no-playlist");
        if (_nodePath is not null)
        {
            start.ArgumentList.Add("--js-runtimes");
            start.ArgumentList.Add("node:" + _nodePath);
        }
        // MUSIC1553: the default (android_vr) client's stream URLs answer 403 to the
        // player's own HTTP client; the android client's URLs play directly in mpv.
        start.ArgumentList.Add("--extractor-args");
        start.ArgumentList.Add("youtube:player_client=android");
        // MUSIC1559: without this the title reaches us in the console code page
        // («�ltimo» for «Último») and the reply can never quote it exactly.
        start.ArgumentList.Add("--encoding");
        start.ArgumentList.Add("utf-8");
        start.ArgumentList.Add("--format");
        start.ArgumentList.Add("140/bestaudio[ext=m4a][protocol=https]/18/b[ext=mp4][protocol=https]/b[protocol=https]");
        start.ArgumentList.Add("--print");
        start.ArgumentList.Add("title");
        start.ArgumentList.Add("--print");
        start.ArgumentList.Add("urls");
        start.ArgumentList.Add("ytsearch1:" + query);
        using Process process = Process.Start(start) ?? throw new IOException("yt-dlp did not start.");
        HelperProcessJob.Assign(process);
        Task<string> outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(ResolveTimeout);
        try
        {
            await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            // Renew al máximo (B-APP-2): yt-dlp still running is ended, never left behind; its own deadline is a
            // stream not resolved (nothing played yet, so the browser gets its try), the caller's cancel stays one.
            TryStop(process);
            if (cancellationToken.IsCancellationRequested)
                throw;
            return (null, null);
        }
        string output = await outputTask.ConfigureAwait(false);
        _ = await errorTask.ConfigureAwait(false);
        if (process.ExitCode != 0) return (null, null);
        string[] lines = output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(static value => value.Trim())
            .Where(static value => value.Length > 0)
            .ToArray();
        // Printed in argument order: the title line, then the URL line(s).
        string? line = lines.FirstOrDefault(static value =>
            value.StartsWith("https://", StringComparison.OrdinalIgnoreCase));
        string? title = lines.FirstOrDefault(static value =>
            !value.StartsWith("https://", StringComparison.OrdinalIgnoreCase));
        if (!Uri.TryCreate(line, UriKind.Absolute, out Uri? uri)
            || uri.Scheme != Uri.UriSchemeHttps
            || !(uri.Host.EndsWith("googlevideo.com", StringComparison.OrdinalIgnoreCase)
                || uri.Host.EndsWith("youtube.com", StringComparison.OrdinalIgnoreCase)))
            return (null, null);
        if (title is not null && Encoding.UTF8.GetByteCount(title) > 512)
            title = null;
        return (uri, title);
    }

    private async ValueTask<ExternalCapabilityReceipt> StartAndVerifyAsync(
        string operation,
        string query,
        string? title,
        Uri stream,
        CancellationToken cancellationToken)
    {
        string pipeName = "baxy-youtube-" + Guid.NewGuid().ToString("N");
        var start = new ProcessStartInfo(_mpvPath!)
        {
            UseShellExecute = false,
            CreateNoWindow = false,
        };
        // MUSIC1567: audio only, so no GPU surface competes with the language model and the
        // stream is the small audio one. Renew al máximo (B-APP-7): no log of the player's own
        // (it kept the stream's URL, the person's address in it, and nothing read it).
        foreach (string argument in new[]
        {
            "--no-config",
            "--really-quiet",
            "--force-window=yes",
            "--keep-open=no",
            "--vid=no",
            "--title=BAXY YouTube",
            "--input-ipc-server=\\\\.\\pipe\\" + pipeName,
            stream.AbsoluteUri,
        })
        {
            start.ArgumentList.Add(argument);
        }
        Process player = StartPlayer(start) ?? throw new IOException("mpv did not start.");
        HelperProcessJob.Assign(player);
        try
        {
            using var pipe = new NamedPipeClientStream(
                ".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
            using var connectTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            connectTimeout.CancelAfter(PlayerConnectTimeout);
            await pipe.ConnectAsync(connectTimeout.Token).ConfigureAwait(false);
            using var reader = new StreamReader(
                pipe, new UTF8Encoding(false), detectEncodingFromByteOrderMarks: false,
                bufferSize: 4_096, leaveOpen: true);
            using var writer = new StreamWriter(
                pipe, new UTF8Encoding(false), bufferSize: 4_096, leaveOpen: true)
            { AutoFlush = true };

            double? before = null;
            double? after = null;
            double? readerBefore = null;
            double? readerAfter = null;
            bool paused = true;
            // MUSIC1559: a two-hour mix took longer than 50 × 250 ms to reach
            // its first half second; the window is now about thirty seconds.
            for (int attempt = 0; attempt < 120; attempt++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (player.HasExited) break;
                JsonElement time = await ReadPropertyAsync(
                    reader, writer, "time-pos", cancellationToken).ConfigureAwait(false);
                JsonElement pause = await ReadPropertyAsync(
                    reader, writer, "pause", cancellationToken).ConfigureAwait(false);
                // MUSIC1567: on this laptop the WASAPI clock can stay at zero while
                // the audio is being consumed (time-pos ≈ 0.0001 for a playing
                // stream); the demuxer's reader position still advances in real
                // time, so either clock proves playback.
                JsonElement cacheState = await ReadPropertyAsync(
                    reader, writer, "demuxer-cache-state", cancellationToken).ConfigureAwait(false);
                if (time.ValueKind == JsonValueKind.Number && time.TryGetDouble(out double value))
                {
                    before ??= value;
                    after = value;
                }
                if (cacheState.ValueKind == JsonValueKind.Object
                    && cacheState.TryGetProperty("reader-pts", out JsonElement readerPts)
                    && readerPts.ValueKind == JsonValueKind.Number
                    && readerPts.TryGetDouble(out double readerValue))
                {
                    readerBefore ??= readerValue;
                    readerAfter = readerValue;
                }
                paused = pause.ValueKind != JsonValueKind.False;
                bool clockAdvanced = before.HasValue && after.HasValue && after.Value - before.Value >= 0.5;
                bool readerAdvanced = readerBefore.HasValue && readerAfter.HasValue && readerAfter.Value - readerBefore.Value >= 0.5;
                if ((clockAdvanced || readerAdvanced) && !paused)
                {
                    _activePlayer = player;
                    _activePipe = pipeName;
                    _activeTitle = title;
                    _activeQuery = query;
                    return ExternalJson.Success(operation, ExternalJson.Create(json =>
                    {
                        json.WriteStartObject(); json.WriteNumber("version", 1);
                        json.WriteString("provider", "youtube"); json.WriteString("query", query);
                        json.WriteString("title", title ?? query); json.WriteString("playbackStatus", "playing");
                        // Ronda final 31 (regla 3): the player asks for the audio format only, in its own window.
                        json.WriteBoolean("audioOnly", true); json.WriteString("window", "BAXY YouTube");
                        json.WriteBoolean("titleObserved", title is not null);
                        json.WriteString("progressClock", clockAdvanced ? "audio_clock" : "demuxer_reader");
                        json.WriteNumber("processId", player.Id);
                        json.WriteString("authority", "yt_dlp_mpv_ipc_postread");
                        json.WriteEndObject();
                    }), effectObserved: true);
                }
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            }
            return ExternalJson.Failure(operation, "youtube_mpv_playback_not_verified", true);
        }
        finally
        {
            if (!ReferenceEquals(_activePlayer, player))
            {
                TryStop(player);
                player.Dispose();
            }
        }
    }

    private static async ValueTask<JsonElement> ReadPropertyAsync(
        StreamReader reader,
        StreamWriter writer,
        string property,
        CancellationToken cancellationToken)
    {
        int requestId = Random.Shared.Next(1, int.MaxValue);
        await writer.WriteLineAsync(
            $$"""{"command":["get_property","{{property}}"],"request_id":{{requestId}}}""")
            .ConfigureAwait(false);
        for (int message = 0; message < 256; message++)
        {
            string? line = await reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
            if (line is null) throw new IOException("mpv IPC closed.");
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            if (root.TryGetProperty("request_id", out JsonElement id)
                && id.TryGetInt32(out int actual) && actual == requestId)
            {
                if (root.TryGetProperty("error", out JsonElement error)
                    && error.GetString() != "success")
                    return default;
                return root.TryGetProperty("data", out JsonElement data) ? data.Clone() : default;
            }
        }
        throw new IOException("mpv IPC response was not observed.");
    }

    private void StopActivePlayer()
    {
        Process? process = _activePlayer;
        _activePlayer = null;
        _activePipe = null;
        _activeTitle = null;
        _activeQuery = null;
        if (process is null) return;
        TryStop(process);
        process.Dispose();
    }

    private bool HasActivePlayer =>
        _activePlayer is { } player && _activePipe is not null && !player.HasExited;

    // MUSIC1593 «qué está sonando» after a local playback: the player's own
    // pause state and the title the receipt already named; SMTC never sees mpv.
    private async ValueTask<ExternalCapabilityReceipt> StatusAsync(
        string operation,
        CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!HasActivePlayer)
                return ExternalJson.FailureBeforeEffect(operation, "local_player_inactive");
            bool? paused = await ReadPauseAsync(cancellationToken).ConfigureAwait(false);
            if (paused is null)
                return ExternalJson.FailureBeforeEffect(operation, "local_player_ipc_unavailable");
            // Renew al máximo (B-APP-1): left paused while a system session plays, it is not what is playing.
            if (paused.Value && await SystemSessionPlays(cancellationToken).ConfigureAwait(false))
                return ExternalJson.FailureBeforeEffect(operation, "local_player_paused");
            // Renew al máximo (auditoría de flujos): the system's sessions are named too, as the system's status names
            // its others (6.1), so a session to control by sourceApp has its id; an unread list is no list.
            IReadOnlyList<UserMediaSession> others = [];
            try
            {
                others = await SystemSessions(cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is not OperationCanceledException)
            {
            }

            return ExternalJson.Success(operation, LocalResult(paused.Value ? "paused" : "playing", others),
                effectObserved: false);
        }
        finally
        {
            _gate.Release();
        }
    }

    // MUSIC1593 «pará la música»: stop ends the player; pause/play/toggle set
    // its pause property and read it back; next/previous have no meaning here.
    // How media.status names this player, and so how media.control's sourceApp names it.
    private const string SourceAppUserModelId = "BAXY YouTube (mpv)";

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
            return ExternalJson.FailureBeforeEffect(operation, "media_control_action_invalid");
        }
        // A player the model named (the sourceAppUserModelId media.status gave) is this one only by its own id: it
        // paused itself for «pausa Spotify» while it played, as it went first (BAXY Renew audit 2026-10-15).
        bool named = arguments.TryGetProperty("sourceApp", out JsonElement sourceApp)
            && sourceApp.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(sourceApp.GetString());
        if (named && !string.Equals(sourceApp.GetString(), SourceAppUserModelId, StringComparison.OrdinalIgnoreCase))
            return ExternalJson.FailureBeforeEffect(operation, "media_source_app_not_local_player");
        var effectBoundary = new ExternalEffectBoundary();
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!HasActivePlayer)
                return ExternalJson.FailureBeforeEffect(operation, "local_player_inactive");
            bool? current;
            try
            {
                current = await ReadPauseAsync(cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (action == "stop" && exception is IOException or JsonException)
            {
                // A player whose IPC fails is still stopped by ending it.
                current = null;
            }
            // Renew al máximo (B-APP-1): unnamed, a player left paused while a system session plays is not what the
            // request means («pausa la música» said «already paused» and the person's music played on): the next answers.
            if (!named && current == true && await SystemSessionPlays(cancellationToken).ConfigureAwait(false))
                return ExternalJson.FailureBeforeEffect(operation, "local_player_paused");
            // Renew al máximo (auditoría de flujos): a skip is not this player's; the refusal says what it plays (a read:
            // nothing is sent), so a later «no session» never tells the person nothing plays while it does.
            if (action is "next" or "previous")
            {
                return current is { } skipPaused
                    ? new ExternalCapabilityReceipt(operation, EffectObserved: false, Verified: false,
                        LocalResult(skipPaused ? "paused" : "playing"), "local_player_action_unsupported")
                    : ExternalJson.FailureBeforeEffect(operation, "local_player_ipc_unavailable");
            }
            if (action == "stop")
            {
                Process player = _activePlayer!;
                JsonElement stopped = LocalResult("stopped");
                _activePlayer = null;
                _activePipe = null;
                _activeTitle = null;
                _activeQuery = null;
                effectBoundary.Cross(cancellationToken);
                TryStop(player);
                bool exited = false;
                for (int attempt = 0; attempt < 20; attempt++)
                {
                    exited = player.HasExited;
                    if (exited) break;
                    await Task.Delay(100, cancellationToken).ConfigureAwait(false);
                }
                player.Dispose();
                return exited
                    ? ExternalJson.Success(operation, stopped, effectObserved: true)
                    : ExternalJson.Failure(operation, "local_player_stop_not_verified", effectObserved: true);
            }
            if (current is null)
                return ExternalJson.FailureBeforeEffect(operation, "local_player_ipc_unavailable");
            bool wanted = action switch
            {
                "pause" => true,
                "play" => false,
                _ => !current.Value,
            };
            effectBoundary.Cross(cancellationToken);
            bool? after = await SetPauseAsync(wanted, cancellationToken).ConfigureAwait(false);
            // A player already in the state asked for (paused on «pausa») is done with no effect of this call.
            return after == wanted
                ? ExternalJson.Switched(operation, LocalResult(wanted ? "paused" : "playing"), effectObserved: current.Value != wanted)
                : ExternalJson.Failure(operation, "local_player_pause_not_verified", effectObserved: true);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidOperationException or TimeoutException)
        {
            // BAXY Renew (notebook): once the command may have reached the player the failure is after it, so the
            // dispatch stops here and no other player is pressed by a request meant for this one.
            return effectBoundary.Failure(operation, "local_player_ipc_failed");
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>
    /// Renew al máximo (auditoría de flujos): pauses this player while it plays, before another playback (ronda 19 does
    /// so for the system's sessions BAXY left playing, which never include this one), and says what it paused: its
    /// sourceAppUserModelId and title. Null when nothing was playing here or the pause was not read back.
    /// </summary>
    internal async ValueTask<(string Source, string Title)?> PauseForAnotherPlaybackAsync(
        CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!HasActivePlayer
                || await ReadPauseAsync(cancellationToken).ConfigureAwait(false) != false
                || await SetPauseAsync(true, cancellationToken).ConfigureAwait(false) != true)
            {
                return null;
            }

            return (SourceAppUserModelId, _activeTitle ?? _activeQuery ?? string.Empty);
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidOperationException or TimeoutException)
        {
            // Nothing read back as paused: the new playback goes on.
            return null;
        }
        finally
        {
            _gate.Release();
        }
    }

    /// <summary>Plays again what <see cref="PauseForAnotherPlaybackAsync"/> paused, and says whether it reads playing.</summary>
    internal async ValueTask<bool> ResumeAfterAnotherPlaybackAsync(CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return HasActivePlayer && await SetPauseAsync(false, cancellationToken).ConfigureAwait(false) == false;
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidOperationException or TimeoutException)
        {
            return false;
        }
        finally
        {
            _gate.Release();
        }
    }

    private JsonElement LocalResult(string playbackStatus, IReadOnlyList<UserMediaSession>? others = null) =>
        ExternalJson.Create(json =>
    {
        json.WriteStartObject(); json.WriteNumber("version", 1);
        json.WriteString("provider", "youtube");
        json.WriteString("sourceAppUserModelId", SourceAppUserModelId);
        json.WriteString("title", _activeTitle ?? _activeQuery ?? "");
        json.WriteBoolean("titleObserved", _activeTitle is not null);
        if (_activeQuery is not null) json.WriteString("query", _activeQuery);
        json.WriteString("playbackStatus", playbackStatus);
        if (others is not null) WindowsMediaSessionAdapter.WriteOtherSessions(json, others);
        json.WriteString("authority", "local_youtube_player");
        json.WriteEndObject();
    });

    // Revisión de calidad (nb-q-apps): only the connect to the player's IPC had a deadline; a player that took the
    // connection and never answered (a frozen audio device, a stuck core) held the gate for good, and with it
    // media.status, media.control and the pause that runs before every other playback. One exchange has this long; past
    // it the player reads as unavailable (null), as a connection refused does.
    internal TimeSpan IpcExchangeTimeout { get; init; } = TimeSpan.FromSeconds(10);

    private async ValueTask<bool?> ReadPauseAsync(CancellationToken cancellationToken)
    {
        using var exchange = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        exchange.CancelAfter(IpcExchangeTimeout);
        try
        {
            return await ReadPauseOnceAsync(exchange.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    private async ValueTask<bool?> SetPauseAsync(bool paused, CancellationToken cancellationToken)
    {
        using var exchange = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        exchange.CancelAfter(IpcExchangeTimeout);
        try
        {
            return await SetPauseOnceAsync(paused, exchange.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return null;
        }
    }

    private async ValueTask<bool?> ReadPauseOnceAsync(CancellationToken cancellationToken)
    {
        (StreamReader reader, StreamWriter writer, NamedPipeClientStream pipe)? ipc =
            await ConnectIpcAsync(cancellationToken).ConfigureAwait(false);
        if (ipc is null) return null;
        (StreamReader reader, StreamWriter writer, NamedPipeClientStream pipe) = ipc.Value;
        using (pipe) using (reader) using (writer)
        {
            JsonElement pause = await ReadPropertyAsync(reader, writer, "pause", cancellationToken)
                .ConfigureAwait(false);
            return pause.ValueKind switch
            {
                JsonValueKind.True => true,
                JsonValueKind.False => false,
                _ => null,
            };
        }
    }

    private async ValueTask<bool?> SetPauseOnceAsync(bool paused, CancellationToken cancellationToken)
    {
        (StreamReader reader, StreamWriter writer, NamedPipeClientStream pipe)? ipc =
            await ConnectIpcAsync(cancellationToken).ConfigureAwait(false);
        if (ipc is null) return null;
        (StreamReader reader, StreamWriter writer, NamedPipeClientStream pipe) = ipc.Value;
        using (pipe) using (reader) using (writer)
        {
            int requestId = Random.Shared.Next(1, int.MaxValue);
            await writer.WriteLineAsync(
                $$"""{"command":["set_property","pause",{{(paused ? "true" : "false")}}],"request_id":{{requestId}}}""")
                .ConfigureAwait(false);
            for (int message = 0; message < 256; message++)
            {
                string? line = await reader.ReadLineAsync(cancellationToken).ConfigureAwait(false);
                if (line is null) return null;
                using JsonDocument document = JsonDocument.Parse(line);
                if (document.RootElement.TryGetProperty("request_id", out JsonElement id)
                    && id.TryGetInt32(out int actual) && actual == requestId)
                    break;
            }
            JsonElement pause = await ReadPropertyAsync(reader, writer, "pause", cancellationToken)
                .ConfigureAwait(false);
            return pause.ValueKind switch
            {
                JsonValueKind.True => true,
                JsonValueKind.False => false,
                _ => null,
            };
        }
    }

    private async ValueTask<(StreamReader, StreamWriter, NamedPipeClientStream)?> ConnectIpcAsync(
        CancellationToken cancellationToken)
    {
        if (_activePipe is null) return null;
        var pipe = new NamedPipeClientStream(".", _activePipe, PipeDirection.InOut, PipeOptions.Asynchronous);
        try
        {
            using var connectTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            connectTimeout.CancelAfter(TimeSpan.FromSeconds(5));
            await pipe.ConnectAsync(connectTimeout.Token).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or TimeoutException
            or OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            pipe.Dispose();
            return null;
        }
        var reader = new StreamReader(pipe, new UTF8Encoding(false), detectEncodingFromByteOrderMarks: false,
            bufferSize: 4_096, leaveOpen: true);
        var writer = new StreamWriter(pipe, new UTF8Encoding(false), bufferSize: 4_096, leaveOpen: true)
        { AutoFlush = true };
        return (reader, writer, pipe);
    }

    private static void TryStop(Process process)
    {
        try { if (!process.HasExited) process.Kill(entireProcessTree: true); }
        catch (InvalidOperationException) { }
    }

    private static string? ResolveTool(string environmentName, string directory, string file)
    {
        string? configured = Environment.GetEnvironmentVariable(environmentName);
        string[] candidates =
        [
            configured ?? string.Empty,
            Path.Combine(AppContext.BaseDirectory, "tools", directory, file),
            Path.GetFullPath(Path.Combine(
                AppContext.BaseDirectory, "..", "tools", directory, file)),
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static string? ResolveNode()
    {
        string? configured = Environment.GetEnvironmentVariable("BAXY_NODE_PATH");
        string[] candidates =
        [
            configured ?? string.Empty,
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "nodejs", "node.exe"),
        ];
        return candidates.FirstOrDefault(File.Exists);
    }

    private static string? ExistingFullPath(string? value) =>
        string.IsNullOrWhiteSpace(value) || !File.Exists(value) ? null : Path.GetFullPath(value);
}
