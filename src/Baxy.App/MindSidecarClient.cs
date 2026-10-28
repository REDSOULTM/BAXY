using System.Collections.Concurrent;
using System.ComponentModel;
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
/// Feria 2026-10-27: why the mind stopped being ready, or started anew. <see cref="Cause"/>: <see cref="ProcessEnded"/>
/// (its output ended; <see cref="ExitCode"/> once its process exited), a failed request's name
/// (<see cref="MindSidecarClient.ClassifyRequestFailure"/>) with its <see cref="Request"/> type, <c>startup.</c> and the
/// label of a start that failed (<see cref="MindStartupFailure.TraceLabel"/>), or the App's own start
/// (<see cref="AppStart"/>) and exit (<see cref="AppExit"/>, who asked for it, and the App's exit code). Never a request's
/// arguments.
/// </summary>
internal sealed record MindLoss(string Cause, string? Request = null, int? ExitCode = null)
{
    internal const string ProcessEnded = "process_ended";
    internal const string AppStart = "app_start";
    internal const string AppExit = "app_exit";
}

/// <summary>
/// The model's move in the native loop. <see cref="Kind"/>: <c>action</c> (one tool call: <see cref="Operation"/> with
/// its <see cref="Arguments"/>, which the kernel authorizes and the provider executes and verifies), <c>reply</c> (its
/// answer to the person), <c>question</c> (one question it asks the person), <c>silence</c> (a heartbeat that found
/// nothing needing attention), <see cref="Error"/> (the mind answered the request with an error: <see cref="Text"/> is its
/// code, or <c>invalid</c> when it is no stable label). The App runs what the model chose and publishes what it wrote; it
/// never rewrites either.
/// </summary>
internal sealed record MindStep(string Kind, string? Operation, JsonObject? Arguments, string Text)
{
    internal const string Error = "error";

    /// <summary>The operation the mind uses for the person's answer to a pending confirmation.</summary>
    internal const string ConfirmationAnswer = "confirmation.answer";
}

internal sealed record MindVoiceStatus(
    bool Available,
    bool InputAvailable,
    bool SttAvailable,
    bool Pending,
    bool? WakeAvailable = null,
    bool? SpeechAvailable = null);

/// <summary>
/// Reads the voice state again while the sidecar still reports it as
/// <c>pending</c> (its voice runtime is importing) or its answer did not come
/// (a slow read under load), until it is known. 2026-10-25 (spoken A/B
/// c11b-on1): it gave up after 60 reads, and an ear that loaded later under
/// load was never started and nothing said so. The mind always ends its load
/// (voice.py Voice._load); the read ends this by throwing once its mind is
/// gone. The delay is injected so the schedule is testable without a real clock.
/// </summary>
internal static class VoiceStatusSettling
{
    internal static readonly TimeSpan Interval = TimeSpan.FromSeconds(1);

    internal static async Task<MindVoiceStatus> UntilSettledAsync(
        Func<CancellationToken, Task<MindVoiceStatus?>> read,
        Func<TimeSpan, CancellationToken, Task> delay,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(read);
        ArgumentNullException.ThrowIfNull(delay);
        while (true)
        {
            await delay(Interval, cancellationToken).ConfigureAwait(false);
            if (await read(cancellationToken).ConfigureAwait(false) is { Pending: false } status)
            {
                return status;
            }
        }
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
    // Where the mind writes its trace (src/baxy_mind/__main__.py, trace_dir): the App keeps the mind's stderr beside it.
    internal const string TraceDirectoryEnvironmentVariable = "BAXY_RENEW_TRACE_DIR";
    internal const string StandardErrorLogName = "mind-stderr.log";
    // One model decision (prefix cached) takes about a second; the budget covers a cold cache after a restart.
    internal static readonly TimeSpan TurnRequestTimeout = TimeSpan.FromSeconds(30);
    // The mind waits up to 60 s for its ear to load before it answers a voice.start (voice.py Voice.start). With the
    // same 60 s here, a start it made at the end of that wait came after the App gave up, and the App stopped the
    // microphone the start had just opened (2026-10-25, c11b-on1): the App waits longer than the mind.
    internal static readonly TimeSpan VoiceStartTimeout = TimeSpan.FromSeconds(75);
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

    /// <summary>The mind's process while it runs (the rail reads the memory the model takes).</summary>
    public int? ProcessId => _sidecar?.Process is { HasExited: false } process ? process.Id : null;

    /// <summary>Why the last catalog handshake found the model down, or null.</summary>
    internal MindStartupFailure? LastStartupFailure { get; private set; }

    /// <summary>The mind runs the native loop (turn.decide, turn.continue, turn.confirm).</summary>
    public bool IsTurnAvailable => IsReady && _turnAvailable;

    /// <summary>Whether the mind speaks (its hello offers voice.speak): no speech request is sent otherwise.</summary>
    public bool IsVoiceAvailable => IsReady && _voiceAvailable;

    /// <summary>Transcripción de voz emitida por el sidecar (hilo del pump).</summary>
    public event Action<string>? TranscriptReceived;

    // Ronda final 18-19 (regla 3): the mind stopped being ready, so whoever shows it ready (or listening) is told why:
    // its process ended (its output pump returned, and its voice with it), or a failed request invalidated it with the
    // process still alive.
    public event Action<MindLoss>? ReadyLost;

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
                environment: environment,
                allowBreakaway: false,
                standardErrorLog: Path.Combine(TraceDirectory(), StandardErrorLogName)));
            _sidecar = sidecar;
            _pumpCancellation = new CancellationTokenSource();
            var helloCompletion = new TaskCompletionSource<JsonObject>(
                TaskCreationOptions.RunContinuationsAsynchronously);
            // Arreglos de uso real (2026-10-26): a start abandoned before the hello (the core's start failed and the
            // retry gave up on this mind) stopped waiting, and the pump's end faulted the hello with nobody left to see
            // it: one unobserved IOException per retry, «site unknown», no stack. The fault is observed here.
            _ = helloCompletion.Task.ContinueWith(
                static abandoned => _ = abandoned.Exception,
                CancellationToken.None,
                TaskContinuationOptions.OnlyOnFaulted | TaskContinuationOptions.ExecuteSynchronously,
                TaskScheduler.Default);
            _pump = PumpAsync(sidecar.Process, helloCompletion, _pumpCancellation.Token);
            _ = ReportEndAsync(_pump, sidecar.Process, _pumpCancellation.Token);

            JsonObject hello = await helloCompletion.Task
                .WaitAsync(startupCancellation.Token)
                .ConfigureAwait(false);
            if (Str(hello["protocol"]) != "baxy.mind.v1")
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
        bool ready = reply is not null
            && Str(reply["type"]) == "catalog.ready"
            && Number(reply["count"]) == capabilities.Count;
        return ready;
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
            var tool = new JsonObject
            {
                ["name"] = capability.Name,
                ["description"] = capability.Description,
                ["argumentsSchema"] = JsonNode.Parse(
                    capability.ArgumentsSchema.GetRawText()),
                ["risk"] = capability.Risk,
                // Feria 2026-10-27: what the model may say it can do (mind.py, AREAS), as the panel «Qué puedo hacer».
                ["group"] = FieldStepProjection.Group(capability.Name),
            };
            if (capability.Effects is { } effects)
            {
                // Al máximo 5.1: «corrige» never fills a tool with one (mind.py, CORRECTABLE_RISKS).
                tool["effects"] = new JsonArray([.. effects.Select(static effect => (JsonNode?)effect)]);
            }

            catalog.Add(tool);
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

    /// <summary>
    /// The person's words open a turn; the model answers with its first move. <paramref name="pendingConfirmation"/> is
    /// the call that waits for their «sí» when one does (its operation, and its arguments unless it is a memory call).
    /// </summary>
    public Task<MindStep?> DecideAsync(
        string text,
        JsonObject? pendingConfirmation,
        CancellationToken cancellationToken)
    {
        var request = new JsonObject { ["type"] = "turn.decide", ["text"] = text };
        if (pendingConfirmation is not null)
        {
            request["pendingConfirmation"] = pendingConfirmation;
        }

        return TurnRequestAsync(request, cancellationToken);
    }

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
        return reply is not null && Str(reply["type"]) == "turn.beat.ended";
    }

    /// <summary>
    /// The person's turn has been silent long enough for a notice (<see cref="SilenceNotice"/>): the phrase the model
    /// writes for the call the App is running, trimmed, or null when the mind has none now.
    /// </summary>
    internal async Task<string?> NoticeAsync(CancellationToken cancellationToken)
    {
        if (!IsTurnAvailable)
        {
            return null;
        }

        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "turn.notice" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "turn.notice.result"
            && Str(reply["notice"]) is { } notice && !string.IsNullOrWhiteSpace(notice)
                ? notice.Trim()
                : null;
    }

    /// <summary>The person pressed Sí or No: their answer enters the conversation as the confirmation call.</summary>
    public Task<MindStep?> ConfirmAsync(bool approve, string label, CancellationToken cancellationToken) =>
        TurnRequestAsync(
            new JsonObject { ["type"] = "turn.confirm", ["approve"] = approve, ["label"] = label },
            cancellationToken);

    /// <summary>The session's conversation as the mind holds it (calls and results included), or null.</summary>
    public async Task<JsonArray?> SessionExportAsync(CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "session.export" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "session.exported" && reply["conversation"] is JsonArray conversation
            ? (JsonArray)conversation.DeepClone()
            : null;
    }

    /// <summary>Gives the mind a kept session's conversation back, exactly as it was exported.</summary>
    public async Task<bool> SessionLoadAsync(JsonArray conversation, CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "session.load", ["conversation"] = conversation.DeepClone() },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "session.ready";
    }

    /// <summary>The person had BAXY forget everything or deleted every conversation: the mind's trace, its archive and
    /// the slot states a vision question set aside go (trace.forget, src/baxy_mind). Whether the mind said none is left.
    /// </summary>
    public async Task<bool> TraceForgetAsync(CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "trace.forget" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        bool cleared = reply is not null && Str(reply["type"]) == "trace.forgotten" && Flag(reply["cleared"]) == true;
        // P0.12: the mind's stderr log names the request that failed and its error, as the trace does: it goes with it.
        return (_sidecar?.ForgetStandardError()
            ?? BoundedStandardErrorLog.ForgetFiles(Path.Combine(TraceDirectory(), StandardErrorLogName))) && cleared;
    }

    /// <summary>The mind's trace folder, as the mind resolves it (src/baxy_mind/__main__.py, trace_dir).</summary>
    internal static string TraceDirectory() =>
        Environment.GetEnvironmentVariable(TraceDirectoryEnvironmentVariable) is { } given
            && !string.IsNullOrWhiteSpace(given)
                ? given.Trim()
                : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "renew");

    /// <summary>Push-to-talk let go: the direct request being heard ends now.</summary>
    public async Task<bool> VoiceReleaseAsync(TimeSpan timeout, CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.release" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "voice.released";
    }

    /// <summary>A new conversation: the model forgets the session's turns.</summary>
    public async Task<bool> NewSessionAsync(CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "session.new" },
            TurnRequestTimeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "session.ready";
    }

    private async Task<MindStep?> TurnRequestAsync(JsonObject request, CancellationToken cancellationToken)
    {
        if (!IsTurnAvailable)
        {
            return null;
        }

        return ParseStep(await RequestAsync(request, TurnRequestTimeout, cancellationToken,
            returnProtocolError: true).ConfigureAwait(false));
    }

    internal static MindStep? ParseStep(JsonObject? reply)
    {
        if (reply is not null && Str(reply["type"]) == "error")
        {
            return new MindStep(MindStep.Error, null, null, ShellTrace.SanitizeLabel(Str(reply["code"])));
        }

        if (reply is null || Str(reply["type"]) != "turn.result")
        {
            return null;
        }

        switch (Str(reply["kind"]))
        {
            // A name the model made up keeps the wire's «_» (the mind gives back the dotted name only of a catalog
            // tool): it goes on to the loop, which answers unknown_operation for the model to read, instead of the turn
            // failing with decision_unavailable.
            case "action" when Str(reply["operation"]) is { Length: > 0 and <= 256 } operation
                && operation.All(static c => char.IsAsciiLetterOrDigit(c) || c is '.' or '_' or '-'):
                return new MindStep(
                    "action",
                    operation,
                    reply["arguments"]?.DeepClone() as JsonObject ?? new JsonObject(),
                    string.Empty);
            case "clarify" when Str(reply["question"]) is { Length: > 0 } question:
                return new MindStep("question", null, null, question.Trim());
            case "conversation" when Str(reply["reply"]) is { Length: > 0 } text:
                return new MindStep("reply", null, null, text.Trim());
            case "silence":
                return new MindStep("silence", null, null, string.Empty);
            default:
                return null;
        }
    }

    public async Task<bool> VoiceStartAsync(
        string mode,
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        if (mode is not ("direct" or "wake"))
        {
            return false;
        }

        // 2026-10-22, review of the App: a start whose answer did not come in time (or that its caller gave up on) still
        // opens the microphone in the mind once it runs, while the App takes it as failed; a stop queued right behind
        // it closes it. A start the mind answered, even refusing it, needs none.
        JsonObject? reply;
        try
        {
            reply = await RequestAsync(
                new JsonObject { ["type"] = "voice.start", ["mode"] = mode },
                timeout,
                cancellationToken,
                returnProtocolError: true).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            _ = await VoiceStopAsync(timeout, CancellationToken.None).ConfigureAwait(false);
            throw;
        }

        if (reply is null)
        {
            _ = await VoiceStopAsync(timeout, CancellationToken.None).ConfigureAwait(false);
            return false;
        }

        return Str(reply["type"]) == "voice.started"
            && Str(reply["mode"]) == mode;
    }

    public async Task<bool> VoiceStopAsync(TimeSpan timeout, CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.stop" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "voice.stopped";
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
            || Str(reply["type"]) != "voice.status.result"
            || reply["status"] is not JsonObject status)
        {
            return null;
        }

        return new MindVoiceStatus(
            Flag(status["available"]) ?? false,
            Flag(status["input"]) ?? false,
            Flag(status["stt"]) ?? false,
            Flag(status["pending"]) ?? false,
            Flag(status["wake"]),
            Flag(status["tts"]));
    }

    public async Task<bool> VoiceSpeakAsync(
        string text,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        bool notice = false)
    {
        if (string.IsNullOrWhiteSpace(text) || text.Length > 8_192)
        {
            return false;
        }

        var request = new JsonObject { ["type"] = "voice.speak", ["text"] = text };
        if (notice)
        {
            // The voice tells the silence notice (SilenceNotice) by this mark, not by its words.
            request["notice"] = true;
        }

        JsonObject? reply = await RequestAsync(
            request,
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null
            && Str(reply["type"]) == "voice.speak.result"
            && Flag(reply["accepted"]) == true;
    }

    public async Task<bool> VoiceCancelAsync(
        TimeSpan timeout,
        CancellationToken cancellationToken)
    {
        JsonObject? reply = await RequestAsync(
            new JsonObject { ["type"] = "voice.cancel" },
            timeout,
            cancellationToken).ConfigureAwait(false);
        return reply is not null && Str(reply["type"]) == "voice.cancelled";
    }

    private async Task<JsonObject?> RequestAsync(
        JsonObject request,
        TimeSpan timeout,
        CancellationToken cancellationToken,
        bool returnProtocolError = false)
    {
        // Cancellation and speech are handled by the sidecar apart from model work and never wait for an inference.
        // 2026-10-22, review of the App: so are releasing push-to-talk and reading the voice's state (the mind answers
        // them on its reader, __main__.py), which here still queued behind a turn: a release let go of late.
        if (Str(request["type"]) is "voice.cancel" or "voice.speak" or "voice.release" or "voice.status")
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
        string requestType = Str(request["type"]) ?? "unknown";
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
            if (Str(reply["type"]) != "error")
            {
                return reply;
            }

            // P0.12: an error the mind answered left no trace; its code is a label (anything else reads «invalid»).
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "mind.request.error",
                $"{ShellTrace.SanitizeLabel(Str(reply["code"]))}.{requestType}.id.{requestId}");
            return returnProtocolError ? reply : null;
        }
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            string failure = ClassifyRequestFailure(exception, timeoutExpired);
            if (InvalidatesMind(failure, requestType) && _ready)
            {
                _ready = false;
                ReadyLost?.Invoke(new MindLoss(failure, requestType));
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
    /// three times). A closed mind was already marked by its reader. Nor is a late turn.notice: it waits behind the
    /// turn's own decision, which may write a long document (feria 2026-10-27).
    /// </summary>
    internal static bool InvalidatesMind(string failure, string requestType) =>
        failure switch
        {
            "request_io" => true,
            "request_timeout" => !requestType.StartsWith("voice.", StringComparison.Ordinal)
                && requestType != "turn.notice",
            _ => false,
        };

    // Revisión de calidad (2026-10-25): a field of the mind's line that is not of its type is no value, never an
    // exception (a cast threw out of the reader, which ended with the mind still running, and out of the request).
    private static string? Str(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    private static bool? Flag(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out bool flag) ? flag : null;

    private static int? Number(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out int number) ? number : null;

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

                switch (Str(message["type"]))
                {
                    case "hello":
                        helloCompletion.TrySetResult(message);
                        continue;
                    case "voice.transcript":
                        if (Str(message["text"]) is { Length: > 0 } transcript)
                        {
                            TranscriptReceived?.Invoke(transcript);
                        }

                        continue;
                    case "voice.event":
                        VoiceEventReceived?.Invoke(message);
                        continue;
                }

                if (Str(message["id"]) is { Length: > 0 } id
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

    // Feria 2026-10-27: the output can end a moment before the process does; its exit code is waited for that moment,
    // never when this side ended it (its shutdown releases the process meanwhile). Whoever shows the mind is told either way.
    private async Task ReportEndAsync(Task pump, Process process, CancellationToken shutdown)
    {
        await pump.ConfigureAwait(false);
        int? exitCode = null;
        try
        {
            if (!shutdown.IsCancellationRequested)
            {
                using var exited = new CancellationTokenSource(TimeSpan.FromSeconds(2));
                await process.WaitForExitAsync(exited.Token).ConfigureAwait(false);
                exitCode = process.ExitCode;
            }
        }
        catch (Exception exception) when (exception is OperationCanceledException or InvalidOperationException
            or Win32Exception or NotSupportedException)
        {
            // Still running (its reader failed), or already released: no exit code to tell.
        }
        finally
        {
            ReadyLost?.Invoke(new MindLoss(MindLoss.ProcessEnded, ExitCode: exitCode));
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
