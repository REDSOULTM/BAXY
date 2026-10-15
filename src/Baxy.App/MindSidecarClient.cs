using System.Collections.Concurrent;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>
/// r22 (2026-10-09): why the mind's model did not start, from the catalog
/// reply's <c>startup</c> object. Only stable causes cross; the server's own
/// startup lines stay in the mind's report (paths scrubbed there).
/// </summary>
internal sealed record MindStartupFailure(string Cause, long? ExitCode)
{
    internal static readonly IReadOnlySet<string> Causes = new HashSet<string>(StringComparer.Ordinal)
    {
        "vram_insuficiente",
        "ram_insuficiente",
        "proceso_salio",
        "tiempo",
    };

    /// <summary>The stable trace label: the cause, with the exit code when the server exited.</summary>
    internal string TraceLabel => ExitCode is { } code && Cause == "proceso_salio"
        ? Cause + "." + code.ToString(CultureInfo.InvariantCulture)
        : Cause;

    internal static MindStartupFailure? FromReply(JsonObject? reply)
    {
        if (reply is null
            || (string?)reply["type"] != "error"
            || reply["startup"] is not JsonObject startup
            || startup["cause"] is not JsonValue causeValue
            || !causeValue.TryGetValue(out string? cause)
            || !Causes.Contains(cause))
        {
            return null;
        }

        long? exitCode = startup["exitCode"] is JsonValue exitValue && exitValue.TryGetValue(out long code)
            ? code
            : null;
        return new MindStartupFailure(cause, exitCode);
    }
}

/// <summary>
/// The model's move in the native loop. <see cref="Kind"/>: <c>action</c> (one tool call: <see cref="Operation"/> with
/// its <see cref="Arguments"/>, which the kernel authorizes and the provider executes and verifies), <c>reply</c> (its
/// answer to the person), <c>question</c> (one question it asks the person), <c>silence</c> (a heartbeat that found
/// nothing needing attention). The App runs what the model chose and publishes what it wrote; it never rewrites either.
/// </summary>
internal sealed record MindStep(string Kind, string? Operation, JsonObject? Arguments, string Text)
{

    /// <summary>The operation the mind uses for the person's answer to a pending confirmation.</summary>
    internal const string ConfirmationAnswer = "confirmation.answer";
}

internal sealed record MindVoiceStatus(
    bool Available,
    bool InputAvailable,
    bool SttAvailable,
    bool VadAvailable,
    bool TtsAvailable,
    bool AecAvailable,
    bool DuckingAvailable,
    string Mode,
    bool Listening,
    bool Speaking,
    bool Pending = false);

/// <summary>
/// Reads the voice state again while the sidecar still reports it as
/// <c>pending</c> (its voice runtime is importing), a bounded number of times.
/// The delay is injected so the schedule is testable without a real clock.
/// </summary>
internal static class VoiceStatusSettling
{
    internal static readonly TimeSpan Interval = TimeSpan.FromSeconds(1);
    internal const int MaximumReads = 60;

    internal static async Task<MindVoiceStatus?> UntilSettledAsync(
        Func<CancellationToken, Task<MindVoiceStatus?>> read,
        Func<TimeSpan, CancellationToken, Task> delay,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(read);
        ArgumentNullException.ThrowIfNull(delay);
        MindVoiceStatus? status = null;
        for (int attempt = 0; attempt < MaximumReads; attempt++)
        {
            await delay(Interval, cancellationToken).ConfigureAwait(false);
            status = await read(cancellationToken).ConfigureAwait(false);
            if (status is { Pending: false })
            {
                return status;
            }
        }

        return status;
    }
}

/// <summary>The core's authenticated catalog the mind is configured with once the core said hello.</summary>
internal sealed record MindStartupCatalog(
    IReadOnlyList<OperationDescriptor> Capabilities,
    ApplicationCatalogSnapshot? ApplicationCatalog,
    GameCatalogSnapshot? GameCatalog);

/// <summary>
/// Client of the mind sidecar (baxy.mind.v1): a second local process on the same JSONL + Job Object boundary as the
/// core. It keeps the session's conversation with the model; this side sends the person's words, each verified result
/// and the person's answer to a confirmation, and reads back the model's next move. Optional and fail-closed: when it
/// is not configured, does not start or dies, every request returns null and nothing runs by another route.
/// </summary>
internal sealed class MindSidecarClient : IAsyncDisposable
{
    internal const string DisabledEnvironmentVariable = "BAXY_MIND_DISABLED";
    internal const string PythonEnvironmentVariable = "BAXY_MIND_PYTHON";
    internal const string PythonPathEnvironmentVariable = "BAXY_MIND_PYTHONPATH";
    internal const string GpuLayersEnvironmentVariable = "BAXY_MIND_NGL";
    // One model decision (prefix cached) takes about a second; the budget covers a cold cache after a restart.
    internal static readonly TimeSpan TurnRequestTimeout = TimeSpan.FromSeconds(30);
    private const int MaximumLineBytes = 1024 * 1024;

    private readonly ConcurrentDictionary<string, TaskCompletionSource<JsonObject>> _pending = new();
    private readonly SemaphoreSlim _writeLock = new(1, 1);
    // Model work is serial in Python. Its execution deadline starts only after
    // the previous request completes, not while waiting behind that request.
    private readonly SemaphoreSlim _requestLock = new(1, 1);
    private LocalJsonlSidecarProcess? _sidecar;
    private Task? _pump;
    private CancellationTokenSource? _pumpCancellation;
    private long _requestSequence;
    private volatile bool _ready;
    private volatile bool _turnAvailable;
    private volatile bool _voiceAvailable;
    private bool _disposed;

    public bool IsReady => _ready && _sidecar?.Process is { HasExited: false };

    /// <summary>Why the last catalog handshake found the model down, or null.</summary>
    internal MindStartupFailure? LastStartupFailure { get; private set; }

    /// <summary>The mind runs the native loop (turn.decide, turn.continue, turn.confirm).</summary>
    public bool IsTurnAvailable => IsReady && _turnAvailable;

    /// <summary>Whether the mind speaks (its hello offers voice.speak): no speech request is sent otherwise.</summary>
    public bool IsVoiceAvailable => IsReady && _voiceAvailable;

    /// <summary>Transcripción de voz emitida por el sidecar (hilo del pump).</summary>
    public event Action<string>? TranscriptReceived;

    /// <summary>Estado no sensible de la tubería de voz (hilo del pump).</summary>
    public event Action<JsonObject>? VoiceEventReceived;

    internal static bool IsDisabled =>
        string.Equals(
            Environment.GetEnvironmentVariable(DisabledEnvironmentVariable),
            "1",
            StringComparison.Ordinal);

    public static bool IsConfigured =>
        !IsDisabled
        && !string.IsNullOrWhiteSpace(
            Environment.GetEnvironmentVariable(PythonEnvironmentVariable));

    /// <summary>
    /// Ronda 22 (r18: «listo» 9-15 s before <c>startup.mind.ready</c>): the process and its model start while the
    /// core still says hello; <c>catalog.configure</c> goes once <paramref name="catalog"/> carries the core's
    /// authenticated catalog. A catalog that never comes (the core failed, cancelled) ends the start without a mind.
    /// Never throws to the caller: returns false and stays disabled on any failure.
    /// </summary>
    internal async Task<bool> TryStartAsync(
        Task<MindStartupCatalog> catalog,
        TimeSpan handshakeTimeout,
        CancellationToken cancellationToken)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentNullException.ThrowIfNull(catalog);
        if (_ready)
        {
            return true;
        }

        string? python = Environment.GetEnvironmentVariable(PythonEnvironmentVariable);
        if (string.IsNullOrWhiteSpace(python) || !File.Exists(python))
        {
            return false;
        }

        using var startupTimeout = new CancellationTokenSource(handshakeTimeout);
        using var startupCancellation = CancellationTokenSource.CreateLinkedTokenSource(
            cancellationToken,
            startupTimeout.Token);
        try
        {
            var environment = new Dictionary<string, string>(StringComparer.Ordinal);
            string? pythonPath =
                Environment.GetEnvironmentVariable(PythonPathEnvironmentVariable);
            if (!string.IsNullOrWhiteSpace(pythonPath))
            {
                environment["PYTHONPATH"] = pythonPath;
            }

            var sidecar = LocalJsonlSidecarProcess.Start(new LocalJsonlSidecarDefinition(
                "mind",
                python,
                Path.GetDirectoryName(python)!,
                arguments: ["-X", "utf8", "-m", "baxy_mind"],
                environment: environment));
            _sidecar = sidecar;
            _pumpCancellation = new CancellationTokenSource();
            var helloCompletion = new TaskCompletionSource<JsonObject>(
                TaskCreationOptions.RunContinuationsAsynchronously);
            _pump = PumpAsync(sidecar.Process, helloCompletion, _pumpCancellation.Token);

            JsonObject hello = await helloCompletion.Task
                .WaitAsync(startupCancellation.Token)
                .ConfigureAwait(false);
            if ((string?)hello["protocol"] != "baxy.mind.v1")
            {
                throw new InvalidDataException("El sidecar de mente no habla baxy.mind.v1.");
            }

            _ready = true;
            bool hasLlm = hello["models"] is JsonObject models
                && models["llm"] is JsonValue;
            JsonArray? requests = hello["requests"] as JsonArray;
            _turnAvailable = hasLlm
                && requests?.Any(static request => (string?)request == "turn.confirm") == true;
            _voiceAvailable = requests?.Any(static request => (string?)request == "voice.speak") == true;
            MindStartupCatalog inputs = await catalog
                .WaitAsync(startupCancellation.Token)
                .ConfigureAwait(false);
            if (!await ConfigureCatalogAsync(
                    inputs.Capabilities,
                    inputs.ApplicationCatalog,
                    inputs.GameCatalog,
                    handshakeTimeout,
                    startupCancellation.Token).ConfigureAwait(false))
            {
                throw new InvalidDataException(
                    "El sidecar de mente rechazó el catálogo autenticado del core.");
            }

            return true;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            await ShutdownQuietlyAsync().ConfigureAwait(false);
            return false;
        }
    }

    private async Task<bool> ConfigureCatalogAsync(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        GameCatalogSnapshot? gameCatalog,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject request = CreateCatalogConfigureRequest(
            capabilities,
            applicationCatalog,
            gameCatalog);
        JsonObject? reply = await RequestAsync(
            request,
            timeout,
            cancellationToken,
            returnProtocolError: true).ConfigureAwait(false);
        LastStartupFailure = MindStartupFailure.FromReply(reply);
        return reply is not null
            && (string?)reply["type"] == "catalog.ready"
            && (int?)reply["count"] == capabilities.Count;
    }

    internal static JsonObject CreateCatalogConfigureRequest(
        IReadOnlyList<OperationDescriptor> capabilities,
        ApplicationCatalogSnapshot? applicationCatalog,
        GameCatalogSnapshot? gameCatalog = null)
    {
        ArgumentNullException.ThrowIfNull(capabilities);
        var catalog = new JsonArray();
        foreach (OperationDescriptor capability in capabilities)
        {
            catalog.Add(new JsonObject
            {
                ["name"] = capability.Name,
                ["description"] = capability.Description,
                ["argumentsSchema"] = JsonNode.Parse(
                    capability.ArgumentsSchema.GetRawText()),
                ["risk"] = capability.Risk,
            });
        }

        var request = new JsonObject
        {
            ["type"] = "catalog.configure",
            ["capabilities"] = catalog,
        };
        if (applicationCatalog is not null)
        {
            ContractValidator.Validate(applicationCatalog);
            var names = new JsonArray();
            foreach (string name in applicationCatalog.Names)
            {
                names.Add(name);
            }

            request["applicationCatalog"] = new JsonObject
            {
                ["version"] = applicationCatalog.Version,
                ["verified"] = applicationCatalog.Verified,
                ["complete"] = applicationCatalog.Complete,
                ["names"] = names,
            };
        }
        if (gameCatalog is not null)
        {
            ContractValidator.Validate(gameCatalog);
            var entries = new JsonArray();
            foreach (GameCatalogEntry entry in gameCatalog.Entries)
            {
                entries.Add(new JsonObject
                {
                    ["provider"] = entry.Provider,
                    ["appId"] = entry.AppId,
                    ["name"] = entry.Name,
                });
            }

            request["gameCatalog"] = new JsonObject
            {
                ["version"] = gameCatalog.Version,
                ["verified"] = gameCatalog.Verified,
                ["complete"] = gameCatalog.Complete,
                ["entries"] = entries,
            };
        }

        return request;
    }

    /// <summary>The person's words open a turn; the model answers with its first move.</summary>
    public Task<MindStep?> DecideAsync(string text, CancellationToken cancellationToken) =>
        TurnRequestAsync(new JsonObject { ["type"] = "turn.decide", ["text"] = text }, cancellationToken);

    /// <summary>
    /// The verified result of the model's last call goes back to it; it answers with its next move. With
    /// <paramref name="final"/> the step budget is spent and the model answers in words from what the results show.
    /// </summary>
    public Task<MindStep?> ContinueAsync(
        string observation,
        bool final,
        bool beat,
        CancellationToken cancellationToken) =>
        TurnRequestAsync(
            new JsonObject
            {
                ["type"] = "turn.continue", ["observation"] = observation, ["final"] = final, ["beat"] = beat,
            },
            cancellationToken);

    /// <summary>The heartbeat: the moment as the App observed it; the model decides whether to intervene.</summary>
    public Task<MindStep?> BeatAsync(JsonObject context, CancellationToken cancellationToken) =>
        TurnRequestAsync(new JsonObject { ["type"] = "turn.beat", ["context"] = context }, cancellationToken);

    /// <summary>The heartbeat's turn ended: what it did joins the conversation unless it was silence.</summary>
    public async Task<bool> EndBeatAsync(CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "turn.beat.end" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "turn.beat.ended";
    }

    /// <summary>The person pressed Sí or No: their answer enters the conversation as the confirmation call.</summary>
    public Task<MindStep?> ConfirmAsync(bool approve, string label, CancellationToken cancellationToken) =>
        TurnRequestAsync(
            new JsonObject { ["type"] = "turn.confirm", ["approve"] = approve, ["label"] = label },
            cancellationToken);

    /// <summary>A new conversation: the model forgets the session's turns.</summary>
    public async Task<bool> NewSessionAsync(CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "session.new" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "session.ready";
    }

    private async Task<MindStep?> TurnRequestAsync(JsonObject request, CancellationToken cancellationToken)
    {
        if (!IsTurnAvailable)
        {
            return null;
        }

        return ParseStep(await RequestAsync(request, TurnRequestTimeout, cancellationToken).ConfigureAwait(false));
    }

    internal static MindStep? ParseStep(JsonObject? reply)
    {
        if (reply is null || (string?)reply["type"] != "turn.result")
        {
            return null;
        }

        switch ((string?)reply["kind"])
        {
            case "action" when (string?)reply["operation"] is { Length: > 0 and <= 256 } operation
                && operation.All(static c => char.IsAsciiLetterOrDigit(c) || c == '.'):
                return new MindStep(
                    "action",
                    operation,
                    reply["arguments"]?.DeepClone() as JsonObject ?? new JsonObject(),
                    string.Empty);
            case "clarify" when (string?)reply["question"] is { Length: > 0 } question:
                return new MindStep("question", null, null, question.Trim());
            case "conversation" when (string?)reply["reply"] is { Length: > 0 } text:
                return new MindStep("reply", null, null, text.Trim());
            case "silence":
                return new MindStep("silence", null, null, string.Empty);
            default:
                return null;
        }
    }

    public Task<bool> VoiceStartAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken) =>
        VoiceStartAsync("direct", timeout, cancellationToken);

    public async Task<bool> VoiceStartAsync(
        string mode,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        if (mode is not ("direct" or "wake"))
        {
            return false;
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.start", ["mode"] = mode },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && (string?)reply["type"] == "voice.started"
            && (string?)reply["mode"] == mode;
    }

    public async Task<bool> VoiceStopAsync(TimeSpan timeout, CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.stop" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "voice.stopped";
    }

    public async Task<MindVoiceStatus?> VoiceStatusAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.status" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        if (reply is null
            || (string?)reply["type"] != "voice.status.result"
            || reply["status"] is not JsonObject status)
        {
            return null;
        }

        return new MindVoiceStatus(
            (bool?)status["available"] ?? false,
            (bool?)status["input"] ?? false,
            (bool?)status["stt"] ?? false,
            (bool?)status["vad"] ?? false,
            (bool?)status["tts"] ?? false,
            (bool?)status["aec"] ?? false,
            (bool?)status["ducking"] ?? false,
            (string?)status["mode"] ?? "off",
            (bool?)status["listening"] ?? false,
            (bool?)status["speaking"] ?? false,
            (bool?)status["pending"] ?? false);
    }

    public async Task<bool> VoiceSpeakAsync(
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(text) || text.Length > 8_192)
        {
            return false;
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.speak", ["text"] = text },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && (string?)reply["type"] == "voice.speak.result"
            && (bool?)reply["accepted"] == true;
    }

    public async Task<bool> VoiceCancelAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.cancel" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && (string?)reply["type"] == "voice.cancelled";
    }

    private async Task<JsonObject?> RequestAsync(
        JsonObject request,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        bool returnProtocolError = false)
    {
        // Cancellation and speech are handled by the sidecar apart from model work and never wait for an inference.
        if ((string?)request["type"] is "voice.cancel" or "voice.speak" or "shutdown")
        {
            return await SendRequestAsync(request, timeout, returnProtocolError,
                cancellationToken).ConfigureAwait(false);
        }

        await _requestLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return await SendRequestAsync(request, timeout, returnProtocolError,
                cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _requestLock.Release();
        }
    }

    private async Task<JsonObject?> SendRequestAsync(
        JsonObject request,
        TimeSpan timeout,
        bool returnProtocolError,
        CancellationToken cancellationToken)
    {
        if (!IsReady)
        {
            return null;
        }

        string requestId = Interlocked.Increment(ref _requestSequence)
            .ToString(CultureInfo.InvariantCulture);
        request["id"] = requestId;
        string requestType = (string?)request["type"] ?? "unknown";
        string traceId = ShellTraceSink.TurnId;
        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "mind.request.start",
            $"{requestType}.id.{requestId}.budget_ms.{(long)timeout.TotalMilliseconds}");
        var completion = new TaskCompletionSource<JsonObject>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        if (!_pending.TryAdd(requestId, completion))
        {
            return null;
        }

        CancellationTokenSource? timeoutSource = null;
        bool timeoutExpired() => timeoutSource?.IsCancellationRequested == true;
        try
        {
            byte[] utf8Line = SerializeRequestToUtf8(request);
            if (utf8Line.Length > MaximumLineBytes)
            {
                return null;
            }

            LocalJsonlSidecarProcess? sidecar = _sidecar;
            Process? process = sidecar?.Process;
            if (sidecar is null || process is null || process.HasExited)
            {
                _ready = false;
                return null;
            }

            await _writeLock.WaitAsync(cancellationToken).ConfigureAwait(false);
            try
            {
                await sidecar.WriteUtf8LineAsync(utf8Line, cancellationToken)
                    .ConfigureAwait(false);
            }
            finally
            {
                _writeLock.Release();
            }

            timeoutSource = new CancellationTokenSource(timeout);
            using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken, timeoutSource.Token);
            JsonObject reply = await completion.Task.WaitAsync(linked.Token).ConfigureAwait(false);
            return (string?)reply["type"] == "error" && !returnProtocolError
                ? null
                : reply;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            string failure = ClassifyRequestFailure(exception, timeoutExpired);
            if (InvalidatesMind(failure, requestType))
            {
                _ready = false;
            }

            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId,
                "mind.request.failed", $"{failure}.{requestType}.id.{requestId}");
            return null;
        }
        finally
        {
            _pending.TryRemove(requestId, out _);
            timeoutSource?.Dispose();
        }
    }

    /// <summary>
    /// The honest name of a failed request: its own deadline expired
    /// (<c>request_timeout</c>), the mind closed under it (<c>mind_closed</c>,
    /// the reader cancels every pending reply when the sidecar ends, as at app
    /// close), or the transport failed (<c>request_io</c>).
    /// </summary>
    internal static string ClassifyRequestFailure(Exception exception, Func<bool> timeoutExpired) =>
        exception is not OperationCanceledException ? "request_io"
            : timeoutExpired() ? "request_timeout"
            : "mind_closed";

    /// <summary>
    /// Whether a failed request means the model transport can no longer be
    /// trusted. A late voice reply (status, speech, start, stop, cancel) is
    /// not a dead mind: the late reply is discarded and the next turn goes
    /// through (2026-10-08, v2-s02: a slow voice.status relaunched the mind
    /// three times). A closed mind was already marked by its reader.
    /// </summary>
    internal static bool InvalidatesMind(string failure, string requestType) =>
        failure switch
        {
            "request_io" => true,
            "request_timeout" => !requestType.StartsWith("voice.", StringComparison.Ordinal),
            _ => false,
        };

    internal static byte[] SerializeRequestToUtf8(JsonObject request)
    {
        ArgumentNullException.ThrowIfNull(request);
        return JsonSerializer.SerializeToUtf8Bytes(request);
    }

    private async Task PumpAsync(
        Process process,
        TaskCompletionSource<JsonObject> helloCompletion,
        CancellationToken cancellationToken)
    {
        try
        {
            var reader = new BoundedUtf8LineReader(
                process.StandardOutput.BaseStream,
                MaximumLineBytes);
            while (!cancellationToken.IsCancellationRequested)
            {
                BoundedUtf8Line? line = await reader.ReadAsync(cancellationToken).ConfigureAwait(false);
                if (line is null)
                {
                    break;
                }

                if (line.Value.TooLarge || line.Value.Utf8 is not { } utf8)
                {
                    continue;
                }

                JsonObject? message;
                try
                {
                    message = JsonNode.Parse(utf8) as JsonObject;
                }
                catch (JsonException)
                {
                    continue;
                }

                if (message is null)
                {
                    continue;
                }

                switch ((string?)message["type"])
                {
                    case "hello":
                        helloCompletion.TrySetResult(message);
                        continue;
                    case "voice.transcript":
                        if ((string?)message["text"] is { Length: > 0 } transcript)
                        {
                            TranscriptReceived?.Invoke(transcript);
                        }

                        continue;
                    case "voice.event":
                        VoiceEventReceived?.Invoke(message);
                        continue;
                }

                if ((string?)message["id"] is { Length: > 0 } id
                    && _pending.TryRemove(id, out var completion))
                {
                    completion.TrySetResult(message);
                }
            }
        }
        catch (Exception)
        {
            // The pump never throws: the mind becomes unavailable and every request returns null.
        }
        finally
        {
            _ready = false;
            helloCompletion.TrySetException(
                new IOException("El sidecar de mente terminó antes del saludo."));
            foreach (var pending in _pending)
            {
                if (_pending.TryRemove(pending.Key, out var completion))
                {
                    completion.TrySetCanceled(CancellationToken.None);
                }
            }
        }
    }

    private async Task ShutdownQuietlyAsync()
    {
        _ready = false;
        Task? pump = _pump;
        _pump = null;
        CancellationTokenSource? pumpCancellation = _pumpCancellation;
        _pumpCancellation = null;
        LocalJsonlSidecarProcess? sidecar = _sidecar;
        _sidecar = null;
        pumpCancellation?.Cancel();
        try
        {
            if (sidecar is not null)
            {
                await sidecar.DisposeAsync().ConfigureAwait(false);
            }
        }
        finally
        {
            await ObservePumpAsync(pump).ConfigureAwait(false);
            pumpCancellation?.Dispose();
        }
    }

    private static async Task ObservePumpAsync(Task? pump)
    {
        if (pump is null)
        {
            return;
        }

        try
        {
            await pump.ConfigureAwait(false);
        }
        catch (Exception)
        {
            // Pump failures never prevent closing the owned sidecar.
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        await ShutdownQuietlyAsync().ConfigureAwait(false);
        _writeLock.Dispose();
    }
}
