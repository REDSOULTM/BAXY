using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// Shared product admission, turn, session and public-event projection.
/// Field UI (WebView bridge) and the windowless conductor both call this
/// type. Origin policy stays on the UI adapter; this channel has none.
/// </summary>
internal interface IFieldEventSink
{
    bool Publish(JsonObject eventData);
}

internal sealed class CollectingFieldEventSink : IFieldEventSink
{
    private readonly List<JsonObject> _events = [];
    private readonly object _gate = new();

    internal IReadOnlyList<JsonObject> Snapshot()
    {
        lock (_gate)
        {
            return [.. _events];
        }
    }

    public bool Publish(JsonObject eventData)
    {
        ArgumentNullException.ThrowIfNull(eventData);
        lock (_gate)
        {
            _events.Add((JsonObject)eventData.DeepClone());
        }

        return true;
    }
}

/// <summary>
/// Declared publication-boundary injection for honest-terminal tests.
/// Production leaves <see cref="Mode"/> at <see cref="FieldPublicationInjectionMode.None"/>.
/// This is not an agent-mode policy bypass: admission, composition and
/// verification still run; only the public projection is altered.
/// </summary>
internal enum FieldPublicationInjectionMode
{
    None,
    Filter,
    SuppressFinal,
    Silence,
}

internal static class FieldPublicationInjection
{
    internal static FieldPublicationInjectionMode Mode { get; set; }

    internal static void Reset() => Mode = FieldPublicationInjectionMode.None;
}

/// <summary>
/// Declared composition-boundary injection for R07. Production leaves
/// <see cref="Mode"/> at <see cref="FieldCompositionInjectionMode.None"/>.
/// The request still enters through the common channel; only compose is altered.
/// </summary>
internal enum FieldCompositionInjectionMode
{
    None,
    Reject,
    Timeout,
    Exhaust,
}

internal static class FieldCompositionInjection
{
    internal const string EnvironmentVariable = "BAXY_COMPOSITION_INJECTION";

    internal static FieldCompositionInjectionMode Mode { get; set; }

    internal static void Reset()
    {
        Mode = FieldCompositionInjectionMode.None;
    }

    internal static FieldCompositionInjectionMode Resolve()
    {
        if (Mode != FieldCompositionInjectionMode.None)
        {
            return Mode;
        }

        return Environment.GetEnvironmentVariable(EnvironmentVariable) switch
        {
            "reject" => FieldCompositionInjectionMode.Reject,
            "timeout" => FieldCompositionInjectionMode.Timeout,
            "exhaust" => FieldCompositionInjectionMode.Exhaust,
            _ => FieldCompositionInjectionMode.None,
        };
    }
}

internal sealed class FieldProductChannel : IAsyncDisposable
{
    internal const int MaximumRequestBodyCharacters = 65_536;
    internal const int MaximumPathCharacters = 2_048;

    private readonly MainWindowViewModel _viewModel;
    private readonly IFieldEventSink _sink;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly CancellationTokenSource _channelLifetime = new();
    private readonly SynchronizationContext _uiContext;
    private readonly Timer _progressPulse;
    private readonly Timer _milestoneDue;
    private readonly string _sessionId = Guid.NewGuid().ToString("N")[..12];
    private string _sessionLabel = "current";
    private string _accessibilityMode = "normal";
    private long _activitySequence;
    private long _turnSequence;
    private FieldProgressNotice? _publishedProgress;
    private bool _progressPublished;
    private DateTimeOffset? _progressPublishedUtc;
    private bool _disposed;
    private int _admissionSequence;

    internal FieldProductChannel(
        MainWindowViewModel viewModel,
        IFieldEventSink sink,
        FieldTelemetrySampler telemetry,
        CancellationToken lifetimeCancellation)
    {
        _viewModel = viewModel ?? throw new ArgumentNullException(nameof(viewModel));
        _sink = sink ?? throw new ArgumentNullException(nameof(sink));
        _telemetry = telemetry ?? throw new ArgumentNullException(nameof(telemetry));
        _lifetimeCancellation = lifetimeCancellation;
        _uiContext = SynchronizationContext.Current ?? new SynchronizationContext();
        _viewModel.MessageAdded += OnMessageAdded;
        _viewModel.CompositionFailed += OnCompositionFailed;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _progressPulse = new Timer(
            _ => PostToUi(OnProgressPulse),
            null,
            Timeout.Infinite,
            Timeout.Infinite);
        _milestoneDue = new Timer(
            _ => PostToUi(OnMilestoneDue),
            null,
            Timeout.Infinite,
            Timeout.Infinite);
    }

    internal MainWindowViewModel ViewModel => _viewModel;

    internal string SessionId => _sessionId;

    internal string SessionLabel => _sessionLabel;

    internal int AdmissionCount => Volatile.Read(ref _admissionSequence);

    internal async Task<FieldHttpResponse> HandleHttpAsync(
        string method,
        string path,
        string? body)
    {
        method = (method ?? "GET").ToUpperInvariant();
        path ??= "/";
        if (path.Length > MaximumPathCharacters || body?.Length > MaximumRequestBodyCharacters)
        {
            return Error("request_too_large", 413);
        }

        string route = path.Split('?', 2)[0];
        if (method == "GET" && route == "/agent/status")
        {
            return Json(new JsonObject
            {
                ["built"] = _viewModel.IsReady,
                ["healthy"] = _viewModel.IsReady && !_viewModel.HasStartupError,
                ["ready"] = _viewModel.IsReady && !_viewModel.IsBusy,
            });
        }

        if (method == "GET" && route == "/model")
        {
            return Json(ModelInfo());
        }

        if (method == "GET" && route == "/metrics")
        {
            FieldMetricSnapshot metrics = await _telemetry
                .SampleAsync(_lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(MetricsJson(metrics));
        }

        if (method == "GET" && route == "/hardware"
            || method == "POST" && route == "/hardware/redetect")
        {
            FieldHardwareSnapshot hardware = await _telemetry
                .HardwareAsync(_lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(HardwareJson(hardware));
        }

        if (method == "GET" && route == "/surfaces")
        {
            return Json(Surfaces());
        }

        if (method == "GET" && route == "/voice/status")
        {
            return Json(VoiceStatus());
        }

        if (method == "POST" && route == "/voice/start")
        {
            if (!FieldBridgeContract.TryAcceptVoiceControl(
                    _viewModel.IsReady,
                    out string voiceError,
                    out int voiceStatus))
            {
                return Error(voiceError, voiceStatus);
            }

            bool running = _viewModel.IsWakeListening
                || await _viewModel.SetWakeVoiceAsync(true, _lifetimeCancellation)
                    .ConfigureAwait(true);
            return Json(new JsonObject
            {
                ["ok"] = running,
                ["running"] = running,
                ["last_error"] = running ? null : "voice_unavailable",
            }, running ? 200 : 503);
        }

        if (method == "POST" && route == "/voice/stop")
        {
            bool stopped = await _viewModel
                .SetWakeVoiceAsync(false, _lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = stopped, ["running"] = !stopped },
                stopped ? 200 : 503);
        }

        if (method == "POST" && route == "/voice/trigger")
        {
            if (!FieldBridgeContract.TryAcceptVoiceControl(
                    _viewModel.IsReady,
                    out string triggerError,
                    out int triggerStatus))
            {
                return Error(triggerError, triggerStatus);
            }

            bool running = await _viewModel
                .StartDirectVoiceAsync(_lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = running, ["running"] = running },
                running ? 200 : 503);
        }

        if (method == "POST" && route == "/turn")
        {
            return await HandleTurnAsync(body).ConfigureAwait(true);
        }

        if (method == "POST" && route == "/activity")
        {
            JsonObject? payload = ParseBody(body);
            string source = NormalizeActivitySource((string?)payload?["src"]);
            string text = ((string?)payload?["msg"] ?? string.Empty).Trim();
            if (text.Length > 0)
            {
                PostActivity(source, text);
            }

            return Json(new JsonObject { ["ok"] = true });
        }

        if (method == "POST" && route == "/log/clear")
        {
            Publish(new JsonObject { ["type"] = "log_clear" });
            return FieldHttpResponse.Empty();
        }

        if (method == "GET" && route == "/sessions")
        {
            return Json(Sessions());
        }

        if (method == "POST" && route == "/sessions/new")
        {
            if (!_viewModel.StartNewUiSession())
            {
                return Error("turn_in_progress", 409);
            }

            _sessionLabel = "current";
            Publish(new JsonObject { ["type"] = "log_clear" });
            Publish(SessionEvent());
            return Json(new JsonObject { ["ok"] = true, ["id"] = _sessionId });
        }

        if (method == "POST" && route == "/sessions/load")
        {
            JsonObject? payload = ParseBody(body);
            return string.Equals((string?)payload?["id"], _sessionId, StringComparison.Ordinal)
                ? Json(new JsonObject { ["ok"] = true })
                : Error("session_not_found", 404);
        }

        if (method == "POST" && route == "/sessions/rename")
        {
            JsonObject? payload = ParseBody(body);
            string title = ((string?)payload?["title"] ?? string.Empty).Trim();
            if (!string.Equals((string?)payload?["id"], _sessionId, StringComparison.Ordinal)
                || title.Length is < 1 or > 80)
            {
                return Error("invalid_session", 400);
            }

            _sessionLabel = title;
            Publish(SessionEvent());
            return Json(new JsonObject { ["ok"] = true });
        }

        if (method == "GET" && route == "/memory")
        {
            return Json(new JsonObject
            {
                ["items"] = new JsonArray(),
                ["error"] = "La memoria privada se gestiona mediante el chat de BAXY.",
            });
        }

        if (route == "/memory" || route.StartsWith("/memory/", StringComparison.Ordinal))
        {
            return Error("private_memory_requires_chat", 409);
        }

        if (method == "GET" && route == "/triggers")
        {
            return Json(new JsonObject { ["items"] = new JsonArray() });
        }

        if (route == "/triggers" || route.StartsWith("/triggers/", StringComparison.Ordinal))
        {
            return Error("routines_require_planner", 409);
        }

        if (method == "GET" && route == "/tools")
        {
            return Json(new JsonObject
            {
                ["mode"] = "trusted_v2",
                ["direct_execution"] = false,
                ["items"] = new JsonArray(),
                ["tools"] = new JsonArray(),
            });
        }

        if (route == "/tools/execute")
        {
            return Error("direct_tool_execution_disabled", 403);
        }

        if (method == "GET" && route == "/profile")
        {
            return Json(new JsonObject { ["active"] = "vram4" });
        }

        if (method == "PUT" && route == "/profile")
        {
            JsonObject? payload = ParseBody(body);
            string profile = (string?)payload?["name"] ?? string.Empty;
            return profile == "vram4"
                ? Json(new JsonObject { ["ok"] = true, ["active"] = profile })
                : Error("profile_not_available", 409);
        }

        if (method == "GET" && route == "/accessibility")
        {
            return Json(new JsonObject { ["active"] = _accessibilityMode });
        }

        if (method == "PUT" && route == "/accessibility")
        {
            string mode = (string?)ParseBody(body)?["mode"] ?? string.Empty;
            if (mode is not ("normal" or "no_vidente" or "movilidad"))
            {
                return Error("invalid_accessibility_mode", 400);
            }

            _accessibilityMode = mode;
            if (mode != "normal" && _viewModel.IsMicAvailable)
            {
                _ = await _viewModel.SetWakeVoiceAsync(true, _lifetimeCancellation)
                    .ConfigureAwait(true);
            }

            return Json(new JsonObject { ["ok"] = true, ["active"] = mode });
        }

        if (method == "GET" && route == "/agent/modes")
        {
            return Json(new JsonObject
            {
                ["items"] = new JsonArray(new JsonObject
                {
                    ["name"] = "auto",
                    ["description"] = "Planner local con selección segura de herramientas",
                }),
            });
        }

        if (method == "GET" && route == "/agent/personas")
        {
            return Json(new JsonObject
            {
                ["items"] = new JsonArray(new JsonObject
                {
                    ["name"] = "default",
                    ["description"] = "BAXY local",
                    ["tone"] = "direct",
                }),
            });
        }

        if (method == "GET" && route == "/voice/inventory")
        {
            return Json(VoiceInventory());
        }

        if (method == "GET" && route == "/settings")
        {
            return Json(CurrentSettings());
        }

        if (method == "PUT" && route == "/settings")
        {
            return PutConfirmationMode(body);
        }

        if (method == "GET" && route == "/agent/system_prompt")
        {
            return Json(new JsonObject
            {
                ["prompt"] = "La mente local de BAXY administra su prompt y sus skills en el sidecar baxy_mind.",
            });
        }

        if (method == "POST" && route == "/agent/restart")
        {
            await _viewModel.InitializeAsync(_lifetimeCancellation).ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = _viewModel.IsReady });
        }

        if (method == "POST" && route == "/agent/recycle_server")
        {
            return Error("recycle_not_required", 409);
        }

        if (method == "POST" && route == "/upload")
        {
            return Error("attachments_not_supported", 501);
        }

        return Error("not_found", 404);
    }

    internal IReadOnlyList<JsonObject> CreateSocketBootstrap()
    {
        var events = new List<JsonObject>
        {
            new()
            {
                ["type"] = "state",
                ["value"] = CurrentConversationState(),
            },
            AgentEvent(),
            new() { ["type"] = "model", ["info"] = ModelInfo() },
            new()
            {
                ["type"] = "ctx",
                ["used"] = 0,
                ["budget"] = ContextSize(),
            },
            new()
            {
                ["type"] = "surfaces",
                ["sessions"] = 1,
                ["memory"] = 0,
                ["triggers"] = 0,
                ["tools"] = ProductCatalog.ToolDescriptors.Count,
            },
            SessionEvent(),
            FieldBridgeContract.CreateProgressPayload(CurrentProgress()),
        };
        foreach (ConversationMessage entry in _viewModel.Messages)
        {
            events.Add(ActivityEvent(entry));
        }

        return events;
    }

    internal FieldProgressNotice? CurrentProgress() =>
        FieldBridgeContract.ResolveProgress(
            _viewModel.IsReady,
            _viewModel.IsBusy,
            _viewModel.HasStartupError,
            _viewModel.StatusDescription,
            _viewModel.ProgressLabel);

    internal JsonObject AgentEvent() => new()
    {
        ["type"] = "agent",
        ["built"] = _viewModel.IsReady,
        ["healthy"] = _viewModel.IsReady && !_viewModel.HasStartupError,
        ["ready"] = _viewModel.IsReady && !_viewModel.IsBusy,
    };

    internal JsonObject SessionEvent() => new()
    {
        ["type"] = "session",
        ["id"] = _sessionId,
        ["label"] = _sessionLabel,
    };

    internal JsonObject ActivityEvent(ConversationMessage message)
    {
        var entry = new JsonObject
        {
            ["id"] = $"native-{Interlocked.Increment(ref _activitySequence)}",
            ["src"] = message.IsUser ? "YOU" : "BAXY",
            ["msg"] = message.Body,
            ["ts"] = message.CreatedAt.ToLocalTime().ToString(
                "HH:mm:ss",
                CultureInfo.InvariantCulture),
        };
        if (!string.IsNullOrWhiteSpace(message.Route))
        {
            entry["route"] = message.Route;
        }

        return new JsonObject
        {
            ["type"] = "activity",
            ["entry"] = entry,
        };
    }

    private void OnCompositionFailed(PendingModelMessage pending, string failure)
    {
        string route = PublicResponseRoute.FromDraft(pending.Draft);
        Publish(new JsonObject
        {
            ["type"] = "composition_failed",
            ["cause"] = failure,
            ["controlsUsable"] = true,
            ["route"] = route,
            ["injected"] = FieldCompositionInjection.Resolve()
                != FieldCompositionInjectionMode.None,
        });
    }

    internal static string NormalizeActivitySource(string? source) => source switch
    {
        "TOOL" or "YOU" or "BAXY" or "GEMMA" or "MEMORY" or "TRIGGER" or "BOOT"
            or "THOUGHT" or "SYSTEM" or "CONTEXT" => source,
        _ => "SYSTEM",
    };

    internal static FieldModelIdentity ResolveModelIdentity(string? modelPath)
    {
        string fileName = string.IsNullOrWhiteSpace(modelPath)
            ? string.Empty
            : Path.GetFileName(modelPath);
        string alias = string.IsNullOrWhiteSpace(fileName)
            ? "local-model"
            : Path.GetFileNameWithoutExtension(fileName);
        string family = alias switch
        {
            var value when value.Contains("qwen3.5", StringComparison.OrdinalIgnoreCase)
                => "qwen 3.5",
            var value when value.Contains("qwen3", StringComparison.OrdinalIgnoreCase)
                => "qwen 3",
            var value when value.Contains("phi-4", StringComparison.OrdinalIgnoreCase)
                => "phi 4",
            var value when value.Contains("gemma-4", StringComparison.OrdinalIgnoreCase)
                => "gemma 4",
            var value when value.Contains("llama", StringComparison.OrdinalIgnoreCase)
                => "llama",
            _ => "local model",
        };
        Match parameterMatch = Regex.Match(
            alias,
            @"(?<![A-Za-z0-9])(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        if (!parameterMatch.Success)
        {
            parameterMatch = Regex.Match(
                alias,
                @"E(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }

        Match quantizationMatch = Regex.Match(
            alias,
            @"(?<value>Q\d(?:_[A-Za-z0-9]+)+)(?=$|[-.])",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        long size = !string.IsNullOrWhiteSpace(modelPath) && File.Exists(modelPath)
            ? new FileInfo(modelPath).Length
            : 0;
        return new FieldModelIdentity(
            alias,
            fileName,
            family,
            parameterMatch.Success
                ? parameterMatch.Groups["value"].Value.ToLowerInvariant()
                : "unknown",
            quantizationMatch.Success
                ? quantizationMatch.Groups["value"].Value.ToUpperInvariant()
                : "local",
            size);
    }

    private async Task<FieldHttpResponse> HandleTurnAsync(string? body)
    {
        string turnId = "t" + Interlocked.Increment(ref _turnSequence)
            .ToString(CultureInfo.InvariantCulture);
        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.SubmitReceived);
        JsonObject? payload = ParseBody(body);
        string text = (string?)payload?["text"] ?? string.Empty;
        // Attachments in the FieldCenter body are not a product contract:
        // /upload already answers attachments_not_supported. They are ignored
        // here so the conductor and the UI share the same admission.
        if (!FieldBridgeContract.TryAcceptTurn(
                _viewModel.IsInputEnabled,
                text,
                out string turnError,
                out int turnStatus))
        {
            PublishAdmission(turnId, accepted: false, turnStatus, turnError);
            return Error(turnError, turnStatus);
        }

        try
        {
            _ = MissionInputContract.ValidateAndTrim(
                new MissionInput(text, MissionInputSource.Text));
        }
        catch (MissionInputRejectedException)
        {
            _viewModel.PublishInputRejection();
            PublishAdmission(turnId, accepted: false, 400, "invalid_text");
            return Error("invalid_text", 400);
        }

        PublishAdmission(turnId, accepted: true, 200, error: null);
        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.BridgeCrossed);

        try
        {
            await _viewModel.SubmitAsync(
                    new MissionInput(text, MissionInputSource.Text),
                    _lifetimeCancellation)
                .ConfigureAwait(true);
        }
        catch (MissionInputRejectedException)
        {
            _viewModel.PublishInputRejection();
            PublishAdmission(turnId, accepted: false, 400, "invalid_text");
            return Error("invalid_text", 400);
        }

        // Publication-boundary stall after admission+dispatch. Composition and
        // verification still ran; the public projection stays silent.
        if (FieldPublicationInjection.Mode == FieldPublicationInjectionMode.Silence)
        {
            try
            {
                using var linked = CancellationTokenSource.CreateLinkedTokenSource(
                    _lifetimeCancellation,
                    _channelLifetime.Token);
                await Task.Delay(Timeout.InfiniteTimeSpan, linked.Token)
                    .ConfigureAwait(true);
            }
            catch (OperationCanceledException)
            {
                return Error("cancelled", 409);
            }
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.ResponseFinal);
        return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
    }

    private void PublishAdmission(string turnId, bool accepted, int status, string? error)
    {
        Interlocked.Increment(ref _admissionSequence);
        Publish(new JsonObject
        {
            ["type"] = "admission",
            ["turnId"] = turnId,
            ["accepted"] = accepted,
            ["status"] = status,
            ["error"] = error,
        });
    }

    private void OnMessageAdded(ConversationMessage message)
    {
        if (FieldPublicationInjection.Mode == FieldPublicationInjectionMode.Silence)
        {
            return;
        }

        if (!message.IsUser)
        {
            if (FieldPublicationInjection.Mode == FieldPublicationInjectionMode.Filter)
            {
                Publish(new JsonObject
                {
                    ["type"] = "publication_discard",
                    ["reason"] = "filtered",
                });
                return;
            }

            if (FieldPublicationInjection.Mode == FieldPublicationInjectionMode.SuppressFinal)
            {
                Publish(new JsonObject
                {
                    ["type"] = "publication_error",
                    ["reason"] = "final_not_delivered",
                });
                return;
            }

            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                "t" + Interlocked.Read(ref _turnSequence)
                    .ToString(CultureInfo.InvariantCulture),
                ShellTraceStages.VisibleText);
        }

        Publish(ActivityEvent(message));
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady)
            or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.HasStartupError))
        {
            Publish(AgentEvent());
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady))
        {
            Publish(new JsonObject { ["type"] = "model", ["info"] = ModelInfo() });
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.HasCompositionError)
            or nameof(MainWindowViewModel.PendingModelMessageCount)
            or nameof(MainWindowViewModel.IsListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking)
            or nameof(MainWindowViewModel.StatusDescription))
        {
            Publish(new JsonObject
            {
                ["type"] = "state",
                ["value"] = CurrentConversationState(),
            });
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady)
            or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.HasStartupError)
            or nameof(MainWindowViewModel.StatusDescription)
            or nameof(MainWindowViewModel.ProgressLabel))
        {
            PublishProgress();
            SyncProgressPulse();
            if (eventArgs.PropertyName is nameof(MainWindowViewModel.ProgressLabel)
                && _viewModel.ProgressLabel is not null)
            {
                RestartMilestoneDue();
            }
        }
    }

    private void OnProgressPulse()
    {
        _viewModel.TryEmitDueMilestone(DateTimeOffset.UtcNow);
        PublishProgress(forcePulse: true);
    }

    private void OnMilestoneDue()
    {
        _viewModel.TryEmitDueMilestone(DateTimeOffset.UtcNow);
        PublishProgress();
        RestartMilestoneDue();
    }

    private void SyncProgressPulse()
    {
        bool busy = _viewModel.IsBusy || !_viewModel.IsReady;
        if (busy)
        {
            _ = _progressPulse.Change(
                FieldBridgeContract.ProgressPulse,
                FieldBridgeContract.ProgressPulse);
            _ = _milestoneDue.Change(
                FieldBridgeContract.MilestoneDue,
                Timeout.InfiniteTimeSpan);
        }
        else
        {
            _ = _progressPulse.Change(Timeout.Infinite, Timeout.Infinite);
            _ = _milestoneDue.Change(Timeout.Infinite, Timeout.Infinite);
        }
    }

    private void RestartMilestoneDue()
    {
        if (_viewModel.IsBusy || !_viewModel.IsReady)
        {
            _ = _milestoneDue.Change(
                FieldBridgeContract.MilestoneDue,
                Timeout.InfiniteTimeSpan);
        }
        else
        {
            _ = _milestoneDue.Change(Timeout.Infinite, Timeout.Infinite);
        }
    }

    private void PublishProgress(bool forcePulse = false)
    {
        if (FieldPublicationInjection.Mode == FieldPublicationInjectionMode.Silence)
        {
            return;
        }

        FieldProgressNotice? notice = CurrentProgress();
        DateTimeOffset now = DateTimeOffset.UtcNow;
        bool sameStage = _progressPublished
            && string.Equals(
                notice?.Stage,
                _publishedProgress?.Stage,
                StringComparison.Ordinal)
            && string.Equals(
                notice?.Label,
                _publishedProgress?.Label,
                StringComparison.Ordinal);
        if (sameStage
            && !(forcePulse && FieldBridgeContract.ShouldPulseProgress(_progressPublishedUtc, now)))
        {
            return;
        }

        if (!Publish(FieldBridgeContract.CreateProgressPayload(notice, now)))
        {
            return;
        }

        _publishedProgress = notice;
        _progressPublishedUtc = now;
        _progressPublished = true;
        if (notice is not null)
        {
            ShellTraceSink.Record(
                ShellTraceScopes.Turn,
                "t" + Interlocked.Read(ref _turnSequence)
                    .ToString(CultureInfo.InvariantCulture),
                ShellTraceStages.VisibleIndication,
                notice.Stage);
        }
    }

    private string CurrentConversationState()
    {
        if (_viewModel.HasCompositionError)
        {
            return "error";
        }

        if (_viewModel.IsVoiceSpeaking)
        {
            return "speaking";
        }

        if (_viewModel.IsListening
            || _viewModel.StatusDescription == "Te escucho")
        {
            return "listening";
        }

        return _viewModel.IsBusy || _viewModel.PendingModelMessageCount > 0
            ? "thinking" : "idle";
    }

    private void PostActivity(string source, string text)
    {
        Publish(new JsonObject
        {
            ["type"] = "activity",
            ["entry"] = new JsonObject
            {
                ["id"] = $"native-{Interlocked.Increment(ref _activitySequence)}",
                ["src"] = source,
                ["msg"] = text,
                ["ts"] = DateTimeOffset.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture),
            },
        });
    }

    private JsonObject Sessions() => new()
    {
        ["sessions"] = new JsonArray(new JsonObject
        {
            ["id"] = _sessionId,
            ["label"] = _sessionLabel,
            ["ts"] = DateTimeOffset.Now.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture),
            ["turn_count"] = _viewModel.Messages.Count(static message => message.IsUser),
            ["current"] = true,
        }),
    };

    private static JsonObject Surfaces() => new()
    {
        ["sessions"] = 1,
        ["memory"] = 0,
        ["triggers"] = 0,
        ["tools"] = ProductCatalog.ToolDescriptors.Count,
    };

    private JsonObject VoiceStatus() => new()
    {
        ["available"] = _viewModel.IsMicAvailable,
        ["running"] = _viewModel.IsListening || _viewModel.IsWakeListening,
        ["mode"] = _viewModel.IsListening ? "direct" : _viewModel.IsWakeListening ? "wake" : "off",
        ["speaking"] = _viewModel.IsVoiceSpeaking,
        ["last_error"] = _viewModel.IsMicAvailable ? null : "voice_unavailable",
    };

    private JsonObject VoiceInventory() => new()
    {
        ["stt_default"] = "parakeet-tdt-0.6b-v3-int8",
        ["stt"] = new JsonArray(new JsonObject
        {
            ["name"] = "parakeet-tdt-0.6b-v3-int8",
            ["size_label"] = "int8 · local",
            ["downloaded"] = _viewModel.IsMicAvailable,
        }),
        ["tts"] = new JsonArray(new JsonObject
        {
            ["name"] = "es_MX-claude-high",
            ["downloaded"] = _viewModel.IsMicAvailable,
        }),
        ["wake"] = new JsonObject
        {
            ["name"] = "Baxy",
            ["downloaded"] = _viewModel.IsMicAvailable,
        },
        ["languages"] = new JsonArray("es", "en"),
    };

    private JsonObject CurrentSettings()
    {
        string? modelPath = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        FieldModelIdentity identity = ResolveModelIdentity(modelPath);
        return new JsonObject
        {
            ["llamaUrl"] = "local sidecar",
            ["modelAlias"] = identity.Alias,
            ["ggufPath"] = identity.FileName,
            ["ctxSize"] = ContextSize(),
            ["sttProvider"] = "sherpa-onnx (local)",
            ["sttModel"] = "parakeet-tdt-0.6b-v3-int8",
            ["ttsProvider"] = "sherpa-onnx piper (local)",
            ["ttsVoice"] = "es_MX-claude-high",
            ["wakeWord"] = "Baxy",
            ["wakeWordEnabled"] = _viewModel.IsWakeListening,
            ["voiceEnabled"] = _viewModel.IsMicAvailable,
            ["visionAlways"] = false,
            ["telemetry"] = false,
            ["confirmationPolicy"] = ConfirmationModeStore.Read(
                MemoryOperationProtector.ResolveDataRoot()) == ConfirmationMode.Bypass
                ? "bypass"
                : "normal",
        };
    }

    private static FieldHttpResponse PutConfirmationMode(string? body)
    {
        JsonNode? node;
        try
        {
            node = string.IsNullOrWhiteSpace(body) ? null : JsonNode.Parse(body);
        }
        catch (JsonException)
        {
            return Error("invalid_settings", 400);
        }

        string? raw = node?["confirmationPolicy"]?.GetValue<string>();
        ConfirmationMode mode = ConfirmationModeStore.Parse(raw) ?? ConfirmationMode.Normal;
        ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(), mode);
        return Json(new JsonObject
        {
            ["ok"] = true,
            ["confirmationPolicy"] = mode == ConfirmationMode.Bypass ? "bypass" : "normal",
        });
    }

    private static JsonObject ModelInfo()
    {
        string? modelPath = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        FieldModelIdentity identity = ResolveModelIdentity(modelPath);
        return new JsonObject
        {
            ["family"] = identity.Family,
            ["params"] = identity.Parameters,
            ["runtime"] = "local",
            ["quant"] = identity.Quantization,
            ["size_bytes"] = identity.SizeBytes,
            ["name_full"] = identity.FileName,
            ["context_size"] = ContextSize(),
            ["mmproj"] = false,
        };
    }

    private static int ContextSize()
    {
        string? raw = Environment.GetEnvironmentVariable("BAXY_MIND_CTX");
        return int.TryParse(raw, NumberStyles.None, CultureInfo.InvariantCulture, out int value)
            && value is >= 1024 and <= 131072
            ? value
            : 4096;
    }

    private static JsonObject MetricsJson(FieldMetricSnapshot metrics)
    {
        var placeholders = new JsonObject();
        foreach ((string key, bool value) in metrics.Placeholder)
        {
            placeholders[key] = value;
        }

        return new JsonObject
        {
            ["cpu"] = metrics.Cpu,
            ["mem"] = metrics.Mem,
            ["mem_used_gb"] = metrics.MemUsedGb,
            ["gpu"] = metrics.Gpu,
            ["net"] = metrics.Net,
            ["dsk"] = metrics.Dsk,
            ["tmp"] = metrics.Tmp,
            ["uptime"] = metrics.Uptime,
            ["placeholder"] = placeholders,
        };
    }

    private static JsonObject HardwareJson(FieldHardwareSnapshot hardware) => new()
    {
        ["cpu"] = hardware.Cpu,
        ["cpu_cores"] = hardware.CpuCores,
        ["mem"] = hardware.Mem,
        ["mem_total_gb"] = hardware.MemTotalGb,
        ["gpu"] = hardware.Gpu,
        ["gpu_vram_gb"] = hardware.GpuVramGb,
    };

    private static JsonObject? ParseBody(string? body)
    {
        if (string.IsNullOrWhiteSpace(body))
        {
            return new JsonObject();
        }

        try
        {
            return JsonNode.Parse(body) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static FieldHttpResponse Json(JsonObject body, int status = 200) =>
        FieldHttpResponse.Json(body, status);

    private static FieldHttpResponse Error(string code, int status) =>
        Json(new JsonObject { ["ok"] = false, ["error"] = code }, status);

    private bool Publish(JsonObject eventData) => _sink.Publish(eventData);

    private void PostToUi(Action action)
    {
        if (_disposed)
        {
            return;
        }

        _uiContext.Post(
            _ =>
            {
                if (!_disposed)
                {
                    action();
                }
            },
            null);
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _viewModel.MessageAdded -= OnMessageAdded;
        _viewModel.CompositionFailed -= OnCompositionFailed;
        _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        await _channelLifetime.CancelAsync();
        _channelLifetime.Dispose();
        await _progressPulse.DisposeAsync();
        await _milestoneDue.DisposeAsync();
    }
}
