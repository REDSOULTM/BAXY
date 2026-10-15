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

internal sealed class FieldProductChannel : IAsyncDisposable
{
    internal const int MaximumRequestBodyCharacters = 65_536;
    internal const int MaximumPathCharacters = 2_048;

    private readonly MainWindowViewModel _viewModel;
    private readonly IFieldEventSink _sink;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly SynchronizationContext _uiContext;
    private readonly Timer _progressPulse;
    private readonly string _sessionId = Guid.NewGuid().ToString("N")[..12];
    private string _sessionLabel = "current";
    private long _activitySequence;
    private long _turnSequence;
    private FieldProgressNotice? _publishedProgress;
    private bool _progressPublished;
    private DateTimeOffset? _progressPublishedUtc;
    private bool _disposed;
    // Estabilización M: the memory panel runs the chat's own catalog operations; its count is read from the store
    // when the view asks for the surfaces and the store may have changed since (first read, a chat change).
    private readonly MemoryPanel _memory;
    private bool _memoryCountStale = true;
    // Encargo I2 (identidad redpc: the open panel listed 3 while the counter said 4 after a save by chat): every chat
    // change of the store is numbered and travels in the counter's own event, so the open list is read again with it.
    private int _memoryRevision;

    // The host's presentation of the accessible mode (FieldUiBridge: the view's zoom), applied as the view reads it.
    internal Action<bool>? ApplyPresentation { get; set; }

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
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _viewModel.MemoryChanged += OnMemoryChanged;
        _memory = new MemoryPanel(() => _viewModel.CoreClient, () => _viewModel.MemoryProtector);
        _progressPulse = new Timer(
            _ => PostToUi(OnProgressPulse),
            null,
            Timeout.Infinite,
            Timeout.Infinite);
    }

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
                ["ready"] = _viewModel.IsReady && !_viewModel.IsBusy && !_viewModel.IsMindPreparing,
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
            if (_memoryCountStale)
            {
                _memoryCountStale = !await _memory.RefreshCountAsync(_lifetimeCancellation).ConfigureAwait(true);
                Publish(SurfacesEvent());
            }

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

        if (method == "POST" && route == "/confirmation/answer")
        {
            JsonObject? answer = ParseBody(body);
            if (answer?["approve"] is not JsonValue approveValue || !approveValue.TryGetValue(out bool approve))
            {
                return Error("invalid_answer", 400);
            }

            if (!_viewModel.HasPendingConfirmation)
            {
                return Error("nothing_pending", 409);
            }

            await _viewModel.AnswerConfirmationAsync(approve, _lifetimeCancellation).ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = true });
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

        if (route == "/memory" || route.StartsWith("/memory/", StringComparison.Ordinal))
        {
            int before = _memory.Count;
            FieldHttpResponse memory = await _memory.HandleAsync(method, route, body, _lifetimeCancellation)
                .ConfigureAwait(true);
            if (_memory.Count != before)
            {
                Publish(SurfacesEvent());
            }

            return memory;
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

        // Estabilización U: the accessible mode is the profile's file (PresentationModeStore), the same one the chat's
        // system.settings.set writes. It changes only how the view is presented: the host scales the view
        // (ApplyPresentation) and the view switches its own styles; nothing BAXY can do changes with it.
        if (method == "GET" && route == "/accessibility")
        {
            return Json(PresentationMode(PresentationModeStore.ReadAccessible(MemoryOperationProtector.ResolveDataRoot())));
        }

        if (method == "PUT" && route == "/accessibility")
        {
            string mode = (string?)ParseBody(body)?["mode"] ?? string.Empty;
            if (mode is not (PresentationModeStore.Normal or PresentationModeStore.Accessible))
            {
                return Error("invalid_accessibility_mode", 400);
            }

            string root = MemoryOperationProtector.ResolveDataRoot();
            PresentationModeStore.WriteAccessible(root, mode == PresentationModeStore.Accessible);
            JsonObject applied = PresentationMode(PresentationModeStore.ReadAccessible(root));
            applied["ok"] = true;
            return Json(applied);
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

        // The historical panel's «apply» changes nothing on the host (its diagnostics are read-only), and never the
        // confirmation mode, which has its own route and gesture (revisión U, H1).
        if (method == "PUT" && route == "/settings")
        {
            return Json(new JsonObject { ["ok"] = true });
        }

        if (method == "GET" && route == "/confirmation")
        {
            return Json(ConfirmationPolicy(MemoryOperationProtector.ResolveDataRoot()));
        }

        if (method == "PUT" && route == "/confirmation")
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
            SurfacesEvent(),
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
            _viewModel.IsReady && !_viewModel.IsMindPreparing,
            _viewModel.IsBusy,
            _viewModel.HasStartupError,
            _viewModel.StatusDescription,
            null);

    internal JsonObject AgentEvent() => new()
    {
        ["type"] = "agent",
        ["built"] = _viewModel.IsReady,
        ["healthy"] = _viewModel.IsReady && !_viewModel.HasStartupError,
        ["ready"] = _viewModel.IsReady && !_viewModel.IsBusy && !_viewModel.IsMindPreparing,
        // A risky call waits for the person: the interface shows Sí and No under BAXY's question.
        ["pendingConfirmation"] = _viewModel.HasPendingConfirmation,
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
        await _viewModel.WaitForCoreRecoveryAsync().ConfigureAwait(true);
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
            PublishAdmission(turnId, accepted: false, 400, "invalid_text");
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.ResponseFinal);
        return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
    }

    private void PublishAdmission(string turnId, bool accepted, int status, string? error)
    {
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
        if (!message.IsUser)
        {
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
            or nameof(MainWindowViewModel.HasStartupError)
            or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.HasPendingConfirmation))
        {
            Publish(AgentEvent());
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady))
        {
            Publish(new JsonObject { ["type"] = "model", ["info"] = ModelInfo() });
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsBusy)
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
            or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.StatusDescription))
        {
            PublishProgress();
            SyncProgressPulse();
        }
    }

    private void OnProgressPulse()
    {
        PublishProgress(forcePulse: true);
    }

    private void SyncProgressPulse()
    {
        bool busy = _viewModel.IsBusy || !_viewModel.IsReady;
        if (busy)
        {
            _ = _progressPulse.Change(
                FieldBridgeContract.ProgressPulse,
                FieldBridgeContract.ProgressPulse);
        }
        else
        {
            _ = _progressPulse.Change(Timeout.Infinite, Timeout.Infinite);
        }
    }

    private void PublishProgress(bool forcePulse = false)
    {
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
        if (_viewModel.IsVoiceSpeaking)
        {
            return "speaking";
        }

        if (_viewModel.IsListening
            || _viewModel.StatusDescription == "Te escucho")
        {
            return "listening";
        }

        return _viewModel.IsBusy ? "thinking" : "idle";
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

    private JsonObject Surfaces() => new()
    {
        ["sessions"] = 1,
        ["memory"] = _memory.Count,
        ["memory_revision"] = Volatile.Read(ref _memoryRevision),
        ["triggers"] = 0,
        ["tools"] = ProductCatalog.ToolDescriptors.Count,
    };

    private JsonObject SurfacesEvent()
    {
        JsonObject surfaces = Surfaces();
        surfaces["type"] = "surfaces";
        return surfaces;
    }

    private void OnMemoryChanged()
    {
        Interlocked.Increment(ref _memoryRevision);
        _memoryCountStale = true;
    }

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
        };
    }

    // Estabilización U: the bypass switch of BAXY's own view writes the profile's confirmation-mode through the same
    // store the engine reads on every invocation (ConfirmationModeStore). Only the trusted document reaches this route
    // (FieldUiBridge, HistoricalFieldOriginPolicy); the conscious gesture is the view's own confirmation. A body that
    // names no policy changes nothing.
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

        ConfirmationMode? mode = node?["confirmationPolicy"] is JsonValue policy
            && policy.TryGetValue(out string? raw)
            && raw is "normal" or "bypass"
                ? ConfirmationModeStore.Parse(raw)
                : null;
        if (mode is not { } chosen)
        {
            return Error("invalid_confirmation_policy", 400);
        }

        string root = MemoryOperationProtector.ResolveDataRoot();
        ConfirmationModeStore.Write(root, chosen);
        JsonObject written = ConfirmationPolicy(root);
        written["ok"] = true;
        return Json(written);
    }

    private static JsonObject ConfirmationPolicy(string root) => new()
    {
        ["confirmationPolicy"] = ConfirmationModeStore.Read(root) == ConfirmationMode.Bypass ? "bypass" : "normal",
    };

    private JsonObject PresentationMode(bool accessible)
    {
        ApplyPresentation?.Invoke(accessible);
        return new JsonObject
        {
            ["active"] = accessible ? PresentationModeStore.Accessible : PresentationModeStore.Normal,
        };
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
        // The same variable and default the mind passes to llama-server (src/baxy_mind/__main__.py).
        string? raw = Environment.GetEnvironmentVariable("BAXY_RENEW_CTX");
        return int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value)
            && value > 0
            ? value
            : 49152;
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
        _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        _viewModel.MemoryChanged -= OnMemoryChanged;
        await _progressPulse.DisposeAsync();
    }
}
