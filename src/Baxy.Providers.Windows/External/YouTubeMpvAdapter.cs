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

    public bool CanHandle(string operation) => operation == "media.play.youtube";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
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
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            Uri? stream = _streamResolver is null
                ? await ResolveStreamAsync(query, cancellationToken).ConfigureAwait(false)
                : await _streamResolver(query, cancellationToken).ConfigureAwait(false);
            if (stream is null)
                return ExternalJson.FailureBeforeEffect(
                    operation, "youtube_stream_not_resolved");
            effectBoundary.Cross(cancellationToken);
            StopActivePlayer();
            return await StartAndVerifyAsync(operation, query, stream, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "youtube_local_player_failed");
        }
        catch (Exception exception) when (exception is IOException or JsonException
            or InvalidOperationException or TimeoutException)
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

    private async ValueTask<Uri?> ResolveStreamAsync(
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
        start.ArgumentList.Add("--format");
        start.ArgumentList.Add("18/b[ext=mp4][protocol=https]/b[protocol=https]");
        start.ArgumentList.Add("--get-url");
        start.ArgumentList.Add("ytsearch1:" + query);
        using Process process = Process.Start(start) ?? throw new IOException("yt-dlp did not start.");
        Task<string> outputTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        Task<string> errorTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(45));
        await process.WaitForExitAsync(timeout.Token).ConfigureAwait(false);
        string output = await outputTask.ConfigureAwait(false);
        _ = await errorTask.ConfigureAwait(false);
        if (process.ExitCode != 0) return null;
        string? line = output.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries)
            .Select(static value => value.Trim())
            .FirstOrDefault();
        if (!Uri.TryCreate(line, UriKind.Absolute, out Uri? uri)
            || uri.Scheme != Uri.UriSchemeHttps
            || !(uri.Host.EndsWith("googlevideo.com", StringComparison.OrdinalIgnoreCase)
                || uri.Host.EndsWith("youtube.com", StringComparison.OrdinalIgnoreCase)))
            return null;
        return uri;
    }

    private async ValueTask<ExternalCapabilityReceipt> StartAndVerifyAsync(
        string operation,
        string query,
        Uri stream,
        CancellationToken cancellationToken)
    {
        string pipeName = "baxy-youtube-" + Guid.NewGuid().ToString("N");
        var start = new ProcessStartInfo(_mpvPath!)
        {
            UseShellExecute = false,
            CreateNoWindow = false,
        };
        foreach (string argument in new[]
        {
            "--no-config",
            "--really-quiet",
            "--force-window=yes",
            "--keep-open=no",
            "--title=BAXY YouTube",
            "--input-ipc-server=\\\\.\\pipe\\" + pipeName,
            stream.AbsoluteUri,
        })
        {
            start.ArgumentList.Add(argument);
        }
        Process player = Process.Start(start) ?? throw new IOException("mpv did not start.");
        try
        {
            using var pipe = new NamedPipeClientStream(
                ".", pipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
            using var connectTimeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            connectTimeout.CancelAfter(TimeSpan.FromSeconds(15));
            await pipe.ConnectAsync(connectTimeout.Token).ConfigureAwait(false);
            using var reader = new StreamReader(
                pipe, new UTF8Encoding(false), detectEncodingFromByteOrderMarks: false,
                bufferSize: 4_096, leaveOpen: true);
            using var writer = new StreamWriter(
                pipe, new UTF8Encoding(false), bufferSize: 4_096, leaveOpen: true)
            { AutoFlush = true };

            double? before = null;
            double? after = null;
            bool paused = true;
            for (int attempt = 0; attempt < 50; attempt++)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (player.HasExited) break;
                JsonElement time = await ReadPropertyAsync(
                    reader, writer, "time-pos", cancellationToken).ConfigureAwait(false);
                JsonElement pause = await ReadPropertyAsync(
                    reader, writer, "pause", cancellationToken).ConfigureAwait(false);
                if (time.ValueKind == JsonValueKind.Number && time.TryGetDouble(out double value))
                {
                    before ??= value;
                    after = value;
                }
                paused = pause.ValueKind != JsonValueKind.False;
                if (before.HasValue && after.HasValue && after.Value - before.Value >= 0.5 && !paused)
                {
                    _activePlayer = player;
                    return ExternalJson.Success(operation, ExternalJson.Create(json =>
                    {
                        json.WriteStartObject(); json.WriteNumber("version", 1);
                        json.WriteString("provider", "youtube"); json.WriteString("query", query);
                        json.WriteString("title", query); json.WriteString("playbackStatus", "playing");
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
        if (process is null) return;
        TryStop(process);
        process.Dispose();
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
