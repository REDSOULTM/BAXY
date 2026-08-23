using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using System.Windows;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

namespace Baxy.App;

internal sealed record FieldHttpResponse(
    int Status,
    string Body,
    IReadOnlyDictionary<string, string> Headers)
{
    internal static FieldHttpResponse Json(JsonNode body, int status = 200) =>
        new(
            status,
            body.ToJsonString(),
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["Content-Type"] = "application/json; charset=utf-8",
                ["Cache-Control"] = "no-store",
            });

    internal static FieldHttpResponse Empty(int status = 204) =>
        new(status, string.Empty, new Dictionary<string, string>());
}

internal sealed record FieldModelIdentity(
    string Alias,
    string FileName,
    string Family,
    string Parameters,
    string Quantization,
    long SizeBytes);

internal sealed class FieldUiBridge : IAsyncDisposable
{
    internal const string Channel = "baxy.field.v1";
    internal const string TraceMarkKind = "trace_mark";
    private const int MaximumBridgeMessageCharacters = 1_048_576;
    private const int MaximumRequestBodyCharacters = 65_536;
    private const int MaximumPathCharacters = 2_048;

    private readonly Window _window;
    private readonly WebView2 _webView;
    private readonly MainWindowViewModel _viewModel;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly HashSet<string> _sockets = new(StringComparer.Ordinal);
    private readonly string _sessionId = Guid.NewGuid().ToString("N")[..12];
    private string _sessionLabel = "current";
    private string _accessibilityMode = "normal";
    private long _activitySequence;
    private long _turnSequence;
    private FieldProgressNotice? _publishedProgress;
    private bool _progressPublished;
    private DateTimeOffset? _progressPublishedUtc;
    private readonly System.Windows.Threading.DispatcherTimer _progressPulse;
    private bool _disposed;

    internal FieldUiBridge(
        Window window,
        WebView2 webView,
        MainWindowViewModel viewModel,
        FieldTelemetrySampler telemetry,
        CancellationToken lifetimeCancellation)
    {
        _window = window ?? throw new ArgumentNullException(nameof(window));
        _webView = webView ?? throw new ArgumentNullException(nameof(webView));
        _viewModel = viewModel ?? throw new ArgumentNullException(nameof(viewModel));
        _telemetry = telemetry ?? throw new ArgumentNullException(nameof(telemetry));
        _lifetimeCancellation = lifetimeCancellation;
        _webView.WebMessageReceived += OnWebMessageReceived;
        _viewModel.MessageAdded += OnMessageAdded;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _progressPulse = new System.Windows.Threading.DispatcherTimer
        {
            Interval = FieldBridgeContract.ProgressPulse,
        };
        _progressPulse.Tick += OnProgressPulse;
    }

    private async void OnWebMessageReceived(
        object? sender,
        CoreWebView2WebMessageReceivedEventArgs eventArgs)
    {
        if (_disposed
            || !HistoricalFieldOriginPolicy.IsTrustedDocumentSource(eventArgs.Source))
        {
            return;
        }

        string raw = eventArgs.WebMessageAsJson;
        if (raw.Length > MaximumBridgeMessageCharacters)
        {
            return;
        }

        JsonObject? message;
        try
        {
            message = JsonNode.Parse(raw) as JsonObject;
        }
        catch (JsonException)
        {
            return;
        }

        if (message is null
            || (string?)message["channel"] != Channel
            || message["kind"] is not JsonValue kindValue
            || !kindValue.TryGetValue(out string? kind)
            || string.IsNullOrWhiteSpace(kind))
        {
            return;
        }

        string? id = (string?)message["id"];
        try
        {
            switch (kind)
            {
                case "http":
                    FieldHttpResponse response = await HandleHttpAsync(message)
                        .ConfigureAwait(true);
                    Reply(id, HttpValue(response));
                    break;
                case "socket_open":
                    OpenSocket(message);
                    break;
                case "socket_close":
                    CloseSocket(message);
                    break;
                case "window_command":
                    Reply(id, HandleWindowCommand((string?)message["command"]));
                    break;
                case "window_drag":
                    TryDragWindow();
                    break;
                case TraceMarkKind:
                    RecordDocumentMark(message);
                    break;
            }
        }
        catch (OperationCanceledException) when (_lifetimeCancellation.IsCancellationRequested)
        {
            ReplyError(id, "BAXY is closing");
        }
        catch (Exception exception) when (IsExpectedBridgeFailure(exception))
        {
            ReplyError(id, "The local BAXY bridge could not complete the request.");
        }
    }

    private async Task<FieldHttpResponse> HandleHttpAsync(JsonObject message)
    {
        string method = ((string?)message["method"] ?? "GET").ToUpperInvariant();
        string path = (string?)message["path"] ?? "/";
        string? body = (string?)message["body"];
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
            bool running = await _viewModel
                .StartDirectVoiceAsync(_lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = running, ["running"] = running },
                running ? 200 : 503);
        }

        if (method == "POST" && route == "/turn")
        {
            string turnId = "t" + Interlocked.Increment(ref _turnSequence)
                .ToString(CultureInfo.InvariantCulture);
            ShellTraceSink.Record(
                ShellTraceScopes.Bridge,
                turnId,
                ShellTraceStages.SubmitReceived);
            if (!_viewModel.IsInputEnabled)
            {
                return Error("agent_not_ready", 409);
            }

            JsonObject? payload = ParseBody(body);
            string text = (string?)payload?["text"] ?? string.Empty;
            if (string.IsNullOrWhiteSpace(text))
            {
                return Error("invalid_text", 400);
            }

            ShellTraceSink.Record(
                ShellTraceScopes.Bridge,
                turnId,
                ShellTraceStages.BridgeCrossed);
            await _viewModel.SubmitAsync(
                    new MissionInput(text, MissionInputSource.Text),
                    _lifetimeCancellation)
                .ConfigureAwait(true);
            ShellTraceSink.Record(
                ShellTraceScopes.Bridge,
                turnId,
                ShellTraceStages.ResponseFinal);
            return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
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
            PostEvent(new JsonObject { ["type"] = "log_clear" });
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
            PostEvent(new JsonObject { ["type"] = "log_clear" });
            PostSession();
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
            PostSession();
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

    /// <summary>
    /// Registra una marca temporal emitida por el documento. Sólo se aceptan
    /// etapas del vocabulario cerrado y sólo cuando el registro está activo:
    /// la vista no puede escribir texto libre ni inventar etapas, y sin
    /// instrumentación esta rama no hace nada.
    /// </summary>
    private static void RecordDocumentMark(JsonObject message)
    {
        string stage = (string?)message["stage"] ?? string.Empty;
        if (Array.IndexOf(ShellTraceStages.DocumentReportable, stage) < 0)
        {
            return;
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Turn,
            ShellTrace.SanitizeId((string?)message["id"]),
            stage);
    }

    private void OpenSocket(JsonObject message)
    {
        string socketId = (string?)message["socketId"] ?? string.Empty;
        string url = (string?)message["url"] ?? string.Empty;
        if (socketId.Length is < 1 or > 128
            || !HistoricalFieldOriginPolicy.IsTrustedEventSocket(url))
        {
            return;
        }

        _sockets.Add(socketId);
        PostSocket(socketId, "open");
        PostSocketMessage(socketId, new JsonObject
        {
            ["type"] = "state",
            ["value"] = CurrentConversationState(),
        });
        PostSocketMessage(socketId, AgentEvent());
        PostSocketMessage(socketId, new JsonObject { ["type"] = "model", ["info"] = ModelInfo() });
        PostSocketMessage(socketId, new JsonObject
        {
            ["type"] = "ctx",
            ["used"] = 0,
            ["budget"] = ContextSize(),
        });
        PostSocketMessage(socketId, new JsonObject
        {
            ["type"] = "surfaces",
            ["sessions"] = 1,
            ["memory"] = 0,
            ["triggers"] = 0,
            ["tools"] = ProductCatalog.ToolDescriptors.Count,
        });
        PostSocketMessage(socketId, SessionEvent());
        // Un socket que se reconecta recibe el estado actual, nunca fragmentos
        // ya publicados: la indicación se recalcula, no se reproduce.
        PostSocketMessage(
            socketId,
            FieldBridgeContract.CreateProgressPayload(CurrentProgress()));
        foreach (ConversationMessage entry in _viewModel.Messages)
        {
            PostSocketMessage(socketId, ActivityEvent(entry));
        }
    }

    private void CloseSocket(JsonObject message)
    {
        string socketId = (string?)message["socketId"] ?? string.Empty;
        if (_sockets.Remove(socketId))
        {
            PostSocket(socketId, "close", code: 1000, reason: "closed");
        }
    }

    private JsonValue? HandleWindowCommand(string? command)
    {
        switch (command)
        {
            case "minimize":
                _window.WindowState = WindowState.Minimized;
                return JsonValue.Create(true);
            case "toggle_maximize":
                _window.WindowState = _window.WindowState == WindowState.Maximized
                    ? WindowState.Normal
                    : WindowState.Maximized;
                return JsonValue.Create(_window.WindowState == WindowState.Maximized);
            case "is_maximized":
                return JsonValue.Create(_window.WindowState == WindowState.Maximized);
            case "close":
                _window.Close();
                return JsonValue.Create(true);
            default:
                return JsonValue.Create(false);
        }
    }

    private void TryDragWindow()
    {
        if (_window.WindowState == WindowState.Maximized)
        {
            return;
        }

        try
        {
            _window.DragMove();
        }
        catch (InvalidOperationException)
        {
            // The pointer may have been released before the native drag began.
        }
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

        PostEvent(ActivityEvent(message));
    }

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady)
            or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.HasStartupError))
        {
            PostEvent(AgentEvent());
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady))
        {
            PostEvent(new JsonObject { ["type"] = "model", ["info"] = ModelInfo() });
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.IsListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking)
            or nameof(MainWindowViewModel.StatusDescription))
        {
            PostEvent(new JsonObject
            {
                ["type"] = "state",
                ["value"] = CurrentConversationState(),
            });
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady)
            or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.HasStartupError)
            or nameof(MainWindowViewModel.StatusDescription))
        {
            PublishProgress();
            SyncProgressPulse();
        }
    }

    private void OnProgressPulse(object? sender, EventArgs eventArgs) => PublishProgress(forcePulse: true);

    private void SyncProgressPulse()
    {
        bool busy = _viewModel.IsBusy || !_viewModel.IsReady;
        if (busy)
        {
            if (!_progressPulse.IsEnabled)
                _progressPulse.Start();
        }
        else if (_progressPulse.IsEnabled)
        {
            _progressPulse.Stop();
        }
    }

    /// <summary>
    /// Publica una indicación honesta de progreso mientras el turno sigue en
    /// curso. Nunca anticipa un éxito ni describe una decisión interna: sólo
    /// dice, con lenguaje de persona, qué está ocurriendo ahora. El payload usa
    /// el evento histórico <c>boot_stage</c> que el lector sellado ya entiende,
    /// así que un lector antiguo lo muestra y uno que no lo conozca lo ignora
    /// sin reinterpretar nada.
    /// </summary>
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

        // Sólo se considera publicada la indicación que llegó de verdad al
        // lector. Si el envío se pierde por una carrera de navegación o cierre,
        // el siguiente cambio de estado vuelve a intentarlo en vez de quedar
        // silenciado por la deduplicación.
        if (!PostEvent(FieldBridgeContract.CreateProgressPayload(notice, now)))
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

    internal FieldProgressNotice? CurrentProgress() =>
        FieldBridgeContract.ResolveProgress(
            _viewModel.IsReady,
            _viewModel.IsBusy,
            _viewModel.HasStartupError,
            _viewModel.StatusDescription);

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

    private JsonObject AgentEvent() => new()
    {
        ["type"] = "agent",
        ["built"] = _viewModel.IsReady,
        ["healthy"] = _viewModel.IsReady && !_viewModel.HasStartupError,
        ["ready"] = _viewModel.IsReady && !_viewModel.IsBusy,
    };

    private JsonObject ActivityEvent(ConversationMessage message) => new()
    {
        ["type"] = "activity",
        ["entry"] = new JsonObject
        {
            ["id"] = $"native-{Interlocked.Increment(ref _activitySequence)}",
            ["src"] = message.IsUser ? "YOU" : "BAXY",
            ["msg"] = message.Body,
            ["ts"] = message.CreatedAt.ToLocalTime().ToString("HH:mm:ss", CultureInfo.InvariantCulture),
        },
    };

    private void PostActivity(string source, string text)
    {
        PostEvent(new JsonObject
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

    private void PostSession() => PostEvent(SessionEvent());

    private JsonObject SessionEvent() => new()
    {
        ["type"] = "session",
        ["id"] = _sessionId,
        ["label"] = _sessionLabel,
    };

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
            ["name"] = "windows-sapi",
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
            ["ttsProvider"] = "windows sapi (local)",
            ["ttsVoice"] = "system spanish voice",
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

    internal static string NormalizeActivitySource(string? source) => source switch
    {
        "TOOL" or "YOU" or "BAXY" or "GEMMA" or "MEMORY" or "TRIGGER" or "BOOT"
            or "THOUGHT" or "SYSTEM" or "CONTEXT" => source,
        _ => "SYSTEM",
    };

    private static FieldHttpResponse Json(JsonObject body, int status = 200) =>
        FieldHttpResponse.Json(body, status);

    private static FieldHttpResponse Error(string code, int status) =>
        Json(new JsonObject { ["ok"] = false, ["error"] = code }, status);

    private static JsonObject HttpValue(FieldHttpResponse response)
    {
        var headers = new JsonObject();
        foreach ((string key, string value) in response.Headers)
        {
            headers[key] = value;
        }

        return new JsonObject
        {
            ["status"] = response.Status,
            ["body"] = response.Body,
            ["headers"] = headers,
        };
    }

    private void Reply(string? id, JsonNode? value)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return;
        }

        PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "reply",
            ["id"] = id,
            ["ok"] = true,
            ["value"] = value?.DeepClone(),
        });
    }

    private void ReplyError(string? id, string error)
    {
        if (string.IsNullOrWhiteSpace(id))
        {
            return;
        }

        PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "reply",
            ["id"] = id,
            ["ok"] = false,
            ["error"] = error,
        });
    }

    private bool PostEvent(JsonObject eventData)
    {
        bool delivered = false;
        foreach (string socketId in _sockets.ToArray())
        {
            delivered |= PostSocketMessage(socketId, eventData);
        }

        return delivered;
    }

    private bool PostSocketMessage(string socketId, JsonObject eventData) =>
        PostSocket(socketId, "message", data: eventData.ToJsonString());

    private bool PostSocket(
        string socketId,
        string eventName,
        string? data = null,
        int? code = null,
        string? reason = null)
    {
        return PostEnvelope(new JsonObject
        {
            ["channel"] = Channel,
            ["kind"] = "socket_event",
            ["socketId"] = socketId,
            ["event"] = eventName,
            ["data"] = data,
            ["code"] = code,
            ["reason"] = reason,
        });
    }

    private bool PostEnvelope(JsonObject envelope)
    {
        if (_disposed || _webView.CoreWebView2 is null)
        {
            return false;
        }

        try
        {
            _webView.CoreWebView2.PostWebMessageAsJson(envelope.ToJsonString());
            return true;
        }
        catch (InvalidOperationException)
        {
            // Navigation or teardown raced the event; the next state replay wins.
            return false;
        }
    }

    private static bool IsExpectedBridgeFailure(Exception exception) => exception is
        JsonException
        or IOException
        or InvalidOperationException
        or ArgumentException
        or Baxy.Kernel.Planning.MissionPlanValidationException
        or UnauthorizedAccessException;

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _progressPulse.Stop();
        _progressPulse.Tick -= OnProgressPulse;
        _webView.WebMessageReceived -= OnWebMessageReceived;
        _viewModel.MessageAdded -= OnMessageAdded;
        _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        foreach (string socketId in _sockets.ToArray())
        {
            PostSocket(socketId, "close", code: 1001, reason: "BAXY closing");
        }

        _sockets.Clear();
        await _telemetry.DisposeAsync();
    }
}
