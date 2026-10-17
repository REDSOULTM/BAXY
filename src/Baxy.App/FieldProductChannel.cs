using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>Where <see cref="FieldProductChannel"/> publishes its events (<see cref="FieldUiBridge"/> posts them to
/// the view).</summary>
internal interface IFieldEventSink
{
    bool Publish(JsonObject eventData);
}

/// <summary>
/// The Field view's routes and public events: turn admission, sessions, voice,
/// settings and the events it publishes. Only <see cref="FieldUiBridge"/> (the
/// WebView adapter) calls this type; the origin policy stays on that adapter,
/// this channel has none.
/// </summary>
internal sealed class FieldProductChannel : IAsyncDisposable
{
    internal const int MaximumRequestBodyCharacters = 65_536;
    internal const int MaximumPathCharacters = 2_048;

    private readonly MainWindowViewModel _viewModel;
    private readonly IFieldEventSink _sink;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly string _sessionId = Guid.NewGuid().ToString("N")[..12];
    private string _sessionLabel = "current";
    private long _activitySequence;
    private long _turnSequence;
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
        _viewModel.MessageAdded += OnMessageAdded;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _viewModel.MemoryChanged += OnMemoryChanged;
        _memory = new MemoryPanel(() => _viewModel.CoreClient, () => _viewModel.MemoryProtector);
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
            return Json(AgentStatus());
        }

        if (method == "GET" && route == "/model")
        {
            // Ronda final 17 (regla 3): the model is said loaded only once the mind that serves it is ready.
            return _viewModel.IsMindReady ? Json(ModelInfo())
                : Error(MindUnavailable ? "mind_unavailable" : "model_not_loaded", 503);
        }

        if (method == "GET" && route == "/metrics")
        {
            FieldMetricSnapshot metrics = await _telemetry
                .SampleAsync(_lifetimeCancellation)
                .ConfigureAwait(true);
            return Json(MetricsJson(metrics));
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
            long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
            JsonObject? answer = ParseBody(body);
            if (answer?["approve"] is not JsonValue approveValue || !approveValue.TryGetValue(out bool approve))
            {
                return Error("invalid_answer", 400);
            }

            if (!_viewModel.HasPendingConfirmation)
            {
                return Error("nothing_pending", 409);
            }

            await _viewModel.AnswerConfirmationAsync(approve, arrivedAt, _lifetimeCancellation).ConfigureAwait(true);
            return Json(new JsonObject { ["ok"] = true });
        }

        if (method == "POST" && route == "/activity")
        {
            // The view's own lines (its shortcuts help) are SYSTEM lines; BAXY's and the person's come from the turn,
            // so the line carries only its text.
            JsonObject? payload = ParseBody(body);
            string text = ((string?)payload?["msg"] ?? string.Empty).Trim();
            if (text.Length > 0)
            {
                PostSystemActivity(text);
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
            int? before = _memory.Count;
            FieldHttpResponse memory = await _memory.HandleAsync(method, route, body, _lifetimeCancellation)
                .ConfigureAwait(true);
            if (_memory.Count != before)
            {
                Publish(SurfacesEvent());
            }

            return memory;
        }

        if (method == "GET" && route == "/tools")
        {
            return Json(new JsonObject
            {
                // The tools the model is offered (the count the surface shows), with the catalog's own short
                // descriptions (ronda final 21: the mind reads its English ones, tool_descriptions.en.v1.json).
                ["items"] = new JsonArray([.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                {
                    Baxy.Contracts.OperationDescriptor tool = ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor));
                    return (JsonNode)new JsonObject
                    {
                        ["name"] = tool.Name,
                        ["description"] = tool.Description,
                        ["schema"] = JsonNode.Parse(tool.ArgumentsSchema.GetRawText()),
                    };
                })]),
            });
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

        if (method == "GET" && route == "/voice/inventory")
        {
            return Json(VoiceInventory());
        }

        if (method == "GET" && route == "/settings")
        {
            return Json(CurrentSettings());
        }

        if (method == "GET" && route == "/confirmation")
        {
            return Json(ConfirmationPolicy(MemoryOperationProtector.ResolveDataRoot()));
        }

        if (method == "PUT" && route == "/confirmation")
        {
            return PutConfirmationMode(body);
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
            ModelEvent(),
            SurfacesEvent(),
            SessionEvent(),
        };
        foreach (ConversationMessage entry in _viewModel.Messages)
        {
            events.Add(ActivityEvent(entry));
        }

        return events;
    }

    internal JsonObject AgentEvent()
    {
        JsonObject agent = AgentStatus();
        agent["type"] = "agent";
        return agent;
    }

    // The interface's gate and what it shows: whether a turn is accepted now, the failure's code (the engine's or the
    // last turn's), and whether a risky call waits for the person (Sí and No under BAXY's question).
    // Ronda final 17 (regla 3): «ready» needs the mind ready too; a mind that failed or is not configured is said.
    private JsonObject AgentStatus() => new()
    {
        ["built"] = _viewModel.IsReady,
        ["ready"] = _viewModel.IsReady && _viewModel.IsMindReady && !_viewModel.IsBusy && !_viewModel.IsMindPreparing,
        ["failure"] = _viewModel.Failure ?? (MindUnavailable ? "mind_unavailable" : null),
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

        return new FieldModelIdentity(
            alias,
            fileName,
            family,
            parameterMatch.Success
                ? parameterMatch.Groups["value"].Value.ToLowerInvariant()
                : "unknown");
    }

    private async Task<FieldHttpResponse> HandleTurnAsync(string? body)
    {
        // The person's words arrived now; the turn may still wait for the engine's recovery or a heartbeat.
        long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
        string turnId = "t" + Interlocked.Increment(ref _turnSequence)
            .ToString(CultureInfo.InvariantCulture);
        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.SubmitReceived);
        JsonObject? payload = ParseBody(body);
        string text = (string?)payload?["text"] ?? string.Empty;
        await _viewModel.WaitForCoreRecoveryAsync().ConfigureAwait(true);
        if (!FieldBridgeContract.TryAcceptTurn(
                _viewModel.IsInputEnabled,
                text,
                out string turnError,
                out int turnStatus))
        {
            return Error(turnError, turnStatus);
        }

        try
        {
            _ = MissionInputContract.ValidateAndTrim(
                new MissionInput(text, MissionInputSource.Text));
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.BridgeCrossed);

        try
        {
            await _viewModel.SubmitAsync(
                    new MissionInput(text, MissionInputSource.Text),
                    arrivedAt,
                    _lifetimeCancellation)
                .ConfigureAwait(true);
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(
            ShellTraceScopes.Bridge,
            turnId,
            ShellTraceStages.ResponseFinal);
        return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
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
            or nameof(MainWindowViewModel.Failure)
            or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.IsMindReady)
            or nameof(MainWindowViewModel.HasPendingConfirmation))
        {
            Publish(AgentEvent());
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsReady) or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(ModelEvent());
        }

        if (eventArgs.PropertyName is nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.IsListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking)
            or nameof(MainWindowViewModel.Failure)
            or nameof(MainWindowViewModel.StatusDescription)
            // Ronda final 19 (regla 3): a mind no longer ready turns the state to «error» (MindUnavailable) at once.
            or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(new JsonObject
            {
                ["type"] = "state",
                ["value"] = CurrentConversationState(),
            });
        }
    }

    private string CurrentConversationState()
    {
        if (_viewModel.IsVoiceSpeaking)
        {
            return "speaking";
        }

        if (_viewModel.IsListening)
        {
            return "listening";
        }

        return _viewModel.IsBusy ? "thinking"
            : _viewModel.Failure is not null || MindUnavailable ? "error"
            : "idle";
    }

    private void PostSystemActivity(string text)
    {
        Publish(new JsonObject
        {
            ["type"] = "activity",
            ["entry"] = new JsonObject
            {
                ["id"] = $"native-{Interlocked.Increment(ref _activitySequence)}",
                ["src"] = "SYSTEM",
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
        ["last_error"] = _viewModel.VoiceFailure ?? (_viewModel.IsMicAvailable ? null : "voice_unavailable"),
    };

    // The voice models are the launcher's (BAXY_RENEW_STT_DIR, _TTS_MODEL, _WAKE_DIR): each is named by its path and
    // shown as on disk only when the file the mind loads is there (voice.py, voice_output.py).
    private static JsonObject VoiceInventory()
    {
        string stt = Environment.GetEnvironmentVariable("BAXY_RENEW_STT_DIR") ?? string.Empty;
        string tts = Environment.GetEnvironmentVariable("BAXY_RENEW_TTS_MODEL") ?? string.Empty;
        string wake = Environment.GetEnvironmentVariable("BAXY_RENEW_WAKE_DIR") ?? string.Empty;
        return new JsonObject
        {
            ["stt"] = new JsonObject
            {
                ["name"] = Path.GetFileName(stt.TrimEnd('\\', '/')),
                ["downloaded"] = stt.Length > 0 && File.Exists(Path.Combine(stt, "tokens.txt")),
            },
            ["tts"] = new JsonObject
            {
                ["name"] = Path.GetFileNameWithoutExtension(tts),
                ["downloaded"] = tts.Length > 0 && File.Exists(tts) && File.Exists(tts + ".json"),
            },
            ["wake"] = new JsonObject
            {
                ["name"] = Path.GetFileName(wake.TrimEnd('\\', '/')),
                ["downloaded"] = wake.Length > 0 && File.Exists(Path.Combine(wake, "config.json")),
            },
        };
    }

    // What the settings panel shows: the model the mind was given (BAXY_MIND_LLM_GGUF), its context and the voice's
    // live state; the voice models come from /voice/inventory.
    private JsonObject CurrentSettings()
    {
        string? modelPath = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        FieldModelIdentity identity = ResolveModelIdentity(modelPath);
        return new JsonObject
        {
            ["modelAlias"] = identity.Alias,
            ["ggufPath"] = identity.FileName,
            ["ctxSize"] = ContextSize(),
            ["wakeWordEnabled"] = _viewModel.IsWakeListening,
            // Whether a microphone was found and the voice can listen, not a switch.
            ["micAvailable"] = _viewModel.IsMicAvailable,
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

    private bool MindUnavailable => !_viewModel.IsMindReady && !_viewModel.IsMindPreparing;

    // The model event: its identity once the mind serving it is ready, null before (the interface then asks /model,
    // which says whether it is still loading or the mind is unavailable).
    private JsonObject ModelEvent() =>
        new() { ["type"] = "model", ["info"] = _viewModel.IsMindReady ? ModelInfo() : null };

    private static JsonObject ModelInfo()
    {
        string? modelPath = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF");
        FieldModelIdentity identity = ResolveModelIdentity(modelPath);
        return new JsonObject
        {
            ["family"] = identity.Family,
            ["params"] = identity.Parameters,
            ["runtime"] = "local",
            ["context_size"] = ContextSize(),
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

    // A reading the PC did not give (no GPU counter, no CPU sample, no memory, disk or boot figures) travels as null;
    // the view shows «—».
    private static JsonObject MetricsJson(FieldMetricSnapshot metrics) => new()
    {
        ["cpu"] = metrics.Cpu,
        ["mem"] = metrics.Mem,
        ["mem_used_gb"] = metrics.MemUsedGb,
        ["gpu"] = metrics.Gpu,
        ["dsk"] = metrics.Dsk,
        ["uptime"] = metrics.Uptime,
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

    public ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return ValueTask.CompletedTask;
        }

        _disposed = true;
        _viewModel.MessageAdded -= OnMessageAdded;
        _viewModel.PropertyChanged -= OnViewModelPropertyChanged;
        _viewModel.MemoryChanged -= OnMemoryChanged;
        return ValueTask.CompletedTask;
    }
}
