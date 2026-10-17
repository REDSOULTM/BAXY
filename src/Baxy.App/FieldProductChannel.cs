using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>Where <see cref="FieldProductChannel"/> publishes its events (<see cref="FieldUiBridge"/> posts them to
/// the view).</summary>
internal interface IFieldEventSink
{
    bool Publish(JsonObject eventData);
}

/// <summary>
/// The Field view's routes and public events (design v4): turn admission, the conversation with its steps and cards
/// (<see cref="FieldTranscript"/>), what left the PC, voice, the start's pieces, sessions, settings, the catalog and the
/// triggers. Only <see cref="FieldUiBridge"/> (the WebView adapter) calls this type; the origin policy stays on that
/// adapter, this channel has none. Every value it sends was observed; one it could not read travels as null.
/// </summary>
internal sealed class FieldProductChannel : IAsyncDisposable
{
    internal const int MaximumRequestBodyCharacters = 65_536;
    internal const int MaximumPathCharacters = 2_048;
    private const int MaximumSessionLabel = 80;

    private readonly MainWindowViewModel _viewModel;
    private readonly IFieldEventSink _sink;
    private readonly FieldTelemetrySampler _telemetry;
    private readonly CancellationToken _lifetimeCancellation;
    private readonly FieldTranscript _transcript = new();
    private readonly FieldSessionStore _sessions = FieldSessionStore.CreateDefault();
    private string _sessionId = NewSessionId();
    private string? _sessionLabel;
    private DateTimeOffset _sessionCreated = DateTimeOffset.UtcNow;
    private int? _triggerCount;
    private bool _disposed;
    // The memory panel runs the chat's own catalog operations; its count is read from the store when the view asks
    // for the surfaces and the store may have changed since (first read, a chat change).
    private readonly MemoryPanel _memory;
    private bool _memoryCountStale = true;
    // Every chat change of the store is numbered and travels in the counter's own event, so an open list is read again.
    private int _memoryRevision;

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
        FieldStepProjection.Validate();
        _viewModel.MessageAdded += OnMessageAdded;
        _viewModel.PropertyChanged += OnViewModelPropertyChanged;
        _viewModel.MemoryChanged += OnMemoryChanged;
        _viewModel.StepStarted += OnStepStarted;
        _viewModel.StepCompleted += OnStepCompleted;
        _viewModel.ConfirmationAsked += OnConfirmationAsked;
        _viewModel.ConfirmationResolved += OnConfirmationResolved;
        _viewModel.VoicePartial += OnVoicePartial;
        _viewModel.VoiceWake += OnVoiceWake;
        _memory = new MemoryPanel(() => _viewModel.CoreClient, () => _viewModel.MemoryProtector);
    }

    internal async Task<FieldHttpResponse> HandleHttpAsync(string method, string path, string? body)
    {
        method = (method ?? "GET").ToUpperInvariant();
        path ??= "/";
        if (path.Length > MaximumPathCharacters || body?.Length > MaximumRequestBodyCharacters)
        {
            return Error("request_too_large", 413);
        }

        string route = path.Split('?', 2)[0];
        switch (method, route)
        {
            case ("GET", "/agent/status"):
                return Json(AgentStatus());
            case ("GET", "/model"):
                // The model is said loaded only once the mind that serves it is ready.
                return _viewModel.IsMindReady ? Json(ModelInfo())
                    : Error(MindUnavailable ? "mind_unavailable" : "model_not_loaded", 503);
            case ("GET", "/metrics"):
                return Json(MetricsJson(await _telemetry.SampleAsync(_lifetimeCancellation).ConfigureAwait(true)));
            case ("GET", "/surfaces"):
                if (_memoryCountStale)
                {
                    _memoryCountStale = !await _memory.RefreshCountAsync(_lifetimeCancellation).ConfigureAwait(true);
                    Publish(SurfacesEvent());
                }

                return Json(Surfaces());
            case ("GET", "/voice/status"):
                return Json(VoiceStatus());
            case ("POST", "/voice/start"):
                return await VoiceStartAsync().ConfigureAwait(true);
            case ("POST", "/voice/stop"):
            {
                bool stopped = await _viewModel.SetWakeVoiceAsync(false, _lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = stopped, ["running"] = !stopped }, stopped ? 200 : 503);
            }

            case ("POST", "/voice/trigger"):
            {
                if (!FieldBridgeContract.TryAcceptVoiceControl(_viewModel.IsReady, out string error, out int status))
                {
                    return Error(error, status);
                }

                bool running = await _viewModel.StartDirectVoiceAsync(_lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = running, ["running"] = running }, running ? 200 : 503);
            }

            case ("POST", "/voice/release"):
            {
                bool released = await _viewModel.ReleaseDirectVoiceAsync(_lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = released }, released ? 200 : 503);
            }

            case ("POST", "/turn"):
                return await HandleTurnAsync(body).ConfigureAwait(true);
            case ("POST", "/confirmation/answer"):
            {
                long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
                if (ParseBody(body)?["approve"] is not JsonValue approveValue || !approveValue.TryGetValue(out bool approve))
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

            case ("POST", "/power"):
            {
                if (ParseBody(body)?["on"] is not JsonValue onValue || !onValue.TryGetValue(out bool on))
                {
                    return Error("invalid_power", 400);
                }

                bool now = await _viewModel.SetPowerAsync(on, _lifetimeCancellation).ConfigureAwait(true);
                return Json(new JsonObject { ["ok"] = now == on, ["on"] = now });
            }

            case ("GET", "/sessions"):
                return Json(Sessions());
            case ("POST", "/sessions/new"):
                return await NewSessionAsync().ConfigureAwait(true);
            case ("POST", "/sessions/load"):
                return await LoadSessionAsync((string?)ParseBody(body)?["id"] ?? string.Empty).ConfigureAwait(true);
            case ("POST", "/sessions/rename"):
                return RenameSession(ParseBody(body));
            case ("GET", "/catalog"):
                return Json(FieldStepProjection.Catalog());
            case ("GET", "/triggers"):
                return await TriggersAsync().ConfigureAwait(true);
            case ("POST", "/triggers/cancel"):
                return await CancelTriggerAsync(ParseBody(body)).ConfigureAwait(true);
            case ("GET", "/settings/general"):
                return Json(_viewModel.Settings.GeneralJson(Autostart()));
            case ("PUT", "/settings/general"):
                return PutGeneral(ParseBody(body));
            case ("GET", "/proposals"):
                return Json(_viewModel.Settings.ProposalsJson());
            case ("PUT", "/proposals"):
            {
                if (ParseBody(body) is not { } proposals)
                {
                    return Error("invalid_proposals", 400);
                }

                _viewModel.Settings.ApplyProposals(proposals, DateTimeOffset.UtcNow);
                return Json(_viewModel.Settings.ProposalsJson());
            }

            // The accessible mode is the profile's file (PresentationModeStore), the same one the chat's
            // system.settings.set writes. It changes only how the view is presented: the view switches its own styles.
            case ("GET", "/accessibility"):
                return Json(PresentationMode(PresentationModeStore.ReadAccessible(MemoryOperationProtector.ResolveDataRoot())));
            case ("PUT", "/accessibility"):
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

            case ("GET", "/voice/inventory"):
                return Json(VoiceInventory());
            case ("GET", "/settings"):
                return Json(CurrentSettings());
            case ("GET", "/confirmation"):
                return Json(ConfirmationPolicy(MemoryOperationProtector.ResolveDataRoot()));
            case ("PUT", "/confirmation"):
                return PutConfirmationMode(body);
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

        return Error("not_found", 404);
    }

    /// <summary>What a view that (re)connects receives: the current state, never fragments already published.</summary>
    internal IReadOnlyList<JsonObject> CreateSocketBootstrap() =>
    [
        StateEvent(),
        AgentEvent(),
        ModelEvent(),
        SurfacesEvent(),
        SessionEvent(),
        new() { ["type"] = "transcript", ["items"] = _transcript.Snapshot() },
        VoiceEvent(),
        BootEvent(),
        ContextEvent(),
    ];

    // ---- the conversation ---------------------------------------------------------------------------------------

    private void OnMessageAdded(ConversationMessage message)
    {
        if (!message.IsUser)
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, ShellTraceStages.VisibleText);
        }

        if (message.IsUser)
        {
            _sessionLabel ??= Clip(message.Body, 40);
            Publish(ItemEvent(_transcript.You(message.Body)));
            Publish(SessionEvent());
            return;
        }

        Publish(ItemEvent(_transcript.Words(message.Body, message.Silent)));
    }

    private void OnStepStarted(string id, string operation, JsonObject arguments)
    {
        JsonObject step = FieldStepProjection.Started(id, operation, arguments);
        Publish(ItemEvent(_transcript.Step(step)));
        Publish(StepEvent("start", step));
    }

    private void OnStepCompleted(NativeTurnStep step)
    {
        // What left the PC: a call that reaches the internet and got to its provider (the kernel let it through).
        string? net = step.Sent && NativeTurnLoop.ReachesTheNetwork(step.Operation, step.Arguments)
            ? FieldStepProjection.NetWhat(step.Operation, step.Arguments)
            : null;
        JsonObject? view = FieldStepProjection.Finished(step.Id, step, net);
        if (view is null)
        {
            if (_transcript.Drop(step.Id) is { } reply)
            {
                Publish(ItemEvent(reply));
            }

            return;
        }

        Publish(ItemEvent(_transcript.Step(view)));
        Publish(StepEvent("end", view));
        // The view lights «Salió a internet» and adds it to the session's log (the step keeps it in the transcript).
        if (net is not null)
        {
            Publish(new JsonObject
            {
                ["type"] = "net",
                ["what"] = net,
                ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
            });
        }

        // Bypass ran a call normal mode would have asked about: the conversation says so (design v4).
        if (step.Sent && ConfirmationModeStore.Read(MemoryOperationProtector.ResolveDataRoot()) == ConfirmationMode.Bypass
            && FieldStepProjection.NormalModeAsks(step.Operation, step.Arguments))
        {
            string title = FieldStepProjection.Label(step.Operation, step.Arguments);
            Publish(ItemEvent(_transcript.System("Bypass · hecho sin preguntar: " + char.ToLowerInvariant(title[0]) + title[1..])));
        }

        if (step.Operation == "schedule.alarms" && step.Sent)
        {
            _triggerCount = null; // read again when the view asks
        }
    }

    private void OnConfirmationAsked(NativeTurnConfirmation asked, string? beatActivity)
    {
        string? context = asked.Proposal ? beatActivity switch
        {
            HeartbeatMoment.Playing => "porque estás jugando",
            HeartbeatMoment.InCall => "porque estás en una llamada",
            HeartbeatMoment.Watching => "porque estás viendo algo",
            _ => "por iniciativa propia",
        } : null;
        JsonObject card = FieldStepProjection.Card(_transcript.NextId("k"), asked.Proposal ? "proposal" : "confirm",
            asked.Operation, asked.Arguments, asked.Risk, asked.ExpiresUtc, context);
        Publish(ItemEvent(_transcript.Card(card)));
    }

    private void OnConfirmationResolved(string outcome)
    {
        string status = outcome switch
        {
            "approved" => "yes",
            "declined" => "no",
            "expired" => "expired",
            _ => "dropped",
        };
        if (_transcript.Resolve(status, null) is { } card)
        {
            Publish(ItemEvent(card));
        }
    }

    private void OnVoicePartial(string text) => Publish(new JsonObject { ["type"] = "voice_partial", ["text"] = text });

    private void OnVoiceWake() => Publish(new JsonObject { ["type"] = "voice_wake" });

    private static JsonObject ItemEvent(JsonObject item) => new() { ["type"] = "item", ["item"] = item };

    private JsonObject StepEvent(string phase, JsonObject step)
    {
        var data = (JsonObject)step.DeepClone();
        data["type"] = "step";
        data["phase"] = phase;
        data["turn"] = _transcript.Turn ?? string.Empty;
        return data;
    }

    private async Task<FieldHttpResponse> HandleTurnAsync(string? body)
    {
        // The person's words arrived now; the turn may still wait for the engine's recovery or a heartbeat.
        long arrivedAt = System.Diagnostics.Stopwatch.GetTimestamp();
        string turnId = ShellTraceSink.TurnId;
        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.SubmitReceived);
        string text = (string?)ParseBody(body)?["text"] ?? string.Empty;
        await _viewModel.WaitForCoreRecoveryAsync().ConfigureAwait(true);
        if (!FieldBridgeContract.TryAcceptTurn(_viewModel.IsInputEnabled, text, out string turnError, out int turnStatus))
        {
            return Error(turnError, turnStatus);
        }

        try
        {
            _ = MissionInputContract.ValidateAndTrim(new MissionInput(text, MissionInputSource.Text));
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.BridgeCrossed);
        if (!_viewModel.IsPowered)
        {
            // Writing to BAXY at rest wakes it (design v4), the voice too once the view turns its mode back on.
            await _viewModel.SetPowerAsync(true, _lifetimeCancellation).ConfigureAwait(true);
        }

        try
        {
            await _viewModel.SubmitAsync(new MissionInput(text, MissionInputSource.Text), arrivedAt, _lifetimeCancellation)
                .ConfigureAwait(true);
        }
        catch (MissionInputRejectedException)
        {
            return Error("invalid_text", 400);
        }

        ShellTraceSink.Record(ShellTraceScopes.Bridge, turnId, ShellTraceStages.ResponseFinal);
        return Json(new JsonObject { ["ok"] = true, ["status"] = "accepted" });
    }

    // ---- sessions -------------------------------------------------------------------------------------------------

    private string SessionTitle => _sessionLabel ?? "Conversación nueva";

    private JsonObject SessionEvent() => new() { ["type"] = "session", ["id"] = _sessionId, ["label"] = SessionTitle };

    private JsonObject Sessions()
    {
        var list = new JsonArray(new JsonObject
        {
            ["id"] = _sessionId,
            ["label"] = SessionTitle,
            ["ts"] = "ahora",
            ["turn_count"] = _transcript.Requests,
            ["current"] = true,
        });
        foreach (FieldSessionStore.Session kept in _sessions.List().Where(s => s.Id != _sessionId))
        {
            list.Add(new JsonObject
            {
                ["id"] = kept.Id,
                ["label"] = kept.Label.Length > 0 ? kept.Label : "Conversación",
                ["ts"] = When(kept.Updated),
                ["turn_count"] = null,
                ["current"] = false,
            });
        }

        return new JsonObject { ["sessions"] = list };
    }

    // Keeps the current conversation (what the view showed and the mind's own) when it holds anything.
    private async Task SaveCurrentAsync()
    {
        if (_transcript.Items.Count == 0)
        {
            return;
        }

        JsonArray? mind = await _viewModel.ExportMindSessionAsync(_lifetimeCancellation).ConfigureAwait(true);
        _sessions.Save(new FieldSessionStore.Session(_sessionId, SessionTitle, _sessionCreated, DateTimeOffset.UtcNow,
            _transcript.Snapshot(), mind));
        Publish(SurfacesEvent());
    }

    private async Task<FieldHttpResponse> NewSessionAsync()
    {
        if (_viewModel.IsBusy)
        {
            return Error("turn_in_progress", 409);
        }

        await SaveCurrentAsync().ConfigureAwait(true);
        if (!_viewModel.StartNewUiSession())
        {
            return Error("turn_in_progress", 409);
        }

        StartSession(NewSessionId(), null, DateTimeOffset.UtcNow, null);
        return Json(new JsonObject { ["ok"] = true, ["id"] = _sessionId });
    }

    private async Task<FieldHttpResponse> LoadSessionAsync(string id)
    {
        if (id == _sessionId)
        {
            return Json(new JsonObject { ["ok"] = true });
        }

        if (_sessions.Load(id) is not { } kept)
        {
            return Error("session_not_found", 404);
        }

        if (_viewModel.IsBusy)
        {
            return Error("turn_in_progress", 409);
        }

        await SaveCurrentAsync().ConfigureAwait(true);
        // The heartbeat reads the session's words; the mind gets its own conversation back as it was kept.
        var messages = new List<ConversationMessage>();
        foreach (JsonNode? node in kept.Items)
        {
            if (node is JsonObject item && (string?)item["text"] is { Length: > 0 } text
                && (string?)item["who"] is "you" or "baxy")
            {
                messages.Add(new ConversationMessage((string?)item["who"] == "you" ? "Tú" : "BAXY", text,
                    (string?)item["who"] == "you", kept.Updated));
            }
        }

        if (!await _viewModel.OpenSessionAsync(kept.Mind, messages, _lifetimeCancellation).ConfigureAwait(true))
        {
            return Error("session_not_opened", 409);
        }

        StartSession(kept.Id, kept.Label, kept.Created, kept.Items);
        return Json(new JsonObject { ["ok"] = true });
    }

    private void StartSession(string id, string? label, DateTimeOffset created, JsonArray? items)
    {
        _sessionId = id;
        _sessionLabel = string.IsNullOrWhiteSpace(label) ? null : label;
        _sessionCreated = created;
        _transcript.Replace(items);
        Publish(new JsonObject { ["type"] = "transcript", ["items"] = _transcript.Snapshot() });
        Publish(SessionEvent());
        Publish(SurfacesEvent());
    }

    private FieldHttpResponse RenameSession(JsonObject? payload)
    {
        string id = (string?)payload?["id"] ?? string.Empty;
        string title = ((string?)payload?["title"] ?? string.Empty).Trim();
        if (title.Length is < 1 or > MaximumSessionLabel)
        {
            return Error("invalid_session", 400);
        }

        if (id == _sessionId)
        {
            _sessionLabel = title;
            Publish(SessionEvent());
            return Json(new JsonObject { ["ok"] = true });
        }

        return _sessions.Rename(id, title) ? Json(new JsonObject { ["ok"] = true }) : Error("session_not_found", 404);
    }

    private static string NewSessionId() => Guid.NewGuid().ToString("N")[..12];

    private static string When(DateTimeOffset utc)
    {
        DateTime local = utc.ToLocalTime().DateTime;
        int days = (DateTime.Today - local.Date).Days;
        return days switch
        {
            0 => local.ToString("HH:mm", CultureInfo.InvariantCulture),
            1 => "ayer",
            < 7 => local.ToString("ddd", CultureInfo.GetCultureInfo("es-ES")).TrimEnd('.'),
            _ => local.ToString("d MMM", CultureInfo.GetCultureInfo("es-ES")).TrimEnd('.'),
        };
    }

    // ---- triggers (BAXY's alarms and reminders) -------------------------------------------------------------------

    private async Task<FieldHttpResponse> TriggersAsync()
    {
        OperationResponse? response = await _viewModel.SendPanelOperationAsync("schedule.alarms",
            new JsonObject { ["action"] = "list", ["limit"] = 50 }, _lifetimeCancellation).ConfigureAwait(true);
        return TriggersReply(response);
    }

    private async Task<FieldHttpResponse> CancelTriggerAsync(JsonObject? payload)
    {
        string at = ((string?)payload?["at"] ?? string.Empty).Trim();
        string kind = (string?)payload?["kind"] is "alarm" ? "alarm" : "reminder";
        if (at.Length is < 4 or > 32)
        {
            return Error("invalid_trigger", 400);
        }

        OperationResponse? cancelled = await _viewModel.SendPanelOperationAsync("schedule.alarms",
            new JsonObject { ["action"] = "cancel", ["at"] = at, ["kind"] = kind }, _lifetimeCancellation).ConfigureAwait(true);
        if (cancelled is not { Status: OperationStatuses.Completed, Verified: true })
        {
            return Error(cancelled?.ErrorCode ?? "trigger_not_cancelled", 409);
        }

        return await TriggersAsync().ConfigureAwait(true);
    }

    private FieldHttpResponse TriggersReply(OperationResponse? response)
    {
        if (response is not { Status: OperationStatuses.Completed } || response.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("notifications", out JsonElement notifications) || notifications.ValueKind != JsonValueKind.Array)
        {
            return Error(response?.ErrorCode ?? "triggers_unavailable", 503);
        }

        var items = new JsonArray();
        foreach (JsonElement item in notifications.EnumerateArray())
        {
            items.Add(new JsonObject
            {
                ["kind"] = item.TryGetProperty("kind", out JsonElement kind) ? kind.GetString() : "reminder",
                ["title"] = item.TryGetProperty("title", out JsonElement title) ? title.GetString() : null,
                ["next_local"] = item.TryGetProperty("nextRunLocal", out JsonElement next) ? next.GetString() : null,
                ["state"] = item.TryGetProperty("state", out JsonElement state) ? state.GetString() : null,
            });
        }

        int count = result.TryGetProperty("count", out JsonElement total) && total.TryGetInt32(out int n) ? n : items.Count;
        if (_triggerCount != count)
        {
            _triggerCount = count;
            Publish(SurfacesEvent());
        }

        return Json(new JsonObject { ["count"] = count, ["items"] = items, ["truncated"] = count > items.Count });
    }

    // ---- settings ---------------------------------------------------------------------------------------------------

    // «Arrancar con Windows» is the Run key's entry for this executable, when this copy may own the sign-in start
    // (WindowsAutostartRegistration); null when it may not (a worktree build) or the key could not be read.
    private static bool? Autostart()
    {
        try
        {
            return WindowsAutostartRegistration.CreateDefault().IsRegisteredForCurrent();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidOperationException
            or System.Security.SecurityException)
        {
            return null;
        }
    }

    private FieldHttpResponse PutGeneral(JsonObject? body)
    {
        if (body is null)
        {
            return Error("invalid_settings", 400);
        }

        if (body["autostart"] is JsonValue autostart && autostart.TryGetValue(out bool start))
        {
            try
            {
                if (!WindowsAutostartRegistration.CreateDefault().SetForCurrent(start, Environment.GetCommandLineArgs()))
                {
                    return Error("autostart_not_available", 409);
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
                or InvalidOperationException or System.Security.SecurityException)
            {
                return Error("autostart_not_changed", 409);
            }
        }

        _viewModel.Settings.ApplyGeneral(body);
        return Json(_viewModel.Settings.GeneralJson(Autostart()));
    }

    // The bypass switch of BAXY's own view writes the profile's confirmation mode through the same store the engine
    // reads on every invocation (ConfirmationModeStore). A body that names no policy changes nothing.
    private static FieldHttpResponse PutConfirmationMode(string? body)
    {
        ConfirmationMode? mode = ParseBody(body)?["confirmationPolicy"] is JsonValue policy
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

    private static JsonObject PresentationMode(bool accessible) => new()
    {
        ["active"] = accessible ? PresentationModeStore.Accessible : PresentationModeStore.Normal,
    };

    // ---- state events -------------------------------------------------------------------------------------------------

    private void OnViewModelPropertyChanged(object? sender, PropertyChangedEventArgs eventArgs)
    {
        string? name = eventArgs.PropertyName;
        if (name is nameof(MainWindowViewModel.IsReady) or nameof(MainWindowViewModel.IsBusy)
            or nameof(MainWindowViewModel.Failure) or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.IsMindReady) or nameof(MainWindowViewModel.HasPendingConfirmation))
        {
            Publish(AgentEvent());
        }

        if (name is nameof(MainWindowViewModel.IsReady) or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(ModelEvent());
        }

        if (name is nameof(MainWindowViewModel.IsBusy) or nameof(MainWindowViewModel.IsListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking) or nameof(MainWindowViewModel.Failure)
            or nameof(MainWindowViewModel.StatusDescription) or nameof(MainWindowViewModel.IsMindReady))
        {
            Publish(StateEvent());
        }

        if (name is nameof(MainWindowViewModel.IsListening) or nameof(MainWindowViewModel.IsWakeListening)
            or nameof(MainWindowViewModel.IsVoiceSpeaking) or nameof(MainWindowViewModel.IsMicAvailable)
            or nameof(MainWindowViewModel.VoiceFailure))
        {
            Publish(VoiceEvent());
        }

        if (name is nameof(MainWindowViewModel.IsMindReady) or nameof(MainWindowViewModel.IsMindPreparing)
            or nameof(MainWindowViewModel.VoicePieces) or nameof(MainWindowViewModel.MindStartedAt))
        {
            Publish(BootEvent());
        }

        if (name is nameof(MainWindowViewModel.OwnerActivity))
        {
            Publish(ContextEvent());
        }

        // A turn that ended keeps the conversation as it stands (the session survives a restart).
        if (name is nameof(MainWindowViewModel.IsBusy) && !_viewModel.IsBusy && !_disposed)
        {
            _ = SaveCurrentAsync();
        }
    }

    private JsonObject StateEvent() => new() { ["type"] = "state", ["value"] = CurrentConversationState() };

    private string CurrentConversationState() =>
        _viewModel.IsVoiceSpeaking ? "speaking"
        : _viewModel.IsListening ? "listening"
        : _viewModel.IsBusy ? "thinking"
        : _viewModel.Failure is not null || MindUnavailable ? "error"
        : "idle";

    internal JsonObject AgentEvent()
    {
        JsonObject agent = AgentStatus();
        agent["type"] = "agent";
        return agent;
    }

    // The interface's gate: whether a turn is accepted now, the failure's code and whether a call waits for the person.
    private JsonObject AgentStatus() => new()
    {
        ["built"] = _viewModel.IsReady,
        ["ready"] = _viewModel.IsReady && _viewModel.IsMindReady && !_viewModel.IsBusy && !_viewModel.IsMindPreparing,
        ["failure"] = _viewModel.Failure ?? (MindUnavailable ? "mind_unavailable" : null),
        ["pendingConfirmation"] = _viewModel.HasPendingConfirmation,
    };

    private JsonObject VoiceEvent()
    {
        JsonObject voice = VoiceStatus();
        voice["type"] = "voice";
        return voice;
    }

    private JsonObject VoiceStatus() => new()
    {
        ["available"] = _viewModel.IsMicAvailable,
        ["running"] = _viewModel.IsListening || _viewModel.IsWakeListening,
        ["mode"] = _viewModel.IsListening ? "direct" : _viewModel.IsWakeListening ? "wake" : "off",
        ["speaking"] = _viewModel.IsVoiceSpeaking,
        ["last_error"] = _viewModel.VoiceFailure ?? (_viewModel.IsMicAvailable ? null : "voice_unavailable"),
    };

    // The start's pieces, each marked only once the mind reports it (null before); no percentage is made up.
    private JsonObject BootEvent()
    {
        MindVoiceStatus? voice = _viewModel.VoicePieces;
        return new JsonObject
        {
            ["type"] = "boot",
            ["stt"] = voice?.SttAvailable,
            ["wake"] = voice?.WakeAvailable,
            ["tts"] = voice?.SpeechAvailable,
            ["model"] = _viewModel.IsMindReady,
            ["startedAt"] = _viewModel.MindStartedAt.ToUnixTimeMilliseconds(),
            ["readyAt"] = _viewModel.MindReadyAt?.ToUnixTimeMilliseconds(),
            ["failed"] = !_viewModel.IsMindReady && _viewModel.MindFailed ? "mind_unavailable" : null,
        };
    }

    private JsonObject ContextEvent() => new()
    {
        ["type"] = "context",
        ["activity"] = _viewModel.OwnerActivity switch
        {
            HeartbeatMoment.Playing => "game",
            HeartbeatMoment.InCall => "call",
            HeartbeatMoment.Watching => "video",
            HeartbeatMoment.Away => "away",
            _ => "free",
        },
    };

    private JsonObject Surfaces() => new()
    {
        ["sessions"] = 1 + _sessions.List().Count(s => s.Id != _sessionId),
        ["memory"] = _memory.Count,
        ["memory_revision"] = Volatile.Read(ref _memoryRevision),
        ["tools"] = Baxy.Kernel.Operations.ProductCatalog.ToolDescriptors.Count,
        ["triggers"] = _triggerCount,
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

    private async Task<FieldHttpResponse> VoiceStartAsync()
    {
        if (!FieldBridgeContract.TryAcceptVoiceControl(_viewModel.IsReady, out string error, out int status))
        {
            return Error(error, status);
        }

        bool running = _viewModel.IsWakeListening
            || await _viewModel.SetWakeVoiceAsync(true, _lifetimeCancellation).ConfigureAwait(true);
        return Json(new JsonObject
        {
            ["ok"] = running,
            ["running"] = running,
            ["last_error"] = running ? null : "voice_unavailable",
        }, running ? 200 : 503);
    }

    // ---- model, voice inventory, metrics ----------------------------------------------------------------------------

    internal static FieldModelIdentity ResolveModelIdentity(string? modelPath)
    {
        string fileName = string.IsNullOrWhiteSpace(modelPath) ? string.Empty : Path.GetFileName(modelPath);
        string alias = string.IsNullOrWhiteSpace(fileName) ? "local-model" : Path.GetFileNameWithoutExtension(fileName);
        string family = alias switch
        {
            var value when value.Contains("qwen3.5", StringComparison.OrdinalIgnoreCase) => "qwen 3.5",
            var value when value.Contains("qwen3", StringComparison.OrdinalIgnoreCase) => "qwen 3",
            var value when value.Contains("phi-4", StringComparison.OrdinalIgnoreCase) => "phi 4",
            var value when value.Contains("gemma-4", StringComparison.OrdinalIgnoreCase) => "gemma 4",
            var value when value.Contains("llama", StringComparison.OrdinalIgnoreCase) => "llama",
            _ => "local model",
        };
        Match parameterMatch = Regex.Match(alias, @"(?<![A-Za-z0-9])(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        if (!parameterMatch.Success)
        {
            parameterMatch = Regex.Match(alias, @"E(?<value>\d+(?:\.\d+)?B)(?=$|[-_.])",
                RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        }

        return new FieldModelIdentity(alias, fileName, family,
            parameterMatch.Success ? parameterMatch.Groups["value"].Value.ToLowerInvariant() : "unknown");
    }

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

    // The model the mind was given (BAXY_MIND_LLM_GGUF) and its context.
    private static JsonObject CurrentSettings()
    {
        FieldModelIdentity identity = ResolveModelIdentity(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"));
        return new JsonObject
        {
            ["modelAlias"] = identity.Alias,
            ["ggufPath"] = identity.FileName,
            ["ctxSize"] = ContextSize(),
        };
    }

    private bool MindUnavailable => !_viewModel.IsMindReady && !_viewModel.IsMindPreparing;

    // The model event: its identity once the mind serving it is ready, null before.
    private JsonObject ModelEvent() =>
        new() { ["type"] = "model", ["info"] = _viewModel.IsMindReady ? ModelInfo() : null };

    private static JsonObject ModelInfo()
    {
        FieldModelIdentity identity = ResolveModelIdentity(Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"));
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
        return int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value) && value > 0
            ? value
            : 49152;
    }

    // A reading the PC did not give (no GPU counter, no temperature, no model process) travels as null; the view
    // shows «—».
    private static JsonObject MetricsJson(FieldMetricSnapshot metrics) => new()
    {
        ["cpu"] = metrics.Cpu,
        ["gpu"] = metrics.Gpu,
        ["temp"] = metrics.GpuTemperature,
        ["model_vram_gb"] = metrics.ModelVramGb,
        ["model_ram_gb"] = metrics.ModelRamGb,
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

    private static string Clip(string text, int maximum)
    {
        string single = string.Join(' ', text.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return single.Length <= maximum ? single : single[..(maximum - 1)].TrimEnd() + "…";
    }

    private static FieldHttpResponse Json(JsonObject body, int status = 200) => FieldHttpResponse.Json(body, status);

    private static FieldHttpResponse Error(string code, int status) =>
        Json(new JsonObject { ["ok"] = false, ["error"] = code }, status);

    private bool Publish(JsonObject eventData) => _sink.Publish(eventData);

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
        _viewModel.StepStarted -= OnStepStarted;
        _viewModel.StepCompleted -= OnStepCompleted;
        _viewModel.ConfirmationAsked -= OnConfirmationAsked;
        _viewModel.ConfirmationResolved -= OnConfirmationResolved;
        _viewModel.VoicePartial -= OnVoicePartial;
        _viewModel.VoiceWake -= OnVoiceWake;
        try
        {
            // The conversation as it stands is kept when BAXY closes.
            await SaveCurrentAsync().ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is OperationCanceledException or IOException or InvalidOperationException)
        {
        }
    }
}
